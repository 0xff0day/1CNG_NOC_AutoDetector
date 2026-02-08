from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


def parse(outputs: Dict[str, str], errors: Dict[str, str], device: Dict[str, Any]) -> Dict[str, Any]:
    _ = device
    metrics: List[Dict[str, Any]] = []

    def _safe_float(x: str) -> Optional[float]:
        try:
            return float(x)
        except Exception:
            return None

    top_txt = outputs.get("cpu", "")
    m = re.search(r"%Cpu\(s\):\s*.*?(\d+\.\d+)\s*us,\s*(\d+\.\d+)\s*sy,.*?(\d+\.\d+)\s*id", top_txt)
    if m:
        idle = _safe_float(m.group(3))
        if idle is not None:
            metrics.append({"variable": "CPU_USAGE", "value": round(100.0 - idle, 2)})

    mem_txt = outputs.get("memory", "")
    for l in mem_txt.splitlines():
        if l.lower().startswith("mem:"):
            p = l.split()
            if len(p) >= 3:
                tot = _safe_float(p[1])
                used = _safe_float(p[2])
                if tot and tot > 0 and used is not None:
                    metrics.append({"variable": "MEMORY_USAGE", "value": round((used / tot) * 100.0, 2)})

    df_txt = outputs.get("disk", "")
    maxu = None
    lines = [l for l in df_txt.splitlines() if l.strip()]
    for l in lines[1:]:
        p = l.split()
        if len(p) < 6:
            continue
        pct = p[-2]
        if pct.endswith("%"):
            v = _safe_float(pct[:-1])
            if v is not None:
                maxu = v if maxu is None else max(maxu, v)
    if maxu is not None:
        metrics.append({"variable": "DISK_USAGE", "value": float(maxu)})

    up_txt = outputs.get("load", "")
    mload = re.search(r"load average:\s*([0-9]+\.[0-9]+)", up_txt)
    if mload:
        v = _safe_float(mload.group(1))
        if v is not None:
            metrics.append({"variable": "LOAD", "value": v})

    link_txt = outputs.get("interfaces", "")
    down = 0
    total = 0
    for l in link_txt.splitlines():
        m2 = re.match(r"^\d+:\s*([^:]+):\s*<([^>]*)>", l.strip())
        if not m2:
            continue
        name = m2.group(1)
        flags = m2.group(2)
        if name == "lo":
            continue
        total += 1
        if "UP" not in flags.split(","):
            down += 1
    if total == 0:
        if_state = "unknown"
    elif down == 0:
        if_state = "up"
    elif down == total:
        if_state = "down"
    else:
        if_state = "degraded"
    metrics.append({"variable": "INTERFACE_STATUS", "value_text": if_state})

    err_cnt = 0
    for l in outputs.get("interface_errors", "").splitlines():
        if re.search(r"\berrors\b|\bdropped\b|\boverrun\b", l, re.IGNORECASE):
            for n in re.findall(r"\b(\d+)\b", l):
                try:
                    err_cnt += int(n)
                except Exception:
                    pass
    metrics.append({"variable": "INTERFACE_ERRORS", "value": float(err_cnt)})

    rt_txt = outputs.get("routing", "")
    rt_state = "unknown" if not rt_txt.strip() else "up"
    if rt_txt.strip() and len(rt_txt.splitlines()) < 2:
        rt_state = "degraded"
    metrics.append({"variable": "ROUTING_STATE", "value_text": rt_state})

    log_txt = outputs.get("logs", "")
    log_err = len([l for l in log_txt.splitlines() if l.strip()])
    metrics.append({"variable": "LOG_ERRORS", "value": float(log_err)})

    metrics.append({"variable": "UPTIME", "value_text": (outputs.get("uptime", "") or "").strip()})

    return {"metrics": metrics, "raw": {"errors": errors}}
