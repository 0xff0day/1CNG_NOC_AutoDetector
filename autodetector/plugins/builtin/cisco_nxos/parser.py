from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


def _safe_float(x: str) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None


def _parse_cpu(text: str) -> Optional[float]:
    m = re.search(r"CPU\s+states\s*:\s*(\d+)%\s*user,\s*(\d+)%\s*kernel", text, re.IGNORECASE)
    if m:
        u = _safe_float(m.group(1))
        k = _safe_float(m.group(2))
        if u is not None and k is not None:
            return round(u + k, 2)
    m = re.search(r"CPU\s+utilization\s*:\s*(\d+)%", text, re.IGNORECASE)
    if m:
        return _safe_float(m.group(1))
    return None


def _parse_mem(text: str) -> Optional[float]:
    m = re.search(r"Memory\s+usage\s*:\s*(\d+)%", text, re.IGNORECASE)
    if m:
        return _safe_float(m.group(1))
    m = re.search(r"Memory\s+\(.*?\)\s*:\s*(\d+)%", text, re.IGNORECASE)
    if m:
        return _safe_float(m.group(1))
    return None


def _parse_interfaces_status(text: str) -> str:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if len(lines) <= 1:
        return "unknown"
    down = 0
    total = 0
    for l in lines[1:]:
        total += 1
        if re.search(r"\bnotconnect\b|\bdown\b|\bdisabled\b|\berr-?disabled\b", l, re.IGNORECASE):
            down += 1
    if total == 0:
        return "unknown"
    if down == 0:
        return "up"
    if down == total:
        return "down"
    return "degraded"


def _parse_int_errors(text: str) -> int:
    cnt = 0
    for l in text.splitlines():
        if re.search(r"\bCRC\b|\binput\s+errors\b|\boutput\s+errors\b", l, re.IGNORECASE):
            nums = re.findall(r"\b(\d+)\b", l)
            for n in nums:
                try:
                    cnt += int(n)
                except Exception:
                    pass
    return cnt


def _parse_routing(text: str) -> str:
    if not text.strip():
        return "unknown"
    if re.search(r"\b0\s+routes\b", text, re.IGNORECASE):
        return "degraded"
    return "up"


def _count_log_errors(text: str) -> int:
    if not text.strip():
        return 0
    bad = 0
    for l in text.splitlines():
        if re.search(r"%.*-\d+-", l):
            if re.search(r"\bERR\b|\bERROR\b|\bCRIT\b|\bFAIL\b|\bDOWN\b", l, re.IGNORECASE):
                bad += 1
    return bad


def parse(outputs: Dict[str, str], errors: Dict[str, str], device: Dict[str, Any]) -> Dict[str, Any]:
    _ = device
    metrics: List[Dict[str, Any]] = []

    cpu = _parse_cpu(outputs.get("cpu", ""))
    if cpu is not None:
        metrics.append({"variable": "CPU_USAGE", "value": cpu})

    mem = _parse_mem(outputs.get("memory", ""))
    if mem is not None:
        metrics.append({"variable": "MEMORY_USAGE", "value": mem})

    metrics.append({"variable": "INTERFACE_STATUS", "value_text": _parse_interfaces_status(outputs.get("interfaces", ""))})

    metrics.append({"variable": "INTERFACE_ERRORS", "value": float(_parse_int_errors(outputs.get("interface_errors", "")) )})

    metrics.append({"variable": "ROUTING_STATE", "value_text": _parse_routing(outputs.get("routing", ""))})

    metrics.append({"variable": "LOG_ERRORS", "value": float(_count_log_errors(outputs.get("logs", "")) )})

    uptime_text = outputs.get("uptime", "")
    metrics.append({"variable": "UPTIME", "value_text": uptime_text.strip()})

    return {"metrics": metrics, "raw": {"errors": errors}}
