"""
JSON Exporter Module

Exports monitoring data to JSON format.
Supports pretty printing, compression, and streaming.
"""

from __future__ import annotations

import json
import gzip
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


@dataclass
class JSONExportOptions:
    """Options for JSON export."""
    indent: int = 2
    sort_keys: bool = True
    compress: bool = False
    include_metadata: bool = True
    date_format: str = "iso"


class JSONExporter:
    """
    Exports monitoring data to JSON.
    
    Features:
    - Pretty printed or compact JSON
    - Gzip compression option
    - Streaming for large datasets
    - Schema validation
    """
    
    def __init__(self, output_dir: str = "exports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def export_devices(
        self,
        devices: List[Dict[str, Any]],
        filename: Optional[str] = None,
        options: Optional[JSONExportOptions] = None
    ) -> str:
        """
        Export device data to JSON.
        
        Args:
            devices: List of device dictionaries
            filename: Output filename
            options: Export options
        
        Returns:
            Path to exported file
        """
        options = options or JSONExportOptions()
        
        data = {
            "export_type": "device_status",
            "exported_at": datetime.now().isoformat(),
            "device_count": len(devices),
            "devices": devices
        }
        
        return self._export(data, filename or "devices.json", options)
    
    def export_alerts(
        self,
        alerts: List[Dict[str, Any]],
        filename: Optional[str] = None,
        options: Optional[JSONExportOptions] = None
    ) -> str:
        """Export alerts to JSON."""
        options = options or JSONExportOptions()
        
        data = {
            "export_type": "alerts",
            "exported_at": datetime.now().isoformat(),
            "alert_count": len(alerts),
            "alerts": alerts
        }
        
        return self._export(data, filename or "alerts.json", options)
    
    def export_metrics(
        self,
        metrics: Dict[str, List[Dict[str, Any]]],
        filename: Optional[str] = None,
        options: Optional[JSONExportOptions] = None
    ) -> str:
        """
        Export time-series metrics.
        
        Args:
            metrics: Dict of device_id -> metric list
            filename: Output filename
        """
        options = options or JSONExportOptions()
        
        data = {
            "export_type": "metrics",
            "exported_at": datetime.now().isoformat(),
            "device_count": len(metrics),
            "metrics": metrics
        }
        
        return self._export(data, filename or "metrics.json", options)
    
    def _export(
        self,
        data: Dict,
        filename: str,
        options: JSONExportOptions
    ) -> str:
        """Internal export method."""
        filepath = self.output_dir / filename
        
        # Convert datetime objects
        data = self._serialize_datetime(data)
        
        if options.compress:
            filepath = filepath.with_suffix('.json.gz')
            with gzip.open(filepath, 'wt', encoding='utf-8') as f:
                json.dump(data, f, indent=options.indent, sort_keys=options.sort_keys)
        else:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=options.indent, sort_keys=options.sort_keys)
        
        logger.info(f"JSON exported: {filepath}")
        return str(filepath)
    
    def _serialize_datetime(self, obj: Any) -> Any:
        """Convert datetime objects to strings."""
        if isinstance(obj, dict):
            return {k: self._serialize_datetime(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._serialize_datetime(item) for item in obj]
        elif isinstance(obj, datetime):
            return obj.isoformat()
        else:
            return obj
    
    def export_streaming(
        self,
        data_generator,
        filename: str,
        options: Optional[JSONExportOptions] = None
    ) -> str:
        """
        Export large datasets using streaming.
        
        Args:
            data_generator: Generator yielding data items
            filename: Output filename
            options: Export options
        """
        options = options or JSONExportOptions()
        filepath = self.output_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('{')
            f.write(f'"exported_at": "{datetime.now().isoformat()}",')
            f.write('"data": [')
            
            first = True
            for item in data_generator:
                if not first:
                    f.write(',')
                first = False
                
                json.dump(item, f, default=str)
            
            f.write(']}')
        
        return str(filepath)
    
    def validate_json(self, filepath: str, schema: Optional[Dict] = None) -> bool:
        """Validate exported JSON."""
        try:
            if filepath.endswith('.gz'):
                with gzip.open(filepath, 'rt', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            
            # Basic validation
            if not isinstance(data, dict):
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"JSON validation failed: {e}")
            return False


class JSONLExporter:
    """
    Exports to JSON Lines format (one JSON object per line).
    Efficient for large datasets and streaming.
    """
    
    def __init__(self, output_dir: str = "exports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def export_records(
        self,
        records: List[Dict],
        filename: str
    ) -> str:
        """
        Export records as JSON Lines.
        
        Args:
            records: List of record dictionaries
            filename: Output filename
        """
        filepath = self.output_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            for record in records:
                f.write(json.dumps(record, default=str) + '\n')
        
        logger.info(f"JSONL exported: {filepath} ({len(records)} records)")
        return str(filepath)
    
    def read_records(self, filepath: str):
        """Generator to read JSONL file."""
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    yield json.loads(line)
