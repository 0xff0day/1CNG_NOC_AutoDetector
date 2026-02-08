"""
Time-Series Data Store

SQLite-based time-series storage for device metrics.
Supports efficient querying, aggregation, and retention.
"""

from __future__ import annotations

import sqlite3
import json
import time
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import threading
import logging

logger = logging.getLogger(__name__)


@dataclass
class MetricRecord:
    """Single metric time-series record."""
    device_id: str
    variable: str
    value: float
    timestamp: float
    unit: str = ""
    metadata: Optional[Dict] = None


@dataclass
class TimeRange:
    """Time range for queries."""
    start: float
    end: float
    
    @classmethod
    def from_duration(cls, hours: int = 24) -> "TimeRange":
        """Create range from now back N hours."""
        end = time.time()
        start = end - (hours * 3600)
        return cls(start, end)


class TimeSeriesStore:
    """
    SQLite-based time-series storage for metrics.
    
    Features:
    - Automatic partitioning by time
    - Efficient downsampling
    - Data retention policies
    - Concurrent access support
    """
    
    def __init__(self, db_path: str = "metrics.db"):
        self.db_path = Path(db_path)
        self._lock = threading.RLock()
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT NOT NULL,
                    variable TEXT NOT NULL,
                    value REAL NOT NULL,
                    timestamp REAL NOT NULL,
                    unit TEXT,
                    metadata TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS idx_metrics_device_var 
                ON metrics(device_id, variable, timestamp);
                
                CREATE INDEX IF NOT EXISTS idx_metrics_timestamp 
                ON metrics(timestamp);
                
                CREATE TABLE IF NOT EXISTS metric_summary (
                    device_id TEXT,
                    variable TEXT,
                    date TEXT,
                    avg_value REAL,
                    min_value REAL,
                    max_value REAL,
                    count INTEGER,
                    PRIMARY KEY (device_id, variable, date)
                );
            """)
            conn.commit()
            logger.info(f"Initialized time-series database at {self.db_path}")
    
    def store(self, record: MetricRecord) -> bool:
        """Store a single metric record."""
        try:
            with self._lock, sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """INSERT INTO metrics 
                       (device_id, variable, value, timestamp, unit, metadata)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        record.device_id,
                        record.variable,
                        record.value,
                        record.timestamp,
                        record.unit,
                        json.dumps(record.metadata) if record.metadata else None
                    )
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to store metric: {e}")
            return False
    
    def store_batch(self, records: List[MetricRecord]) -> int:
        """Store multiple records efficiently."""
        if not records:
            return 0
        
        try:
            with self._lock, sqlite3.connect(self.db_path) as conn:
                data = [
                    (
                        r.device_id,
                        r.variable,
                        r.value,
                        r.timestamp,
                        r.unit,
                        json.dumps(r.metadata) if r.metadata else None
                    )
                    for r in records
                ]
                
                conn.executemany(
                    """INSERT INTO metrics 
                       (device_id, variable, value, timestamp, unit, metadata)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    data
                )
                conn.commit()
                return len(records)
        except Exception as e:
            logger.error(f"Failed to store batch: {e}")
            return 0
    
    def query(
        self,
        device_id: str,
        variable: str,
        time_range: Optional[TimeRange] = None,
        limit: int = 1000
    ) -> List[MetricRecord]:
        """
        Query metrics for device and variable.
        
        Args:
            device_id: Device identifier
            variable: Variable name
            time_range: Optional time range filter
            limit: Maximum records to return
        
        Returns:
            List of metric records
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                if time_range:
                    cursor = conn.execute(
                        """SELECT device_id, variable, value, timestamp, unit, metadata
                           FROM metrics 
                           WHERE device_id = ? AND variable = ? 
                           AND timestamp >= ? AND timestamp <= ?
                           ORDER BY timestamp DESC
                           LIMIT ?""",
                        (device_id, variable, time_range.start, time_range.end, limit)
                    )
                else:
                    cursor = conn.execute(
                        """SELECT device_id, variable, value, timestamp, unit, metadata
                           FROM metrics 
                           WHERE device_id = ? AND variable = ? 
                           ORDER BY timestamp DESC
                           LIMIT ?""",
                        (device_id, variable, limit)
                    )
                
                records = []
                for row in cursor.fetchall():
                    records.append(MetricRecord(
                        device_id=row[0],
                        variable=row[1],
                        value=row[2],
                        timestamp=row[3],
                        unit=row[4] or "",
                        metadata=json.loads(row[5]) if row[5] else None
                    ))
                
                return records
        except Exception as e:
            logger.error(f"Query failed: {e}")
            return []
    
    def get_latest(
        self,
        device_id: str,
        variable: str
    ) -> Optional[MetricRecord]:
        """Get most recent value for variable."""
        results = self.query(device_id, variable, limit=1)
        return results[0] if results else None
    
    def get_aggregates(
        self,
        device_id: str,
        variable: str,
        time_range: TimeRange
    ) -> Dict[str, float]:
        """
        Get aggregate statistics for time range.
        
        Returns:
            Dict with min, max, avg, count
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """SELECT 
                        MIN(value) as min_val,
                        MAX(value) as max_val,
                        AVG(value) as avg_val,
                        COUNT(*) as count
                       FROM metrics 
                       WHERE device_id = ? AND variable = ? 
                       AND timestamp >= ? AND timestamp <= ?""",
                    (device_id, variable, time_range.start, time_range.end)
                )
                
                row = cursor.fetchone()
                if row:
                    return {
                        "min": row[0] if row[0] is not None else 0,
                        "max": row[1] if row[1] is not None else 0,
                        "avg": row[2] if row[2] is not None else 0,
                        "count": row[3]
                    }
                return {"min": 0, "max": 0, "avg": 0, "count": 0}
        except Exception as e:
            logger.error(f"Aggregate query failed: {e}")
            return {"min": 0, "max": 0, "avg": 0, "count": 0}
    
    def get_timeseries(
        self,
        device_id: str,
        variables: List[str],
        time_range: TimeRange,
        interval: str = "raw"
    ) -> Dict[str, List[Tuple[float, float]]]:
        """
        Get time-series data for multiple variables.
        
        Args:
            device_id: Device identifier
            variables: List of variable names
            time_range: Time range
            interval: Aggregation interval (raw, 1m, 5m, 1h)
        
        Returns:
            Dict mapping variable to list of (timestamp, value) tuples
        """
        result = {}
        
        for var in variables:
            if interval == "raw":
                records = self.query(device_id, var, time_range)
                result[var] = [(r.timestamp, r.value) for r in records]
            else:
                # Downsample
                result[var] = self._downsample(device_id, var, time_range, interval)
        
        return result
    
    def _downsample(
        self,
        device_id: str,
        variable: str,
        time_range: TimeRange,
        interval: str
    ) -> List[Tuple[float, float]]:
        """Downsample data to specified interval."""
        interval_seconds = {
            "1m": 60, "5m": 300, "15m": 900, "1h": 3600
        }.get(interval, 300)
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    f"""SELECT 
                        (CAST(timestamp / {interval_seconds} AS INTEGER) * {interval_seconds}) as bucket,
                        AVG(value) as avg_val
                       FROM metrics 
                       WHERE device_id = ? AND variable = ? 
                       AND timestamp >= ? AND timestamp <= ?
                       GROUP BY bucket
                       ORDER BY bucket""",
                    (device_id, variable, time_range.start, time_range.end)
                )
                
                return [(row[0], row[1]) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Downsample failed: {e}")
            return []
    
    def cleanup_old_data(self, retention_days: int = 90) -> int:
        """Remove data older than retention period."""
        cutoff = time.time() - (retention_days * 24 * 3600)
        
        try:
            with self._lock, sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "DELETE FROM metrics WHERE timestamp < ?",
                    (cutoff,)
                )
                conn.commit()
                deleted = cursor.rowcount
                logger.info(f"Cleaned up {deleted} old records")
                return deleted
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            return 0
    
    def vacuum(self) -> None:
        """Optimize database file."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("VACUUM")
                conn.commit()
                logger.info("Database vacuumed")
        except Exception as e:
            logger.error(f"Vacuum failed: {e}")
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get database storage statistics."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Count records
                cursor = conn.execute("SELECT COUNT(*) FROM metrics")
                total_records = cursor.fetchone()[0]
                
                # Count by device
                cursor = conn.execute(
                    "SELECT device_id, COUNT(*) FROM metrics GROUP BY device_id"
                )
                device_counts = {row[0]: row[1] for row in cursor.fetchall()}
                
                # Get time range
                cursor = conn.execute(
                    "SELECT MIN(timestamp), MAX(timestamp) FROM metrics"
                )
                row = cursor.fetchone()
                time_range = (row[0], row[1]) if row else (None, None)
                
                # Database file size
                db_size = self.db_path.stat().st_size
                
                return {
                    "total_records": total_records,
                    "device_count": len(device_counts),
                    "records_per_device": device_counts,
                    "time_range": time_range,
                    "db_size_bytes": db_size,
                    "db_size_mb": round(db_size / (1024 * 1024), 2)
                }
        except Exception as e:
            logger.error(f"Stats query failed: {e}")
            return {}


class MetricCache:
    """In-memory cache for recent metrics."""
    
    def __init__(self, max_size: int = 10000):
        self.max_size = max_size
        self._cache: Dict[str, MetricRecord] = {}
        self._lock = threading.RLock()
    
    def put(self, record: MetricRecord) -> None:
        """Add record to cache."""
        key = f"{record.device_id}:{record.variable}"
        
        with self._lock:
            self._cache[key] = record
            
            # Trim if too large
            if len(self._cache) > self.max_size:
                # Remove oldest 20%
                sorted_items = sorted(
                    self._cache.items(),
                    key=lambda x: x[1].timestamp
                )
                to_remove = len(sorted_items) // 5
                for key, _ in sorted_items[:to_remove]:
                    del self._cache[key]
    
    def get(self, device_id: str, variable: str) -> Optional[MetricRecord]:
        """Get cached record."""
        key = f"{device_id}:{variable}"
        with self._lock:
            return self._cache.get(key)
    
    def get_latest_for_device(self, device_id: str) -> Dict[str, MetricRecord]:
        """Get all cached variables for device."""
        with self._lock:
            return {
                k.split(":")[1]: v
                for k, v in self._cache.items()
                if k.startswith(f"{device_id}:")
            }
