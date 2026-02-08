from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Callable


class WorkflowStage(Enum):
    """Workflow pipeline stages."""
    OBSERVE = "observe"
    COLLECT = "collect"
    NORMALIZE = "normalize"
    ANALYZE = "analyze"
    CORRELATE = "correlate"
    ALERT = "alert"
    REPORT = "report"
    COMPLETED = "completed"
    FAILED = "failed"


STAGE_ORDER = [
    WorkflowStage.OBSERVE,
    WorkflowStage.COLLECT,
    WorkflowStage.NORMALIZE,
    WorkflowStage.ANALYZE,
    WorkflowStage.CORRELATE,
    WorkflowStage.ALERT,
    WorkflowStage.REPORT,
    WorkflowStage.COMPLETED,
]


@dataclass
class StageResult:
    """Result from a workflow stage execution."""
    stage: WorkflowStage
    success: bool
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    started_at: str
    completed_at: str
    duration_sec: float
    error: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowPipeline:
    """A single workflow pipeline instance."""
    pipeline_id: str
    device_id: str
    current_stage: WorkflowStage
    stage_results: List[StageResult]
    context: Dict[str, Any]
    created_at: str
    updated_at: str
    status: str  # running, completed, failed


class WorkflowOrchestrator:
    """
    Orchestrate the NOC workflow pipeline:
    OBSERVE → COLLECT → NORMALIZE → ANALYZE → CORRELATE → ALERT → REPORT
    """
    
    def __init__(
        self,
        discovery_engine=None,
        collectors=None,
        plugin_loader=None,
        ai_engine=None,
        correlation_engine=None,
        alerting_engine=None,
        reporting_engine=None,
    ):
        self.discovery_engine = discovery_engine
        self.collectors = collectors or {}
        self.plugin_loader = plugin_loader
        self.ai_engine = ai_engine
        self.correlation_engine = correlation_engine
        self.alerting_engine = alerting_engine
        self.reporting_engine = reporting_engine
        
        # Stage handlers
        self._stage_handlers: Dict[WorkflowStage, Callable] = {
            WorkflowStage.OBSERVE: self._execute_observe,
            WorkflowStage.COLLECT: self._execute_collect,
            WorkflowStage.NORMALIZE: self._execute_normalize,
            WorkflowStage.ANALYZE: self._execute_analyze,
            WorkflowStage.CORRELATE: self._execute_correlate,
            WorkflowStage.ALERT: self._execute_alert,
            WorkflowStage.REPORT: self._execute_report,
        }
        
        # Pipeline registry
        self._pipelines: Dict[str, WorkflowPipeline] = {}
        self._hooks: Dict[WorkflowStage, List[Callable]] = {stage: [] for stage in WorkflowStage}
    
    def create_pipeline(
        self,
        device_id: str,
        initial_context: Optional[Dict[str, Any]] = None
    ) -> WorkflowPipeline:
        """Create a new workflow pipeline."""
        now = datetime.now(timezone.utc).isoformat()
        
        pipeline = WorkflowPipeline(
            pipeline_id=f"PIPE-{uuid.uuid4().hex[:12].upper()}",
            device_id=device_id,
            current_stage=WorkflowStage.OBSERVE,
            stage_results=[],
            context=initial_context or {},
            created_at=now,
            updated_at=now,
            status="pending",
        )
        
        self._pipelines[pipeline.pipeline_id] = pipeline
        return pipeline
    
    def run_pipeline(
        self,
        pipeline_id: str,
        skip_stages: Optional[List[WorkflowStage]] = None
    ) -> WorkflowPipeline:
        """
        Execute the complete workflow pipeline.
        Enforces strict stage ordering: OBSERVE → COLLECT → NORMALIZE → ANALYZE → CORRELATE → ALERT → REPORT
        """
        pipeline = self._pipelines.get(pipeline_id)
        if not pipeline:
            raise ValueError(f"Pipeline {pipeline_id} not found")
        
        skip_stages = skip_stages or []
        pipeline.status = "running"
        
        try:
            # Execute each stage in order
            for stage in STAGE_ORDER:
                if stage in [WorkflowStage.COMPLETED, WorkflowStage.FAILED]:
                    continue
                
                if stage in skip_stages:
                    continue
                
                # Check if we can proceed (previous stage must be complete)
                if not self._can_proceed_to_stage(pipeline, stage):
                    raise WorkflowError(
                        f"Cannot proceed to {stage.value}: previous stage not complete or failed"
                    )
                
                # Execute stage
                pipeline.current_stage = stage
                result = self._execute_stage(pipeline, stage)
                pipeline.stage_results.append(result)
                pipeline.updated_at = datetime.now(timezone.utc).isoformat()
                
                # If stage failed, mark pipeline failed and stop
                if not result.success:
                    pipeline.status = "failed"
                    return pipeline
            
            # All stages complete
            pipeline.current_stage = WorkflowStage.COMPLETED
            pipeline.status = "completed"
            
        except Exception as e:
            pipeline.status = "failed"
            pipeline.context["error"] = str(e)
            raise
        
        return pipeline
    
    def _can_proceed_to_stage(
        self,
        pipeline: WorkflowPipeline,
        target_stage: WorkflowStage
    ) -> bool:
        """Check if pipeline can proceed to target stage."""
        if target_stage == WorkflowStage.OBSERVE:
            return True  # First stage always allowed
        
        # Find previous stage
        target_idx = STAGE_ORDER.index(target_stage)
        prev_stage = STAGE_ORDER[target_idx - 1]
        
        # Check if previous stage completed successfully
        for result in pipeline.stage_results:
            if result.stage == prev_stage:
                return result.success
        
        return False
    
    def _execute_stage(
        self,
        pipeline: WorkflowPipeline,
        stage: WorkflowStage
    ) -> StageResult:
        """Execute a single workflow stage."""
        started_at = time.time()
        started_iso = datetime.now(timezone.utc).isoformat()
        
        # Get input from previous stage
        input_data = self._get_stage_input(pipeline, stage)
        
        try:
            # Execute pre-hooks
            for hook in self._hooks.get(stage, []):
                hook(pipeline, stage, "pre")
            
            # Execute stage handler
            handler = self._stage_handlers.get(stage)
            if not handler:
                raise WorkflowError(f"No handler for stage {stage.value}")
            
            output_data = handler(pipeline, input_data)
            
            # Execute post-hooks
            for hook in self._hooks.get(stage, []):
                hook(pipeline, stage, "post")
            
            completed_at = time.time()
            
            return StageResult(
                stage=stage,
                success=True,
                input_data=input_data,
                output_data=output_data,
                started_at=started_iso,
                completed_at=datetime.now(timezone.utc).isoformat(),
                duration_sec=round(completed_at - started_at, 3),
            )
            
        except Exception as e:
            completed_at = time.time()
            
            return StageResult(
                stage=stage,
                success=False,
                input_data=input_data,
                output_data={},
                started_at=started_iso,
                completed_at=datetime.now(timezone.utc).isoformat(),
                duration_sec=round(completed_at - started_at, 3),
                error=str(e),
            )
    
    def _get_stage_input(
        self,
        pipeline: WorkflowPipeline,
        stage: WorkflowStage
    ) -> Dict[str, Any]:
        """Get input data for a stage from previous stage output."""
        if stage == WorkflowStage.OBSERVE:
            # OBSERVE gets device info from context
            return {
                "device_id": pipeline.device_id,
                "device_config": pipeline.context.get("device_config", {}),
            }
        
        # Get output from previous stage
        stage_idx = STAGE_ORDER.index(stage)
        prev_stage = STAGE_ORDER[stage_idx - 1]
        
        for result in pipeline.stage_results:
            if result.stage == prev_stage:
                return result.output_data
        
        return {}
    
    # Stage Implementation Methods
    
    def _execute_observe(
        self,
        pipeline: WorkflowPipeline,
        input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        STAGE 1: OBSERVE
        - Discover device if needed
        - Detect OS type
        - Validate device accessibility
        """
        device_id = input_data["device_id"]
        device_config = input_data.get("device_config", {})
        
        output = {
            "device_id": device_id,
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "discovery_method": None,
            "os_detected": None,
            "os_confidence": 0.0,
        }
        
        # If discovery engine available, try OS detection
        if self.discovery_engine:
            host = device_config.get("host")
            if host:
                detection_result = self.discovery_engine.detect_os(
                    host,
                    device_config.get("transport", "ssh"),
                    device_config.get("port", 22)
                )
                output["os_detected"] = detection_result.get("os")
                output["os_confidence"] = detection_result.get("confidence", 0.0)
                output["discovery_method"] = detection_result.get("method", "unknown")
        
        # Use configured OS if detection failed or not available
        if not output["os_detected"]:
            output["os_detected"] = device_config.get("os", "unknown")
            output["os_confidence"] = 1.0 if device_config.get("os") else 0.0
            output["discovery_method"] = "config"
        
        # Store in pipeline context for later stages
        pipeline.context["os_type"] = output["os_detected"]
        
        return output
    
    def _execute_collect(
        self,
        pipeline: WorkflowPipeline,
        input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        STAGE 2: COLLECT
        - Connect to device via SSH/Telnet
        - Execute commands from plugin command_map
        - Handle connection errors and retries
        """
        device_id = input_data["device_id"]
        device_config = input_data.get("device_config", {})
        os_type = pipeline.context.get("os_type", device_config.get("os", "unknown"))
        
        output = {
            "device_id": device_id,
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "os_type": os_type,
            "commands_executed": 0,
            "outputs": {},
            "errors": {},
            "collection_time_sec": 0.0,
        }
        
        if os_type == "unknown":
            raise WorkflowError("Cannot collect: OS type unknown")
        
        # Load plugin to get commands
        if not self.plugin_loader:
            raise WorkflowError("Plugin loader not configured")
        
        plugin = self.plugin_loader.load(os_type)
        commands = plugin.get_commands()
        
        # Get collector
        transport = device_config.get("transport", "ssh")
        collector = self.collectors.get(transport)
        
        if not collector:
            raise WorkflowError(f"Collector for {transport} not available")
        
        # Execute collection
        start_time = time.time()
        
        outputs, errors = collector.run_commands(
            host=device_config.get("host"),
            username=device_config.get("username"),
            password=device_config.get("password"),
            commands=commands,
        )
        
        output["outputs"] = outputs
        output["errors"] = errors
        output["commands_executed"] = len(commands)
        output["collection_time_sec"] = round(time.time() - start_time, 3)
        
        return output
    
    def _execute_normalize(
        self,
        pipeline: WorkflowPipeline,
        input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        STAGE 3: NORMALIZE
        - Parse CLI outputs using plugin parser
        - Normalize to standard variable schema
        - Extract metrics with proper units
        """
        device_id = input_data["device_id"]
        os_type = input_data.get("os_type", "unknown")
        outputs = input_data.get("outputs", {})
        errors = input_data.get("errors", {})
        
        output = {
            "device_id": device_id,
            "normalized_at": datetime.now(timezone.utc).isoformat(),
            "os_type": os_type,
            "metrics": [],
            "variables": {},
            "parse_errors": [],
        }
        
        if os_type == "unknown":
            raise WorkflowError("Cannot normalize: OS type unknown")
        
        # Load plugin and parse
        plugin = self.plugin_loader.load(os_type)
        
        device_config = {
            "id": device_id,
            "os": os_type,
        }
        
        parse_result = plugin.parse(outputs, errors, device_config)
        
        output["metrics"] = parse_result.get("metrics", [])
        output["variables"] = parse_result.get("variables", {})
        output["raw_outputs"] = outputs  # Keep for correlation
        
        return output
    
    def _execute_analyze(
        self,
        pipeline: WorkflowPipeline,
        input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        STAGE 4: ANALYZE (AI)
        - Run threshold checks
        - Detect anomalies
        - Calculate health scores
        - Generate predictions
        """
        device_id = input_data["device_id"]
        metrics = input_data.get("metrics", [])
        os_type = input_data.get("os_type", "unknown")
        
        output = {
            "device_id": device_id,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
            "ai_findings": [],
            "alerts_generated": [],
            "health_score": 100.0,
            "anomaly_count": 0,
        }
        
        if not self.ai_engine:
            # Pass-through if no AI engine
            output["ai_findings"] = [{"type": "info", "message": "AI engine not configured"}]
            return output
        
        # Analyze each metric
        for metric in metrics:
            variable = metric.get("variable")
            value = metric.get("value")
            
            if variable and value is not None:
                # Run AI detection
                ai_result = self.ai_engine.analyze(
                    device_id=device_id,
                    variable=variable,
                    value=value,
                    os_type=os_type,
                )
                
                if ai_result.get("findings"):
                    output["ai_findings"].extend(ai_result["findings"])
                
                if ai_result.get("alert"):
                    output["alerts_generated"].append(ai_result["alert"])
        
        # Calculate overall health
        if output["alerts_generated"]:
            critical_count = sum(
                1 for a in output["alerts_generated"]
                if a.get("severity") == "critical"
            )
            output["health_score"] = max(0, 100 - (critical_count * 25))
            output["anomaly_count"] = len(output["alerts_generated"])
        
        return output
    
    def _execute_correlate(
        self,
        pipeline: WorkflowPipeline,
        input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        STAGE 5: CORRELATE
        - Find related incidents
        - Build impact chains
        - Identify root causes
        """
        device_id = input_data["device_id"]
        alerts = input_data.get("alerts_generated", [])
        ai_findings = input_data.get("ai_findings", [])
        
        output = {
            "device_id": device_id,
            "correlated_at": datetime.now(timezone.utc).isoformat(),
            "incidents": [],
            "related_devices": [],
            "root_causes": [],
            "impact_chains": [],
        }
        
        if not self.correlation_engine:
            return output
        
        # Correlate alerts into incidents
        for alert in alerts:
            incident = self.correlation_engine.find_or_create_incident(
                alert=alert,
                device_id=device_id,
            )
            
            if incident:
                output["incidents"].append(incident)
        
        # Find related devices and impact chains
        impact_analysis = self.correlation_engine.analyze_impact(
            source_device=device_id,
            alerts=alerts,
        )
        
        output["related_devices"] = impact_analysis.get("related_devices", [])
        output["impact_chains"] = impact_analysis.get("impact_chains", [])
        output["root_causes"] = impact_analysis.get("root_causes", [])
        
        return output
    
    def _execute_alert(
        self,
        pipeline: WorkflowPipeline,
        input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        STAGE 6: ALERT
        - Deduplicate alerts
        - Apply routing rules
        - Send notifications
        - Create audit trail
        """
        device_id = input_data["device_id"]
        alerts = input_data.get("alerts_generated", [])
        incidents = input_data.get("incidents", [])
        
        output = {
            "device_id": device_id,
            "alerted_at": datetime.now(timezone.utc).isoformat(),
            "alerts_processed": len(alerts),
            "alerts_sent": 0,
            "alerts_suppressed": 0,
            "notifications": [],
        }
        
        if not self.alerting_engine:
            return output
        
        # Process each alert
        for alert in alerts:
            # Check deduplication
            if self.alerting_engine.is_duplicate(alert):
                output["alerts_suppressed"] += 1
                continue
            
            # Apply routing
            route_result = self.alerting_engine.route_alert(alert)
            
            # Send notifications
            for channel in route_result.get("channels", []):
                notification = self.alerting_engine.send_notification(
                    alert=alert,
                    channel=channel,
                )
                output["notifications"].append(notification)
            
            output["alerts_sent"] += 1
        
        return output
    
    def _execute_report(
        self,
        pipeline: WorkflowPipeline,
        input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        STAGE 7: REPORT
        - Generate metrics summary
        - Update dashboard data
        - Log to time-series storage
        """
        device_id = input_data["device_id"]
        metrics = pipeline.stage_results[2].output_data.get("metrics", []) if len(pipeline.stage_results) > 2 else []
        health_score = input_data.get("health_score", 100.0)
        
        output = {
            "device_id": device_id,
            "reported_at": datetime.now(timezone.utc).isoformat(),
            "metrics_stored": 0,
            "report_generated": False,
            "dashboard_updated": False,
        }
        
        if not self.reporting_engine:
            return output
        
        # Store metrics
        for metric in metrics:
            self.reporting_engine.store_metric(
                device_id=device_id,
                timestamp=output["reported_at"],
                variable=metric.get("variable"),
                value=metric.get("value"),
            )
            output["metrics_stored"] += 1
        
        # Update dashboard
        self.reporting_engine.update_dashboard(
            device_id=device_id,
            health_score=health_score,
            metrics=metrics,
        )
        output["dashboard_updated"] = True
        
        return output
    
    # Hooks and Utilities
    
    def add_hook(
        self,
        stage: WorkflowStage,
        hook: Callable[[WorkflowPipeline, WorkflowStage, str], None]
    ):
        """Add a pre/post hook for a stage."""
        self._hooks[stage].append(hook)
    
    def get_pipeline_status(self, pipeline_id: str) -> Optional[Dict[str, Any]]:
        """Get current status of a pipeline."""
        pipeline = self._pipelines.get(pipeline_id)
        if not pipeline:
            return None
        
        return {
            "pipeline_id": pipeline.pipeline_id,
            "device_id": pipeline.device_id,
            "current_stage": pipeline.current_stage.value,
            "status": pipeline.status,
            "stages_completed": len(pipeline.stage_results),
            "stages_total": len(STAGE_ORDER) - 2,  # Exclude COMPLETED/FAILED
            "created_at": pipeline.created_at,
            "updated_at": pipeline.updated_at,
            "stage_results": [
                {
                    "stage": r.stage.value,
                    "success": r.success,
                    "duration_sec": r.duration_sec,
                    "error": r.error,
                }
                for r in pipeline.stage_results
            ],
        }
    
    def get_pipeline_metrics(self, pipeline_id: str) -> Dict[str, Any]:
        """Get aggregated metrics from pipeline execution."""
        pipeline = self._pipelines.get(pipeline_id)
        if not pipeline:
            return {}
        
        total_duration = sum(
            r.duration_sec for r in pipeline.stage_results if r.success
        )
        
        return {
            "pipeline_id": pipeline_id,
            "total_duration_sec": round(total_duration, 3),
            "stage_durations": {
                r.stage.value: r.duration_sec
                for r in pipeline.stage_results
            },
            "metrics_collected": pipeline.stage_results[2].output_data.get("metrics", []) if len(pipeline.stage_results) > 2 else [],
            "alerts_generated": pipeline.stage_results[4].output_data.get("alerts_generated", []) if len(pipeline.stage_results) > 4 else [],
        }


class WorkflowError(Exception):
    """Workflow execution error."""
    pass
