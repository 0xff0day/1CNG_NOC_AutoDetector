from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from workflow.orchestrator import WorkflowStage, WorkflowPipeline


class WorkflowReporter:
    """
    Generate reports and visualizations of workflow execution.
    """
    
    def __init__(self, orchestrator=None, state_manager=None):
        self.orchestrator = orchestrator
        self.state_manager = state_manager
    
    def generate_pipeline_report(
        self,
        pipeline_id: str,
        format: str = "json",
    ) -> str:
        """Generate detailed report of a pipeline execution."""
        if not self.orchestrator:
            return "Orchestrator not available"
        
        pipeline = self.orchestrator._pipelines.get(pipeline_id)
        if not pipeline:
            # Try to load from state manager
            if self.state_manager:
                state = self.state_manager.load_pipeline_state(pipeline_id)
                if state:
                    return self._format_state_report(state, format)
            return f"Pipeline {pipeline_id} not found"
        
        report = self._build_pipeline_report(pipeline)
        
        if format == "json":
            return json.dumps(report, indent=2)
        elif format == "html":
            return self._render_html_report(report)
        elif format == "text":
            return self._render_text_report(report)
        else:
            return f"Unknown format: {format}"
    
    def _build_pipeline_report(self, pipeline: WorkflowPipeline) -> Dict[str, Any]:
        """Build report data structure from pipeline."""
        return {
            "report_type": "workflow_pipeline",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "pipeline": {
                "id": pipeline.pipeline_id,
                "device_id": pipeline.device_id,
                "status": pipeline.status,
                "created_at": pipeline.created_at,
                "updated_at": pipeline.updated_at,
                "duration_sec": self._calculate_total_duration(pipeline),
            },
            "stages": [
                {
                    "sequence": i + 1,
                    "name": result.stage.value,
                    "status": "success" if result.success else "failed",
                    "duration_sec": result.duration_sec,
                    "input_keys": list(result.input_data.keys()),
                    "output_keys": list(result.output_data.keys()),
                    "error": result.error,
                    "metrics": result.metrics,
                }
                for i, result in enumerate(pipeline.stage_results)
            ],
            "summary": {
                "total_stages": len(pipeline.stage_results),
                "successful_stages": sum(1 for r in pipeline.stage_results if r.success),
                "failed_stages": sum(1 for r in pipeline.stage_results if not r.success),
                "current_stage": pipeline.current_stage.value,
            },
            "data_flow": self._trace_data_flow(pipeline),
        }
    
    def _calculate_total_duration(self, pipeline: WorkflowPipeline) -> float:
        """Calculate total pipeline duration."""
        if not pipeline.stage_results:
            return 0.0
        return sum(r.duration_sec for r in pipeline.stage_results)
    
    def _trace_data_flow(self, pipeline: WorkflowPipeline) -> List[Dict[str, Any]]:
        """Trace how data flows through the pipeline stages."""
        flow = []
        
        for i, result in enumerate(pipeline.stage_results):
            flow.append({
                "stage": result.stage.value,
                "receives_from": pipeline.stage_results[i-1].stage.value if i > 0 else None,
                "input_sample": self._sample_data(result.input_data),
                "output_sample": self._sample_data(result.output_data),
            })
        
        return flow
    
    def _sample_data(self, data: Dict[str, Any], max_keys: int = 5) -> Dict[str, Any]:
        """Create sample of data for reporting."""
        sample = {}
        for i, (key, value) in enumerate(data.items()):
            if i >= max_keys:
                break
            # Truncate large values
            val_str = str(value)
            if len(val_str) > 100:
                val_str = val_str[:100] + "..."
            sample[key] = val_str
        return sample
    
    def _format_state_report(self, state: Dict[str, Any], format: str) -> str:
        """Format a loaded state as report."""
        if format == "json":
            return json.dumps(state, indent=2)
        return f"State report for {state.get('pipeline_id')}"
    
    def _render_html_report(self, report: Dict[str, Any]) -> str:
        """Render report as HTML."""
        pipeline = report["pipeline"]
        stages = report["stages"]
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Workflow Report - {pipeline['id']}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        .header {{ background: #f5f5f5; padding: 20px; border-radius: 5px; }}
        .stage {{ margin: 20px 0; padding: 15px; border-left: 4px solid #ccc; }}
        .stage.success {{ border-left-color: #4caf50; }}
        .stage.failed {{ border-left-color: #f44336; }}
        .metric {{ display: inline-block; margin: 5px 15px 5px 0; }}
        .label {{ font-weight: bold; color: #666; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ text-align: left; padding: 8px; border-bottom: 1px solid #ddd; }}
        th {{ background-color: #f5f5f5; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Workflow Pipeline Report</h1>
        <p><span class="label">Pipeline ID:</span> {pipeline['id']}</p>
        <p><span class="label">Device:</span> {pipeline['device_id']}</p>
        <p><span class="label">Status:</span> {pipeline['status']}</p>
        <p><span class="label">Duration:</span> {pipeline['duration_sec']:.3f}s</p>
    </div>
    
    <h2>Stage Execution</h2>
"""
        
        for stage in stages:
            status_class = "success" if stage['status'] == 'success' else 'failed'
            html += f"""
    <div class="stage {status_class}">
        <h3>{stage['sequence']}. {stage['name'].upper()}</h3>
        <p><span class="label">Status:</span> {stage['status']}</p>
        <p><span class="label">Duration:</span> {stage['duration_sec']:.3f}s</p>
        
        <div class="data-flow">
            <p><span class="label">Input:</span> {', '.join(stage['input_keys'])}</p>
            <p><span class="label">Output:</span> {', '.join(stage['output_keys'])}</p>
        </div>
"""
            if stage.get('error'):
                html += f"""
        <div class="error">
            <p style="color: #f44336;"><strong>Error:</strong> {stage['error']}</p>
        </div>
"""
            
            html += "    </div>"
        
        html += """
</body>
</html>
"""
        return html
    
    def _render_text_report(self, report: Dict[str, Any]) -> str:
        """Render report as plain text."""
        lines = []
        
        p = report["pipeline"]
        lines.extend([
            "=" * 60,
            "WORKFLOW PIPELINE REPORT",
            "=" * 60,
            f"Pipeline ID: {p['id']}",
            f"Device:      {p['device_id']}",
            f"Status:      {p['status']}",
            f"Duration:    {p['duration_sec']:.3f}s",
            f"Generated:   {report['generated_at']}",
            "",
            "STAGE EXECUTION",
            "-" * 60,
        ])
        
        for stage in report["stages"]:
            status_icon = "✓" if stage['status'] == 'success' else "✗"
            lines.extend([
                f"",
                f"[{stage['sequence']}] {stage['name'].upper()}",
                f"    Status:   {status_icon} {stage['status']}",
                f"    Duration: {stage['duration_sec']:.3f}s",
                f"    Input:    {', '.join(stage['input_keys'])}",
                f"    Output:   {', '.join(stage['output_keys'])}",
            ])
            if stage.get('error'):
                lines.append(f"    Error:    {stage['error']}")
        
        lines.extend([
            "",
            "=" * 60,
            f"Summary: {report['summary']['successful_stages']}/{report['summary']['total_stages']} stages successful",
            "=" * 60,
        ])
        
        return "\n".join(lines)
    
    def generate_workflow_dashboard(
        self,
        time_range_hours: int = 24,
    ) -> Dict[str, Any]:
        """Generate dashboard data for workflow monitoring."""
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "time_range_hours": time_range_hours,
            "summary": {
                "total_pipelines": 0,
                "successful": 0,
                "failed": 0,
                "in_progress": 0,
            },
            "stage_performance": {
                stage.value: {
                    "avg_duration_sec": 0.0,
                    "success_rate": 1.0,
                    "total_executions": 0,
                }
                for stage in [
                    WorkflowStage.OBSERVE,
                    WorkflowStage.COLLECT,
                    WorkflowStage.NORMALIZE,
                    WorkflowStage.ANALYZE,
                    WorkflowStage.CORRELATE,
                    WorkflowStage.ALERT,
                    WorkflowStage.REPORT,
                ]
            },
            "device_workflows": [],
            "recent_failures": [],
        }
    
    def visualize_workflow_live(
        self,
        pipeline_id: str,
    ) -> str:
        """Generate live ASCII visualization of workflow."""
        if not self.orchestrator:
            return "Orchestrator not available"
        
        pipeline = self.orchestrator._pipelines.get(pipeline_id)
        if not pipeline:
            return f"Pipeline {pipeline_id} not found"
        
        # Build ASCII visualization
        lines = [
            f"Pipeline: {pipeline_id}",
            f"Device:   {pipeline.device_id}",
            f"Status:   {pipeline.status.upper()}",
            "",
            "WORKFLOW PROGRESS",
            "",
        ]
        
        stages = [
            WorkflowStage.OBSERVE,
            WorkflowStage.COLLECT,
            WorkflowStage.NORMALIZE,
            WorkflowStage.ANALYZE,
            WorkflowStage.CORRELATE,
            WorkflowStage.ALERT,
            WorkflowStage.REPORT,
        ]
        
        stage_results = {r.stage: r for r in pipeline.stage_results}
        
        for i, stage in enumerate(stages):
            result = stage_results.get(stage)
            
            if result:
                if result.success:
                    icon = "✓"
                    status = "done"
                    duration = f"({result.duration_sec:.2f}s)"
                else:
                    icon = "✗"
                    status = "FAILED"
                    duration = ""
            elif pipeline.current_stage == stage:
                icon = "▶"
                status = "running..."
                duration = ""
            else:
                icon = "○"
                status = "pending"
                duration = ""
            
            lines.append(f"  {icon} [{stage.value.upper():12}] {status:12} {duration}")
            
            if i < len(stages) - 1:
                lines.append("       ↓")
        
        return "\n".join(lines)


class WorkflowMetricsCollector:
    """Collect metrics about workflow execution."""
    
    def __init__(self, state_manager=None):
        self.state_manager = state_manager
        self.metrics: Dict[str, List[float]] = {
            "stage_durations": [],
            "pipeline_durations": [],
            "success_rates": [],
        }
    
    def record_stage_execution(
        self,
        stage: WorkflowStage,
        duration_sec: float,
        success: bool,
    ):
        """Record stage execution metrics."""
        key = f"stage_{stage.value}_duration"
        if key not in self.metrics:
            self.metrics[key] = []
        self.metrics[key].append(duration_sec)
        
        # Track success/failure
        status_key = f"stage_{stage.value}_success"
        if status_key not in self.metrics:
            self.metrics[status_key] = []
        self.metrics[status_key].append(1.0 if success else 0.0)
    
    def record_pipeline_completion(
        self,
        duration_sec: float,
        success: bool,
    ):
        """Record pipeline completion metrics."""
        self.metrics["pipeline_durations"].append(duration_sec)
        self.metrics["success_rates"].append(1.0 if success else 0.0)
    
    def get_stage_statistics(self, stage: WorkflowStage) -> Dict[str, Any]:
        """Get statistics for a specific stage."""
        duration_key = f"stage_{stage.value}_duration"
        success_key = f"stage_{stage.value}_success"
        
        durations = self.metrics.get(duration_key, [])
        successes = self.metrics.get(success_key, [])
        
        if not durations:
            return {"stage": stage.value, "samples": 0}
        
        import statistics
        
        return {
            "stage": stage.value,
            "samples": len(durations),
            "avg_duration_sec": statistics.mean(durations),
            "median_duration_sec": statistics.median(durations),
            "min_duration_sec": min(durations),
            "max_duration_sec": max(durations),
            "success_rate": statistics.mean(successes) if successes else 0.0,
        }
    
    def get_all_statistics(self) -> Dict[str, Any]:
        """Get statistics for all stages."""
        stages = [
            WorkflowStage.OBSERVE,
            WorkflowStage.COLLECT,
            WorkflowStage.NORMALIZE,
            WorkflowStage.ANALYZE,
            WorkflowStage.CORRELATE,
            WorkflowStage.ALERT,
            WorkflowStage.REPORT,
        ]
        
        return {
            "by_stage": [self.get_stage_statistics(s) for s in stages],
            "pipeline": {
                "samples": len(self.metrics.get("pipeline_durations", [])),
                "avg_duration": statistics.mean(self.metrics["pipeline_durations"]) if self.metrics.get("pipeline_durations") else 0.0,
                "overall_success_rate": statistics.mean(self.metrics["success_rates"]) if self.metrics.get("success_rates") else 0.0,
            } if self.metrics.get("pipeline_durations") else {"samples": 0},
        }
