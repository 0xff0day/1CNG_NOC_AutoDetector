from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


def parse(outputs: Dict[str, str], errors: Dict[str, str], device: Dict[str, Any]) -> Dict[str, Any]:
    _ = device
    metrics: List[Dict[str, Any]] = []

    def _safe_float(x: str) -> Optional[float]:
        try:
            return float(x)
        except Exception:
            return None

    top_txt = outputs.get("cpu", "")
    m = re.search(r"CPU:\s*(\d+\.\d+)%\s+user,\s*(\d+\.\d+)%\s+nice,\s*(\d+\.\d+)%\s+system,\s*(\d+\.\d+)%\s+interrupt,\s*(\d+\.\d+)%\s+idle", top_txt)
    if m:
        idle = _safe_float(m.group(5))
        if idle is not None:
            metrics.append({"variable": "CPU_USAGE", "value": round(100.0 - idle, 2)})

    mem_txt = outputs.get("memory", "")
    phys = re.search(r"^(\d+)$", mem_txt, re.MULTILINE)
    if phys:
        total = _safe_float(phys.group(1))
        pc = re.search(r"vm\.stats\.vm\.v_page_count\s*\n(\d+)\s*\nvm\.stats\.vm\.v_free_count\s*\n(\d+)", mem_txt, re.IGNORECASE)
        if pc:
            pages = _safe_float(pc.group(1))
            free_pages = _safe_float(pc.group(2))
            if pages and pages > 0 and free_pages is not None:
                used_pct = (1.0 - (free_pages / pages)) * 100.0
                metrics.append({"variable": "MEMORY_USAGE", "value": round(used_pct, 2)})

    df_txt = outputs.get("disk", "")
    maxu = None
    for l in df_txt.splitlines()[1:]:
        parts = l.split()
        if len(parts) < 5:
            continue
        pct = parts[4]
        if pct.endswith("%"):
            v = _safe_float(pct[:-1])
            if v is not None:
                maxu = v if maxu is None else max(maxu, v)
    if maxu is not None:
        metrics.append({"variable": "DISK_USAGE", "value": float(maxu)})

    up_txt = outputs.get("load", "")
    mload = re.search(r"load averages?:\s*([0-9]+\.[0-9]+)", up_txt)
    if mload:
        v = _safe_float(mload.group(1))
        if v is not None:
            metrics.append({"variable": "LOAD", "value": v})

    if_txt = outputs.get("interfaces", "")
    total = 0
    down = 0
    for l in if_txt.splitlines():
        if re.match(r"^[a-z0-9]+:\s+flags=", l):
            name = l.split(":", 1)[0]
            if name == "lo0":
                continue
            total += 1
            if "UP" not in l:
                down += 1
    if total == 0:
        st = "unknown"
    elif down == 0:
        st = "up"
    elif down == total:
        st = "down"
    else:
        st = "degraded"
    metrics.append({"variable": "INTERFACE_STATUS", "value_text": st})

    ni_txt = outputs.get("interface_errors", "")
    err = 0
    for l in ni_txt.splitlines():
        if not l.strip() or l.lower().startswith("name"):
            continue
        nums = re.findall(r"\b(\d+)\b", l)
        for n in nums[-4:]:
            try:
                err += int(n)
            except Exception:
                pass
    metrics.append({"variable": "INTERFACE_ERRORS", "value": float(err)})

    rt_txt = outputs.get("routing", "")
    rt_state = "unknown" if not rt_txt.strip() else "up"
    if re.search(r"\bdefault\b", rt_txt, re.IGNORECASE) is None:
        rt_state = "degraded" if rt_txt.strip() else "unknown"
    metrics.append({"variable": "ROUTING_STATE", "value_text": rt_state})

    lg_txt = outputs.get("logs", "")
    lg_err = 0
    for l in lg_txt.splitlines():
        if re.search(r"\b(error|critical|panic|fail|denied)\b", l, re.IGNORECASE):
            lg_err += 1
    metrics.append({"variable": "LOG_ERRORS", "value": float(lg_err)})

    metrics.append({"variable": "UPTIME", "value_text": (outputs.get("uptime", "") or "").strip()})

    return {"metrics": metrics, "raw": {"errors": errors}}
