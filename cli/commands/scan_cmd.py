"""
Manual Scan Command Module

Handles manual device scanning and discovery commands.
"""

from __future__ import annotations

from typing import Dict, List, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class ScanResult:
    """Scan result for a single device."""
    device_id: str
    success: bool
    metrics_found: int
    errors: List[str]
    duration_ms: float


class ScanCommand:
    """Handles 'nocctl scan' command."""
    
    def __init__(self, collector, parser_engine, device_db):
        self.collector = collector
        self.parser = parser_engine
        self.device_db = device_db
    
    def scan_single(
        self,
        device_id: str,
        verbose: bool = False
    ) -> ScanResult:
        """
        Scan a single device.
        
        Args:
            device_id: Device to scan
            verbose: Show detailed output
        
        Returns:
            ScanResult
        """
        import time
        start = time.time()
        
        device = self.device_db.get(device_id)
        if not device:
            return ScanResult(
                device_id=device_id,
                success=False,
                metrics_found=0,
                errors=["Device not found"],
                duration_ms=0
            )
        
        errors = []
        metrics_found = 0
        
        try:
            # Collect data
            result = self.collector.collect(device)
            
            if result.success:
                # Parse metrics
                metrics = self.parser.parse(result.output, device.get("os_type"))
                metrics_found = len(metrics)
                
                # Store metrics
                self.device_db.update_metrics(device_id, metrics)
            else:
                errors.append(result.error or "Collection failed")
        
        except Exception as e:
            errors.append(str(e))
        
        duration = (time.time() - start) * 1000
        
        result = ScanResult(
            device_id=device_id,
            success=len(errors) == 0,
            metrics_found=metrics_found,
            errors=errors,
            duration_ms=duration
        )
        
        if verbose:
            self._print_verbose(result)
        
        return result
    
    def scan_group(
        self,
        group_name: str,
        verbose: bool = False
    ) -> List[ScanResult]:
        """
        Scan all devices in a group.
        
        Args:
            group_name: Device group to scan
            verbose: Show detailed output
        
        Returns:
            List of ScanResults
        """
        device_ids = self.device_db.get_group_devices(group_name)
        
        results = []
        for device_id in device_ids:
            result = self.scan_single(device_id, verbose=False)
            results.append(result)
            
            if verbose:
                status = "✓" if result.success else "✗"
                print(f"{status} {device_id}: {result.metrics_found} metrics")
        
        return results
    
    def scan_all(self, verbose: bool = False) -> List[ScanResult]:
        """Scan all devices."""
        all_devices = self.device_db.get_all()
        device_ids = [d.get("device_id") for d in all_devices]
        
        results = []
        for device_id in device_ids:
            result = self.scan_single(device_id, verbose=False)
            results.append(result)
        
        if verbose:
            success_count = sum(1 for r in results if r.success)
            print(f"Scanned {len(results)} devices, {success_count} successful")
        
        return results
    
    def _print_verbose(self, result: ScanResult) -> None:
        """Print verbose scan output."""
        print(f"Device: {result.device_id}")
        print(f"Success: {result.success}")
        print(f"Metrics: {result.metrics_found}")
        print(f"Duration: {result.duration_ms:.1f}ms")
        if result.errors:
            print(f"Errors: {', '.join(result.errors)}")
