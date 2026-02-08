from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


def _safe_float(x: str) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None


def _parse_virsh_nodecpustats(text: str) -> Optional[float]:
    """Parse CPU stats from virsh nodecpustats."""
    # Look for: user: 1234567890 ns or percentage values
    m = re.search(r"user[:\s]+(\d+(?:\.\d+)?)", text, re.IGNORECASE)
    if m:
        return _safe_float(m.group(1))
    
    # Alternative: look for percentage directly
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    if m:
        return _safe_float(m.group(1))
    return None


def _parse_virsh_nodememstats(text: str) -> Optional[float]:
    """Parse memory stats from virsh nodememstats."""
    # Look for free, total values
    total_match = re.search(r"total[:\s]+(\d+)", text, re.IGNORECASE)
    free_match = re.search(r"free[:\s]+(\d+)", text, re.IGNORECASE)
    
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


def _parse_virsh_vms(text: str) -> Dict[str, int]:
    """Parse VM list from virsh list --all."""
    total_vms = 0
    running_vms = 0
    
    for line in text.splitlines():
        if line.strip() and not line.startswith("Id"):
            parts = line.split()
            if len(parts) >= 3:
                total_vms += 1
                if parts[2].lower() in ("running", "run"):
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
    """Parse KVM/libvirt CLI outputs into normalized metrics."""
    _ = device
    metrics: List[Dict[str, Any]] = []

    cpu = _parse_virsh_nodecpustats(outputs.get("cpu", ""))
    if cpu is not None:
        metrics.append({"variable": "CPU_USAGE", "value": cpu})

    mem = _parse_virsh_nodememstats(outputs.get("memory", ""))
    if mem is not None:
        metrics.append({"variable": "MEMORY_USAGE", "value": mem})

    disk = _parse_disk_df(outputs.get("disk", ""))
    if disk is not None:
        metrics.append({"variable": "DISK_USAGE", "value": disk})

    # VM counts
    vm_data = _parse_virsh_vms(outputs.get("vms", ""))
    metrics.append({"variable": "VM_COUNT", "value": float(vm_data["total"])})
    metrics.append({"variable": "VM_RUNNING", "value": float(vm_data["running"])})

    if_state = _parse_interface_state(outputs.get("interfaces", ""))
    metrics.append({"variable": "INTERFACE_STATUS", "value_text": if_state})

    log_err = _count_log_errors(outputs.get("logs", ""))
    metrics.append({"variable": "LOG_ERRORS", "value": float(log_err)})

    return {"metrics": metrics, "raw": {"errors": errors}}
