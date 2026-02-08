from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


def _safe_float(x: str) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None


def _parse_xl_info_cpu(text: str) -> Optional[float]:
    """Parse CPU from xl info output."""
    # Look for: nr_cpus : 8
    m = re.search(r"nr_cpus\s*:\s*(\d+)", text)
    if m:
        # Return 0 as we can't get actual usage from xl info alone
        # CPU usage would require xenstat or xentop
        return 0.0
    return None


def _parse_xl_info_memory(text: str) -> Optional[float]:
    """Parse memory from xl info output."""
    # Look for total_memory and free_memory
    total_match = re.search(r"total_memory\s*:\s*(\d+)", text)
    free_match = re.search(r"free_memory\s*:\s*(\d+)", text)
    
    if total_match and free_match:
        total = _safe_float(total_match.group(1))
        free_mem = _safe_float(free_match.group(1))
        if total and total > 0:
            used = total - free_mem
            return round((used / total) * 100.0, 2)
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
        pct = parts[-2]
        if pct.endswith("%"):
            v = _safe_float(pct[:-1])
            if v is not None:
                usages.append(float(v))
    if usages:
        return float(max(usages))
    return None


def _parse_xl_list_vms(text: str) -> Dict[str, int]:
    """Parse VM list from xl list."""
    total_vms = 0
    running_vms = 0
    
    for line in text.splitlines():
        if line.strip() and not line.startswith("Name"):
            parts = line.split()
            if len(parts) >= 2:
                total_vms += 1
                # Check state column - typically "r" for running
                if len(parts) > 1 and parts[1].lower() in ("r", "running"):
                    running_vms += 1
    
    return {"total": total_vms, "running": running_vms}


def _parse_interface_state(text: str) -> str:
    """Parse interface state from ip output."""
    if not text.strip():
        return "unknown"
    down = 0
    total = 0
    for l in text.splitlines():
        m = re.match(r"^\d+:\s*([^:]+):\s*<([^>]*)", l.strip())
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


def _count_log_errors(text: str) -> int:
    if not text.strip():
        return 0
    return len([l for l in text.splitlines() if l.strip()])


def parse(outputs: Dict[str, str], errors: Dict[str, str], device: Dict[str, Any]) -> Dict[str, Any]:
    """Parse Xen CLI outputs into normalized metrics."""
    _ = device
    metrics: List[Dict[str, Any]] = []

    # Xen CPU stats - limited without xentop
    cpu = _parse_xl_info_cpu(outputs.get("cpu", ""))
    if cpu is not None:
        metrics.append({"variable": "CPU_USAGE", "value": cpu})

    mem = _parse_xl_info_memory(outputs.get("memory", ""))
    if mem is not None:
        metrics.append({"variable": "MEMORY_USAGE", "value": mem})

    disk = _parse_disk_df(outputs.get("disk", ""))
    if disk is not None:
        metrics.append({"variable": "DISK_USAGE", "value": disk})

    # VM counts from xl list
    vm_data = _parse_xl_list_vms(outputs.get("vms", ""))
    metrics.append({"variable": "VM_COUNT", "value": float(vm_data["total"])})
    metrics.append({"variable": "VM_RUNNING", "value": float(vm_data["running"])})

    if_state = _parse_interface_state(outputs.get("interfaces", ""))
    metrics.append({"variable": "INTERFACE_STATUS", "value_text": if_state})

    log_err = _count_log_errors(outputs.get("logs", ""))
    metrics.append({"variable": "LOG_ERRORS", "value": float(log_err)})

    return {"metrics": metrics, "raw": {"errors": errors}}
