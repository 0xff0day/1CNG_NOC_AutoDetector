import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from threading import RLock


class SqliteStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._write_lock = RLock()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA foreign_keys=ON;")
            conn.execute("PRAGMA busy_timeout=30000;")
        except Exception:  # noqa: BLE001
            pass
        return conn

    def migrate(self) -> None:
        with self._write_lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS metrics (
                        id TEXT PRIMARY KEY,
                        ts TEXT NOT NULL,
                        device_id TEXT NOT NULL,
                        variable TEXT NOT NULL,
                        value REAL,
                        value_text TEXT,
                        labels_json TEXT
                    );
                    """
                )
                conn.execute("CREATE INDEX IF NOT EXISTS idx_metrics_dev_var_ts ON metrics(device_id, variable, ts);")

                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS metric_rollups (
                        id TEXT PRIMARY KEY,
                        period TEXT NOT NULL,
                        bucket_ts TEXT NOT NULL,
                        device_id TEXT NOT NULL,
                        variable TEXT NOT NULL,
                        count INTEGER NOT NULL,
                        min REAL,
                        max REAL,
                        avg REAL
                    );
                    """
                )
                conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_rollups_unique ON metric_rollups(period, bucket_ts, device_id, variable);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_rollups_dev_var_ts ON metric_rollups(device_id, variable, bucket_ts);")

                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS alerts (
                        id TEXT PRIMARY KEY,
                        ts TEXT NOT NULL,
                        severity TEXT NOT NULL,
                        device_id TEXT NOT NULL,
                        variable TEXT NOT NULL,
                        alert_type TEXT NOT NULL,
                        message TEXT NOT NULL,
                        dedupe_key TEXT NOT NULL,
                        first_seen_ts TEXT NOT NULL,
                        last_seen_ts TEXT NOT NULL,
                        count INTEGER NOT NULL,
                        ack_ts TEXT,
                        ack_note TEXT
                    );
                    """
                )
                conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts_dedupe ON alerts(dedupe_key);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts_ts ON alerts(ts);")

                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS alert_events (
                        id TEXT PRIMARY KEY,
                        ts TEXT NOT NULL,
                        alert_id TEXT NOT NULL,
                        action TEXT NOT NULL,
                        actor TEXT,
                        note TEXT
                    );
                    """
                )
                conn.execute("CREATE INDEX IF NOT EXISTS idx_alert_events_alert_ts ON alert_events(alert_id, ts);")

                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS device_state (
                        device_id TEXT PRIMARY KEY,
                        last_seen_ts TEXT,
                        last_health_score REAL,
                        last_snapshot_json TEXT
                    );
                    """
                )

    def insert_metrics(self, rows: List[Dict[str, Any]]) -> None:
        if not rows:
            return
        with self._write_lock:
            with self._connect() as conn:
                conn.executemany(
                    """
                    INSERT INTO metrics(id, ts, device_id, variable, value, value_text, labels_json)
                    VALUES(?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            r.get("id") or str(uuid.uuid4()),
                            r["ts"],
                            r["device_id"],
                            r["variable"],
                            r.get("value"),
                            r.get("value_text"),
                            json.dumps(r.get("labels") or {}, sort_keys=True),
                        )
                        for r in rows
                    ],
                )

    def get_recent_series(self, device_id: str, variable: str, limit: int) -> List[Tuple[str, Optional[float], Optional[str]]]:
        with self._connect() as conn:
            cur = conn.execute(
                """
                SELECT ts, value, value_text
                FROM metrics
                WHERE device_id = ? AND variable = ?
                ORDER BY ts DESC
                LIMIT ?
                """,
                (device_id, variable, limit),
            )
            return [(r["ts"], r["value"], r["value_text"]) for r in cur.fetchall()]

    def rollup_metrics(self, now: datetime, period: str) -> None:
        if period not in {"hour", "day"}:
            raise ValueError("period must be hour or day")

        if period == "hour":
            bucket = now.replace(minute=0, second=0, microsecond=0).isoformat()
            start = now.replace(minute=0, second=0, microsecond=0)
            end = start.replace(minute=59, second=59, microsecond=999999)
        else:
            bucket = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start.replace(hour=23, minute=59, second=59, microsecond=999999)

        start_ts = start.isoformat()
        end_ts = end.isoformat()

        with self._write_lock:
            with self._connect() as conn:
                cur = conn.execute(
                    """
                    SELECT device_id, variable,
                           COUNT(*) as c,
                           MIN(value) as mn,
                           MAX(value) as mx,
                           AVG(value) as av
                    FROM metrics
                    WHERE ts >= ? AND ts <= ? AND value IS NOT NULL
                    GROUP BY device_id, variable
                    """,
                    (start_ts, end_ts),
                )
                rows = cur.fetchall()
                for r in rows:
                    rid = str(uuid.uuid4())
                    conn.execute(
                        """
                        INSERT INTO metric_rollups(id, period, bucket_ts, device_id, variable, count, min, max, avg)
                        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(period, bucket_ts, device_id, variable) DO UPDATE SET
                            count=excluded.count,
                            min=excluded.min,
                            max=excluded.max,
                            avg=excluded.avg
                        """,
                        (rid, period, bucket, r["device_id"], r["variable"], int(r["c"]), r["mn"], r["mx"], r["av"]),
                    )

    def prune_metrics(self, before_ts: str) -> None:
        with self._write_lock:
            with self._connect() as conn:
                conn.execute("DELETE FROM metrics WHERE ts < ?", (before_ts,))

    def prune_alerts(self, before_ts: str) -> None:
        with self._write_lock:
            with self._connect() as conn:
                conn.execute("DELETE FROM alerts WHERE ts < ?", (before_ts,))
                conn.execute("DELETE FROM alert_events WHERE ts < ?", (before_ts,))

    def prune_rollups(self, before_ts: str) -> None:
        with self._write_lock:
            with self._connect() as conn:
                conn.execute("DELETE FROM metric_rollups WHERE bucket_ts < ?", (before_ts,))

    def list_rollups(self, period: str, since_ts: str, limit: int = 10000) -> List[Dict[str, Any]]:
        if period not in {"hour", "day"}:
            raise ValueError("period must be hour or day")
        with self._connect() as conn:
            cur = conn.execute(
                """
                SELECT period, bucket_ts, device_id, variable, count, min, max, avg
                FROM metric_rollups
                WHERE period = ? AND bucket_ts >= ?
                ORDER BY bucket_ts DESC
                LIMIT ?
                """,
                (period, since_ts, int(limit)),
            )
            return [dict(r) for r in cur.fetchall()]

    @staticmethod
    def _insert_alert_event_with_conn(conn: sqlite3.Connection, alert_id: str, action: str, actor: str = "", note: str = "") -> None:
        if not alert_id:
            return
        ts = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO alert_events(id, ts, alert_id, action, actor, note) VALUES(?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), ts, alert_id, action, actor, note),
        )

    def upsert_alert(self, alert: Dict[str, Any]) -> Dict[str, Any]:
        with self._write_lock:
            with self._connect() as conn:
                existing = conn.execute("SELECT * FROM alerts WHERE dedupe_key = ?", (alert["dedupe_key"],)).fetchone()
                if existing is None:
                    alert_id = alert.get("id") or str(uuid.uuid4())
                    conn.execute(
                        """
                        INSERT INTO alerts(
                            id, ts, severity, device_id, variable, alert_type, message,
                            dedupe_key, first_seen_ts, last_seen_ts, count, ack_ts, ack_note
                        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)
                        """,
                        (
                            alert_id,
                            alert["ts"],
                            alert["severity"],
                            alert["device_id"],
                            alert["variable"],
                            alert["alert_type"],
                            alert["message"],
                            alert["dedupe_key"],
                            alert["ts"],
                            alert["ts"],
                            1,
                        ),
                    )
                    alert["id"] = alert_id
                    alert["count"] = 1
                    alert["ack_ts"] = None
                    self._insert_alert_event_with_conn(conn, alert_id=alert_id, action="created", actor="system", note=alert.get("message", ""))
                    return alert

                count = int(existing["count"]) + 1
                conn.execute(
                    """
                    UPDATE alerts
                    SET ts = ?, severity = ?, message = ?, last_seen_ts = ?, count = ?
                    WHERE id = ?
                    """,
                    (alert["ts"], alert["severity"], alert["message"], alert["ts"], count, existing["id"]),
                )
                out = dict(existing)
                out.update({"ts": alert["ts"], "severity": alert["severity"], "message": alert["message"], "count": count})
                self._insert_alert_event_with_conn(conn, alert_id=str(existing["id"]), action="updated", actor="system", note=alert.get("message", ""))
                return out

    def list_alerts(self, limit: int) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            cur = conn.execute("SELECT * FROM alerts ORDER BY ts DESC LIMIT ?", (limit,))
            return [dict(r) for r in cur.fetchall()]

    def list_alerts_since(self, since_ts: str, limit: int = 5000) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT * FROM alerts WHERE ts >= ? ORDER BY ts DESC LIMIT ?",
                (since_ts, int(limit)),
            )
            return [dict(r) for r in cur.fetchall()]

    def ack_alert(self, alert_id: str, note: str = "", actor: str = "") -> None:
        ts = datetime.now(timezone.utc).isoformat()
        with self._write_lock:
            with self._connect() as conn:
                conn.execute("UPDATE alerts SET ack_ts = ?, ack_note = ? WHERE id = ?", (ts, note, alert_id))
        self.insert_alert_event(alert_id=alert_id, action="acked", actor=actor or "operator", note=note)

    def insert_alert_event(self, alert_id: str, action: str, actor: str = "", note: str = "") -> None:
        if not alert_id:
            return
        ts = datetime.now(timezone.utc).isoformat()
        with self._write_lock:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO alert_events(id, ts, alert_id, action, actor, note) VALUES(?, ?, ?, ?, ?, ?)",
                    (str(uuid.uuid4()), ts, alert_id, action, actor, note),
                )

    def set_device_state(self, device_id: str, last_seen_ts: str, health_score: float, snapshot: Dict[str, Any]) -> None:
        with self._write_lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO device_state(device_id, last_seen_ts, last_health_score, last_snapshot_json)
                    VALUES(?, ?, ?, ?)
                    ON CONFLICT(device_id) DO UPDATE SET
                        last_seen_ts=excluded.last_seen_ts,
                        last_health_score=excluded.last_health_score,
                        last_snapshot_json=excluded.last_snapshot_json
                    """,
                    (device_id, last_seen_ts, health_score, json.dumps(snapshot, sort_keys=True, default=str)),
                )

    def get_device_state(self, device_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM device_state WHERE device_id = ?", (device_id,)).fetchone()
            return dict(row) if row else None
