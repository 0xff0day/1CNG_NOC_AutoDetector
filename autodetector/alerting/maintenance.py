from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class SilenceDecision:
    suppressed: bool
    reason: str


def _parse_iso(ts: str) -> Optional[datetime]:
    try:
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:  # noqa: BLE001
        return None


def _tags_match(rule_tags: List[str], device_tags: List[str]) -> bool:
    if not rule_tags:
        return True
    s = set(t.lower() for t in (device_tags or []))
    return any(rt.lower() in s for rt in rule_tags)


def is_suppressed(cfg: Any, alert: Dict[str, Any], device_tags: List[str], now: datetime) -> SilenceDecision:
    raw_cfg = cfg.raw if hasattr(cfg, "raw") else cfg
    acfg = raw_cfg.get("alerting") or {}

    var = str(alert.get("variable", ""))
    sev = str(alert.get("severity", ""))

    for s in (acfg.get("silences") or []):
        rule_tags = [str(x) for x in (s.get("tags") or [])]
        if not _tags_match(rule_tags, device_tags):
            continue

        variables = [str(x) for x in (s.get("variables") or [])]
        if variables and var not in variables:
            continue

        severities = [str(x) for x in (s.get("severities") or [])]
        if severities and sev not in severities:
            continue

        start = _parse_iso(str(s.get("start_ts", "")))
        end = _parse_iso(str(s.get("end_ts", "")))
        if start and now < start:
            continue
        if end and now > end:
            continue

        return SilenceDecision(True, str(s.get("reason", "silenced")))

    for mw in (acfg.get("maintenance_windows") or []):
        rule_tags = [str(x) for x in (mw.get("tags") or [])]
        if not _tags_match(rule_tags, device_tags):
            continue

        start = _parse_iso(str(mw.get("start_ts", "")))
        end = _parse_iso(str(mw.get("end_ts", "")))
        if not start or not end:
            continue
        if start <= now <= end:
            return SilenceDecision(True, str(mw.get("reason", "maintenance")))

    return SilenceDecision(False, "")
