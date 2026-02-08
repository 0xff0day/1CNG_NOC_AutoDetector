from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


def _safe_float(x: str) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None


def _parse_uptime_load(text: str) -> Optional[float]:
    m = re.search(r"load average:\s*([0-9]+\.[0-9]+)", text)
    if m:
        return _safe_float(m.group(1))
    return None


def _parse_esxtop_cpu(text: str) -> Optional[float]:
    m = re.search(r"\bCPU\s+usage\s*:\s*(\d+\.?\d*)%", text, re.IGNORECASE)
    if m:
        return _safe_float(m.group(1))
    return None


def _parse_mem(text: str) -> Optional[float]:
    m = re.search(r"Used\s+Memory:\s*(\d+)\s*MB", text, re.IGNORECASE)
    m2 = re.search(r"Physical\s+Memory:\s*(\d+)\s*MB", text, re.IGNORECASE)
    if m and m2:
        u = _safe_float(m.group(1))
        t = _safe_float(m2.group(1))
        if u is not None and t and t > 0:
            return round((u / t) * 100.0, 2)
    return None


def _parse_disk(text: str) -> Optional[float]:
    max_used = None
    for l in text.splitlines():
        parts = l.split()
        if len(parts) < 6:
            continue
        if parts[0].startswith("/vmfs/"):
            try:
                cap = float(parts[2])
                free = float(parts[3])
                if cap > 0:
                    used = (cap - free) / cap * 100.0
                    max_used = used if max_used is None else max(max_used, used)
            except Exception:
                pass
    if max_used is not None:
        return round(max_used, 2)
    return None


def _parse_nics(text: str) -> str:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if len(lines) < 2:
        return "unknown"
    down = 0
    total = 0
    for l in lines[1:]:
        total += 1
        if re.search(r"\bDown\b", l):
            down += 1
    if total == 0:
        return "unknown"
    if down == 0:
        return "up"
    if down == total:
        return "down"
    return "degraded"


def _count_log_errors(text: str) -> int:
    bad = 0
    for l in text.splitlines():
        if re.search(r"\b(error|panic|assert|fail)\b", l, re.IGNORECASE):
            bad += 1
    return bad


def parse(outputs: Dict[str, str], errors: Dict[str, str], device: Dict[str, Any]) -> Dict[str, Any]:
    _ = device
    metrics: List[Dict[str, Any]] = []

    cpu = _parse_esxtop_cpu(outputs.get("load", ""))
    if cpu is not None:
        metrics.append({"variable": "CPU_USAGE", "value": cpu})

    mem = _parse_mem(outputs.get("memory", ""))
    if mem is not None:
        metrics.append({"variable": "MEMORY_USAGE", "value": mem})

    disk = _parse_disk(outputs.get("disk", ""))
    if disk is not None:
        metrics.append({"variable": "DISK_USAGE", "value": disk})

    load = _parse_uptime_load(outputs.get("uptime", ""))
    if load is not None:
        metrics.append({"variable": "LOAD", "value": load})

    metrics.append({"variable": "INTERFACE_STATUS", "value_text": _parse_nics(outputs.get("interfaces", ""))})

    metrics.append({"variable": "LOG_ERRORS", "value": float(_count_log_errors(outputs.get("logs", "")) )})

    metrics.append({"variable": "UPTIME", "value_text": (outputs.get("uptime", "") or "").strip()})

    return {"metrics": metrics, "raw": {"errors": errors}}
