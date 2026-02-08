from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from autodetector.storage.sqlite_store import SqliteStore
from autodetector.plugin.schema_loader import variable_weight


def _thresholds(cfg: Dict[str, Any], variable: str) -> Optional[Dict[str, float]]:
    t = (((cfg.get("ai") or {}).get("thresholds") or {}).get(variable))
    if not t:
        return None
    warn = t.get("warn")
    crit = t.get("crit")
    if warn is None and crit is None:
        return None
    return {"warn": float(warn) if warn is not None else math.inf, "crit": float(crit) if crit is not None else math.inf}


def _zscore(series: List[float], x: float) -> float:
    if len(series) < 5:
        return 0.0
    mean = sum(series) / len(series)
    var = sum((v - mean) ** 2 for v in series) / max(1, (len(series) - 1))
    stdev = math.sqrt(var)
    if stdev == 0:
        return 0.0
    return (x - mean) / stdev


def _trend_slope(series: List[float]) -> float:
    n = len(series)
    if n < 5:
        return 0.0
    xs = list(range(n))
    x_mean = sum(xs) / n
    y_mean = sum(series) / n
    num = sum((xs[i] - x_mean) * (series[i] - y_mean) for i in range(n))
    den = sum((xs[i] - x_mean) ** 2 for i in range(n))
    if den == 0:
        return 0.0
    return num / den


def _detect_routing_instability(routing_output: str) -> List[Dict[str, Any]]:
    """Detect routing protocol instability from routing table output."""
    issues = []
    
    # BGP instability patterns
    bgp_patterns = [
        (r"BGP\s+neighbor\s+\S+\s+(?:DOWN|IDLE|ACTIVE)", "BGP neighbor down"),
        (r"BGP\s+state\s*:\s*(?:Idle|Active|Connect)", "BGP in non-established state"),
        (r"flap\s*count\s*:\s*(\d+)", "BGP flapping detected"),
    ]
    
    # OSPF instability patterns
    ospf_patterns = [
        (r"OSPF\s+neighbor\s+\S+\s+(?:DOWN|INIT|2WAY)", "OSPF neighbor not full"),
        (r"SPF\s+algorithm\s+executed\s+(\d+)\s+times", "Frequent SPF recalculation"),
        (r"LSA\s+count\s*:\s*(\d+)", "High LSA count"),
    ]
    
    all_patterns = bgp_patterns + ospf_patterns
    
    for pattern, description in all_patterns:
        matches = re.finditer(pattern, routing_output, re.IGNORECASE)
        for match in matches:
            count = 1
            if match.groups():
                try:
                    count = int(match.group(1))
                except:
                    pass
            
            if count > 5:  # Threshold for instability
                issues.append({
                    "protocol": "BGP" if "BGP" in pattern else "OSPF",
                    "severity": "critical" if count > 20 else "warning",
                    "description": description,
                    "count": count,
                })
    
    return issues


def _analyze_log_patterns(log_output: str) -> List[Dict[str, Any]]:
    """Analyze log output for patterns indicating issues."""
    patterns = []
    
    # Critical error patterns
    critical_patterns = [
        (r"(?i)kernel.*panic", "Kernel panic detected", "critical"),
        (r"(?i)out\s+of\s+memory", "Out of memory condition", "critical"),
        (r"(?i)segmentation\s+fault", "Segmentation fault", "critical"),
        (r"(?i)hardware.*error", "Hardware error", "critical"),
        (r"(?i)power.*supply.*fail", "Power supply failure", "critical"),
    ]
    
    # Warning patterns
    warning_patterns = [
        (r"(?i)authentication.*fail", "Authentication failure", "warning"),
        (r"(?i)connection.*refused", "Connection refused", "warning"),
        (r"(?i)timeout", "Timeout detected", "warning"),
        (r"(?i)high.*cpu", "High CPU usage", "warning"),
        (r"(?i)disk.*full", "Disk full warning", "warning"),
    ]
    
    all_patterns = critical_patterns + warning_patterns
    
    for pattern, description, severity in all_patterns:
        matches = list(re.finditer(pattern, log_output))
        if matches:
            patterns.append({
                "pattern": pattern,
                "description": description,
                "severity": severity,
                "count": len(matches),
                "samples": [m.group(0)[:100] for m in matches[:3]],
            })
    
    return patterns


def _generate_root_cause_suggestions(
    alerts: List[Dict[str, Any]],
    health_score: float,
    device_id: str,
    os_name: str,
    correlated_devices: List[str] = None,
) -> List[str]:
    """Generate human-readable root cause suggestions."""
    suggestions = []
    
    # Group alerts by type
    critical_alerts = [a for a in alerts if a["severity"] == "critical"]
    interface_alerts = [a for a in alerts if "INTERFACE" in a["variable"]]
    routing_alerts = [a for a in alerts if "ROUTING" in a["variable"]]
    resource_alerts = [a for a in alerts if a["variable"] in {"CPU_USAGE", "MEMORY_USAGE", "DISK_USAGE"}]
    
    # Generate contextual suggestions
    if interface_alerts and routing_alerts:
        suggestions.append(
            f"CRITICAL: {device_id} has both interface and routing issues. "
            "Likely upstream connectivity problem or physical layer issue. "
            "Check fiber/cable connections and upstream switch/router."
        )
    
    if resource_alerts:
        high_resources = [a for a in resource_alerts if a.get("value", 0) > 90]
        if high_resources:
            suggestions.append(
                f"WARNING: {device_id} experiencing high resource utilization. "
                f"Consider: 1) Check for runaway processes, 2) Add more resources, "
                f"3) Review scheduled tasks during peak hours."
            )
    
    if correlated_devices:
        suggestions.append(
            f"CORRELATED FAILURE: {device_id} failure correlates with {len(correlated_devices)} other devices. "
            f"Check shared infrastructure: power, network segment, or upstream device. "
            f"Affected devices: {', '.join(correlated_devices[:5])}"
        )
    
    # Device-specific suggestions
    if "cisco" in os_name.lower():
        if any("CPU" in a["variable"] for a in critical_alerts):
            suggestions.append(
                "CISCO SPECIFIC: High CPU may be due to: 1) ARP inspection, "
                "2) ACL processing, 3) NetFlow/sFlow, 4) Routing table instability. "
                "Run 'show processes cpu sorted' to identify process."
            )
    
    if "junos" in os_name.lower():
        if any("ROUTING" in a["variable"] for a in alerts):
            suggestions.append(
                "JUNOS SPECIFIC: Check 'show chassis routing-engine' for RE status. "
                "Verify no control plane policy drops with 'show system statistics'."
            )
    
    # Temperature/power suggestions
    temp_alerts = [a for a in alerts if "TEMP" in a["variable"]]
    power_alerts = [a for a in alerts if "POWER" in a["variable"]]
    
    if temp_alerts:
        suggestions.append(
            "HARDWARE: High temperature detected. Check: 1) Fan operation, "
            "2) Airflow blockage, 3) Ambient temperature, 4) Failed cooling unit."
        )
    
    if power_alerts:
        suggestions.append(
            "HARDWARE: Power issue detected. Check: 1) Power supply LEDs, "
            "2) Power cables, 3) UPS status, 4) Redundant power supply status."
        )
    
    # Generic fallback if no specific suggestions
    if not suggestions and critical_alerts:
        suggestions.append(
            f"ALERT: {len(critical_alerts)} critical issues detected on {device_id}. "
            "Immediate investigation required. Review device logs and physical status."
        )
    
    return suggestions[:5]  # Top 5 suggestions


def analyze_device(
    cfg: Any,
    store: SqliteStore,
    device_id: str,
    snapshot: Dict[str, Any],
    now: datetime,
    correlated_devices: List[str] = None,
) -> Dict[str, Any]:
    """
    Comprehensive AI analysis of device metrics.
    
    Implements:
    1. Threshold breach detection
    2. Anomaly detection (Z-score)
    3. Trend prediction (ETA to threshold)
    4. Flapping detection
    5. Routing instability detection
    6. Log pattern intelligence
    7. Correlated failure context
    8. Health scoring (0-100)
    9. Root cause suggestion generation
    """
    raw_cfg = cfg.raw if hasattr(cfg, "raw") else cfg
    alerts: List[Dict[str, Any]] = []
    
    metrics = snapshot.get("metrics", []) or []
    metric_by_var: Dict[str, Dict[str, Any]] = {m.get("variable"): m for m in metrics if m.get("variable")}
    
    health_score = 100.0
    predictions: List[Dict[str, Any]] = []
    os_name = str(snapshot.get("os") or snapshot.get("raw", {}).get("os") or "")
    
    # Raw outputs for advanced analysis
    raw_outputs = snapshot.get("raw", {}).get("outputs", {})
    
    # 1. Threshold Detection (lines 70-91)
    for variable, m in metric_by_var.items():
        val = m.get("value")
        val_text = m.get("value_text")
        
        w = 1.0
        try:
            if os_name:
                w = float(variable_weight(os_name, variable, default=1.0))
        except Exception:
            w = 1.0
        
        thr = _thresholds(raw_cfg, variable)
        if thr and isinstance(val, (int, float)):
            if float(val) >= thr["crit"]:
                alerts.append({
                    "severity": "critical",
                    "variable": variable,
                    "alert_type": "threshold",
                    "message": f"{variable}={val} exceeded critical threshold={thr['crit']}",
                })
                health_score -= 25 * w
            elif float(val) >= thr["warn"]:
                alerts.append({
                    "severity": "warning",
                    "variable": variable,
                    "alert_type": "threshold",
                    "message": f"{variable}={val} exceeded warning threshold={thr['warn']}",
                })
                health_score -= 10 * w
        
        # State-based failures
        if variable in {"INTERFACE_STATUS", "ROUTING_STATE", "POWER_STATUS", "HARDWARE_HEALTH"} and isinstance(val_text, str):
            failure_states = {"down", "failed", "inactive", "no", "false", "error", "critical"}
            if val_text.lower() in failure_states:
                alerts.append({
                    "severity": "critical",
                    "variable": variable,
                    "alert_type": "state",
                    "message": f"{variable} indicates failure state: {val_text}",
                })
                health_score -= 30 * w
        
        # Interface errors
        if variable == "INTERFACE_ERRORS" and isinstance(val, (int, float)):
            if float(val) > 0:
                sev = "warning" if float(val) < 50 else "critical"
                alerts.append({
                    "severity": sev,
                    "variable": variable,
                    "alert_type": "interface_errors",
                    "message": f"Interface errors detected: {val}",
                })
                health_score -= (5 if sev == "warning" else 15) * w
    
    # 2. Anomaly Detection (Z-score) (lines 118-146)
    for variable, m in metric_by_var.items():
        val = m.get("value")
        
        w = 1.0
        try:
            if os_name:
                w = float(variable_weight(os_name, variable, default=1.0))
        except Exception:
            w = 1.0
        
        if isinstance(val, (int, float)):
            anom_cfg = (raw_cfg.get("ai") or {}).get("anomaly") or {}
            window_points = int(anom_cfg.get("window_points", 30))
            series_rows = store.get_recent_series(device_id, variable, limit=window_points)
            series = [float(r[1]) for r in reversed(series_rows) if r[1] is not None]
            
            if len(series) >= max(5, window_points // 3):
                z = _zscore(series[:-1] if len(series) > 1 else series, float(val))
                z_warn = float(anom_cfg.get("zscore_warn", 2.5))
                z_crit = float(anom_cfg.get("zscore_crit", 3.5))
                
                if abs(z) >= z_crit:
                    alerts.append({
                        "severity": "critical",
                        "variable": variable,
                        "alert_type": "anomaly",
                        "message": f"{variable} statistical anomaly detected (z-score={z:.2f}, value={val})",
                    })
                    health_score -= 15 * w
                elif abs(z) >= z_warn:
                    alerts.append({
                        "severity": "warning",
                        "variable": variable,
                        "alert_type": "anomaly",
                        "message": f"{variable} deviation from baseline (z-score={z:.2f}, value={val})",
                    })
                    health_score -= 5 * w
    
    # 3. Trend Prediction (lines 148-169)
    for variable, m in metric_by_var.items():
        val = m.get("value")
        
        if isinstance(val, (int, float)):
            anom_cfg = (raw_cfg.get("ai") or {}).get("anomaly") or {}
            window_points = int(anom_cfg.get("window_points", 30))
            series_rows = store.get_recent_series(device_id, variable, limit=window_points)
            series = [float(r[1]) for r in reversed(series_rows) if r[1] is not None]
            
            if len(series) >= 5:
                slope = _trend_slope(series)
                
                # Rising trend detection
                if variable in {"CPU_USAGE", "MEMORY_USAGE", "DISK_USAGE", "LOAD", "TEMPERATURE"} and slope > 0.3:
                    sev = "info" if slope < 1.0 else "warning"
                    alerts.append({
                        "severity": sev,
                        "variable": variable,
                        "alert_type": "trend",
                        "message": f"{variable} showing upward trend (slope={slope:.2f}/interval)",
                    })
                    
                    # Calculate ETA to thresholds
                    thr = _thresholds(raw_cfg, variable)
                    if thr and slope > 0:
                        warn_t = float(thr.get("warn", math.inf))
                        crit_t = float(thr.get("crit", math.inf))
                        
                        if warn_t != math.inf:
                            eta_warn = (warn_t - float(val)) / slope
                            if 0 < eta_warn < 5000:
                                predictions.append({
                                    "variable": variable,
                                    "target": "warn",
                                    "eta_points": round(eta_warn, 2),
                                    "eta_human": f"~{round(eta_warn * 10)} minutes" if eta_warn < 600 else f"~{round(eta_warn / 6)} hours",
                                })
                        
                        if crit_t != math.inf:
                            eta_crit = (crit_t - float(val)) / slope
                            if 0 < eta_crit < 5000:
                                predictions.append({
                                    "variable": variable,
                                    "target": "crit",
                                    "eta_points": round(eta_crit, 2),
                                    "eta_human": f"~{round(eta_crit * 10)} minutes" if eta_crit < 600 else f"~{round(eta_crit / 6)} hours",
                                })
    
    # 4. Flapping Detection (lines 171-200)
    flap_cfg = (raw_cfg.get("ai") or {}).get("flapping") or {}
    flap_window_points = int((flap_cfg.get("window_sec", 300)) // max(1, int((raw_cfg.get("polling") or {}).get("fast_sec", 10))))
    flap_warn = int(flap_cfg.get("state_change_warn", 6))
    flap_crit = int(flap_cfg.get("state_change_crit", 12))
    
    for variable in {"INTERFACE_STATUS", "ROUTING_STATE", "POWER_STATUS"}:
        rows = store.get_recent_series(device_id, variable, limit=max(10, flap_window_points))
        states = [str(r[2] or "").lower() for r in reversed(rows)]
        
        if len(states) >= 5:
            changes = sum(1 for i in range(1, len(states)) if states[i] and states[i - 1] and states[i] != states[i - 1])
            
            if changes >= flap_crit:
                alerts.append({
                    "severity": "critical",
                    "variable": variable,
                    "alert_type": "flap",
                    "message": f"{variable} critically unstable - {changes} state changes detected",
                })
                health_score -= 20
            elif changes >= flap_warn:
                alerts.append({
                    "severity": "warning",
                    "variable": variable,
                    "alert_type": "flap",
                    "message": f"{variable} flapping detected - {changes} state changes",
                })
                health_score -= 10
    
    # 5. Routing Instability Detection
    if "routing" in raw_outputs:
        routing_issues = _detect_routing_instability(raw_outputs.get("routing", ""))
        for issue in routing_issues:
            alerts.append({
                "severity": issue["severity"],
                "variable": "ROUTING_STATE",
                "alert_type": "routing_instability",
                "message": f"Routing instability: {issue['description']} (count={issue.get('count', 1)})",
                "protocol": issue.get("protocol", "unknown"),
            })
            health_score -= 15 if issue["severity"] == "critical" else 8
    
    # 6. Log Pattern Intelligence
    if "logs" in raw_outputs:
        log_patterns = _analyze_log_patterns(raw_outputs.get("logs", ""))
        for pattern in log_patterns:
            alerts.append({
                "severity": pattern["severity"],
                "variable": "LOG_ERRORS",
                "alert_type": "log_pattern",
                "message": f"Log pattern: {pattern['description']} (occurrences={pattern['count']})",
                "pattern": pattern["pattern"],
                "samples": pattern.get("samples", []),
            })
            health_score -= 10 if pattern["severity"] == "critical" else 5
    
    # 7. Health Score Calculation
    if health_score < 0:
        health_score = 0.0
    health_score = round(health_score, 2)
    
    # 8. Root Cause Suggestion Generation
    root_cause_suggestions = _generate_root_cause_suggestions(
        alerts, health_score, device_id, os_name, correlated_devices
    )
    
    return {
        "health_score": health_score,
        "alerts": alerts,
        "predictions": predictions[:10],
        "root_cause_suggestions": root_cause_suggestions,
        "analysis_summary": {
            "critical_count": len([a for a in alerts if a["severity"] == "critical"]),
            "warning_count": len([a for a in alerts if a["severity"] == "warning"]),
            "info_count": len([a for a in alerts if a["severity"] == "info"]),
            "has_correlated_failure": bool(correlated_devices),
            "correlated_device_count": len(correlated_devices) if correlated_devices else 0,
        },
    }
