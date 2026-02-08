from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def parse(outputs: Dict[str, str], errors: Dict[str, str], device: Dict[str, Any]) -> Dict[str, Any]:
    _ = device
    metrics: List[Dict[str, Any]] = []

    def _load_json(text: str) -> Any:
        t = (text or "").strip()
        if not t:
            return None
        try:
            return json.loads(t)
        except Exception:
            return None

    cpu = _load_json(outputs.get("cpu", ""))
    if isinstance(cpu, dict) and isinstance(cpu.get("cpu"), (int, float)):
        metrics.append({"variable": "CPU_USAGE", "value": float(cpu["cpu"])})

    mem = _load_json(outputs.get("memory", ""))
    if isinstance(mem, dict) and isinstance(mem.get("mem"), (int, float)):
        metrics.append({"variable": "MEMORY_USAGE", "value": float(mem["mem"])})

    disks = _load_json(outputs.get("disk", ""))
    max_disk = None
    if isinstance(disks, dict) and isinstance(disks.get("disks"), list):
        for d in disks.get("disks"):
            if isinstance(d, dict) and isinstance(d.get("usedPct"), (int, float)):
                v = float(d["usedPct"])
                max_disk = v if max_disk is None else max(max_disk, v)
    if max_disk is not None:
        metrics.append({"variable": "DISK_USAGE", "value": float(max_disk)})

    load = _load_json(outputs.get("load", ""))
    if isinstance(load, dict) and isinstance(load.get("queue"), (int, float)):
        metrics.append({"variable": "LOAD", "value": float(load["queue"])})

    ifs = _load_json(outputs.get("interfaces", ""))
    total = 0
    down = 0
    if isinstance(ifs, list):
        for x in ifs:
            if not isinstance(x, dict):
                continue
            total += 1
            st = str(x.get("Status", "")).lower()
            if st not in {"up"}:
                down += 1
    iface_state = "unknown"
    if total > 0:
        if down == 0:
            iface_state = "up"
        elif down == total:
            iface_state = "down"
        else:
            iface_state = "degraded"
    metrics.append({"variable": "INTERFACE_STATUS", "value_text": iface_state})

    st = _load_json(outputs.get("interface_errors", ""))
    err_cnt = 0
    if isinstance(st, list):
        for x in st:
            if not isinstance(x, dict):
                continue
            for k in ["ReceivedErrors", "OutboundErrors", "ReceivedDiscarded", "OutboundDiscarded"]:
                v = x.get(k)
                if isinstance(v, (int, float)):
                    err_cnt += int(v)
    metrics.append({"variable": "INTERFACE_ERRORS", "value": float(err_cnt)})

    lg = _load_json(outputs.get("logs", ""))
    log_err = 0
    if isinstance(lg, list):
        log_err = len(lg)
    metrics.append({"variable": "LOG_ERRORS", "value": float(log_err)})

    up = _load_json(outputs.get("uptime", ""))
    boot = None
    if isinstance(up, dict):
        boot = up.get("boot")
    if isinstance(boot, str) and boot:
        metrics.append({"variable": "UPTIME", "value_text": boot})
    else:
        metrics.append({"variable": "UPTIME", "value_text": (outputs.get("uptime", "") or "").strip()})

    return {"metrics": metrics, "raw": {"errors": errors}}
