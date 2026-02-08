"""
LLM Integration with AI Detection Engine

Integrates local LLM capabilities with the NOC detection system for:
- Enhanced root cause analysis
- Natural language alert explanations
- Intelligent correlation insights
- Predictive maintenance recommendations
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging

from ..llm import LLMRegistry, ModelConfig, ModelArchitecture, GenerationResult
from ..llm.noc_training_data import NOCTrainingDataBuilder

logger = logging.getLogger(__name__)


@dataclass
class LLMInsight:
    """Structured insight from LLM analysis."""
    insight_type: str  # root_cause, prediction, recommendation, correlation
    confidence: float
    summary: str
    details: str
    action_items: List[str]
    supporting_evidence: List[str]
    estimated_impact: str
    model_used: str
    generation_time_ms: float


class LLMDetectionIntegrator:
    """
    Integrates local LLM with the detection engine.
    
    Provides AI-powered analysis of network alerts and metrics
    using locally-hosted LLM models.
    """
    
    def __init__(self, default_model: Optional[str] = None):
        self.default_model = default_model
        self._context_cache: Dict[str, List[Dict[str, Any]]] = {}
        self.max_context_items = 10
    
    def analyze_alert(
        self,
        device_id: str,
        alert_data: Dict[str, Any],
        metrics_snapshot: Dict[str, Any],
        model_name: Optional[str] = None
    ) -> Optional[LLMInsight]:
        """
        Analyze a network alert using LLM.
        
        Args:
            device_id: Device identifier
            alert_data: Alert information (severity, type, message)
            metrics_snapshot: Current device metrics
            model_name: Specific model to use (default if None)
        
        Returns:
            LLMInsight with analysis results
        """
        model = self._get_model(model_name)
        if not model:
            logger.warning("No LLM model available for analysis")
            return None
        
        # Build prompt
        prompt = self._build_alert_analysis_prompt(
            device_id, alert_data, metrics_snapshot
        )
        
        # Generate with timing
        start_time = time.time()
        try:
            result = model.generate(
                prompt=prompt,
                max_tokens=1024,
                temperature=0.3,  # Lower temp for factual analysis
            )
            generation_time = (time.time() - start_time) * 1000
            
            # Parse structured output
            insight = self._parse_alert_analysis(
                result, model.config.name, generation_time
            )
            
            # Update context cache
            self._update_context(device_id, {
                "type": "alert_analysis",
                "timestamp": time.time(),
                "insight": insight
            })
            
            return insight
            
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            return None
    
    def correlate_incidents(
        self,
        incident_alerts: List[Dict[str, Any]],
        topology_info: Dict[str, Any],
        model_name: Optional[str] = None
    ) -> Optional[LLMInsight]:
        """
        Analyze correlated incidents using LLM.
        
        Args:
            incident_alerts: List of related alerts
            topology_info: Network topology information
            model_name: Specific model to use
        
        Returns:
            LLMInsight with correlation analysis
        """
        model = self._get_model(model_name)
        if not model:
            return None
        
        prompt = self._build_correlation_prompt(incident_alerts, topology_info)
        
        start_time = time.time()
        try:
            result = model.generate(
                prompt=prompt,
                max_tokens=1024,
                temperature=0.3,
            )
            generation_time = (time.time() - start_time) * 1000
            
            return self._parse_correlation_analysis(
                result, model.config.name, generation_time
            )
            
        except Exception as e:
            logger.error(f"LLM correlation failed: {e}")
            return None
    
    def predict_maintenance(
        self,
        device_id: str,
        metric_history: List[Dict[str, Any]],
        days_ahead: int = 7,
        model_name: Optional[str] = None
    ) -> Optional[LLMInsight]:
        """
        Predict maintenance needs using LLM.
        
        Args:
            device_id: Device identifier
            metric_history: Historical metrics data
            days_ahead: Prediction horizon
            model_name: Specific model to use
        
        Returns:
            LLMInsight with predictions
        """
        model = self._get_model(model_name)
        if not model:
            return None
        
        prompt = self._build_prediction_prompt(
            device_id, metric_history, days_ahead
        )
        
        start_time = time.time()
        try:
            result = model.generate(
                prompt=prompt,
                max_tokens=1024,
                temperature=0.4,
            )
            generation_time = (time.time() - start_time) * 1000
            
            return self._parse_prediction(
                result, model.config.name, generation_time
            )
            
        except Exception as e:
            logger.error(f"LLM prediction failed: {e}")
            return None
    
    def explain_health_score(
        self,
        device_id: str,
        health_score: float,
        contributing_factors: Dict[str, float],
        model_name: Optional[str] = None
    ) -> str:
        """
        Generate natural language explanation of health score.
        
        Returns human-readable explanation of the score and factors.
        """
        model = self._get_model(model_name)
        if not model:
            return f"Health Score: {health_score}/100"
        
        prompt = self._build_health_explanation_prompt(
            device_id, health_score, contributing_factors
        )
        
        try:
            result = model.generate(
                prompt=prompt,
                max_tokens=512,
                temperature=0.5,
            )
            return result.text.strip()
            
        except Exception as e:
            logger.error(f"Health explanation failed: {e}")
            return f"Health Score: {health_score}/100"
    
    def generate_runbook_step(
        self,
        issue_type: str,
        device_type: str,
        current_step: int,
        previous_outputs: List[str],
        model_name: Optional[str] = None
    ) -> Optional[str]:
        """
        Generate next troubleshooting step using LLM.
        
        Args:
            issue_type: Type of issue being troubleshot
            device_type: Device vendor/OS type
            current_step: Current step number
            previous_outputs: Results from previous steps
            model_name: Specific model to use
        
        Returns:
            Recommended next CLI command or action
        """
        model = self._get_model(model_name)
        if not model:
            return None
        
        prompt = self._build_runbook_prompt(
            issue_type, device_type, current_step, previous_outputs
        )
        
        try:
            result = model.generate(
                prompt=prompt,
                max_tokens=256,
                temperature=0.3,
            )
            return result.text.strip()
            
        except Exception as e:
            logger.error(f"Runbook generation failed: {e}")
            return None
    
    def _get_model(self, model_name: Optional[str] = None):
        """Get LLM model instance."""
        name = model_name or self.default_model
        if not name:
            # Try to use first available model
            available = LLMRegistry.list_loaded_models()
            if available:
                name = available[0]
            else:
                return None
        
        return LLMRegistry.get_loaded_model(name)
    
    def _build_alert_analysis_prompt(
        self,
        device_id: str,
        alert_data: Dict[str, Any],
        metrics: Dict[str, Any]
    ) -> str:
        """Build prompt for alert analysis."""
        return f"""Analyze the following network alert and provide a detailed assessment.

Device: {device_id}
Alert Type: {alert_data.get('type', 'Unknown')}
Severity: {alert_data.get('severity', 'Unknown')}
Message: {alert_data.get('message', 'N/A')}
Timestamp: {alert_data.get('timestamp', 'N/A')}

Current Metrics:
{json.dumps(metrics, indent=2)}

Provide your analysis in this JSON format:
{{
    "root_cause": "Primary cause of the issue",
    "confidence": 85,
    "impact": "Description of business/operational impact",
    "immediate_actions": ["Action 1", "Action 2", "Action 3"],
    "investigation_steps": ["Step 1", "Step 2"],
    "prevention": "How to prevent recurrence"
}}

Analysis:"""
    
    def _build_correlation_prompt(
        self,
        alerts: List[Dict[str, Any]],
        topology: Dict[str, Any]
    ) -> str:
        """Build prompt for incident correlation."""
        alerts_text = json.dumps(alerts, indent=2)
        topology_text = json.dumps(topology, indent=2)
        
        return f"""Analyze these correlated network alerts and identify the common root cause.

Alerts:
{alerts_text}

Network Topology:
{topology_text}

Provide analysis in this JSON format:
{{
    "common_root_cause": "Identified shared cause",
    "confidence": 90,
    "impact_chain": "How the issue propagates",
    "primary_device": "Device where issue originated",
    "resolution_strategy": "Strategy to resolve all alerts",
    "affected_services": ["Service 1", "Service 2"]
}}

Analysis:"""
    
    def _build_prediction_prompt(
        self,
        device_id: str,
        history: List[Dict[str, Any]],
        days: int
    ) -> str:
        """Build prompt for maintenance prediction."""
        history_summary = json.dumps(history[-30:], indent=2)  # Last 30 data points
        
        return f"""Predict maintenance needs for the next {days} days based on historical metrics.

Device: {device_id}

Historical Metrics (last 30 samples):
{history_summary}

Provide prediction in this JSON format:
{{
    "predicted_issues": ["Issue 1", "Issue 2"],
    "confidence": 75,
    "timeline": "When issues are likely to occur",
    "recommended_maintenance": ["Maintenance 1", "Maintenance 2"],
    "risk_level": "High/Medium/Low",
    "resource_needs": "Estimated resources required"
}}

Prediction:"""
    
    def _build_health_explanation_prompt(
        self,
        device_id: str,
        score: float,
        factors: Dict[str, float]
    ) -> str:
        """Build prompt for health score explanation."""
        factors_text = "\n".join([f"- {k}: {v:.1f}%" for k, v in factors.items()])
        
        return f"""Explain the following device health score in clear, actionable terms.

Device: {device_id}
Health Score: {score}/100

Contributing Factors:
{factors_text}

Provide a brief natural language explanation (2-3 sentences) of what this score means and what actions should be taken.

Explanation:"""
    
    def _build_runbook_prompt(
        self,
        issue_type: str,
        device_type: str,
        step: int,
        previous_outputs: List[str]
    ) -> str:
        """Build prompt for runbook step generation."""
        previous = "\n".join([f"{i+1}. {out}" for i, out in enumerate(previous_outputs)])
        
        return f"""Generate the next troubleshooting step for the following issue.

Issue Type: {issue_type}
Device Type: {device_type}
Current Step: {step}

Previous Steps and Results:
{previous}

Provide the next CLI command to run or action to take. Be specific to {device_type}.

Next Step:"""
    
    def _parse_alert_analysis(
        self,
        result: GenerationResult,
        model_name: str,
        gen_time: float
    ) -> LLMInsight:
        """Parse LLM output into structured insight."""
        try:
            # Try to extract JSON from output
            text = result.text.strip()
            
            # Find JSON block
            if "```json" in text:
                json_str = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                json_str = text.split("```")[1].split("```")[0]
            else:
                json_str = text
            
            data = json.loads(json_str)
            
            return LLMInsight(
                insight_type="root_cause",
                confidence=float(data.get("confidence", 0)) / 100,
                summary=data.get("root_cause", "Unknown"),
                details=data.get("impact", ""),
                action_items=data.get("immediate_actions", []),
                supporting_evidence=data.get("investigation_steps", []),
                estimated_impact=data.get("impact", ""),
                model_used=model_name,
                generation_time_ms=gen_time
            )
            
        except json.JSONDecodeError:
            # Fallback to text parsing
            return LLMInsight(
                insight_type="root_cause",
                confidence=0.5,
                summary=result.text[:200],
                details=result.text,
                action_items=[],
                supporting_evidence=[],
                estimated_impact="",
                model_used=model_name,
                generation_time_ms=gen_time
            )
    
    def _parse_correlation_analysis(
        self,
        result: GenerationResult,
        model_name: str,
        gen_time: float
    ) -> LLMInsight:
        """Parse correlation output into insight."""
        try:
            text = result.text.strip()
            
            if "```json" in text:
                json_str = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                json_str = text.split("```")[1].split("```")[0]
            else:
                json_str = text
            
            data = json.loads(json_str)
            
            return LLMInsight(
                insight_type="correlation",
                confidence=float(data.get("confidence", 0)) / 100,
                summary=data.get("common_root_cause", "Unknown correlation"),
                details=data.get("impact_chain", ""),
                action_items=[data.get("resolution_strategy", "")],
                supporting_evidence=data.get("affected_services", []),
                estimated_impact=data.get("impact_chain", ""),
                model_used=model_name,
                generation_time_ms=gen_time
            )
            
        except json.JSONDecodeError:
            return LLMInsight(
                insight_type="correlation",
                confidence=0.5,
                summary=result.text[:200],
                details=result.text,
                action_items=[],
                supporting_evidence=[],
                estimated_impact="",
                model_used=model_name,
                generation_time_ms=gen_time
            )
    
    def _parse_prediction(
        self,
        result: GenerationResult,
        model_name: str,
        gen_time: float
    ) -> LLMInsight:
        """Parse prediction output into insight."""
        try:
            text = result.text.strip()
            
            if "```json" in text:
                json_str = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                json_str = text.split("```")[1].split("```")[0]
            else:
                json_str = text
            
            data = json.loads(json_str)
            
            return LLMInsight(
                insight_type="prediction",
                confidence=float(data.get("confidence", 0)) / 100,
                summary=f"Predicted issues: {', '.join(data.get('predicted_issues', []))}",
                details=data.get("timeline", ""),
                action_items=data.get("recommended_maintenance", []),
                supporting_evidence=[data.get("risk_level", "")],
                estimated_impact=data.get("resource_needs", ""),
                model_used=model_name,
                generation_time_ms=gen_time
            )
            
        except json.JSONDecodeError:
            return LLMInsight(
                insight_type="prediction",
                confidence=0.5,
                summary=result.text[:200],
                details=result.text,
                action_items=[],
                supporting_evidence=[],
                estimated_impact="",
                model_used=model_name,
                generation_time_ms=gen_time
            )
    
    def _update_context(self, device_id: str, context_item: Dict[str, Any]) -> None:
        """Update context cache for device."""
        if device_id not in self._context_cache:
            self._context_cache[device_id] = []
        
        self._context_cache[device_id].append(context_item)
        
        # Keep only recent context
        if len(self._context_cache[device_id]) > self.max_context_items:
            self._context_cache[device_id] = self._context_cache[device_id][-self.max_context_items:]
    
    def get_context(self, device_id: str) -> List[Dict[str, Any]]:
        """Get recent context for device."""
        return self._context_cache.get(device_id, [])


def create_default_noc_model_config(name: str, architecture: str, model_path: str) -> ModelConfig:
    """Create a default model configuration for NOC use."""
    arch = ModelArchitecture(architecture)
    
    return ModelConfig(
        name=name,
        architecture=arch,
        model_path=model_path,
        context_length=8192,
        max_tokens=2048,
        temperature=0.3,  # Lower for factual accuracy
        top_p=0.9,
        top_k=40,
        repetition_penalty=1.1,
        stop_sequences=["<|endoftext|>", "<|im_end|>"],
        custom_params={
            "use_cache": True,
            "noc_optimized": True,
        }
    )
