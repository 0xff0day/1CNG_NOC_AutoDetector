from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


def _safe_float(x: str) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None


def _parse_perf(text: str) -> Dict[str, Optional[float]]:
    cpu = None
    mem = None
    m = re.search(r"CPU\s+states:\s*(\d+)%\s+user\s+(\d+)%\s+system", text, re.IGNORECASE)
    if m:
        u = _safe_float(m.group(1))
        s = _safe_float(m.group(2))
        if u is not None and s is not None:
            cpu = round(u + s, 2)
    m2 = re.search(r"Memory\s+states:\s*(\d+)%\s+used", text, re.IGNORECASE)
    if m2:
        mem = _safe_float(m2.group(1))
    m3 = re.search(r"CPU\s+usage\s*:\s*(\d+)%", text, re.IGNORECASE)
    if cpu is None and m3:
        cpu = _safe_float(m3.group(1))
    m4 = re.search(r"Memory\s+usage\s*:\s*(\d+)%", text, re.IGNORECASE)
    if mem is None and m4:
        mem = _safe_float(m4.group(1))
    return {"cpu": cpu, "mem": mem}


def _parse_if_status(text: str) -> str:
    if not text.strip():
        return "unknown"
    down = 0
    up = 0
    for l in text.splitlines():
        if re.search(r"\bstatus\b.*\bdown\b", l, re.IGNORECASE):
            down += 1
        if re.search(r"\bstatus\b.*\bup\b", l, re.IGNORECASE):
            up += 1
    if up == 0 and down == 0:
        return "unknown"
    if down == 0:
        return "up"
    if up == 0:
        return "down"
    return "degraded"


def _parse_if_errors(text: str) -> int:
    total = 0
    for l in text.splitlines():
        if re.search(r"\berr\b|\berrors\b|\bcrc\b", l, re.IGNORECASE):
            for n in re.findall(r"\b(\d+)\b", l):
                try:
                    total += int(n)
                except Exception:
                    pass
    return total


def _parse_routing(text: str) -> str:
    if not text.strip():
        return "unknown"
    m = re.search(r"\bTotal\s+routes\s*:\s*(\d+)", text, re.IGNORECASE)
    if m:
        try:
            return "up" if int(m.group(1)) > 0 else "degraded"
        except Exception:
            return "degraded"
    return "up"


def _count_log_errors(text: str) -> int:
    if not text.strip():
        return 0
    bad = 0
    for l in text.splitlines():
        if re.search(r"\b(error|critical|fail|down|denied)\b", l, re.IGNORECASE):
            bad += 1
    return bad


def parse(outputs: Dict[str, str], errors: Dict[str, str], device: Dict[str, Any]) -> Dict[str, Any]:
    _ = device
    metrics: List[Dict[str, Any]] = []

    perf = _parse_perf(outputs.get("cpu", "") + "\n" + outputs.get("memory", ""))
    if perf.get("cpu") is not None:
        metrics.append({"variable": "CPU_USAGE", "value": float(perf["cpu"])})
    if perf.get("mem") is not None:
        metrics.append({"variable": "MEMORY_USAGE", "value": float(perf["mem"])})

    metrics.append({"variable": "INTERFACE_STATUS", "value_text": _parse_if_status(outputs.get("interfaces", ""))})
    metrics.append({"variable": "INTERFACE_ERRORS", "value": float(_parse_if_errors(outputs.get("interface_errors", "")) )})
    metrics.append({"variable": "ROUTING_STATE", "value_text": _parse_routing(outputs.get("routing", ""))})
    metrics.append({"variable": "LOG_ERRORS", "value": float(_count_log_errors(outputs.get("logs", "")) )})
    metrics.append({"variable": "UPTIME", "value_text": (outputs.get("uptime", "") or "").strip()})

    return {"metrics": metrics, "raw": {"errors": errors}}
