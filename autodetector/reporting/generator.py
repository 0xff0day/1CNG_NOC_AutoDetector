from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, List

import pandas as pd

from autodetector.integrations.telegram import send_telegram_message
from autodetector.plugin.registry import load_builtin_registry
from autodetector.storage.sqlite_store import SqliteStore


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _alerts_table(store: SqliteStore, limit: int = 1000) -> List[Dict[str, Any]]:
    return store.list_alerts(limit=limit)


def generate_reports(cfg: Any, store: SqliteStore, now: datetime, range_name: str) -> Dict[str, Any]:
    raw_cfg = cfg.raw if hasattr(cfg, "raw") else cfg
    rep_cfg = raw_cfg.get("reporting") or {}
    out_dir = str(rep_cfg.get("output_dir", "./reports"))
    _ensure_dir(out_dir)

    formats = rep_cfg.get("formats") or ["json", "txt"]
    alerts = _alerts_table(store, limit=2000)

    registry = load_builtin_registry()
    device_meta = {d.id: {"os": d.os, "tags": d.tags or []} for d in getattr(cfg, "devices", [])}

    def _group(device_id: str) -> str:
        m = device_meta.get(device_id) or {}
        osn = str(m.get("os", ""))
        g = registry.group_for_os(osn)
        return g

    sev_counts = {"info": 0, "warning": 0, "critical": 0}
    group_counts = {"network": 0, "server": 0, "hypervisor": 0, "unknown": 0}
    for a in alerts:
        sev = str(a.get("severity", "info"))
        if sev in sev_counts:
            sev_counts[sev] += 1
        group_counts[_group(str(a.get("device_id", "")))] += 1

    cap: Dict[str, Any] = {"top_by_avg": [], "notes": []}
    sec: Dict[str, Any] = {"log_error_alerts": 0, "top_devices": []}

    if range_name in {"day", "month", "year"}:
        if range_name == "day":
            period = "hour"
            since = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        elif range_name == "month":
            period = "day"
            since = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
        else:
            period = "day"
            since = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()

        rollups = store.list_rollups(period=period, since_ts=since, limit=20000)
        payload_rollups = rollups

        interesting = {"CPU_USAGE", "MEMORY_USAGE", "DISK_USAGE", "LOAD"}
        top = [r for r in rollups if str(r.get("variable")) in interesting and r.get("avg") is not None]
        top_sorted = sorted(top, key=lambda r: float(r.get("avg") or 0.0), reverse=True)[:20]
        cap["top_by_avg"] = [
            {
                "device_id": r.get("device_id"),
                "variable": r.get("variable"),
                "avg": r.get("avg"),
                "max": r.get("max"),
                "bucket_ts": r.get("bucket_ts"),
            }
            for r in top_sorted
        ]

        sec_alerts = [a for a in alerts if str(a.get("variable")) == "LOG_ERRORS"]
        sec["log_error_alerts"] = len(sec_alerts)
        by_dev: Dict[str, int] = {}
        for a in sec_alerts:
            did = str(a.get("device_id", ""))
            by_dev[did] = by_dev.get(did, 0) + 1
        sec["top_devices"] = sorted(
            [{"device_id": k, "count": v, "group": _group(k)} for k, v in by_dev.items()],
            key=lambda x: int(x.get("count", 0)),
            reverse=True,
        )[:10]
    else:
        payload_rollups = None

    payload = {
        "generated_ts": now.isoformat(),
        "range": range_name,
        "categories": {
            "Network Health": {"alerts": group_counts.get("network", 0)},
            "Server Health": {"alerts": group_counts.get("server", 0)},
            "Hypervisor Health": {"alerts": group_counts.get("hypervisor", 0)},
            "Performance": {"notes": "Use metric_rollups for trends"},
            "Security Logs": sec,
            "Capacity Planning": cap,
        },
        "summary": {"severity_counts": sev_counts, "group_counts": group_counts},
        "alerts": alerts,
    }

    if payload_rollups is not None:
        payload["metric_rollups"] = payload_rollups

    base = os.path.join(out_dir, f"report_{range_name}_{now.strftime('%Y%m%dT%H%M%SZ')}")
    written: List[str] = []

    if "json" in formats:
        p = base + ".json"
        with open(p, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, sort_keys=True, default=str)
        written.append(p)

    if "txt" in formats:
        p = base + ".txt"
        with open(p, "w", encoding="utf-8") as f:
            f.write(f"Generated: {payload['generated_ts']}\n")
            f.write(f"Range: {range_name}\n")
            f.write(f"Severity: critical={sev_counts['critical']} warning={sev_counts['warning']} info={sev_counts['info']}\n")
            f.write(f"Groups: network={group_counts.get('network',0)} server={group_counts.get('server',0)} hypervisor={group_counts.get('hypervisor',0)}\n")
            if cap.get("top_by_avg"):
                f.write("\nCapacity (top by avg):\n")
                for r in cap["top_by_avg"][:20]:
                    f.write(f"{r['device_id']} {r['variable']} avg={r['avg']} max={r['max']} bucket={r['bucket_ts']}\n")
            if sec.get("log_error_alerts"):
                f.write("\nSecurity Logs (LOG_ERRORS alerts):\n")
                f.write(f"count={sec['log_error_alerts']}\n")
                for r in sec.get("top_devices", [])[:10]:
                    f.write(f"{r['device_id']} count={r['count']} group={r['group']}\n")
            f.write("\nAlerts:\n")
            for a in alerts[:500]:
                f.write(f"[{a['severity']}] {a['ts']} {a['device_id']} {a['variable']} {a['alert_type']} - {a['message']}\n")
        written.append(p)

    if "xlsx" in formats:
        p = base + ".xlsx"
        df = pd.DataFrame(alerts)
        with pd.ExcelWriter(p, engine="openpyxl") as w:
            df.to_excel(w, index=False, sheet_name="alerts")
        written.append(p)

    tg = (raw_cfg.get("integrations") or {}).get("telegram") or {}
    if bool(tg.get("enabled", False)):
        cap_top = cap.get("top_by_avg") or []
        cap_line = ""
        if cap_top:
            first = cap_top[0]
            cap_line = f"Top capacity: {first.get('device_id')} {first.get('variable')} avg={first.get('avg')} max={first.get('max')}\n"
        sec_line = ""
        if int(sec.get("log_error_alerts") or 0) > 0:
            sec_line = f"LOG_ERRORS alerts: {sec.get('log_error_alerts')}\n"
        msg = (
            f"Report generated: {range_name}\n"
            f"Critical: {sev_counts['critical']}  Warning: {sev_counts['warning']}  Info: {sev_counts['info']}\n"
            f"Network: {group_counts.get('network', 0)}  Server: {group_counts.get('server', 0)}  Hypervisor: {group_counts.get('hypervisor', 0)}\n"
            + cap_line
            + sec_line
            + "Files:\n" + "\n".join(written)
        )
        send_telegram_message(cfg, msg)

    return {"written": written, "count_alerts": len(alerts)}
