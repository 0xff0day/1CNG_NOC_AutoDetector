from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from autodetector.storage.sqlite_store import SqliteStore


def build_dedupe_key(alert: Dict[str, Any], fields: List[str]) -> str:
    parts = []
    for f in fields:
        parts.append(str(alert.get(f, "")))
    return "|".join(parts)


def should_emit_alert(store: SqliteStore, alert: Dict[str, Any], cooldown_sec: int) -> bool:
    key = alert["dedupe_key"]
    existing = None
    for a in store.list_alerts(limit=200):
        if a.get("dedupe_key") == key:
            existing = a
            break

    if not existing:
        return True

    try:
        last = datetime.fromisoformat(existing["last_seen_ts"])
    except Exception:  # noqa: BLE001
        return True

    now = datetime.now(timezone.utc)
    delta = (now - last).total_seconds()
    if delta >= cooldown_sec:
        return True

    return False
