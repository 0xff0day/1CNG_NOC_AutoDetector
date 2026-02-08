"""
Alert History Logger

Logs all alert activity for auditing and analysis.
Persistent storage of alert lifecycle.
"""

from __future__ import annotations

import json
import time
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sqlite3
import logging

logger = logging.getLogger(__name__)


@dataclass
class HistoryEntry:
    """Single history entry."""
    entry_id: str
    alert_id: str
    event_type: str  # created, acknowledged, resolved, escalated, notified
    timestamp: float
    device_id: str
    severity: str
    message: str
    user: Optional[str] = None
    details: Optional[Dict] = None


class AlertHistoryLogger:
    """
    Persistent logging of alert history.
    
    Stores:
    - Alert creation
    - Acknowledgments
    - Resolutions
    - Escalations
    - Notifications sent
    """
    
    def __init__(self, db_path: str = "alert_history.db"):
        self.db_path = Path(db_path)
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize SQLite database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS alert_history (
                    entry_id TEXT PRIMARY KEY,
                    alert_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    device_id TEXT NOT NULL,
                    severity TEXT,
                    message TEXT,
                    user TEXT,
                    details TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_alert_id 
                ON alert_history(alert_id)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp 
                ON alert_history(timestamp)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_device 
                ON alert_history(device_id, timestamp)
            """)
            
            conn.commit()
    
    def log_event(
        self,
        alert_id: str,
        event_type: str,
        device_id: str,
        severity: str = "",
        message: str = "",
        user: Optional[str] = None,
        details: Optional[Dict] = None
    ) -> str:
        """
        Log a history event.
        
        Returns:
            Entry ID
        """
        entry_id = f"{int(time.time()*1000)}-{alert_id[:8]}"
        timestamp = time.time()
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """INSERT INTO alert_history 
                       (entry_id, alert_id, event_type, timestamp, device_id, 
                        severity, message, user, details)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        entry_id,
                        alert_id,
                        event_type,
                        timestamp,
                        device_id,
                        severity,
                        message,
                        user,
                        json.dumps(details) if details else None
                    )
                )
                conn.commit()
            
            return entry_id
            
        except Exception as e:
            logger.error(f"Failed to log history: {e}")
            return ""
    
    def get_alert_history(
        self,
        alert_id: str
    ) -> List[HistoryEntry]:
        """Get complete history for an alert."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """SELECT entry_id, alert_id, event_type, timestamp, 
                              device_id, severity, message, user, details
                       FROM alert_history 
                       WHERE alert_id = ?
                       ORDER BY timestamp""",
                    (alert_id,)
                )
                
                entries = []
                for row in cursor.fetchall():
                    entries.append(HistoryEntry(
                        entry_id=row[0],
                        alert_id=row[1],
                        event_type=row[2],
                        timestamp=row[3],
                        device_id=row[4],
                        severity=row[5] or "",
                        message=row[6] or "",
                        user=row[7],
                        details=json.loads(row[8]) if row[8] else None
                    ))
                
                return entries
                
        except Exception as e:
            logger.error(f"Failed to get history: {e}")
            return []
    
    def get_device_history(
        self,
        device_id: str,
        hours: int = 24
    ) -> List[HistoryEntry]:
        """Get alert history for a device."""
        since = time.time() - (hours * 3600)
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """SELECT entry_id, alert_id, event_type, timestamp, 
                              device_id, severity, message, user, details
                       FROM alert_history 
                       WHERE device_id = ? AND timestamp >= ?
                       ORDER BY timestamp DESC""",
                    (device_id, since)
                )
                
                entries = []
                for row in cursor.fetchall():
                    entries.append(HistoryEntry(
                        entry_id=row[0],
                        alert_id=row[1],
                        event_type=row[2],
                        timestamp=row[3],
                        device_id=row[4],
                        severity=row[5] or "",
                        message=row[6] or "",
                        user=row[7],
                        details=json.loads(row[8]) if row[8] else None
                    ))
                
                return entries
                
        except Exception as e:
            logger.error(f"Failed to get device history: {e}")
            return []
    
    def query_history(
        self,
        event_type: Optional[str] = None,
        device_id: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 1000
    ) -> List[HistoryEntry]:
        """Query history with filters."""
        query = "SELECT * FROM alert_history WHERE 1=1"
        params = []
        
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        
        if device_id:
            query += " AND device_id = ?"
            params.append(device_id)
        
        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time)
        
        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(query, params)
                
                entries = []
                for row in cursor.fetchall():
                    entries.append(HistoryEntry(
                        entry_id=row[0],
                        alert_id=row[1],
                        event_type=row[2],
                        timestamp=row[3],
                        device_id=row[4],
                        severity=row[5] or "",
                        message=row[6] or "",
                        user=row[7],
                        details=json.loads(row[8]) if row[8] else None
                    ))
                
                return entries
                
        except Exception as e:
            logger.error(f"Failed to query history: {e}")
            return []
    
    def get_alert_statistics(
        self,
        hours: int = 24
    ) -> Dict[str, Any]:
        """Get alert statistics for time period."""
        since = time.time() - (hours * 3600)
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Total events
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM alert_history WHERE timestamp >= ?",
                    (since,)
                )
                total = cursor.fetchone()[0]
                
                # By event type
                cursor = conn.execute(
                    """SELECT event_type, COUNT(*) 
                       FROM alert_history 
                       WHERE timestamp >= ?
                       GROUP BY event_type""",
                    (since,)
                )
                by_type = {row[0]: row[1] for row in cursor.fetchall()}
                
                # By severity
                cursor = conn.execute(
                    """SELECT severity, COUNT(*) 
                       FROM alert_history 
                       WHERE timestamp >= ? AND severity != ''
                       GROUP BY severity""",
                    (since,)
                )
                by_severity = {row[0]: row[1] for row in cursor.fetchall()}
                
                # Unique alerts
                cursor = conn.execute(
                    """SELECT COUNT(DISTINCT alert_id) 
                       FROM alert_history 
                       WHERE timestamp >= ?""",
                    (since,)
                )
                unique_alerts = cursor.fetchone()[0]
                
                return {
                    "total_events": total,
                    "unique_alerts": unique_alerts,
                    "by_event_type": by_type,
                    "by_severity": by_severity,
                    "period_hours": hours
                }
                
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {}
    
    def export_to_json(
        self,
        filepath: str,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> int:
        """Export history to JSON file."""
        entries = self.query_history(
            start_time=start_time,
            end_time=end_time,
            limit=100000
        )
        
        data = [
            {
                "entry_id": e.entry_id,
                "alert_id": e.alert_id,
                "event_type": e.event_type,
                "timestamp": e.timestamp,
                "device_id": e.device_id,
                "severity": e.severity,
                "message": e.message,
                "user": e.user,
                "details": e.details
            }
            for e in entries
        ]
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        return len(entries)
    
    def cleanup_old(self, days: int = 90) -> int:
        """Remove history older than specified days."""
        cutoff = time.time() - (days * 24 * 3600)
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "DELETE FROM alert_history WHERE timestamp < ?",
                    (cutoff,)
                )
                conn.commit()
                deleted = cursor.rowcount
                logger.info(f"Cleaned up {deleted} old history entries")
                return deleted
        except Exception as e:
            logger.error(f"Failed to cleanup: {e}")
            return 0
