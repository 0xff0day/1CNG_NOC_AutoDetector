from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from workflow.orchestrator import WorkflowOrchestrator, WorkflowStage
from workflow.scheduler import WorkflowScheduler, WorkflowStateManager


class WorkflowCLI:
    """CLI commands for workflow management."""
    
    def __init__(
        self,
        orchestrator: WorkflowOrchestrator,
        scheduler: WorkflowScheduler,
        state_manager: WorkflowStateManager,
    ):
        self.orchestrator = orchestrator
        self.scheduler = scheduler
        self.state_manager = state_manager
    
    def cmd_workflow_run(
        self,
        device_ids: List[str],
        skip_stages: Optional[List[str]] = None,
        verbose: bool = False,
    ) -> Dict[str, Any]:
        """
        Run workflow pipeline for specified devices.
        Usage: nocctl workflow run --devices r1,r2,r3 [--skip observe] [--verbose]
        """
        # Parse skip stages
        skip = []
        if skip_stages:
            for stage_name in skip_stages:
                try:
                    skip.append(WorkflowStage(stage_name.lower()))
                except ValueError:
                    return {
                        "error": f"Invalid stage: {stage_name}",
                        "valid_stages": [s.value for s in WorkflowStage],
                    }
        
        # Run workflows
        results = self.scheduler.run_manual(device_ids, skip_stages=skip)
        
        output = {
            "command": "workflow run",
            "devices": device_ids,
            "results": [],
            "summary": {
                "total": len(results),
                "succeeded": sum(1 for r in results if r.get("status") == "completed"),
                "failed": sum(1 for r in results if r.get("status") == "failed"),
            },
        }
        
        for result in results:
            item = {
                "device_id": result["device_id"],
                "pipeline_id": result["pipeline_id"],
                "status": result["status"],
                "stages_completed": len(result.get("stages", [])),
            }
            
            if verbose:
                item["stages"] = result.get("stages", [])
            
            output["results"].append(item)
        
        return output
    
    def cmd_workflow_status(
        self,
        pipeline_id: Optional[str] = None,
        device_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Check workflow status.
        Usage: nocctl workflow status [--pipeline PIPELINE_ID] [--device DEVICE_ID]
        """
        if pipeline_id:
            status = self.orchestrator.get_pipeline_status(pipeline_id)
            if not status:
                return {"error": f"Pipeline {pipeline_id} not found"}
            return status
        
        if device_id:
            # Get recent pipelines for device
            history = self.state_manager.get_device_workflow_history(device_id, limit=5)
            return {
                "device_id": device_id,
                "recent_pipelines": history,
            }
        
        # Return scheduler status
        return self.scheduler.get_status()
    
    def cmd_workflow_trace(
        self,
        pipeline_id: str,
    ) -> Dict[str, Any]:
        """
        Trace complete workflow execution with all stage details.
        Usage: nocctl workflow trace PIPELINE_ID
        """
        pipeline = self.orchestrator._pipelines.get(pipeline_id)
        if not pipeline:
            return {"error": f"Pipeline {pipeline_id} not found"}
        
        trace = {
            "pipeline_id": pipeline_id,
            "device_id": pipeline.device_id,
            "status": pipeline.status,
            "created_at": pipeline.created_at,
            "updated_at": pipeline.updated_at,
            "stages": [],
        }
        
        for i, result in enumerate(pipeline.stage_results):
            stage_info = {
                "sequence": i + 1,
                "stage": result.stage.value,
                "status": "success" if result.success else "failed",
                "duration_sec": result.duration_sec,
                "started_at": result.started_at,
                "completed_at": result.completed_at,
            }
            
            if result.error:
                stage_info["error"] = result.error
            
            # Include output summary
            stage_info["output_summary"] = self._summarize_output(
                result.stage,
                result.output_data,
            )
            
            trace["stages"].append(stage_info)
        
        return trace
    
    def cmd_workflow_history(
        self,
        device_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """
        Show workflow execution history.
        Usage: nocctl workflow history [--device DEVICE_ID] [--status failed] [--limit 50]
        """
        if device_id:
            history = self.state_manager.get_device_workflow_history(device_id, limit)
        else:
            # Get recent workflows from all devices
            history = []
            # Would query from storage
        
        if status:
            history = [h for h in history if h.get("status") == status]
        
        return {
            "history": history[:limit],
            "count": len(history),
        }
    
    def cmd_workflow_schedule(
        self,
        device_id: str,
        interval_sec: Optional[float] = None,
        enable: bool = True,
    ) -> Dict[str, Any]:
        """
        Schedule or unschedule device for automatic workflow runs.
        Usage: nocctl workflow schedule DEVICE_ID [--interval 60] [--enable|--disable]
        """
        if enable:
            # Get device config from somewhere
            device_config = {"id": device_id}  # Would load from config
            
            self.scheduler.schedule_device(
                device_id=device_id,
                device_config=device_config,
                interval_sec=interval_sec,
            )
            
            return {
                "device_id": device_id,
                "scheduled": True,
                "interval_sec": interval_sec or self.scheduler.poll_interval_sec,
            }
        else:
            self.scheduler.unschedule_device(device_id)
            return {
                "device_id": device_id,
                "scheduled": False,
            }
    
    def cmd_workflow_diagram(
        self,
        format: str = "text",
    ) -> str:
        """
        Generate workflow pipeline diagram.
        Usage: nocctl workflow diagram [--format mermaid|graphviz|text]
        """
        stages = [
            "OBSERVE",
            "COLLECT",
            "NORMALIZE",
            "ANALYZE (AI)",
            "CORRELATE",
            "ALERT",
            "REPORT",
        ]
        
        if format == "text":
            lines = [
                "NOC Workflow Pipeline",
                "=" * 50,
                "",
            ]
            
            for i, stage in enumerate(stages, 1):
                lines.append(f"  [{i}] {stage}")
                if i < len(stages):
                    lines.append("       ↓")
            
            lines.extend([
                "",
                "=" * 50,
                "Stages enforce strict ordering and data contracts",
                "Each stage output becomes next stage input",
            ])
            
            return "\n".join(lines)
        
        elif format == "mermaid":
            return """
flowchart LR
    OBS[OBSERVE<br/>Discovery/OS Detection] --> COL[COLLECT<br/>SSH/Telnet Collection]
    COL --> NORM[NORMALIZE<br/>Plugin Parsing]
    NORM --> AI[ANALYZE<br/>AI Detection]
    AI --> CORR[CORRELATE<br/>Incident Clustering]
    CORR --> ALERT[ALERT<br/>Notification]
    ALERT --> REP[REPORT<br/>Metrics Storage]
    
    style OBS fill:#e1f5fe
    style COL fill:#e8f5e9
    style NORM fill:#fff3e0
    style AI fill:#fce4ec
    style CORR fill:#f3e5f5
    style ALERT fill:#ffebee
    style REP fill:#e8eaf6
""".strip()
        
        elif format == "graphviz":
            return """
digraph Workflow {
    rankdir=LR;
    node [shape=box, style="rounded,filled", fontname="Arial"];
    
    OBSERVE [label="OBSERVE\nDiscovery", fillcolor="#e1f5fe"];
    COLLECT [label="COLLECT\nSSH/Telnet", fillcolor="#e8f5e9"];
    NORMALIZE [label="NORMALIZE\nParsing", fillcolor="#fff3e0"];
    ANALYZE [label="ANALYZE\nAI Detection", fillcolor="#fce4ec"];
    CORRELATE [label="CORRELATE\nClustering", fillcolor="#f3e5f5"];
    ALERT [label="ALERT\nNotify", fillcolor="#ffebee"];
    REPORT [label="REPORT\nStorage", fillcolor="#e8eaf6"];
    
    OBSERVE -> COLLECT -> NORMALIZE -> ANALYZE -> CORRELATE -> ALERT -> REPORT;
}
""".strip()
        
        else:
            return f"Unknown format: {format}"
    
    def _summarize_output(
        self,
        stage: WorkflowStage,
        output: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create summary of stage output."""
        summaries = {
            WorkflowStage.OBSERVE: lambda o: {
                "os_detected": o.get("os_detected"),
                "confidence": o.get("os_confidence"),
            },
            WorkflowStage.COLLECT: lambda o: {
                "commands": o.get("commands_executed"),
                "time_sec": o.get("collection_time_sec"),
                "errors": len(o.get("errors", {})),
            },
            WorkflowStage.NORMALIZE: lambda o: {
                "metrics": len(o.get("metrics", [])),
                "variables": list(o.get("variables", {}).keys()),
            },
            WorkflowStage.ANALYZE: lambda o: {
                "findings": len(o.get("ai_findings", [])),
                "alerts": len(o.get("alerts_generated", [])),
                "health_score": o.get("health_score"),
            },
            WorkflowStage.CORRELATE: lambda o: {
                "incidents": len(o.get("incidents", [])),
                "related_devices": len(o.get("related_devices", [])),
            },
            WorkflowStage.ALERT: lambda o: {
                "sent": o.get("alerts_sent"),
                "suppressed": o.get("alerts_suppressed"),
            },
            WorkflowStage.REPORT: lambda o: {
                "metrics_stored": o.get("metrics_stored"),
            },
        }
        
        summarizer = summaries.get(stage, lambda o: {})
        return summarizer(output)
