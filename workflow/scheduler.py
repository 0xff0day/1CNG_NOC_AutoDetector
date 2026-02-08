from __future__ import annotations

import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Callable

from workflow.orchestrator import WorkflowOrchestrator, WorkflowPipeline, WorkflowStage


class WorkflowScheduler:
    """
    Schedule and execute workflows for multiple devices.
    Integrates with the orchestrator to run the full pipeline.
    """
    
    def __init__(
        self,
        orchestrator: WorkflowOrchestrator,
        max_concurrent: int = 10,
        poll_interval_sec: float = 60.0,
    ):
        self.orchestrator = orchestrator
        self.max_concurrent = max_concurrent
        self.poll_interval_sec = poll_interval_sec
        
        self._running = False
        self._scheduler_thread: Optional[threading.Thread] = None
        self._executor = ThreadPoolExecutor(max_workers=max_concurrent)
        self._scheduled_devices: Dict[str, Dict[str, Any]] = {}
        self._last_run: Dict[str, str] = {}
        self._callbacks: List[Callable[[str, str, Dict[str, Any]], None]] = []
    
    def schedule_device(
        self,
        device_id: str,
        device_config: Dict[str, Any],
        interval_sec: Optional[float] = None,
    ):
        """Schedule a device for regular workflow execution."""
        self._scheduled_devices[device_id] = {
            "device_id": device_id,
            "config": device_config,
            "interval_sec": interval_sec or self.poll_interval_sec,
            "last_run": None,
            "enabled": True,
        }
    
    def unschedule_device(self, device_id: str):
        """Remove device from schedule."""
        if device_id in self._scheduled_devices:
            del self._scheduled_devices[device_id]
    
    def start(self):
        """Start the scheduler loop."""
        if self._running:
            return
        
        self._running = True
        self._scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self._scheduler_thread.start()
    
    def stop(self):
        """Stop the scheduler loop."""
        self._running = False
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=5.0)
        self._executor.shutdown(wait=True)
    
    def _scheduler_loop(self):
        """Main scheduler loop."""
        while self._running:
            try:
                self._run_scheduled_devices()
                time.sleep(1.0)  # Check every second
            except Exception as e:
                print(f"Scheduler error: {e}")
                time.sleep(5.0)
    
    def _run_scheduled_devices(self):
        """Run workflows for devices that are due."""
        now = datetime.now(timezone.utc)
        
        devices_to_run = []
        
        for device_id, schedule in self._scheduled_devices.items():
            if not schedule["enabled"]:
                continue
            
            last_run = schedule.get("last_run")
            interval = schedule["interval_sec"]
            
            if last_run is None:
                # Never run, add to queue
                devices_to_run.append(device_id)
            else:
                last_run_dt = datetime.fromisoformat(last_run)
                elapsed = (now - last_run_dt).total_seconds()
                
                if elapsed >= interval:
                    devices_to_run.append(device_id)
        
        # Run workflows in parallel
        if devices_to_run:
            self._run_parallel(devices_to_run)
    
    def _run_parallel(self, device_ids: List[str]):
        """Run workflows for multiple devices in parallel."""
        futures = {}
        
        for device_id in device_ids:
            schedule = self._scheduled_devices.get(device_id)
            if not schedule:
                continue
            
            future = self._executor.submit(
                self._run_single_device,
                device_id,
                schedule["config"],
            )
            futures[future] = device_id
        
        # Process results as they complete
        for future in as_completed(futures):
            device_id = futures[future]
            try:
                result = future.result()
                self._on_complete(device_id, result)
            except Exception as e:
                self._on_error(device_id, str(e))
    
    def _run_single_device(
        self,
        device_id: str,
        device_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Run complete workflow for a single device."""
        # Create pipeline
        pipeline = self.orchestrator.create_pipeline(
            device_id=device_id,
            initial_context={"device_config": device_config},
        )
        
        # Execute full workflow
        completed_pipeline = self.orchestrator.run_pipeline(pipeline.pipeline_id)
        
        # Return results
        return {
            "pipeline_id": completed_pipeline.pipeline_id,
            "status": completed_pipeline.status,
            "stage_count": len(completed_pipeline.stage_results),
            "current_stage": completed_pipeline.current_stage.value,
        }
    
    def _on_complete(self, device_id: str, result: Dict[str, Any]):
        """Handle workflow completion."""
        # Update last run time
        if device_id in self._scheduled_devices:
            self._scheduled_devices[device_id]["last_run"] = datetime.now(timezone.utc).isoformat()
            self._scheduled_devices[device_id]["last_result"] = result
        
        # Notify callbacks
        for callback in self._callbacks:
            try:
                callback(device_id, "complete", result)
            except Exception:
                pass
    
    def _on_error(self, device_id: str, error: str):
        """Handle workflow error."""
        if device_id in self._scheduled_devices:
            self._scheduled_devices[device_id]["last_error"] = error
        
        for callback in self._callbacks:
            try:
                callback(device_id, "error", {"error": error})
            except Exception:
                pass
    
    def on_complete(self, callback: Callable[[str, str, Dict[str, Any]], None]):
        """Register completion callback."""
        self._callbacks.append(callback)
    
    def run_manual(
        self,
        device_ids: List[str],
        skip_stages: Optional[List[WorkflowStage]] = None,
    ) -> List[Dict[str, Any]]:
        """Manually trigger workflows for devices."""
        results = []
        
        for device_id in device_ids:
            schedule = self._scheduled_devices.get(device_id)
            if not schedule:
                continue
            
            pipeline = self.orchestrator.create_pipeline(
                device_id=device_id,
                initial_context={"device_config": schedule["config"]},
            )
            
            completed = self.orchestrator.run_pipeline(
                pipeline.pipeline_id,
                skip_stages=skip_stages,
            )
            
            results.append({
                "device_id": device_id,
                "pipeline_id": completed.pipeline_id,
                "status": completed.status,
                "stages": [
                    {
                        "stage": r.stage.value,
                        "success": r.success,
                        "duration_sec": r.duration_sec,
                    }
                    for r in completed.stage_results
                ],
            })
        
        return results
    
    def get_status(self) -> Dict[str, Any]:
        """Get scheduler status."""
        return {
            "running": self._running,
            "scheduled_devices": len(self._scheduled_devices),
            "max_concurrent": self.max_concurrent,
            "poll_interval_sec": self.poll_interval_sec,
            "devices": [
                {
                    "device_id": d["device_id"],
                    "enabled": d["enabled"],
                    "interval_sec": d["interval_sec"],
                    "last_run": d.get("last_run"),
                    "last_status": d.get("last_result", {}).get("status", "unknown"),
                }
                for d in self._scheduled_devices.values()
            ],
        }


class WorkflowStateManager:
    """Manage and persist workflow state."""
    
    def __init__(self, storage=None):
        self.storage = storage
        self._state_cache: Dict[str, Dict[str, Any]] = {}
    
    def save_pipeline_state(self, pipeline: WorkflowPipeline):
        """Save pipeline state to storage."""
        state = {
            "pipeline_id": pipeline.pipeline_id,
            "device_id": pipeline.device_id,
            "current_stage": pipeline.current_stage.value,
            "status": pipeline.status,
            "stage_results": [
                {
                    "stage": r.stage.value,
                    "success": r.success,
                    "duration_sec": r.duration_sec,
                    "error": r.error,
                    "started_at": r.started_at,
                    "completed_at": r.completed_at,
                }
                for r in pipeline.stage_results
            ],
            "context": pipeline.context,
            "created_at": pipeline.created_at,
            "updated_at": pipeline.updated_at,
        }
        
        self._state_cache[pipeline.pipeline_id] = state
        
        if self.storage:
            self.storage.store_workflow_state(pipeline.pipeline_id, state)
    
    def load_pipeline_state(self, pipeline_id: str) -> Optional[Dict[str, Any]]:
        """Load pipeline state from storage."""
        # Check cache first
        if pipeline_id in self._state_cache:
            return self._state_cache[pipeline_id]
        
        # Load from storage
        if self.storage:
            state = self.storage.load_workflow_state(pipeline_id)
            if state:
                self._state_cache[pipeline_id] = state
            return state
        
        return None
    
    def get_device_workflow_history(
        self,
        device_id: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get workflow history for a device."""
        if not self.storage:
            return []
        
        return self.storage.query_workflow_history(
            device_id=device_id,
            limit=limit,
        )
    
    def get_failed_pipelines(
        self,
        since: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get list of failed pipelines."""
        # Filter from cache
        failed = [
            state for state in self._state_cache.values()
            if state.get("status") == "failed"
        ]
        
        if since and self.storage:
            # Query from storage for historical data
            stored = self.storage.query_workflow_history(
                status="failed",
                since=since,
            )
            # Merge with cache (avoiding duplicates)
            seen_ids = {f["pipeline_id"] for f in failed}
            for f in stored:
                if f["pipeline_id"] not in seen_ids:
                    failed.append(f)
        
        return sorted(
            failed,
            key=lambda x: x.get("updated_at", ""),
            reverse=True,
        )
