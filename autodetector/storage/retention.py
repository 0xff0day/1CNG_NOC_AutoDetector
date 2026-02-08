from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from autodetector.storage.sqlite_store import SqliteStore


@dataclass(frozen=True)
class RetentionPolicy:
    metrics_days: int = 30
    alerts_days: int = 180
    rollup_keep_days: int = 365


def _policy(cfg: Any) -> RetentionPolicy:
    raw_cfg = cfg.raw if hasattr(cfg, "raw") else cfg
    r = (raw_cfg.get("retention") or {})
    return RetentionPolicy(
        metrics_days=int(r.get("metrics_days", 30)),
        alerts_days=int(r.get("alerts_days", 180)),
        rollup_keep_days=int(r.get("rollup_keep_days", 365)),
    )


def run_retention(cfg: Any, store: SqliteStore, now: datetime) -> None:
    pol = _policy(cfg)
    store.rollup_metrics(now=now, period="hour")
    store.rollup_metrics(now=now, period="day")

    store.prune_metrics(before_ts=(now - timedelta(days=pol.metrics_days)).replace(tzinfo=timezone.utc).isoformat())
    store.prune_alerts(before_ts=(now - timedelta(days=pol.alerts_days)).replace(tzinfo=timezone.utc).isoformat())
    store.prune_rollups(before_ts=(now - timedelta(days=pol.rollup_keep_days)).replace(tzinfo=timezone.utc).isoformat())
