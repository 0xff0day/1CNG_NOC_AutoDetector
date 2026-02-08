from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from autodetector.pipeline.orchestrator import run_poll_once
from autodetector.reporting.generator import generate_reports
from autodetector.storage.retention import run_retention
from autodetector.storage.sqlite_store import SqliteStore


def run_scheduler(cfg: Any, store: SqliteStore) -> None:
    polling = cfg.raw.get("polling") or {}
    fast_sec = int(polling.get("fast_sec", 10))
    normal_sec = int(polling.get("normal_sec", 60))
    deep_sec = int(polling.get("deep_audit_sec", 3600))

    rep = cfg.raw.get("reporting") or {}
    sched = rep.get("schedules") or {}

    last_fast = 0.0
    last_normal = 0.0
    last_deep = 0.0
    last_hourly_report = ""
    last_daily_report = ""
    last_hourly_retention = ""

    while True:
        now = datetime.now(timezone.utc)
        t = time.time()

        if t - last_fast >= fast_sec:
            run_poll_once(cfg, store, now=now, deep=False)
            last_fast = t

        if t - last_normal >= normal_sec:
            run_poll_once(cfg, store, now=now, deep=False)
            last_normal = t

        if t - last_deep >= deep_sec:
            run_poll_once(cfg, store, now=now, deep=True)
            last_deep = t

        if bool(sched.get("hourly", True)):
            key = now.strftime("%Y-%m-%dT%H")
            if key != last_hourly_report:
                generate_reports(cfg, store, now=now, range_name="hour")
                last_hourly_report = key

        key = now.strftime("%Y-%m-%dT%H")
        if key != last_hourly_retention:
            run_retention(cfg, store, now=now)
            last_hourly_retention = key

        if bool(sched.get("daily", True)):
            key = now.strftime("%Y-%m-%d")
            if key != last_daily_report:
                generate_reports(cfg, store, now=now, range_name="day")
                last_daily_report = key

        time.sleep(1)
