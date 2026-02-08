"""
Capacity Prediction Module

Predicts resource exhaustion (disk, memory) based on usage trends.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class CapacityPrediction:
    """Capacity prediction result."""
    resource_type: str  # disk, memory, cpu
    current_usage: float
    current_total: float
    growth_rate_per_day: float
    days_until_full: Optional[float]
    days_until_warning: Optional[float]
    confidence: float
    recommendation: str


class CapacityPredictor:
    """
    Predicts when resources will be exhausted.
    
    Uses linear regression on historical usage data.
    """
    
    def __init__(self):
        self.warning_threshold = 85.0
        self.critical_threshold = 95.0
    
    def predict_disk_full(
        self,
        usage_history: List[Tuple[float, float]],  # (timestamp, usage_gb)
        total_capacity_gb: float
    ) -> CapacityPrediction:
        """
        Predict when disk will be full.
        
        Args:
            usage_history: List of (timestamp, usage_gb)
            total_capacity_gb: Total disk capacity
        
        Returns:
            CapacityPrediction
        """
        if len(usage_history) < 7:
            return CapacityPrediction(
                resource_type="disk",
                current_usage=usage_history[-1][1] if usage_history else 0,
                current_total=total_capacity_gb,
                growth_rate_per_day=0,
                days_until_full=None,
                days_until_warning=None,
                confidence=0,
                recommendation="Insufficient data for prediction"
            )
        
        # Calculate growth rate
        growth_rate = self._calculate_growth_rate(usage_history)
        current_usage = usage_history[-1][1]
        
        # Calculate days until thresholds
        warning_level = total_capacity_gb * (self.warning_threshold / 100)
        critical_level = total_capacity_gb * (self.critical_threshold / 100)
        
        if growth_rate > 0:
            days_until_warning = (warning_level - current_usage) / growth_rate
            days_until_full = (total_capacity_gb - current_usage) / growth_rate
        else:
            days_until_warning = None
            days_until_full = None
        
        # Generate recommendation
        if days_until_full and days_until_full < 7:
            recommendation = f"URGENT: Disk will be full in {days_until_full:.1f} days!"
        elif days_until_warning and days_until_warning < 30:
            recommendation = f"WARNING: Disk will reach {self.warning_threshold}% in {days_until_warning:.1f} days."
        else:
            recommendation = "Disk usage is stable."
        
        return CapacityPrediction(
            resource_type="disk",
            current_usage=current_usage,
            current_total=total_capacity_gb,
            growth_rate_per_day=growth_rate,
            days_until_full=days_until_full,
            days_until_warning=days_until_warning,
            confidence=min(1.0, len(usage_history) / 30),
            recommendation=recommendation
        )
    
    def predict_memory_exhaustion(
        self,
        usage_history: List[Tuple[float, float]],
        total_memory_gb: float
    ) -> CapacityPrediction:
        """Predict memory exhaustion."""
        return self.predict_disk_full(usage_history, total_memory_gb)
    
    def _calculate_growth_rate(
        self,
        history: List[Tuple[float, float]]
    ) -> float:
        """Calculate daily growth rate using linear regression."""
        if len(history) < 2:
            return 0.0
        
        # Simple linear regression
        n = len(history)
        sum_x = sum(h[0] for h in history)
        sum_y = sum(h[1] for h in history)
        sum_xy = sum(h[0] * h[1] for h in history)
        sum_x2 = sum(h[0] * h[0] for h in history)
        
        denominator = n * sum_x2 - sum_x * sum_x
        if denominator == 0:
            return 0.0
        
        slope = (n * sum_xy - sum_x * sum_y) / denominator
        
        # Convert to daily growth (assuming timestamps in seconds)
        daily_growth = slope * 86400
        
        return daily_growth
