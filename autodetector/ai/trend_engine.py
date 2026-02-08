"""
AI Trend Detection Engine

Predicts future metric values and detects trends.
Uses linear regression and exponential smoothing for forecasting.
"""

from __future__ import annotations

import math
import statistics
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


@dataclass
class TrendResult:
    """Result of trend analysis."""
    direction: str  # increasing, decreasing, stable
    slope: float
    intercept: float
    r_squared: float
    forecast_1h: float
    forecast_24h: float
    eta_to_threshold: Optional[float]  # hours to reach threshold
    confidence: float
    recommendation: str


@dataclass
class ForecastPoint:
    """Single forecast point."""
    timestamp: float
    value: float
    lower_bound: float
    upper_bound: float
    confidence: float


class TrendEngine:
    """
    Trend detection and forecasting for metrics.
    
    Methods:
    - Linear regression for trend slope
    - Exponential smoothing for forecasting
    - ETA calculation to thresholds
    """
    
    def __init__(
        self,
        min_history_points: int = 10,
        forecast_horizon: int = 24  # hours
    ):
        self.min_history_points = min_history_points
        self.forecast_horizon = forecast_horizon
    
    def analyze_trend(
        self,
        values: List[float],
        timestamps: Optional[List[float]] = None,
        warn_threshold: Optional[float] = None,
        crit_threshold: Optional[float] = None
    ) -> Optional[TrendResult]:
        """
        Analyze trend in metric values.
        
        Args:
            values: Historical values
            timestamps: Optional timestamps (uses index if None)
            warn_threshold: Warning threshold for ETA
            crit_threshold: Critical threshold for ETA
        
        Returns:
            TrendResult or None if insufficient data
        """
        if len(values) < self.min_history_points:
            return None
        
        # Use indices if no timestamps
        if timestamps is None:
            timestamps = list(range(len(values)))
        
        # Calculate linear regression
        slope, intercept, r_squared = self._linear_regression(timestamps, values)
        
        # Determine direction
        if abs(slope) < 0.001:
            direction = "stable"
        elif slope > 0:
            direction = "increasing"
        else:
            direction = "decreasing"
        
        # Forecast
        last_time = timestamps[-1]
        forecast_1h = self._forecast_linear(last_time + 1, slope, intercept)
        forecast_24h = self._forecast_linear(last_time + 24, slope, intercept)
        
        # Calculate ETA to threshold
        eta = None
        threshold = crit_threshold or warn_threshold
        
        if threshold is not None and slope != 0:
            # Time to reach threshold
            time_to_threshold = (threshold - intercept) / slope - last_time
            if time_to_threshold > 0:
                eta = time_to_threshold
        
        # Confidence based on R-squared
        confidence = r_squared
        
        # Generate recommendation
        recommendation = self._generate_recommendation(
            direction, eta, threshold, values[-1], warn_threshold, crit_threshold
        )
        
        return TrendResult(
            direction=direction,
            slope=slope,
            intercept=intercept,
            r_squared=r_squared,
            forecast_1h=forecast_1h,
            forecast_24h=forecast_24h,
            eta_to_threshold=eta,
            confidence=confidence,
            recommendation=recommendation
        )
    
    def _linear_regression(
        self,
        x: List[float],
        y: List[float]
    ) -> Tuple[float, float, float]:
        """
        Calculate linear regression.
        
        Returns:
            (slope, intercept, r_squared)
        """
        n = len(x)
        
        mean_x = statistics.mean(x)
        mean_y = statistics.mean(y)
        
        # Calculate slope
        numerator = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
        denominator = sum((xi - mean_x) ** 2 for xi in x)
        
        if denominator == 0:
            return 0, mean_y, 0
        
        slope = numerator / denominator
        intercept = mean_y - slope * mean_x
        
        # Calculate R-squared
        ss_res = sum((yi - (slope * xi + intercept)) ** 2 for xi, yi in zip(x, y))
        ss_tot = sum((yi - mean_y) ** 2 for yi in y)
        
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        return slope, intercept, max(0, r_squared)
    
    def _forecast_linear(
        self,
        time: float,
        slope: float,
        intercept: float
    ) -> float:
        """Forecast value at given time using linear model."""
        return slope * time + intercept
    
    def _generate_recommendation(
        self,
        direction: str,
        eta: Optional[float],
        threshold: Optional[float],
        current_value: float,
        warn_threshold: Optional[float],
        crit_threshold: Optional[float]
    ) -> str:
        """Generate human-readable recommendation."""
        if direction == "stable":
            return "No significant trend detected. Continue monitoring."
        
        trend_desc = "increasing" if direction == "increasing" else "decreasing"
        
        # Check if approaching threshold
        if threshold is not None:
            if direction == "increasing" and current_value < threshold:
                if eta is not None:
                    if eta < 1:
                        return f"URGENT: Value will reach critical threshold in less than 1 hour!"
                    elif eta < 24:
                        return f"WARNING: Trend shows value will reach threshold in ~{eta:.1f} hours."
                    else:
                        return f"Trend is {trend_desc}. Value will reach threshold in ~{eta:.0f} hours."
            
            if direction == "decreasing" and current_value > threshold:
                return f"Value is {trend_desc} toward safe levels."
        
        # General trend message
        if abs(eta) < 1 if eta else False:
            return f"Rapid {trend_desc} trend detected. Immediate attention recommended."
        
        return f"Trend is {trend_desc}. Monitor closely."
    
    def forecast_series(
        self,
        values: List[float],
        timestamps: List[float],
        hours_ahead: int = 24,
        interval_hours: int = 1
    ) -> List[ForecastPoint]:
        """
        Generate forecast series.
        
        Args:
            values: Historical values
            timestamps: Historical timestamps
            hours_ahead: How many hours to forecast
            interval_hours: Forecast interval
        
        Returns:
            List of forecast points with confidence intervals
        """
        if len(values) < self.min_history_points:
            return []
        
        # Calculate trend
        slope, intercept, r_squared = self._linear_regression(timestamps, values)
        
        # Calculate standard error
        predictions = [slope * t + intercept for t in timestamps]
        residuals = [v - p for v, p in zip(values, predictions)]
        mse = statistics.mean(r ** 2 for r in residuals) if residuals else 0
        std_error = math.sqrt(mse)
        
        # Generate forecasts
        last_time = timestamps[-1]
        forecasts = []
        
        for i in range(1, hours_ahead // interval_hours + 1):
            forecast_time = last_time + i * interval_hours
            forecast_value = slope * forecast_time + intercept
            
            # Confidence intervals widen over time
            confidence_factor = math.sqrt(i) * 1.96  # 95% confidence
            margin = confidence_factor * std_error
            
            confidence = max(0, r_squared * (1 - i * 0.02))  # Decay confidence
            
            forecasts.append(ForecastPoint(
                timestamp=forecast_time,
                value=forecast_value,
                lower_bound=forecast_value - margin,
                upper_bound=forecast_value + margin,
                confidence=confidence
            ))
        
        return forecasts
    
    def detect_change_point(
        self,
        values: List[float],
        window_size: int = 5
    ) -> Optional[int]:
        """
        Detect sudden change points in series.
        
        Returns:
            Index of change point or None
        """
        if len(values) < window_size * 2:
            return None
        
        # Calculate moving averages
        for i in range(window_size, len(values) - window_size):
            before_avg = statistics.mean(values[i-window_size:i])
            after_avg = statistics.mean(values[i:i+window_size])
            
            before_std = statistics.stdev(values[i-window_size:i]) if window_size > 1 else 0
            
            # Check for significant change
            if before_std > 0:
                change = abs(after_avg - before_avg) / before_std
                if change > 3:  # 3 sigma change
                    return i
        
        return None


class DiskMemoryPredictor:
    """
    Specialized predictor for disk full and memory leak detection.
    """
    
    def __init__(self):
        self.trend_engine = TrendEngine()
    
    def predict_disk_full(
        self,
        usage_history: List[float],
        timestamps: List[float],
        total_capacity_gb: float,
        warn_percent: float = 85,
        crit_percent: float = 95
    ) -> Dict:
        """
        Predict when disk will be full.
        
        Returns:
            Dict with prediction details
        """
        if not usage_history:
            return {"error": "No data available"}
        
        current_percent = usage_history[-1]
        
        trend = self.trend_engine.analyze_trend(
            usage_history,
            timestamps,
            warn_threshold=warn_percent,
            crit_threshold=crit_percent
        )
        
        if not trend:
            return {"error": "Insufficient data for prediction"}
        
        # Calculate days to full
        if trend.slope > 0 and trend.eta_to_threshold:
            hours_to_crit = trend.eta_to_threshold
            days_to_crit = hours_to_crit / 24
            
            return {
                "current_usage_percent": current_percent,
                "trend_direction": trend.direction,
                "days_to_critical": round(days_to_crit, 1),
                "hours_to_critical": round(hours_to_crit, 1),
                "r_squared": round(trend.r_squared, 3),
                "confidence": round(trend.confidence, 2),
                "recommendation": trend.recommendation,
                "needs_attention": hours_to_crit < 72  # 3 days
            }
        
        return {
            "current_usage_percent": current_percent,
            "trend_direction": trend.direction,
            "days_to_critical": None,
            "confidence": trend.confidence,
            "recommendation": "No immediate risk detected."
        }
    
    def detect_memory_leak(
        self,
        memory_history: List[float],
        timestamps: List[float],
        process_name: Optional[str] = None
    ) -> Dict:
        """
        Detect potential memory leak.
        
        Returns:
            Dict with leak assessment
        """
        if len(memory_history) < 20:
            return {"error": "Need at least 20 data points for leak detection"}
        
        trend = self.trend_engine.analyze_trend(memory_history, timestamps)
        
        if not trend:
            return {"error": "Could not analyze trend"}
        
        # Calculate growth rate
        growth_per_hour = trend.slope
        
        # Check for consistent growth
        is_leak_suspected = (
            trend.direction == "increasing" and
            trend.r_squared > 0.7 and
            growth_per_hour > 0.5  # More than 0.5% per hour
        )
        
        return {
            "process": process_name or "system",
            "leak_suspected": is_leak_suspected,
            "growth_per_hour_percent": round(growth_per_hour, 2),
            "r_squared": round(trend.r_squared, 3),
            "confidence": round(trend.confidence, 2),
            "recommendation": (
                "Potential memory leak detected. Investigate process memory usage."
                if is_leak_suspected else
                "No significant memory growth detected."
            )
        }
