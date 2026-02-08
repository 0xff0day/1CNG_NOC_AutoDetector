from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class PrometheusExporter:
    """Export metrics in Prometheus exposition format."""
    
    def __init__(self, prefix: str = "noc_"):
        self.prefix = prefix
        self.metrics: Dict[str, Any] = {}
    
    def add_gauge(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
        description: str = ""
    ):
        """Add a gauge metric."""
        full_name = f"{self.prefix}{name}"
        
        if full_name not in self.metrics:
            self.metrics[full_name] = {
                "type": "gauge",
                "description": description,
                "values": [],
            }
        
        label_str = self._format_labels(labels or {})
        self.metrics[full_name]["values"].append({
            "labels": label_str,
            "value": value,
        })
    
    def add_counter(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
        description: str = ""
    ):
        """Add a counter metric."""
        full_name = f"{self.prefix}{name}"
        
        if full_name not in self.metrics:
            self.metrics[full_name] = {
                "type": "counter",
                "description": description,
                "values": [],
            }
        
        label_str = self._format_labels(labels or {})
        self.metrics[full_name]["values"].append({
            "labels": label_str,
            "value": value,
        })
    
    def add_histogram(
        self,
        name: str,
        value: float,
        buckets: List[float],
        labels: Optional[Dict[str, str]] = None,
        description: str = ""
    ):
        """Add a histogram metric."""
        full_name = f"{self.prefix}{name}"
        
        if full_name not in self.metrics:
            self.metrics[full_name] = {
                "type": "histogram",
                "description": description,
                "buckets": buckets,
                "values": [],
            }
        
        label_str = self._format_labels(labels or {})
        
        # Count in each bucket
        bucket_counts = []
        for bucket in buckets:
            count = sum(1 for v in self.metrics[full_name]["values"] if v["raw_value"] <= bucket)
            bucket_counts.append(count)
        
        self.metrics[full_name]["values"].append({
            "labels": label_str,
            "raw_value": value,
            "bucket_counts": bucket_counts,
        })
    
    def _format_labels(self, labels: Dict[str, str]) -> str:
        """Format labels for Prometheus."""
        if not labels:
            return ""
        
        pairs = [f'{k}="{v}"' for k, v in labels.items()]
        return "{" + ",".join(pairs) + "}"
    
    def export(self) -> str:
        """Export all metrics in Prometheus format."""
        lines = []
        
        for name, metric in self.metrics.items():
            # Add HELP and TYPE
            if metric.get("description"):
                lines.append(f"# HELP {name} {metric['description']}")
            lines.append(f"# TYPE {name} {metric['type']}")
            
            # Add values
            if metric["type"] == "histogram":
                for value in metric["values"]:
                    # Output bucket counts
                    for i, bucket in enumerate(metric["buckets"]):
                        bucket_label = value["labels"][:-1] if value["labels"].endswith("}") else value["labels"]
                        if bucket_label:
                            bucket_label += f',le="{bucket}"' + "}"
                        else:
                            bucket_label = f'{{le="{bucket}"}}'
                        lines.append(f"{name}_bucket{bucket_label} {value['bucket_counts'][i]}")
                    
                    # Sum and count
                    lines.append(f"{name}_sum{value['labels']} {value['raw_value']}")
                    lines.append(f"{name}_count{value['labels']} {len(metric['values'])}")
            else:
                for value in metric["values"]:
                    lines.append(f"{name}{value['labels']} {value['value']}")
        
        return "\n".join(lines)
    
    def clear(self):
        """Clear all metrics."""
        self.metrics = {}


class PrometheusMetricsCollector:
    """Collect system metrics for Prometheus."""
    
    def __init__(self, storage=None):
        self.storage = storage
        self.exporter = PrometheusExporter()
    
    def collect_device_metrics(self) -> str:
        """Collect all device metrics."""
        self.exporter.clear()
        
        # Device count
        self.exporter.add_gauge(
            "devices_total",
            self._get_device_count(),
            description="Total number of monitored devices"
        )
        
        # Device status
        for status in ["up", "down", "unknown"]:
            count = self._get_device_count_by_status(status)
            self.exporter.add_gauge(
                "devices_by_status",
                count,
                labels={"status": status},
                description="Number of devices by status"
            )
        
        # Alert counts
        for severity in ["critical", "warning", "info"]:
            count = self._get_alert_count_by_severity(severity)
            self.exporter.add_counter(
                "alerts_total",
                count,
                labels={"severity": severity},
                description="Total number of alerts by severity"
            )
        
        # Collection metrics
        self.exporter.add_gauge(
            "last_collection_timestamp",
            datetime.now(timezone.utc).timestamp(),
            description="Timestamp of last successful collection"
        )
        
        return self.exporter.export()
    
    def _get_device_count(self) -> int:
        """Get total device count."""
        # Would query storage in production
        return 0
    
    def _get_device_count_by_status(self, status: str) -> int:
        """Get device count by status."""
        return 0
    
    def _get_alert_count_by_severity(self, severity: str) -> int:
        """Get alert count by severity."""
        return 0
    
    def write_metrics_file(self, filepath: str):
        """Write metrics to file for node_exporter textfile collector."""
        metrics = self.collect_device_metrics()
        with open(filepath, 'w') as f:
            f.write(metrics)


class StatsDCollector:
    """Send metrics to StatsD."""
    
    def __init__(self, host: str = "localhost", port: int = 8125):
        self.host = host
        self.port = port
        self._socket = None
    
    def _get_socket(self):
        """Get or create UDP socket."""
        if self._socket is None:
            import socket
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        return self._socket
    
    def gauge(self, metric: str, value: float, tags: Optional[Dict[str, str]] = None):
        """Send gauge metric."""
        message = f"{metric}:{value}|g"
        if tags:
            tag_str = ",".join([f"{k}:{v}" for k, v in tags.items()])
            message += f"|#{tag_str}"
        
        self._send(message)
    
    def counter(self, metric: str, value: int = 1, tags: Optional[Dict[str, str]] = None):
        """Send counter metric."""
        message = f"{metric}:{value}|c"
        if tags:
            tag_str = ",".join([f"{k}:{v}" for k, v in tags.items()])
            message += f"|#{tag_str}"
        
        self._send(message)
    
    def timer(self, metric: str, value_ms: float, tags: Optional[Dict[str, str]] = None):
        """Send timing metric."""
        message = f"{metric}:{value_ms}|ms"
        if tags:
            tag_str = ",".join([f"{k}:{v}" for k, v in tags.items()])
            message += f"|#{tag_str}"
        
        self._send(message)
    
    def _send(self, message: str):
        """Send metric to StatsD."""
        try:
            sock = self._get_socket()
            sock.sendto(message.encode(), (self.host, self.port))
        except Exception:
            pass  # StatsD is best-effort
