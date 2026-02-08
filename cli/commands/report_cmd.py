"""
Report on Demand Command Module

Handles manual report generation commands.
"""

from __future__ import annotations

from typing import Optional, List, Dict
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ReportCommand:
    """Handles 'nocctl report' command."""
    
    def __init__(
        self,
        excel_reporter,
        json_exporter,
        txt_reporter,
        category_splitter
    ):
        self.excel = excel_reporter
        self.json = json_exporter
        self.txt = txt_reporter
        self.splitter = category_splitter
    
    def generate(
        self,
        report_type: str,
        format: str = "excel",
        output_dir: Optional[str] = None,
        device_filter: Optional[List[str]] = None,
        time_range_hours: int = 24
    ) -> str:
        """
        Generate report on demand.
        
        Args:
            report_type: Type of report (devices, alerts, metrics, full)
            format: Output format (excel, json, txt, all)
            output_dir: Output directory
            device_filter: Filter to specific devices
            time_range_hours: Time range for data
        
        Returns:
            Path to generated report
        """
        # Gather data
        data = self._gather_data(report_type, time_range_hours, device_filter)
        
        # Generate timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Generate in requested format
        if format == "excel":
            return self.excel.generate_device_report(data["devices"], f"report_{timestamp}.xlsx")
        
        elif format == "json":
            return self.json.export_devices(data["devices"], f"report_{timestamp}.json")
        
        elif format == "txt":
            return self.txt.generate_device_report(data["devices"], f"report_{timestamp}.txt")
        
        elif format == "all":
            paths = []
            paths.append(self.excel.generate_device_report(data["devices"], f"report_{timestamp}.xlsx"))
            paths.append(self.json.export_devices(data["devices"], f"report_{timestamp}.json"))
            paths.append(self.txt.generate_device_report(data["devices"], f"report_{timestamp}.txt"))
            return f"Generated {len(paths)} reports: {', '.join(paths)}"
        
        else:
            raise ValueError(f"Unknown format: {format}")
    
    def _gather_data(
        self,
        report_type: str,
        hours: int,
        device_filter: Optional[List[str]]
    ) -> Dict:
        """Gather data for report."""
        # This would query the actual databases
        # Placeholder implementation
        return {
            "devices": [],
            "alerts": [],
            "metrics": {},
            "generated_at": datetime.now().isoformat(),
            "time_range_hours": hours,
        }
    
    def list_reports(self, reports_dir: str = "reports") -> List[Dict]:
        """List available reports."""
        path = Path(reports_dir)
        if not path.exists():
            return []
        
        reports = []
        for file in path.iterdir():
            if file.suffix in ['.xlsx', '.json', '.txt']:
                stat = file.stat()
                reports.append({
                    "filename": file.name,
                    "type": file.suffix[1:],
                    "size_bytes": stat.st_size,
                    "created": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                })
        
        return sorted(reports, key=lambda x: x["created"], reverse=True)
    
    def delete_report(self, filename: str, reports_dir: str = "reports") -> bool:
        """Delete a report file."""
        path = Path(reports_dir) / filename
        if path.exists():
            path.unlink()
            return True
        return False
