from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


def _safe_float(x: str) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None


def _parse_cpu_top(text: str) -> Optional[float]:
    m = re.search(r"%Cpu\(s\):\s*.*?(\d+\.\d+)\s*us,\s*(\d+\.\d+)\s*sy,.*?(\d+\.\d+)\s*id", text)
    if m:
        idle = _safe_float(m.group(3))
        if idle is not None:
            return round(100.0 - idle, 2)
    return None


def _parse_memory_free(text: str) -> Optional[float]:
    for l in text.splitlines():
        if l.lower().startswith("mem:"):
            p = l.split()
            if len(p) >= 3:
                tot = _safe_float(p[1])
                used = _safe_float(p[2])
                if tot and tot > 0 and used is not None:
                    return round((used / tot) * 100.0, 2)
    return None


def _parse_disk_df(text: str) -> Optional[float]:
    lines = [l for l in text.splitlines() if l.strip()]
    if len(lines) < 2:
        return None
    maxu = None
    for l in lines[1:]:
        p = l.split()
        if len(p) < 6:
            continue
        pct = p[-2]
        if pct.endswith("%"):
            v = _safe_float(pct[:-1])
            if v is not None:
                maxu = v if maxu is None else max(maxu, v)
    return float(maxu) if maxu is not None else None


def _parse_load(text: str) -> Optional[float]:
    m = re.search(r"load average:\s*([0-9]+\.[0-9]+)", text)
    if m:
        return _safe_float(m.group(1))
    return None


def _parse_if_state(text: str) -> str:
    if not text.strip():
        return "unknown"
    down = 0
    total = 0
    for l in text.splitlines():
        m = re.match(r"^\d+:\s*([^:]+):\s*<([^>]*)>", l.strip())
        if not m:
            continue
        name = m.group(1)
        flags = m.group(2)
        if name == "lo":
            continue
        total += 1
        if "UP" not in flags.split(","):
            down += 1
    if total == 0:
        return "unknown"
    if down == 0:
        return "up"
    if down == total:
        return "down"
    return "degraded"


def _parse_if_errors(text: str) -> int:
    total = 0
    for l in text.splitlines():
        if re.search(r"RX:\s+bytes", l):
            continue
        if re.search(r"TX:\s+bytes", l):
            continue
        if re.search(r"\berrors\b|\bdropped\b", l, re.IGNORECASE):
            for n in re.findall(r"\b(\d+)\b", l):
                try:
                    total += int(n)
                except Exception:
                    pass
    return total


def _count_log_errors(text: str) -> int:
    return len([l for l in text.splitlines() if l.strip()])


def parse(outputs: Dict[str, str], errors: Dict[str, str], device: Dict[str, Any]) -> Dict[str, Any]:
    _ = device
    metrics: List[Dict[str, Any]] = []

    cpu = _parse_cpu_top(outputs.get("cpu", ""))
    if cpu is not None:
        metrics.append({"variable": "CPU_USAGE", "value": cpu})

    mem = _parse_memory_free(outputs.get("memory", ""))
    if mem is not None:
        metrics.append({"variable": "MEMORY_USAGE", "value": mem})

    disk = _parse_disk_df(outputs.get("disk", ""))
    if disk is not None:
        metrics.append({"variable": "DISK_USAGE", "value": disk})

    load = _parse_load(outputs.get("load", ""))
    if load is not None:
        metrics.append({"variable": "LOAD", "value": load})

    if_state = _parse_if_state(outputs.get("interfaces", ""))
    metrics.append({"variable": "INTERFACE_STATUS", "value_text": if_state})

    metrics.append({"variable": "INTERFACE_ERRORS", "value": float(_parse_if_errors(outputs.get("interface_errors", "")) )})

    metrics.append({"variable": "LOG_ERRORS", "value": float(_count_log_errors(outputs.get("logs", "")) )})

    metrics.append({"variable": "UPTIME", "value_text": (outputs.get("uptime", "") or "").strip()})

    return {"metrics": metrics, "raw": {"errors": errors}}
