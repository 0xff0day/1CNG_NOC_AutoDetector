from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class DashboardDataExporter:
    """Export dashboard data in various formats for external systems."""
    
    def __init__(self, storage=None):
        self.storage = storage
    
    def export_metrics_summary(
        self,
        device_ids: Optional[List[str]] = None,
        time_range: str = "last24h"
    ) -> Dict[str, Any]:
        """Export metrics summary for dashboard."""
        return {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "time_range": time_range,
            "devices": device_ids or [],
            "summary": {
                "total_devices": 0,
                "online_devices": 0,
                "offline_devices": 0,
                "critical_alerts": 0,
                "warning_alerts": 0,
            },
            "metrics": {},
        }
    
    def export_alert_dashboard(
        self,
        status: str = "active",
        group_by: str = "severity"
    ) -> Dict[str, Any]:
        """Export alert data for dashboard."""
        return {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "group_by": group_by,
            "alert_groups": {
                "critical": [],
                "warning": [],
                "info": [],
            },
            "timeline": [],
        }
    
    def export_topology_view(
        self,
        root_device: Optional[str] = None,
        max_depth: int = 3
    ) -> Dict[str, Any]:
        """Export network topology for visualization."""
        return {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "root_device": root_device,
            "max_depth": max_depth,
            "nodes": [],
            "edges": [],
            "layers": {
                "core": [],
                "distribution": [],
                "access": [],
            },
        }
    
    def export_gauge_data(
        self,
        metric_names: List[str],
        device_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Export gauge metrics for real-time dashboard."""
        gauges = []
        
        for metric in metric_names:
            gauges.append({
                "metric_name": metric,
                "value": 0.0,
                "unit": "percent",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "devices": device_ids or [],
            })
        
        return gauges
    
    def export_to_grafana_json(
        self,
        dashboard_title: str = "NOC Dashboard"
    ) -> str:
        """Export dashboard configuration for Grafana."""
        grafana_dashboard = {
            "dashboard": {
                "id": None,
                "title": dashboard_title,
                "tags": ["noc", "network", "monitoring"],
                "timezone": "UTC",
                "panels": [
                    {
                        "id": 1,
                        "title": "Device Status",
                        "type": "stat",
                        "targets": [
                            {
                                "expr": "noc_devices_total",
                                "legendFormat": "Total Devices",
                            }
                        ],
                    },
                    {
                        "id": 2,
                        "title": "Alert Summary",
                        "type": "graph",
                        "targets": [
                            {
                                "expr": "noc_alerts_total",
                                "legendFormat": "{{severity}}",
                            }
                        ],
                    },
                    {
                        "id": 3,
                        "title": "CPU Usage",
                        "type": "timeseries",
                        "targets": [
                            {
                                "expr": "noc_cpu_usage_percent",
                                "legendFormat": "{{device_id}}",
                            }
                        ],
                    },
                ],
            },
            "overwrite": False,
        }
        
        return json.dumps(grafana_dashboard, indent=2)
    
    def export_to_datadog_format(
        self,
        metrics: List[str]
    ) -> List[Dict[str, Any]]:
        """Export metrics in Datadog format."""
        dd_metrics = []
        
        for metric in metrics:
            dd_metrics.append({
                "metric": f"noc.{metric}",
                "points": [],
                "type": "gauge",
                "host": "",
                "tags": [],
            })
        
        return dd_metrics


class RealtimeDashboardFeed:
    """Feed real-time data to dashboards via WebSocket/SSE."""
    
    def __init__(self):
        self.subscribers: List[Any] = []
        self.last_update = datetime.now(timezone.utc)
    
    def subscribe(self, callback: callable):
        """Subscribe to real-time updates."""
        self.subscribers.append(callback)
    
    def unsubscribe(self, callback: callable):
        """Unsubscribe from updates."""
        if callback in self.subscribers:
            self.subscribers.remove(callback)
    
    def broadcast(self, data: Dict[str, Any]):
        """Broadcast update to all subscribers."""
        self.last_update = datetime.now(timezone.utc)
        
        for callback in self.subscribers:
            try:
                callback(data)
            except Exception:
                pass
    
    def get_feed_data(self) -> Dict[str, Any]:
        """Get current feed data for dashboard."""
        return {
            "timestamp": self.last_update.isoformat(),
            "status": "active",
            "subscriber_count": len(self.subscribers),
        }


class WidgetDataProvider:
    """Provide data for specific dashboard widgets."""
    
    def get_status_widget(self) -> Dict[str, Any]:
        """Data for status overview widget."""
        return {
            "widget": "status_overview",
            "data": {
                "total_devices": 0,
                "online": 0,
                "offline": 0,
                "degraded": 0,
                "unknown": 0,
            },
        }
    
    def get_alert_widget(self) -> Dict[str, Any]:
        """Data for alert summary widget."""
        return {
            "widget": "alert_summary",
            "data": {
                "critical": 0,
                "warning": 0,
                "info": 0,
                "acknowledged": 0,
                "unacknowledged": 0,
            },
        }
    
    def get_performance_widget(
        self,
        metric: str = "CPU_USAGE",
        top_n: int = 10
    ) -> Dict[str, Any]:
        """Data for performance widget."""
        return {
            "widget": "performance",
            "metric": metric,
            "data": {
                "top_n": top_n,
                "devices": [],
            },
        }
    
    def get_topology_widget(
        self,
        focus_device: Optional[str] = None
    ) -> Dict[str, Any]:
        """Data for topology visualization widget."""
        return {
            "widget": "topology",
            "focus": focus_device,
            "data": {
                "nodes": [],
                "edges": [],
            },
        }
    
    def get_geomap_widget(self) -> Dict[str, Any]:
        """Data for geographic map widget."""
        return {
            "widget": "geomap",
            "data": {
                "locations": [],
            },
        }
