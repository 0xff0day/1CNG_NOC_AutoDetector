from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


def _safe_float(x: str) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None


def _parse_cpu_top(text: str) -> Optional[float]:
    """Parse CPU from top output (FreeBSD format)."""
    # FreeBSD top shows: "CPU:  5.0% user,  0.0% nice, 10.0% system,  0.0% interrupt, 85.0% idle"
    m = re.search(r"CPU:\s+([\d.]+)%\s+user.*?,\s+[\d.]+%,\s+([\d.]+)%\s+system.*?", text)
    if m:
        user = _safe_float(m.group(1))
        system = _safe_float(m.group(2))
        if user is not None and system is not None:
            return round(user + system, 2)
    
    # Alternative pattern from vmstat
    vmstat_lines = [l for l in text.splitlines() if l.strip() and not l.startswith("procs")]
    if len(vmstat_lines) >= 2:
        # Last line has CPU stats in columns
        parts = vmstat_lines[-1].split()
        if len(parts) >= 17:
            us = _safe_float(parts[-3]) if parts[-3] != '-' else 0
            sy = _safe_float(parts[-2]) if parts[-2] != '-' else 0
            if us is not None and sy is not None:
                return round(us + sy, 2)
    return None


def _parse_memory_vmstat(text: str) -> Optional[float]:
    """Parse memory from vmstat or sysctl output."""
    # Try sysctl format first
    total_match = re.search(r"hw\.physmem:\s*(\d+)", text)
    avail_match = re.search(r"hw\.usermem:\s*(\d+)", text)
    
    if total_match and avail_match:
        total = _safe_float(total_match.group(1))
        avail = _safe_float(avail_match.group(1))
        if total and total > 0:
            used = total - avail
            return round((used / total) * 100.0, 2)
    
    # vmstat -m format
    for line in text.splitlines():
        m = re.search(r"([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+\d+\s+\d+\s+\d+", line)
        if m:
            total_pages = _safe_float(m.group(1))
            free_pages = _safe_float(m.group(2))
            if total_pages and free_pages and total_pages > 0:
                used_pages = total_pages - free_pages
                return round((used_pages / total_pages) * 100.0, 2)
    return None


def _parse_disk_df(text: str) -> Optional[float]:
    """Parse disk usage from df output."""
    lines = [l for l in text.splitlines() if l.strip()]
    if len(lines) < 2:
        return None
    usages = []
    for l in lines[1:]:
        parts = l.split()
        if len(parts) < 6:
            continue
        # df output format: Filesystem Size Used Avail Capacity ...
        capacity = parts[-2]
        if capacity.endswith("%"):
            v = _safe_float(capacity[:-1])
            if v is not None:
                usages.append(float(v))
    if usages:
        return float(max(usages))
    return None


def _parse_load_uptime(text: str) -> Optional[float]:
    """Parse load average from uptime output."""
    # FreeBSD uptime: "... load averages: 0.52, 0.58, 0.59"
    m = re.search(r"load averages?:\s*([0-9]+\.[0-9]+)", text)
    if m:
        return _safe_float(m.group(1))
    return None


def _parse_interface_state(text: str) -> str:
    """Parse interface state from ifconfig output."""
    if not text.strip():
        return "unknown"
    
    interfaces = text.split("\n\n")
    up_count = 0
    down_count = 0
    total_count = 0
    
    for iface in interfaces:
        if not iface.strip():
            continue
        lines = iface.splitlines()
        if not lines:
            continue
        # First line has interface name and flags
        first_line = lines[0]
        # Match: "em0: flags=8843<UP,BROADCAST,RUNNING,SIMPLEX,MULTICAST>..."
        m = re.match(r"^(\w+):\s*flags=\d+<(.*?)>", first_line)
        if m:
            name = m.group(1)
            if name in ("lo0", "lo1", "lo"):
                continue
            flags = m.group(2).split(",")
            total_count += 1
            if "UP" in flags and "RUNNING" in flags:
                up_count += 1
            else:
                down_count += 1
    
    if total_count == 0:
        return "unknown"
    if down_count == 0:
        return "up"
    if down_count == total_count:
        return "down"
    return "degraded"


def _count_log_errors(text: str) -> int:
    if not text.strip():
        return 0
    return len([l for l in text.splitlines() if l.strip()])


def parse(outputs: Dict[str, str], errors: Dict[str, str], device: Dict[str, Any]) -> Dict[str, Any]:
    """Parse FreeBSD CLI outputs into normalized metrics."""
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
