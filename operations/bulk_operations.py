from __future__ import annotations

from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class BulkOperation:
    operation_id: str
    operation_type: str  # 'scan', 'config_update', 'command', 'discovery'
    targets: List[str]  # device IDs or patterns
    params: Dict[str, Any]
    status: str = "pending"  # pending, running, completed, failed
    created_at: str = ""
    completed_at: Optional[str] = None
    results: List[Dict[str, Any]] = None
    errors: List[Dict[str, Any]] = None

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if self.results is None:
            self.results = []
        if self.errors is None:
            self.errors = []


class BulkOperationManager:
    """Execute operations across multiple devices in parallel."""

    def __init__(self, max_concurrent: int = 10):
        self.max_concurrent = max_concurrent
        self.operations: Dict[str, BulkOperation] = {}
        self._executor = None

    def create_operation(
        self,
        operation_type: str,
        targets: List[str],
        params: Dict[str, Any]
    ) -> BulkOperation:
        """Create a new bulk operation."""
        import uuid
        
        op = BulkOperation(
            operation_id=f"BULK-{uuid.uuid4().hex[:12].upper()}",
            operation_type=operation_type,
            targets=targets,
            params=params
        )
        self.operations[op.operation_id] = op
        return op

    async def execute_bulk_scan(
        self,
        operation_id: str,
        device_configs: List[Dict[str, Any]]
    ) -> BulkOperation:
        """Execute bulk scan across multiple devices."""
        import asyncio
        from autodetector.collector.ssh_collector import SshCollector
        from autodetector.collector.telnet_collector import TelnetCollector
        
        op = self.operations.get(operation_id)
        if not op:
            raise ValueError(f"Operation {operation_id} not found")
        
        op.status = "running"
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def scan_single(device_config: Dict[str, Any]) -> Dict[str, Any]:
            async with semaphore:
                device_id = device_config.get("id", "unknown")
                host = device_config.get("host", "")
                transport = device_config.get("transport", "ssh")
                os_type = device_config.get("os", "")
                
                try:
                    # Load plugin
                    from autodetector.plugin.loader import PluginLoader
                    loader = PluginLoader()
                    plugin = loader.load(os_type)
                    
                    commands = plugin.get_commands()
                    
                    if transport == "telnet":
                        collector = TelnetCollector()
                    else:
                        collector = SshCollector()
                    
                    username = device_config.get("username", "")
                    password = device_config.get("password", "")
                    
                    outputs, errors = collector.run_commands(
                        host, username, password, commands
                    )
                    
                    # Parse results
                    result = plugin.parse(outputs, errors, device_config)
                    
                    return {
                        "device_id": device_id,
                        "status": "success",
                        "metrics_count": len(result.get("metrics", [])),
                        "error_count": len(errors),
                    }
                    
                except Exception as e:
                    return {
                        "device_id": device_id,
                        "status": "error",
                        "error": str(e),
                    }
        
        # Execute all scans
        tasks = [scan_single(cfg) for cfg in device_configs]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for result in results:
            if isinstance(result, Exception):
                op.errors.append({"error": str(result)})
            elif result.get("status") == "success":
                op.results.append(result)
            else:
                op.errors.append(result)
        
        op.status = "completed" if not op.errors else "completed_with_errors"
        op.completed_at = datetime.now(timezone.utc).isoformat()
        
        return op

    async def execute_bulk_config_update(
        self,
        operation_id: str,
        device_configs: List[Dict[str, Any]],
        config_commands: List[str]
    ) -> BulkOperation:
        """Execute config updates across multiple devices."""
        import asyncio
        from autodetector.collector.ssh_collector import SshCollector
        
        op = self.operations.get(operation_id)
        if not op:
            raise ValueError(f"Operation {operation_id} not found")
        
        op.status = "running"
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def update_single(device_config: Dict[str, Any]) -> Dict[str, Any]:
            async with semaphore:
                device_id = device_config.get("id", "unknown")
                host = device_config.get("host", "")
                
                try:
                    collector = SshCollector()
                    username = device_config.get("username", "")
                    password = device_config.get("password", "")
                    
                    # Execute config commands
                    outputs = {}
                    errors = {}
                    
                    for cmd in config_commands:
                        out, err = collector.run_commands(
                            host, username, password, {"cmd": cmd}
                        )
                        outputs.update(out)
                        errors.update(err)
                    
                    return {
                        "device_id": device_id,
                        "status": "success",
                        "commands_executed": len(config_commands),
                    }
                    
                except Exception as e:
                    return {
                        "device_id": device_id,
                        "status": "error",
                        "error": str(e),
                    }
        
        tasks = [update_single(cfg) for cfg in device_configs]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                op.errors.append({"error": str(result)})
            elif result.get("status") == "success":
                op.results.append(result)
            else:
                op.errors.append(result)
        
        op.status = "completed" if not op.errors else "completed_with_errors"
        op.completed_at = datetime.now(timezone.utc).isoformat()
        
        return op

    def get_operation_status(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a bulk operation."""
        op = self.operations.get(operation_id)
        if not op:
            return None
        
        return {
            "operation_id": op.operation_id,
            "type": op.operation_type,
            "status": op.status,
            "total_targets": len(op.targets),
            "successful": len(op.results),
            "failed": len(op.errors),
            "progress_pct": (
                (len(op.results) + len(op.errors)) / len(op.targets) * 100
                if op.targets else 0
            ),
            "created_at": op.created_at,
            "completed_at": op.completed_at,
        }

    def cancel_operation(self, operation_id: str) -> bool:
        """Cancel a running operation."""
        op = self.operations.get(operation_id)
        if op and op.status == "running":
            op.status = "cancelled"
            op.completed_at = datetime.now(timezone.utc).isoformat()
            return True
        return False

    def list_operations(
        self,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """List bulk operations."""
        ops = list(self.operations.values())
        
        if status:
            ops = [op for op in ops if op.status == status]
        
        ops.sort(key=lambda x: x.created_at, reverse=True)
        
        return [
            {
                "operation_id": op.operation_id,
                "type": op.operation_type,
                "status": op.status,
                "targets": len(op.targets),
                "created_at": op.created_at,
            }
            for op in ops[:limit]
        ]
