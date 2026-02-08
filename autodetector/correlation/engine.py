from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Set, Tuple


def _is_duplicate_alert(alert: Dict[str, Any], recent_alerts: List[Dict[str, Any]], cooldown_sec: int = 300) -> bool:
    """Check if alert is a duplicate within cooldown period."""
    alert_key = f"{alert.get('device_id')}:{alert.get('variable')}:{alert.get('alert_type')}"
    
    for recent in recent_alerts:
        recent_key = f"{recent.get('device_id')}:{recent.get('variable')}:{recent.get('alert_type')}"
        if alert_key == recent_key:
            # Check timestamp
            try:
                alert_ts = datetime.fromisoformat(str(alert.get('ts', '')))
                recent_ts = datetime.fromisoformat(str(recent.get('ts', '')))
                if (alert_ts - recent_ts).total_seconds() < cooldown_sec:
                    return True
            except:
                pass
    return False


def _filter_false_positives(alerts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter out likely false positive alerts."""
    filtered = []
    
    for alert in alerts:
        # Skip transient single-occurrence warnings
        if alert.get('severity') == 'warning' and alert.get('alert_type') == 'threshold':
            # Check if it's a single spike that recovered
            if alert.get('duration_sec', 0) < 60:
                continue
        
        # Skip interface errors if interface is up
        if alert.get('alert_type') == 'interface_errors':
            device_id = alert.get('device_id')
            # Would check if interface is currently up
            pass
        
        filtered.append(alert)
    
    return filtered


def correlate_alerts(cfg: Any, alerts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Correlate alerts with noise reduction and dependency analysis.
    
    Implements:
    1. Noise reduction (deduplication, false positive filtering)
    2. Time-window incident clustering
    3. Dependency-based root cause analysis
    4. Correlated failure detection
    """
    raw_cfg = cfg.raw if hasattr(cfg, "raw") else cfg
    deps = ((raw_cfg.get("correlation") or {}).get("dependencies") or [])
    win_sec = int(((raw_cfg.get("correlation") or {}).get("incident_window_sec") or 300))
    
    # 1. Noise Reduction - Filter duplicates
    unique_alerts = []
    for alert in alerts:
        if not _is_duplicate_alert(alert, unique_alerts, cooldown_sec=300):
            unique_alerts.append(alert)
    
    # 2. False Positive Filtering
    filtered_alerts = _filter_false_positives(unique_alerts)
    
    by_device: Dict[str, List[Dict[str, Any]]] = {}
    for a in filtered_alerts:
        by_device.setdefault(a.get("device_id", ""), []).append(a)

    correlations: List[Dict[str, Any]] = []

    def _ts(a: Dict[str, Any]) -> datetime:
        try:
            return datetime.fromisoformat(str(a.get("ts")))
        except Exception:
            return datetime.min

    def _cluster(alerts_in: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        xs = sorted(alerts_in, key=_ts)
        clusters: List[List[Dict[str, Any]]] = []
        cur: List[Dict[str, Any]] = []
        last_t: datetime | None = None
        for a in xs:
            t = _ts(a)
            if last_t is None:
                cur = [a]
                last_t = t
                continue
            if (t - last_t).total_seconds() <= win_sec:
                cur.append(a)
                last_t = t
            else:
                clusters.append(cur)
                cur = [a]
                last_t = t
        if cur:
            clusters.append(cur)
        return clusters

    # 3. Incident Clustering
    for cl in _cluster(filtered_alerts):
        devices = sorted(list({str(a.get("device_id", "")) for a in cl if a.get("device_id")}))
        sev_rank = {"info": 1, "warning": 2, "critical": 3}
        top = sorted(cl, key=lambda a: sev_rank.get(str(a.get("severity")), 0), reverse=True)[:5]
        
        # Calculate correlation confidence
        confidence = min(1.0, len(devices) / 3.0) if len(devices) > 1 else 0.5
        
        correlations.append({
            "type": "incident",
            "incident_id": str(uuid.uuid4()),
            "start_ts": str(min(_ts(a) for a in cl).isoformat()) if cl else "",
            "end_ts": str(max(_ts(a) for a in cl).isoformat()) if cl else "",
            "devices": devices,
            "device_count": len(devices),
            "top_alerts": [{"device_id": a.get("device_id"), "severity": a.get("severity"), "variable": a.get("variable"), "message": a.get("message")} for a in top],
            "confidence": round(confidence, 2),
        })

    # 4. Dependency-Based Root Cause Analysis
    correlated_device_pairs: List[Tuple[str, str]] = []
    
    for d in deps:
        up = d.get("upstream")
        down = d.get("downstream")
        if not up or not down:
            continue

        up_alerts = by_device.get(up, [])
        down_alerts = by_device.get(down, [])

        up_crit = [a for a in up_alerts if a.get("severity") == "critical"]
        down_crit = [a for a in down_alerts if a.get("severity") == "critical"]

        if up_crit and down_crit:
            # Time correlation check
            up_times = [_ts(a) for a in up_crit]
            down_times = [_ts(a) for a in down_crit]
            
            # Check if upstream failed before downstream
            time_correlated = any(
                up_t <= down_t and (down_t - up_t).total_seconds() < 300
                for up_t in up_times
                for down_t in down_times
            )
            
            if time_correlated:
                correlated_device_pairs.append((up, down))
                
                correlations.append({
                    "type": "dependency_root_cause",
                    "root_device": up,
                    "impacted_device": down,
                    "root_alert": up_crit[0].get("message"),
                    "impact_alert": down_crit[0].get("message"),
                    "suggestion": f"CORRELATED: {up} failure likely caused {down} failure. Check shared infrastructure.",
                    "confidence": 0.85,
                })

                correlations.append({
                    "type": "impact_chain",
                    "chain": [up, down],
                    "root": up,
                    "impact": down,
                    "confidence": 0.85,
                })

    # 5. Multi-Device Correlated Failure Detection
    if len(by_device) > 1:
        all_critical_devices = [
            device_id for device_id, device_alerts in by_device.items()
            if any(a.get("severity") == "critical" for a in device_alerts)
        ]
        
        if len(all_critical_devices) >= 3:
            # Likely shared infrastructure failure
            correlations.append({
                "type": "correlated_failure",
                "affected_devices": all_critical_devices,
                "device_count": len(all_critical_devices),
                "suggestion": f"CRITICAL: {len(all_critical_devices)} devices failed simultaneously. "
                              "This indicates shared infrastructure failure. "
                              "Check: 1) Core switch/router, 2) Power distribution, 3) Internet uplink",
                "confidence": 0.9,
            })

    return correlations


def build_impact_map(cfg: Any, device_id: str) -> Dict[str, Any]:
    """Build a map of devices impacted by a given device failure."""
    raw_cfg = cfg.raw if hasattr(cfg, "raw") else cfg
    deps = ((raw_cfg.get("correlation") or {}).get("dependencies") or [])
    
    impacted: List[str] = []
    impact_chain: List[List[str]] = []
    
    # Find direct downstream devices
    direct_downstream = [d.get("downstream") for d in deps if d.get("upstream") == device_id]
    impacted.extend(direct_downstream)
    
    # Build impact chains
    for down in direct_downstream:
        chain = [device_id, down]
        # Find next level
        next_level = [d.get("downstream") for d in deps if d.get("upstream") == down]
        for nl in next_level:
            chain.append(nl)
            impacted.append(nl)
        impact_chain.append(chain)
    
    return {
        "source_device": device_id,
        "directly_impacted": direct_downstream,
        "all_impacted": list(set(impacted)),
        "impact_chains": impact_chain,
        "total_affected": len(set(impacted)) + 1,  # +1 for source
    }
