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

    res = outputs.get("cpu", "") + "\n" + outputs.get("memory", "")
    m_cpu = re.search(r"\b(cpu|CPU)\b.*?(\d+)%", res)
    if m_cpu:
        v = _safe_float(m_cpu.group(2))
        if v is not None:
            metrics.append({"variable": "CPU_USAGE", "value": v})

    m_mem = re.search(r"\b(mem|memory|Memory)\b.*?(\d+)%", res)
    if m_mem:
        v = _safe_float(m_mem.group(2))
        if v is not None:
            metrics.append({"variable": "MEMORY_USAGE", "value": v})

    iface_txt = outputs.get("interfaces", "")
    up = len(re.findall(r"\bstate\s*:\s*up\b", iface_txt, re.IGNORECASE))
    down = len(re.findall(r"\bstate\s*:\s*down\b", iface_txt, re.IGNORECASE))
    if up + down == 0:
        iface_state = "unknown"
    elif down == 0:
        iface_state = "up"
    elif up == 0:
        iface_state = "down"
    else:
        iface_state = "degraded"
    metrics.append({"variable": "INTERFACE_STATUS", "value_text": iface_state})

    err_cnt = 0
    for l in iface_txt.splitlines():
        if re.search(r"\b(error|crc|drop)\b", l, re.IGNORECASE):
            for n in re.findall(r"\b(\d+)\b", l):
                try:
                    err_cnt += int(n)
                except Exception:
                    pass
    metrics.append({"variable": "INTERFACE_ERRORS", "value": float(err_cnt)})

    route_txt = outputs.get("routing", "")
    route_state = "unknown" if not route_txt.strip() else "up"
    if re.search(r"\b0\s+routes\b", route_txt, re.IGNORECASE):
        route_state = "degraded"
    metrics.append({"variable": "ROUTING_STATE", "value_text": route_state})

    log_txt = outputs.get("logs", "")
    log_err = 0
    for l in log_txt.splitlines():
        if re.search(r"\b(error|critical|fail|down|denied)\b", l, re.IGNORECASE):
            log_err += 1
    metrics.append({"variable": "LOG_ERRORS", "value": float(log_err)})

    up_txt = outputs.get("uptime", "")
    metrics.append({"variable": "UPTIME", "value_text": up_txt.strip()})

    return {"metrics": metrics, "raw": {"errors": errors}}
