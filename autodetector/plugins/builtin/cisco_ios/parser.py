from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


def _safe_float(x: str) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None


def _parse_cpu(text: str) -> Optional[float]:
    m = re.search(r"five seconds:\s*(\d+)%/(\d+)%", text, re.IGNORECASE)
    if m:
        return _safe_float(m.group(1))

    m = re.search(r"five seconds:\s*(\d+)%", text, re.IGNORECASE)
    if m:
        return _safe_float(m.group(1))

    return None


def _parse_memory(text: str) -> Optional[float]:
    total = None
    used = None

    m_total = re.search(r"Processor\s+Pool\s+Total:\s*(\d+)", text, re.IGNORECASE)
    m_used = re.search(r"Processor\s+Pool\s+Used:\s*(\d+)", text, re.IGNORECASE)
    if m_total and m_used:
        total = float(m_total.group(1))
        used = float(m_used.group(1))

    if total and total > 0 and used is not None:
        return round((used / total) * 100.0, 2)

    return None


def _parse_interfaces(text: str) -> str:
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


def _parse_route_summary(text: str) -> str:
    if not text.strip():
        return "unknown"
    if re.search(r"\b0\s+routes\b", text, re.IGNORECASE):
        return "degraded"
    return "up"


def _parse_log_errors(text: str) -> int:
    if not text:
        return 0
    count = 0
    for l in text.splitlines():
        if re.search(r"%.*-\d+-", l):
            if re.search(r"\bERR\b|\bERROR\b|\bCRIT\b|\bFAIL\b|\bDOWN\b", l, re.IGNORECASE):
                count += 1
    return count


def parse(outputs: Dict[str, str], errors: Dict[str, str], device: Dict[str, Any]) -> Dict[str, Any]:
    _ = device
    metrics: List[Dict[str, Any]] = []

    cpu = _parse_cpu(outputs.get("cpu", ""))
    if cpu is not None:
        metrics.append({"variable": "CPU_USAGE", "value": cpu})

    mem = _parse_memory(outputs.get("memory", ""))
    if mem is not None:
        metrics.append({"variable": "MEMORY_USAGE", "value": mem})

    int_state = _parse_interfaces(outputs.get("interfaces", ""))
    metrics.append({"variable": "INTERFACE_STATUS", "value_text": int_state})

    route_state = _parse_route_summary(outputs.get("routing", ""))
    metrics.append({"variable": "ROUTING_STATE", "value_text": route_state})

    log_err = _parse_log_errors(outputs.get("logs", ""))
    metrics.append({"variable": "LOG_ERRORS", "value": float(log_err)})

    uptime_text = outputs.get("uptime", "")
    metrics.append({"variable": "UPTIME", "value_text": uptime_text.strip()})

    return {"metrics": metrics, "raw": {"errors": errors}}
