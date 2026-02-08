from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


def _safe_float(x: str) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None


def _parse_cpu_top(text: str) -> Optional[float]:
    m = re.search(r"CPU:\s+([\d.]+)%\s+user.*?sys", text)
    if m:
        user = _safe_float(m.group(1))
        if user is not None:
            return round(user, 2)
    return None


def _parse_memory_vmstat(text: str) -> Optional[float]:
    total_match = re.search(r"hw\.physmem[=:]\s*(\d+)", text)
    free_match = re.search(r"hw\.usermem[=:]\s*(\d+)", text)
    
    if total_match and free_match:
        total = _safe_float(total_match.group(1))
        free_mem = _safe_float(free_match.group(1))
        if total and total > 0 and free_mem is not None:
            used = total - free_mem
            return round((used / total) * 100.0, 2)
    
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 4:
            total_pages = _safe_float(parts[0])
            free_pages = _safe_float(parts[1])
            if total_pages and free_pages and total_pages > 0:
                used_pages = total_pages - free_pages
                return round((used_pages / total_pages) * 100.0, 2)
    return None


def _parse_disk_df(text: str) -> Optional[float]:
    lines = [l for l in text.splitlines() if l.strip()]
    if len(lines) < 2:
        return None
    usages = []
    for l in lines[1:]:
        parts = l.split()
        if len(parts) < 5:
            continue
        capacity = parts[-2] if parts[-2].endswith("%") else parts[-1]
        if capacity.endswith("%"):
            v = _safe_float(capacity[:-1])
            if v is not None:
                usages.append(float(v))
    if usages:
        return float(max(usages))
    return None


def _parse_load_uptime(text: str) -> Optional[float]:
    m = re.search(r"load averages?:\s*([0-9]+\.[0-9]+)", text)
    if m:
        return _safe_float(m.group(1))
    return None


def _parse_interface_state(text: str) -> str:
    if not text.strip():
        return "unknown"
    down = 0
    total = 0
    for l in text.splitlines():
        m = re.match(r"^(\w+):.*flags=\d+<(.*?)>", l)
        if m:
            name = m.group(1)
            if name in ("lo0", "lo"):
                continue
            flags = m.group(2).split(",")
            total += 1
            if "UP" in flags:
                down += 0
            else:
                down += 1
    if total == 0:
        return "unknown"
    if down == 0:
        return "up"
    if down == total:
        return "down"
    return "degraded"


def _count_log_errors(text: str) -> int:
    if not text.strip():
        return 0
    return len([l for l in text.splitlines() if l.strip()])


def parse(outputs: Dict[str, str], errors: Dict[str, str], device: Dict[str, Any]) -> Dict[str, Any]:
    _ = device
    metrics: List[Dict[str, Any]] = []

    cpu = _parse_cpu_top(outputs.get("cpu", ""))
    if cpu is not None:
        metrics.append({"variable": "CPU_USAGE", "value": cpu})

    mem = _parse_memory_vmstat(outputs.get("memory", ""))
    if mem is not None:
        metrics.append({"variable": "MEMORY_USAGE", "value": mem})

    disk = _parse_disk_df(outputs.get("disk", ""))
    if disk is not None:
        metrics.append({"variable": "DISK_USAGE", "value": disk})

    load = _parse_load_uptime(outputs.get("load", ""))
    if load is not None:
        metrics.append({"variable": "LOAD", "value": load})

    if_state = _parse_interface_state(outputs.get("interfaces", ""))
    metrics.append({"variable": "INTERFACE_STATUS", "value_text": if_state})

    log_err = _count_log_errors(outputs.get("logs", ""))
    metrics.append({"variable": "LOG_ERRORS", "value": float(log_err)})

    return {"metrics": metrics, "raw": {"errors": errors}}
