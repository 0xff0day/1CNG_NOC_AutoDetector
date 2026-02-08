from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Tuple


def correlate_alerts(cfg: Any, alerts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    raw_cfg = cfg.raw if hasattr(cfg, "raw") else cfg
    deps = ((raw_cfg.get("correlation") or {}).get("dependencies") or [])
    win_sec = int(((raw_cfg.get("correlation") or {}).get("incident_window_sec") or 300))

    by_device: Dict[str, List[Dict[str, Any]]] = {}
    for a in alerts:
        by_device.setdefault(a.get("device_id", ""), []).append(a)

    correlations: List[Dict[str, Any]] = []

    def _ts(a: Dict[str, Any]) -> datetime:
        try:
            return datetime.fromisoformat(str(a.get("ts")))
        except Exception:  # noqa: BLE001
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

    for cl in _cluster(alerts):
        devices = sorted(list({str(a.get("device_id", "")) for a in cl if a.get("device_id")}))
        sev_rank = {"info": 1, "warning": 2, "critical": 3}
        top = sorted(cl, key=lambda a: sev_rank.get(str(a.get("severity")), 0), reverse=True)[:5]
        correlations.append(
            {
                "type": "incident",
                "incident_id": str(uuid.uuid4()),
                "start_ts": str(min(_ts(a) for a in cl).isoformat()) if cl else "",
                "end_ts": str(max(_ts(a) for a in cl).isoformat()) if cl else "",
                "devices": devices,
                "top_alerts": [{"device_id": a.get("device_id"), "severity": a.get("severity"), "variable": a.get("variable"), "message": a.get("message")} for a in top],
            }
        )

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
            correlations.append(
                {
                    "type": "dependency_root_cause",
                    "root_device": up,
                    "impacted_device": down,
                    "root_alert": up_crit[0].get("message"),
                    "impact_alert": down_crit[0].get("message"),
                    "suggestion": f"Likely upstream impact: {up} -> {down}",
                }
            )

            correlations.append(
                {
                    "type": "impact_chain",
                    "chain": [up, down],
                    "root": up,
                    "impact": down,
                    "confidence": 0.7,
                }
            )

    return correlations
