from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


def _safe_float(x: str) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None


def _parse_top_cpu(text: str) -> Optional[float]:
    m = re.search(r"%Cpu\(s\):\s*.*?(\d+\.\d+)\s*us,\s*(\d+\.\d+)\s*sy,.*?(\d+\.\d+)\s*id", text)
    if m:
        idle = _safe_float(m.group(3))
        if idle is not None:
            return round(100.0 - idle, 2)
    return None


def _parse_memory_free(text: str) -> Optional[float]:
    lines = [l for l in text.splitlines() if l.strip()]
    for l in lines:
        if l.lower().startswith("mem:"):
            parts = l.split()
            if len(parts) >= 3:
                total = _safe_float(parts[1])
                used = _safe_float(parts[2])
                if total and total > 0 and used is not None:
                    return round((used / total) * 100.0, 2)
    return None


def _parse_disk_df(text: str) -> Optional[float]:
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


def _parse_openstack_server_list(text: str) -> Dict[str, int]:
    total_vms = 0
    running_vms = 0
    
    for line in text.splitlines():
        if line.strip() and not line.startswith("ID"):
            parts = line.split("|")
            if len(parts) >= 4:
                total_vms += 1
                status = parts[2].strip().lower()
                if status in ("active", "running"):
                    running_vms += 1
    
    return {"total": total_vms, "running": running_vms}


def _parse_interface_state(text: str) -> str:
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
    _ = device
    metrics: List[Dict[str, Any]] = []

    cpu = _parse_top_cpu(outputs.get("cpu", ""))
    if cpu is not None:
        metrics.append({"variable": "CPU_USAGE", "value": cpu})

    mem = _parse_memory_free(outputs.get("memory", ""))
    if mem is not None:
        metrics.append({"variable": "MEMORY_USAGE", "value": mem})

    disk = _parse_disk_df(outputs.get("disk", ""))
    if disk is not None:
        metrics.append({"variable": "DISK_USAGE", "value": disk})

    vm_data = _parse_openstack_server_list(outputs.get("vms", ""))
    metrics.append({"variable": "VM_COUNT", "value": float(vm_data["total"])})
    metrics.append({"variable": "VM_RUNNING", "value": float(vm_data["running"])})

    if_state = _parse_interface_state(outputs.get("interfaces", ""))
    metrics.append({"variable": "INTERFACE_STATUS", "value_text": if_state})

    log_err = _count_log_errors(outputs.get("logs", ""))
    metrics.append({"variable": "LOG_ERRORS", "value": float(log_err)})

    return {"metrics": metrics, "raw": {"errors": errors}}
