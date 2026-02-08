from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


def _safe_float(x: str) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None


def _parse_cpu_top(text: str) -> Optional[float]:
    """Parse CPU from top output (macOS format)."""
    # macOS top shows: "CPU usage: 10.0% user, 5.0% sys, 85.0% idle"
    m = re.search(r"CPU usage:\s+([\d.]+)%\s+user,\s+([\d.]+)%\s+sys", text)
    if m:
        user = _safe_float(m.group(1))
        system = _safe_float(m.group(2))
        if user is not None and system is not None:
            return round(user + system, 2)
    return None


def _parse_memory_vmstat(text: str) -> Optional[float]:
    """Parse memory from vm_stat output."""
    # vm_stat output on macOS:
    # Pages free: 123456
    # Pages active: 789012
    # Pages inactive: 345678
    # Pages wired down: 901234
    
    free_match = re.search(r"Pages free:\s+(\d+)", text)
    active_match = re.search(r"Pages active:\s+(\d+)", text)
    inactive_match = re.search(r"Pages inactive:\s+(\d+)", text)
    wired_match = re.search(r"Pages wired down:\s+(\d+)", text)
    
    if free_match and active_match and inactive_match and wired_match:
        free_pages = _safe_float(free_match.group(1))
        active_pages = _safe_float(active_match.group(1))
        inactive_pages = _safe_float(inactive_match.group(1))
        wired_pages = _safe_float(wired_match.group(1))
        
        total_pages = free_pages + active_pages + inactive_pages + wired_pages
        used_pages = active_pages + inactive_pages + wired_pages
        
        if total_pages and total_pages > 0:
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
        if len(parts) < 9:
            continue
        # macOS df: Filesystem 1024-blocks Used Available Capacity iused ifree %iused Mounted on
        capacity = parts[-3]
        if capacity.endswith("%"):
            v = _safe_float(capacity[:-1])
            if v is not None:
                usages.append(float(v))
    if usages:
        return float(max(usages))
    return None


def _parse_load_uptime(text: str) -> Optional[float]:
    """Parse load average from uptime output."""
    # macOS uptime: "load averages: 1.23 1.45 1.67"
    m = re.search(r"load averages?:\s*([0-9]+\.[0-9]+)", text)
    if m:
        return _safe_float(m.group(1))
    return None


def _parse_interface_state(text: str) -> str:
    """Parse interface state from netstat or ifconfig output."""
    if not text.strip():
        return "unknown"
    
    # Look for interface status lines
    up_count = 0
    down_count = 0
    total_count = 0
    
    for l in text.splitlines():
        # Match interface lines: "en0: flags=8863<UP,BROADCAST,SMART,RUNNING,SIMPLEX,MULTICAST> mtu 1500"
        m = re.match(r"^(\w+):\s*flags=\d+<(.*?)>", l.strip())
        if m:
            name = m.group(1)
            if name in ("lo0", "lo"):
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
    """Parse macOS CLI outputs into normalized metrics."""
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
