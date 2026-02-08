from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional


def _load_json(text: str) -> Any:
    t = (text or "").strip()
    if not t:
        return None
    try:
        return json.loads(t)
    except Exception:
        return None


def _safe_float(x: str) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None


def _parse_cpu_json(text: str) -> Optional[float]:
    data = _load_json(text)
    if isinstance(data, dict) and isinstance(data.get("CookedValue"), (int, float)):
        return float(data["CookedValue"])
    return None


def _parse_memory_json(text: str) -> Optional[float]:
    data = _load_json(text)
    if isinstance(data, dict):
        total = data.get("TotalVisibleMemorySize")
        free = data.get("FreePhysicalMemory")
        if isinstance(total, (int, float)) and isinstance(free, (int, float)) and total > 0:
            used = total - free
            return round((used / total) * 100.0, 2)
    return None


def _parse_disk_json(text: str) -> Optional[float]:
    data = _load_json(text)
    if isinstance(data, list) and len(data) > 0:
        max_pct = 0.0
        for disk in data:
            if isinstance(disk, dict):
                size = disk.get("Size")
                free = disk.get("FreeSpace")
                if isinstance(size, (int, float)) and isinstance(free, (int, float)) and size > 0:
                    used_pct = ((size - free) / size) * 100.0
                    max_pct = max(max_pct, used_pct)
        return max_pct if max_pct > 0 else None
    return None


def _parse_vms_json(text: str) -> Dict[str, int]:
    data = _load_json(text)
    total = 0
    running = 0
    if isinstance(data, list):
        for vm in data:
            if isinstance(vm, dict):
                total += 1
                state = str(vm.get("State", "")).lower()
                if state in ("running", "operational"):
                    running += 1
    return {"total": total, "running": running}


def _parse_interfaces_json(text: str) -> str:
    data = _load_json(text)
    if not isinstance(data, list):
        return "unknown"
    
    down = 0
    total = 0
    for iface in data:
        if isinstance(iface, dict):
            total += 1
            status = str(iface.get("Status", "")).lower()
            if status not in ("up", "connected"):
                down += 1
    
    if total == 0:
        return "unknown"
    if down == 0:
        return "up"
    if down == total:
        return "down"
    return "degraded"


def _count_log_errors(text: str) -> int:
    data = _load_json(text)
    if isinstance(data, list):
        return len(data)
    return 0


def parse(outputs: Dict[str, str], errors: Dict[str, str], device: Dict[str, Any]) -> Dict[str, Any]:
    """Parse Hyper-V PowerShell JSON outputs into normalized metrics."""
    _ = device
    metrics: List[Dict[str, Any]] = []

    cpu = _parse_cpu_json(outputs.get("cpu", ""))
    if cpu is not None:
        metrics.append({"variable": "CPU_USAGE", "value": cpu})

    mem = _parse_memory_json(outputs.get("memory", ""))
    if mem is not None:
        metrics.append({"variable": "MEMORY_USAGE", "value": mem})

    disk = _parse_disk_json(outputs.get("disk", ""))
    if disk is not None:
        metrics.append({"variable": "DISK_USAGE", "value": disk})

    # VM counts from Get-VM
    vm_data = _parse_vms_json(outputs.get("vms", ""))
    metrics.append({"variable": "VM_COUNT", "value": float(vm_data["total"])})
    metrics.append({"variable": "VM_RUNNING", "value": float(vm_data["running"])})

    if_state = _parse_interfaces_json(outputs.get("interfaces", ""))
    metrics.append({"variable": "INTERFACE_STATUS", "value_text": if_state})

    log_err = _count_log_errors(outputs.get("logs", ""))
    metrics.append({"variable": "LOG_ERRORS", "value": float(log_err)})

    return {"metrics": metrics, "raw": {"errors": errors}}
