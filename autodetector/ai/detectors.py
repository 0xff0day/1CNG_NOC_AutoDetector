from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Dict, List, Optional

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


def analyze_device(cfg: Any, store: SqliteStore, device_id: str, snapshot: Dict[str, Any], now: datetime) -> Dict[str, Any]:
    raw_cfg = cfg.raw if hasattr(cfg, "raw") else cfg
    alerts: List[Dict[str, Any]] = []

    metrics = snapshot.get("metrics", []) or []
    metric_by_var: Dict[str, Dict[str, Any]] = {m.get("variable"): m for m in metrics if m.get("variable")}

    health_score = 100.0
    root_causes: List[str] = []
    predictions: List[Dict[str, Any]] = []
    os_name = str(snapshot.get("os") or snapshot.get("raw", {}).get("os") or "")

    for variable, m in metric_by_var.items():
        val = m.get("value")
        val_text = m.get("value_text")

        w = 1.0
        try:
            if os_name:
                w = float(variable_weight(os_name, variable, default=1.0))
        except Exception:  # noqa: BLE001
            w = 1.0

        thr = _thresholds(raw_cfg, variable)
        if thr and isinstance(val, (int, float)):
            if float(val) >= thr["crit"]:
                alerts.append(
                    {
                        "severity": "critical",
                        "variable": variable,
                        "alert_type": "threshold",
                        "message": f"{variable}={val} exceeded crit={thr['crit']}",
                    }
                )
                health_score -= 25 * w
            elif float(val) >= thr["warn"]:
                alerts.append(
                    {
                        "severity": "warning",
                        "variable": variable,
                        "alert_type": "threshold",
                        "message": f"{variable}={val} exceeded warn={thr['warn']}",
                    }
                )
                health_score -= 10 * w

        if variable in {"INTERFACE_STATUS", "ROUTING_STATE", "POWER"} and isinstance(val_text, str):
            if val_text.lower() in {"down", "failed", "inactive", "no", "false"}:
                alerts.append(
                    {
                        "severity": "critical",
                        "variable": variable,
                        "alert_type": "state",
                        "message": f"{variable} indicates failure: {val_text}",
                    }
                )
                health_score -= 30 * w

        if variable == "INTERFACE_ERRORS" and isinstance(val, (int, float)):
            if float(val) > 0:
                sev = "warning" if float(val) < 50 else "critical"
                alerts.append(
                    {
                        "severity": sev,
                        "variable": variable,
                        "alert_type": "interface_errors",
                        "message": f"Interface errors detected: {val}",
                    }
                )
                health_score -= (5 if sev == "warning" else 15) * w

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
                    alerts.append(
                        {
                            "severity": "critical",
                            "variable": variable,
                            "alert_type": "anomaly",
                            "message": f"{variable} anomaly z={z:.2f} value={val}",
                        }
                    )
                    health_score -= 15 * w
                elif abs(z) >= z_warn:
                    alerts.append(
                        {
                            "severity": "warning",
                            "variable": variable,
                            "alert_type": "anomaly",
                            "message": f"{variable} anomaly z={z:.2f} value={val}",
                        }
                    )
                    health_score -= 5 * w

                slope = _trend_slope(series)
                if variable in {"CPU_USAGE", "MEMORY_USAGE", "DISK_USAGE", "LOAD"} and slope > 0.3:
                    alerts.append(
                        {
                            "severity": "info",
                            "variable": variable,
                            "alert_type": "trend",
                            "message": f"{variable} rising trend slope={slope:.2f}",
                        }
                    )
                    health_score -= 1 * w

                if thr and variable in {"CPU_USAGE", "MEMORY_USAGE", "DISK_USAGE"}:
                    warn_t = float(thr.get("warn", math.inf))
                    crit_t = float(thr.get("crit", math.inf))
                    if slope > 0 and isinstance(val, (int, float)):
                        eta_warn = (warn_t - float(val)) / slope if warn_t != math.inf else math.inf
                        eta_crit = (crit_t - float(val)) / slope if crit_t != math.inf else math.inf
                        if 0 < eta_warn < 5000:
                            predictions.append({"variable": variable, "target": "warn", "eta_points": round(eta_warn, 2)})
                        if 0 < eta_crit < 5000:
                            predictions.append({"variable": variable, "target": "crit", "eta_points": round(eta_crit, 2)})

    flap_cfg = (raw_cfg.get("ai") or {}).get("flapping") or {}
    flap_window_points = int((flap_cfg.get("window_sec", 300)) // max(1, int((raw_cfg.get("polling") or {}).get("fast_sec", 10))))
    flap_warn = int(flap_cfg.get("state_change_warn", 6))
    flap_crit = int(flap_cfg.get("state_change_crit", 12))

    for variable in {"INTERFACE_STATUS", "ROUTING_STATE"}:
        rows = store.get_recent_series(device_id, variable, limit=max(10, flap_window_points))
        states = [str(r[2] or "").lower() for r in reversed(rows)]
        if len(states) >= 5:
            changes = sum(1 for i in range(1, len(states)) if states[i] and states[i - 1] and states[i] != states[i - 1])
            if changes >= flap_crit:
                alerts.append(
                    {
                        "severity": "critical",
                        "variable": variable,
                        "alert_type": "flap",
                        "message": f"{variable} flapping detected changes={changes}",
                    }
                )
                health_score -= 20
            elif changes >= flap_warn:
                alerts.append(
                    {
                        "severity": "warning",
                        "variable": variable,
                        "alert_type": "flap",
                        "message": f"{variable} flapping detected changes={changes}",
                    }
                )
                health_score -= 10

    if health_score < 0:
        health_score = 0.0

    for a in alerts:
        if a["severity"] == "critical":
            root_causes.append(a["message"])

    return {
        "health_score": round(float(health_score), 2),
        "alerts": alerts,
        "root_cause_suggestions": root_causes[:5],
        "predictions": predictions[:20],
    }
