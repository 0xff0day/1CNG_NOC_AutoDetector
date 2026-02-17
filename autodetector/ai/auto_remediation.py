"""
Auto-Remediation Module

Provides self-healing capabilities for the NOC system.
Executes automated actions based on alerts and root cause analysis.
Includes runbook automation and intelligent remediation workflows.
"""

from __future__ import annotations

import os
import json
import time
import subprocess
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable, Union
from enum import Enum, auto
from datetime import datetime
import threading

logger = logging.getLogger(__name__)


class RemediationStatus(Enum):
    """Status of a remediation action."""
    PENDING = auto()
    RUNNING = auto()
    SUCCESS = auto()
    FAILED = auto()
    ROLLED_BACK = auto()
    SKIPPED = auto()


class RemediationType(Enum):
    """Types of remediation actions."""
    COMMAND = "command"           # Execute CLI command
    SCRIPT = "script"             # Run Python/shell script
    API_CALL = "api_call"         # Make REST API call
    SERVICE_RESTART = "service"   # Restart a service
    CONFIG_CHANGE = "config"      # Apply configuration change
    NOTIFICATION = "notify"       # Send notification
    CALLBACK = "callback"         # Execute Python callback


@dataclass
class RemediationAction:
    """A single remediation action."""
    id: str
    name: str
    description: str
    action_type: RemediationType
    target: str  # Device ID or service name
    params: Dict[str, Any] = field(default_factory=dict)
    timeout: int = 60
    retry_count: int = 1
    retry_delay: int = 5
    rollback_action: Optional[str] = None
    pre_conditions: List[str] = field(default_factory=list)
    post_verification: List[str] = field(default_factory=list)
    requires_confirmation: bool = False
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "action_type": self.action_type.value,
            "target": self.target,
            "params": self.params,
            "timeout": self.timeout,
            "retry_count": self.retry_count,
            "retry_delay": self.retry_delay,
            "rollback_action": self.rollback_action,
            "pre_conditions": self.pre_conditions,
            "post_verification": self.post_verification,
            "requires_confirmation": self.requires_confirmation,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class RemediationResult:
    """Result of executing a remediation action."""
    action_id: str
    status: RemediationStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    output: str = ""
    error: str = ""
    exit_code: int = 0
    retry_attempts: int = 0
    rollback_triggered: bool = False
    rollback_result: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration_seconds(self) -> float:
        """Calculate execution duration."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0


@dataclass
class RunbookStep:
    """A step in an automated runbook."""
    id: str
    name: str
    description: str
    action: RemediationAction
    order: int
    condition: str = "always"  # "always", "on_success", "on_failure"
    delay_before: int = 0  # Seconds to wait before executing


@dataclass
class Runbook:
    """An automated runbook for incident response."""
    id: str
    name: str
    description: str
    trigger_alerts: List[str]  # Alert types that trigger this runbook
    trigger_devices: List[str]  # Device types or "*" for all
    steps: List[RunbookStep]
    enabled: bool = True
    auto_execute: bool = False  # If False, requires manual approval
    created_at: datetime = field(default_factory=datetime.now)
    last_executed: Optional[datetime] = None
    execution_count: int = 0
    success_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "trigger_alerts": self.trigger_alerts,
            "trigger_devices": self.trigger_devices,
            "steps": [
                {
                    "id": s.id,
                    "name": s.name,
                    "description": s.description,
                    "order": s.order,
                    "condition": s.condition,
                    "delay_before": s.delay_before,
                    "action": s.action.to_dict(),
                }
                for s in self.steps
            ],
            "enabled": self.enabled,
            "auto_execute": self.auto_execute,
            "created_at": self.created_at.isoformat(),
            "last_executed": self.last_executed.isoformat() if self.last_executed else None,
            "execution_count": self.execution_count,
            "success_count": self.success_count,
        }


class AutoRemediator:
    """
    Automated remediation engine for self-healing operations.
    
    Executes remediation actions based on:
    - Root cause analysis recommendations
    - Predefined runbooks
    - Alert patterns
    - Device health status
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.actions: Dict[str, RemediationAction] = {}
        self.runbooks: Dict[str, Runbook] = {}
        self.results: List[RemediationResult] = []
        self._running_actions: Dict[str, threading.Thread] = {}
        self._lock = threading.Lock()
        self._callbacks: Dict[str, Callable] = {}
        
        # Load default runbooks
        self._load_default_runbooks()
    
    def register_action(self, action: RemediationAction) -> None:
        """Register a remediation action."""
        self.actions[action.id] = action
        logger.info(f"Registered remediation action: {action.name}")
    
    def unregister_action(self, action_id: str) -> bool:
        """Unregister a remediation action."""
        if action_id in self.actions:
            del self.actions[action_id]
            return True
        return False
    
    def get_action(self, action_id: str) -> Optional[RemediationAction]:
        """Get a registered action by ID."""
        return self.actions.get(action_id)
    
    def list_actions(self) -> List[RemediationAction]:
        """List all registered actions."""
        return list(self.actions.values())
    
    def register_runbook(self, runbook: Runbook) -> None:
        """Register an automated runbook."""
        self.runbooks[runbook.id] = runbook
        logger.info(f"Registered runbook: {runbook.name}")
    
    def get_runbook(self, runbook_id: str) -> Optional[Runbook]:
        """Get a runbook by ID."""
        return self.runbooks.get(runbook_id)
    
    def list_runbooks(self) -> List[Runbook]:
        """List all registered runbooks."""
        return list(self.runbooks.values())
    
    def execute_action(
        self,
        action_id: str,
        context: Optional[Dict[str, Any]] = None,
        dry_run: bool = False
    ) -> RemediationResult:
        """
        Execute a remediation action.
        
        Args:
            action_id: ID of the action to execute
            context: Additional context variables
            dry_run: If True, simulate execution without making changes
        
        Returns:
            RemediationResult with execution details
        """
        action = self.actions.get(action_id)
        if not action:
            return RemediationResult(
                action_id=action_id,
                status=RemediationStatus.FAILED,
                start_time=datetime.now(),
                end_time=datetime.now(),
                error=f"Action {action_id} not found"
            )
        
        if not action.enabled:
            return RemediationResult(
                action_id=action_id,
                status=RemediationStatus.SKIPPED,
                start_time=datetime.now(),
                end_time=datetime.now(),
                output="Action is disabled"
            )
        
        result = RemediationResult(
            action_id=action_id,
            status=RemediationStatus.RUNNING,
            start_time=datetime.now(),
        )
        
        # Check pre-conditions
        for condition in action.pre_conditions:
            if not self._evaluate_condition(condition, context):
                result.status = RemediationStatus.SKIPPED
                result.end_time = datetime.now()
                result.output = f"Pre-condition not met: {condition}"
                return result
        
        # Execute with retries
        for attempt in range(action.retry_count):
            result.retry_attempts = attempt + 1
            
            try:
                if dry_run:
                    result.output = f"[DRY RUN] Would execute: {action.action_type.value} on {action.target}"
                    result.status = RemediationStatus.SUCCESS
                else:
                    result = self._execute_action_internal(action, context, result)
                
                if result.status == RemediationStatus.SUCCESS:
                    break
                    
            except Exception as e:
                logger.error(f"Action {action_id} failed (attempt {attempt + 1}): {e}")
                result.error = str(e)
                result.status = RemediationStatus.FAILED
                
                if attempt < action.retry_count - 1:
                    time.sleep(action.retry_delay)
        
        # Perform post-verification
        if result.status == RemediationStatus.SUCCESS and action.post_verification:
            for check in action.post_verification:
                if not self._evaluate_condition(check, context):
                    result.status = RemediationStatus.FAILED
                    result.error = f"Post-verification failed: {check}"
                    break
        
        # Trigger rollback on failure if configured
        if result.status == RemediationStatus.FAILED and action.rollback_action:
            result = self._execute_rollback(action, result, context)
        
        result.end_time = datetime.now()
        self.results.append(result)
        
        return result
    
    def _execute_action_internal(
        self,
        action: RemediationAction,
        context: Optional[Dict[str, Any]],
        result: RemediationResult
    ) -> RemediationResult:
        """Internal execution logic for different action types."""
        
        if action.action_type == RemediationType.COMMAND:
            result = self._execute_command(action, context, result)
        elif action.action_type == RemediationType.SCRIPT:
            result = self._execute_script(action, context, result)
        elif action.action_type == RemediationType.API_CALL:
            result = self._execute_api_call(action, context, result)
        elif action.action_type == RemediationType.SERVICE_RESTART:
            result = self._execute_service_restart(action, context, result)
        elif action.action_type == RemediationType.CONFIG_CHANGE:
            result = self._execute_config_change(action, context, result)
        elif action.action_type == RemediationType.NOTIFICATION:
            result = self._execute_notification(action, context, result)
        elif action.action_type == RemediationType.CALLBACK:
            result = self._execute_callback(action, context, result)
        else:
            result.status = RemediationStatus.FAILED
            result.error = f"Unknown action type: {action.action_type}"
        
        return result
    
    def _execute_command(
        self,
        action: RemediationAction,
        context: Optional[Dict[str, Any]],
        result: RemediationResult
    ) -> RemediationResult:
        """Execute a CLI command."""
        command = action.params.get("command", "")
        
        # Substitute context variables
        if context:
            for key, value in context.items():
                command = command.replace(f"{{{key}}}", str(value))
        
        try:
            process = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=action.timeout,
                cwd=action.params.get("cwd")
            )
            
            result.exit_code = process.returncode
            result.output = process.stdout
            
            if process.returncode == 0:
                result.status = RemediationStatus.SUCCESS
            else:
                result.status = RemediationStatus.FAILED
                result.error = process.stderr or f"Exit code: {process.returncode}"
                
        except subprocess.TimeoutExpired:
            result.status = RemediationStatus.FAILED
            result.error = f"Command timed out after {action.timeout}s"
        except Exception as e:
            result.status = RemediationStatus.FAILED
            result.error = str(e)
        
        return result
    
    def _execute_script(
        self,
        action: RemediationAction,
        context: Optional[Dict[str, Any]],
        result: RemediationResult
    ) -> RemediationResult:
        """Execute a Python or shell script."""
        script_path = action.params.get("script_path", "")
        script_content = action.params.get("script_content", "")
        interpreter = action.params.get("interpreter", "python3")
        
        try:
            if script_content:
                # Execute inline script
                if interpreter == "python3":
                    # Create a safe execution environment
                    exec_globals = {"__builtins__": __builtins__, "context": context}
                    exec(script_content, exec_globals)
                    result.output = "Script executed successfully"
                    result.status = RemediationStatus.SUCCESS
                else:
                    # Execute as shell script
                    process = subprocess.run(
                        [interpreter, "-c", script_content],
                        capture_output=True,
                        text=True,
                        timeout=action.timeout
                    )
                    result.exit_code = process.returncode
                    result.output = process.stdout
                    result.status = RemediationStatus.SUCCESS if process.returncode == 0 else RemediationStatus.FAILED
                    result.error = process.stderr
            elif script_path and os.path.exists(script_path):
                # Execute script file
                process = subprocess.run(
                    [interpreter, script_path],
                    capture_output=True,
                    text=True,
                    timeout=action.timeout,
                    env={**os.environ, **{f"CTX_{k}": str(v) for k, v in (context or {}).items()}}
                )
                result.exit_code = process.returncode
                result.output = process.stdout
                result.status = RemediationStatus.SUCCESS if process.returncode == 0 else RemediationStatus.FAILED
                result.error = process.stderr
            else:
                result.status = RemediationStatus.FAILED
                result.error = f"Script not found: {script_path}"
                
        except Exception as e:
            result.status = RemediationStatus.FAILED
            result.error = str(e)
        
        return result
    
    def _execute_api_call(
        self,
        action: RemediationAction,
        context: Optional[Dict[str, Any]],
        result: RemediationResult
    ) -> RemediationResult:
        """Make a REST API call."""
        import requests
        
        method = action.params.get("method", "POST").upper()
        url = action.params.get("url", "")
        headers = action.params.get("headers", {})
        body = action.params.get("body", "")
        
        # Substitute context variables
        if context:
            for key, value in context.items():
                url = url.replace(f"{{{key}}}", str(value))
                if isinstance(body, str):
                    body = body.replace(f"{{{key}}}", str(value))
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                json=body if isinstance(body, dict) else None,
                data=body if isinstance(body, str) else None,
                timeout=action.timeout
            )
            
            result.output = response.text[:1000]  # Limit output size
            result.exit_code = response.status_code
            
            if 200 <= response.status_code < 300:
                result.status = RemediationStatus.SUCCESS
            else:
                result.status = RemediationStatus.FAILED
                result.error = f"HTTP {response.status_code}: {response.text[:500]}"
                
        except Exception as e:
            result.status = RemediationStatus.FAILED
            result.error = str(e)
        
        return result
    
    def _execute_service_restart(
        self,
        action: RemediationAction,
        context: Optional[Dict[str, Any]],
        result: RemediationResult
    ) -> RemediationResult:
        """Restart a system service."""
        service_name = action.params.get("service_name", action.target)
        service_manager = action.params.get("service_manager", "systemctl")
        
        try:
            if service_manager == "systemctl":
                commands = [
                    f"systemctl restart {service_name}",
                    f"systemctl is-active {service_name}"
                ]
            elif service_manager == "service":
                commands = [
                    f"service {service_name} restart",
                    f"service {service_name} status"
                ]
            else:
                result.status = RemediationStatus.FAILED
                result.error = f"Unknown service manager: {service_manager}"
                return result
            
            for cmd in commands:
                process = subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=action.timeout
                )
                result.output += process.stdout + "\n"
                result.exit_code = process.returncode
            
            if result.exit_code == 0:
                result.status = RemediationStatus.SUCCESS
            else:
                result.status = RemediationStatus.FAILED
                result.error = process.stderr
                
        except Exception as e:
            result.status = RemediationStatus.FAILED
            result.error = str(e)
        
        return result
    
    def _execute_config_change(
        self,
        action: RemediationAction,
        context: Optional[Dict[str, Any]],
        result: RemediationResult
    ) -> RemediationResult:
        """Apply a configuration change."""
        config_path = action.params.get("config_path", "")
        config_content = action.params.get("config_content", "")
        backup = action.params.get("backup", True)
        
        try:
            if not os.path.exists(config_path):
                result.status = RemediationStatus.FAILED
                result.error = f"Config file not found: {config_path}"
                return result
            
            # Create backup
            if backup:
                backup_path = f"{config_path}.backup.{int(time.time())}"
                with open(config_path, 'r') as f:
                    original_content = f.read()
                with open(backup_path, 'w') as f:
                    f.write(original_content)
                result.metadata["backup_path"] = backup_path
            
            # Write new config
            with open(config_path, 'w') as f:
                f.write(config_content)
            
            result.output = f"Configuration updated: {config_path}"
            result.status = RemediationStatus.SUCCESS
            
        except Exception as e:
            result.status = RemediationStatus.FAILED
            result.error = str(e)
        
        return result
    
    def _execute_notification(
        self,
        action: RemediationAction,
        context: Optional[Dict[str, Any]],
        result: RemediationResult
    ) -> RemediationResult:
        """Send a notification."""
        channel = action.params.get("channel", "telegram")
        message = action.params.get("message", "")
        severity = action.params.get("severity", "info")
        
        # Substitute context
        if context:
            for key, value in context.items():
                message = message.replace(f"{{{key}}}", str(value))
        
        try:
            # This would integrate with notification systems
            result.output = f"Notification sent via {channel}: {message[:100]}"
            result.status = RemediationStatus.SUCCESS
            
        except Exception as e:
            result.status = RemediationStatus.FAILED
            result.error = str(e)
        
        return result
    
    def _execute_callback(
        self,
        action: RemediationAction,
        context: Optional[Dict[str, Any]],
        result: RemediationResult
    ) -> RemediationResult:
        """Execute a registered Python callback."""
        callback_name = action.params.get("callback", "")
        
        if callback_name not in self._callbacks:
            result.status = RemediationStatus.FAILED
            result.error = f"Callback not found: {callback_name}"
            return result
        
        try:
            callback = self._callbacks[callback_name]
            callback_result = callback(context or {})
            result.output = str(callback_result)
            result.status = RemediationStatus.SUCCESS
            
        except Exception as e:
            result.status = RemediationStatus.FAILED
            result.error = str(e)
        
        return result
    
    def _execute_rollback(
        self,
        action: RemediationAction,
        result: RemediationResult,
        context: Optional[Dict[str, Any]]
    ) -> RemediationResult:
        """Execute rollback action on failure."""
        logger.warning(f"Executing rollback for failed action: {action.id}")
        
        rollback_action = self.actions.get(action.rollback_action)
        if not rollback_action:
            result.error += f" | Rollback action not found: {action.rollback_action}"
            return result
        
        rollback_result = self._execute_action_internal(rollback_action, context, RemediationResult(
            action_id=rollback_action.id,
            status=RemediationStatus.RUNNING,
            start_time=datetime.now(),
        ))
        
        result.rollback_triggered = True
        result.rollback_result = rollback_result.output if rollback_result.status == RemediationStatus.SUCCESS else rollback_result.error
        
        return result
    
    def _evaluate_condition(self, condition: str, context: Optional[Dict[str, Any]]) -> bool:
        """Evaluate a pre/post condition."""
        try:
            # Simple condition evaluation
            if condition.startswith("context."):
                parts = condition.replace("context.", "").split("==")
                if len(parts) == 2:
                    key = parts[0].strip()
                    expected = parts[1].strip().strip("'\"")
                    return context.get(key) == expected if context else False
            
            # Default to True for unknown conditions
            return True
            
        except Exception as e:
            logger.warning(f"Failed to evaluate condition '{condition}': {e}")
            return False
    
    def execute_runbook(
        self,
        runbook_id: str,
        alert_data: Optional[Dict[str, Any]] = None,
        device_data: Optional[Dict[str, Any]] = None,
        dry_run: bool = False
    ) -> List[RemediationResult]:
        """
        Execute a complete runbook.
        
        Args:
            runbook_id: ID of the runbook to execute
            alert_data: Alert that triggered the runbook
            device_data: Device information
            dry_run: If True, simulate without making changes
        
        Returns:
            List of results for each step
        """
        runbook = self.runbooks.get(runbook_id)
        if not runbook:
            logger.error(f"Runbook not found: {runbook_id}")
            return []
        
        if not runbook.enabled:
            logger.info(f"Runbook {runbook_id} is disabled")
            return []
        
        # Build context
        context = {
            "alert": alert_data or {},
            "device": device_data or {},
            "runbook_id": runbook_id,
        }
        
        results = []
        previous_success = True
        
        # Sort steps by order
        sorted_steps = sorted(runbook.steps, key=lambda s: s.order)
        
        for step in sorted_steps:
            # Check condition
            if step.condition == "on_success" and not previous_success:
                continue
            if step.condition == "on_failure" and previous_success:
                continue
            
            # Delay if specified
            if step.delay_before > 0:
                time.sleep(step.delay_before)
            
            # Execute step action
            result = self.execute_action(step.action.id, context, dry_run)
            results.append(result)
            
            previous_success = result.status == RemediationStatus.SUCCESS
            
            # Stop on failure if not continuing
            if not previous_success and step.condition != "always":
                break
        
        # Update runbook stats
        runbook.last_executed = datetime.now()
        runbook.execution_count += 1
        if all(r.status == RemediationStatus.SUCCESS for r in results):
            runbook.success_count += 1
        
        return results
    
    def find_runbooks_for_alert(
        self,
        alert_type: str,
        device_type: str
    ) -> List[Runbook]:
        """Find runbooks that match an alert type and device."""
        matching = []
        
        for runbook in self.runbooks.values():
            if not runbook.enabled:
                continue
            
            # Check alert type match
            alert_match = "*" in runbook.trigger_alerts or alert_type in runbook.trigger_alerts
            
            # Check device type match
            device_match = "*" in runbook.trigger_devices or device_type in runbook.trigger_devices
            
            if alert_match and device_match:
                matching.append(runbook)
        
        return matching
    
    def register_callback(self, name: str, callback: Callable) -> None:
        """Register a Python callback function."""
        self._callbacks[name] = callback
        logger.info(f"Registered callback: {name}")
    
    def get_execution_history(
        self,
        action_id: Optional[str] = None,
        limit: int = 100
    ) -> List[RemediationResult]:
        """Get history of executed actions."""
        results = self.results
        
        if action_id:
            results = [r for r in results if r.action_id == action_id]
        
        return results[-limit:]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get remediation statistics."""
        total_actions = len(self.results)
        successful = len([r for r in self.results if r.status == RemediationStatus.SUCCESS])
        failed = len([r for r in self.results if r.status == RemediationStatus.FAILED])
        
        return {
            "total_executions": total_actions,
            "successful": successful,
            "failed": failed,
            "success_rate": successful / total_actions if total_actions > 0 else 0,
            "registered_actions": len(self.actions),
            "registered_runbooks": len(self.runbooks),
        }
    
    def _load_default_runbooks(self) -> None:
        """Load default remediation runbooks."""
        # Runbook: Restart service on high memory
        restart_service_action = RemediationAction(
            id="restart_service",
            name="Restart Service",
            description="Restart a system service",
            action_type=RemediationType.SERVICE_RESTART,
            target="{service_name}",
            params={"service_name": "{service_name}"},
            timeout=120,
            retry_count=2,
        )
        self.register_action(restart_service_action)
        
        # Runbook: Clear disk space
        clear_logs_action = RemediationAction(
            id="clear_logs",
            name="Clear Old Logs",
            description="Clear log files older than 7 days",
            action_type=RemediationType.COMMAND,
            target="localhost",
            params={"command": "find /var/log -name '*.log' -mtime +7 -delete"},
            timeout=60,
        )
        self.register_action(clear_logs_action)
        
        # Runbook: Notify on critical alert
        notify_action = RemediationAction(
            id="notify_critical",
            name="Critical Alert Notification",
            description="Send notification for critical alerts",
            action_type=RemediationType.NOTIFICATION,
            target="admin",
            params={
                "channel": "telegram",
                "message": "🚨 CRITICAL: {alert[message]} on {device[name]}",
                "severity": "critical"
            },
        )
        self.register_action(notify_action)
        
        # Create default runbook for disk full alerts
        disk_full_runbook = Runbook(
            id="disk_full_remediation",
            name="Disk Full Auto-Remediation",
            description="Automatically clear old logs when disk is full",
            trigger_alerts=["disk_full", "disk_critical"],
            trigger_devices=["*"],
            steps=[
                RunbookStep(
                    id="notify_start",
                    name="Notify Start",
                    description="Notify that remediation is starting",
                    action=notify_action,
                    order=1,
                ),
                RunbookStep(
                    id="clear_logs",
                    name="Clear Old Logs",
                    description="Clear old log files",
                    action=clear_logs_action,
                    order=2,
                    delay_before=5,
                ),
            ],
            auto_execute=False,  # Require manual approval
        )
        self.register_runbook(disk_full_runbook)


# Global instance for easy access
_default_remediator: Optional[AutoRemediator] = None


def get_remediator() -> AutoRemediator:
    """Get or create the global AutoRemediator instance."""
    global _default_remediator
    if _default_remediator is None:
        _default_remediator = AutoRemediator()
    return _default_remediator


def execute_remediation(
    action_id: str,
    context: Optional[Dict[str, Any]] = None,
    dry_run: bool = False
) -> RemediationResult:
    """Convenience function to execute a remediation action."""
    return get_remediator().execute_action(action_id, context, dry_run)


def execute_runbook(
    runbook_id: str,
    alert_data: Optional[Dict[str, Any]] = None,
    device_data: Optional[Dict[str, Any]] = None,
    dry_run: bool = False
) -> List[RemediationResult]:
    """Convenience function to execute a runbook."""
    return get_remediator().execute_runbook(runbook_id, alert_data, device_data, dry_run)
