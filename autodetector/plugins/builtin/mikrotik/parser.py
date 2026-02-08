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

    res = outputs.get("cpu", "")
    m = re.search(r"cpu-load:\s*(\d+)", res, re.IGNORECASE)
    if m:
        v = _safe_float(m.group(1))
        if v is not None:
            metrics.append({"variable": "CPU_USAGE", "value": v})

    m2 = re.search(r"total-memory:\s*(\d+)", res, re.IGNORECASE)
    m3 = re.search(r"free-memory:\s*(\d+)", res, re.IGNORECASE)
    if m2 and m3:
        t = _safe_float(m2.group(1))
        f = _safe_float(m3.group(1))
        if t and t > 0 and f is not None:
            metrics.append({"variable": "MEMORY_USAGE", "value": round(((t - f) / t) * 100.0, 2)})

    if_txt = outputs.get("interfaces", "")
    down = 0
    total = 0
    for l in if_txt.splitlines():
        if not l.strip():
            continue
        total += 1
        if re.search(r"\bdisabled\b|\bdown\b", l, re.IGNORECASE):
            down += 1
    if total == 0:
        state = "unknown"
    elif down == 0:
        state = "up"
    elif down == total:
        state = "down"
    else:
        state = "degraded"
    metrics.append({"variable": "INTERFACE_STATUS", "value_text": state})

    err_txt = outputs.get("interface_errors", "")
    err_cnt = 0
    for l in err_txt.splitlines():
        if re.search(r"\berrors\b|\bcrc\b|\bdrop\b", l, re.IGNORECASE):
            for n in re.findall(r"\b(\d+)\b", l):
                try:
                    err_cnt += int(n)
                except Exception:
                    pass
    metrics.append({"variable": "INTERFACE_ERRORS", "value": float(err_cnt)})

    route_txt = outputs.get("routing", "")
    route_state = "unknown"
    mrc = re.search(r"\bcount:\s*(\d+)\b", route_txt, re.IGNORECASE)
    if mrc:
        try:
            rc = int(mrc.group(1))
            route_state = "up" if rc > 0 else "degraded"
        except Exception:
            route_state = "degraded"
    metrics.append({"variable": "ROUTING_STATE", "value_text": route_state})

    log_txt = outputs.get("logs", "")
    log_err = 0
    for l in log_txt.splitlines():
        if re.search(r"\b(error|critical|fail|down|denied)\b", l, re.IGNORECASE):
            log_err += 1
    metrics.append({"variable": "LOG_ERRORS", "value": float(log_err)})

    up_m = re.search(r"uptime:\s*(.+)$", res, re.IGNORECASE | re.MULTILINE)
    metrics.append({"variable": "UPTIME", "value_text": (up_m.group(1).strip() if up_m else "")})

    return {"metrics": metrics, "raw": {"errors": errors}}
