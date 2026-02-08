"""
Task Scheduler Module

Schedules and manages polling, discovery, and maintenance tasks.
Supports cron-like expressions and multiple scheduling backends.
"""

from __future__ import annotations

import time
import threading
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class TaskPriority(Enum):
    """Task priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class ScheduledTask:
    """Scheduled task definition."""
    task_id: str
    name: str
    schedule: str  # cron expression or interval
    callback: Callable
    args: tuple
    kwargs: dict
    priority: TaskPriority
    enabled: bool = True
    last_run: Optional[float] = None
    next_run: Optional[float] = None
    run_count: int = 0
    max_runs: Optional[int] = None


class TaskScheduler:
    """
    Task scheduler for periodic operations.
    
    Features:
    - Cron-like scheduling
    - Interval-based scheduling
    - Priority queue
    - Concurrent execution
    - Task persistence
    """
    
    def __init__(self, max_workers: int = 5):
        self.max_workers = max_workers
        self._tasks: Dict[str, ScheduledTask] = {}
        self._scheduler_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()
        self._lock = threading.Lock()
        self._running = False
    
    def start(self) -> None:
        """Start the scheduler."""
        if self._running:
            return
        
        self._shutdown_event.clear()
        self._running = True
        
        self._scheduler_thread = threading.Thread(
            target=self._scheduler_loop,
            name="TaskScheduler",
            daemon=True
        )
        self._scheduler_thread.start()
        
        logger.info("Task scheduler started")
    
    def stop(self) -> None:
        """Stop the scheduler."""
        self._shutdown_event.set()
        self._running = False
        
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=5)
        
        logger.info("Task scheduler stopped")
    
    def add_task(
        self,
        task_id: str,
        name: str,
        schedule: str,
        callback: Callable,
        args: tuple = (),
        kwargs: Optional[Dict] = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        max_runs: Optional[int] = None
    ) -> ScheduledTask:
        """
        Add a scheduled task.
        
        Args:
            task_id: Unique task identifier
            name: Human-readable name
            schedule: Cron expression (e.g., "*/5 * * * *") or interval (e.g., "300s")
            callback: Function to execute
            args: Positional arguments
            kwargs: Keyword arguments
            priority: Task priority
            max_runs: Maximum number of executions
        
        Returns:
            ScheduledTask object
        """
        task = ScheduledTask(
            task_id=task_id,
            name=name,
            schedule=schedule,
            callback=callback,
            args=args,
            kwargs=kwargs or {},
            priority=priority,
            max_runs=max_runs
        )
        
        # Calculate next run
        task.next_run = self._calculate_next_run(schedule)
        
        with self._lock:
            self._tasks[task_id] = task
        
        logger.info(f"Added scheduled task: {name} ({task_id})")
        return task
    
    def remove_task(self, task_id: str) -> bool:
        """Remove a scheduled task."""
        with self._lock:
            if task_id in self._tasks:
                del self._tasks[task_id]
                logger.info(f"Removed task: {task_id}")
                return True
        return False
    
    def enable_task(self, task_id: str) -> bool:
        """Enable a disabled task."""
        with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id].enabled = True
                return True
        return False
    
    def disable_task(self, task_id: str) -> bool:
        """Disable a task temporarily."""
        with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id].enabled = False
                return True
        return False
    
    def _scheduler_loop(self) -> None:
        """Main scheduler loop."""
        while not self._shutdown_event.is_set():
            current_time = time.time()
            
            with self._lock:
                # Find tasks to run
                tasks_to_run = []
                for task in self._tasks.values():
                    if not task.enabled:
                        continue
                    
                    if task.next_run and current_time >= task.next_run:
                        tasks_to_run.append(task)
                
                # Sort by priority
                tasks_to_run.sort(key=lambda t: t.priority.value, reverse=True)
            
            # Execute tasks
            for task in tasks_to_run:
                try:
                    self._execute_task(task)
                except Exception as e:
                    logger.error(f"Task {task.name} failed: {e}")
            
            # Sleep until next check
            time.sleep(1)
    
    def _execute_task(self, task: ScheduledTask) -> None:
        """Execute a single task."""
        logger.debug(f"Executing task: {task.name}")
        
        try:
            task.callback(*task.args, **task.kwargs)
            task.last_run = time.time()
            task.run_count += 1
            
            # Check max runs
            if task.max_runs and task.run_count >= task.max_runs:
                task.enabled = False
                logger.info(f"Task {task.name} reached max runs, disabled")
            else:
                # Schedule next run
                task.next_run = self._calculate_next_run(task.schedule)
                
        except Exception as e:
            logger.error(f"Task execution failed: {task.name} - {e}")
            # Still schedule next run to avoid getting stuck
            task.next_run = self._calculate_next_run(task.schedule)
    
    def _calculate_next_run(self, schedule: str) -> float:
        """
        Calculate next execution time from schedule.
        
        Supports:
        - Interval: "300s", "5m", "1h"
        - Cron: "*/5 * * * *"
        """
        current_time = time.time()
        
        # Try parsing as interval
        if schedule.endswith('s'):
            try:
                seconds = int(schedule[:-1])
                return current_time + seconds
            except ValueError:
                pass
        
        if schedule.endswith('m'):
            try:
                minutes = int(schedule[:-1])
                return current_time + (minutes * 60)
            except ValueError:
                pass
        
        if schedule.endswith('h'):
            try:
                hours = int(schedule[:-1])
                return current_time + (hours * 3600)
            except ValueError:
                pass
        
        # Try cron expression (simplified)
        # For full cron support, use croniter library
        try:
            from croniter import croniter
            itr = croniter(schedule, datetime.now())
            next_dt = itr.get_next(datetime)
            return next_dt.timestamp()
        except ImportError:
            logger.warning("croniter not installed, using default 5min interval")
            return current_time + 300
        except Exception as e:
            logger.error(f"Failed to parse schedule '{schedule}': {e}")
            return current_time + 300
    
    def list_tasks(self) -> List[Dict]:
        """List all scheduled tasks."""
        with self._lock:
            return [
                {
                    "task_id": t.task_id,
                    "name": t.name,
                    "schedule": t.schedule,
                    "enabled": t.enabled,
                    "priority": t.priority.name,
                    "last_run": t.last_run,
                    "next_run": t.next_run,
                    "run_count": t.run_count,
                }
                for t in self._tasks.values()
            ]
    
    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """Get status of a specific task."""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return None
            
            return {
                "task_id": task.task_id,
                "name": task.name,
                "enabled": task.enabled,
                "last_run": task.last_run,
                "next_run": task.next_run,
                "run_count": task.run_count,
            }


class PollingScheduler:
    """
    Specialized scheduler for device polling.
    """
    
    def __init__(self, task_scheduler: TaskScheduler):
        self.scheduler = task_scheduler
        self._poll_callbacks: Dict[str, Callable] = {}
    
    def schedule_device_poll(
        self,
        device_id: str,
        interval_seconds: int,
        poll_callback: Callable
    ) -> str:
        """
        Schedule regular polling for a device.
        
        Args:
            device_id: Device to poll
            interval_seconds: Polling interval
            poll_callback: Function to call for polling
        
        Returns:
            Task ID
        """
        task_id = f"poll_{device_id}"
        
        self._poll_callbacks[device_id] = poll_callback
        
        self.scheduler.add_task(
            task_id=task_id,
            name=f"Poll {device_id}",
            schedule=f"{interval_seconds}s",
            callback=poll_callback,
            priority=TaskPriority.NORMAL
        )
        
        return task_id
    
    def unschedule_device_poll(self, device_id: str) -> bool:
        """Remove polling schedule for a device."""
        task_id = f"poll_{device_id}"
        return self.scheduler.remove_task(task_id)
    
    def update_poll_interval(
        self,
        device_id: str,
        new_interval: int
    ) -> bool:
        """Update polling interval for a device."""
        # Remove old schedule
        self.unschedule_device_poll(device_id)
        
        # Get callback
        callback = self._poll_callbacks.get(device_id)
        if not callback:
            return False
        
        # Add new schedule
        self.schedule_device_poll(device_id, new_interval, callback)
        return True
