from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class Route:
    contact_group: str
    channels: List[str]


def _tags_match(rule_tags: List[str], device_tags: List[str]) -> bool:
    if not rule_tags:
        return True
    s = set(t.lower() for t in (device_tags or []))
    return any(rt.lower() in s for rt in rule_tags)


def route_alert(cfg: Any, alert: Dict[str, Any], device_tags: List[str]) -> Route:
    raw_cfg = cfg.raw if hasattr(cfg, "raw") else cfg
    acfg = raw_cfg.get("alerting") or {}

    for r in (acfg.get("routes") or []):
        if not _tags_match([str(x) for x in (r.get("tags") or [])], device_tags):
            continue

        variables = [str(x) for x in (r.get("variables") or [])]
        if variables and str(alert.get("variable", "")) not in variables:
            continue

        severities = [str(x) for x in (r.get("severities") or [])]
        if severities and str(alert.get("severity", "")) not in severities:
            continue

        return Route(contact_group=str(r.get("contact_group", "default")), channels=[str(x) for x in (r.get("channels") or ["telegram"])])

    return Route(contact_group="default", channels=["telegram"])


def contact_group(cfg: Any, name: str) -> Dict[str, Any]:
    raw_cfg = cfg.raw if hasattr(cfg, "raw") else cfg
    groups = ((raw_cfg.get("alerting") or {}).get("contact_groups") or {})
    return groups.get(name) or {}
