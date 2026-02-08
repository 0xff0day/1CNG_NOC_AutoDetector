from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


def _safe_float(x: str) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None


def _parse_cpu(text: str) -> Optional[float]:
    m = re.search(r"CPU\s+utilization:\s*(\d+)%", text, re.IGNORECASE)
    if m:
        return _safe_float(m.group(1))
    m = re.search(r"\b(\d+)%\s+idle\b", text, re.IGNORECASE)
    if m:
        idle = _safe_float(m.group(1))
        if idle is not None:
            return round(100.0 - idle, 2)
    return None


def _parse_mem(text: str) -> Optional[float]:
    m = re.search(r"Memory\s+utilization\s*:\s*(\d+)%", text, re.IGNORECASE)
    if m:
        return _safe_float(m.group(1))
    m2 = re.search(r"Physical memory:\s*(\d+)%\s+used", text, re.IGNORECASE)
    if m2:
        return _safe_float(m2.group(1))
    return None


def _parse_interfaces(text: str) -> str:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if len(lines) < 2:
        return "unknown"
    down = 0
    total = 0
    for l in lines[1:]:
        parts = l.split()
        if len(parts) < 3:
            continue
        name, admin, oper = parts[0], parts[1].lower(), parts[2].lower()
        if name.startswith("lo"):
            continue
        total += 1
        if admin != "up" or oper != "up":
            down += 1
    if total == 0:
        return "unknown"
    if down == 0:
        return "up"
    if down == total:
        return "down"
    return "degraded"


def _parse_int_errors(text: str) -> int:
    nums = re.findall(r"\berrors\s+(\d+)\b", text, re.IGNORECASE)
    total = 0
    for n in nums:
        try:
            total += int(n)
        except Exception:
            pass
    return total


def _parse_routing(text: str) -> str:
    if not text.strip():
        return "unknown"
    m = re.search(r"\bTotal routes:\s*(\d+)\b", text, re.IGNORECASE)
    if m:
        try:
            v = int(m.group(1))
            return "up" if v > 0 else "degraded"
        except Exception:
            pass
    return "up"


def _count_log_errors(text: str) -> int:
    if not text.strip():
        return 0
    bad = 0
    for l in text.splitlines():
        if re.search(r"\b(error|critical|fail|down)\b", l, re.IGNORECASE):
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

    metrics.append({"variable": "INTERFACE_STATUS", "value_text": _parse_interfaces(outputs.get("interfaces", ""))})
    metrics.append({"variable": "INTERFACE_ERRORS", "value": float(_parse_int_errors(outputs.get("interface_errors", "")) )})
    metrics.append({"variable": "ROUTING_STATE", "value_text": _parse_routing(outputs.get("routing", ""))})
    metrics.append({"variable": "LOG_ERRORS", "value": float(_count_log_errors(outputs.get("logs", "")) )})

    metrics.append({"variable": "UPTIME", "value_text": (outputs.get("uptime", "") or "").strip()})

    return {"metrics": metrics, "raw": {"errors": errors}}
