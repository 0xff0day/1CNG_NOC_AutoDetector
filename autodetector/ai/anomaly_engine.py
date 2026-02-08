"""
AI Anomaly Detection Engine

Detects anomalous metric values using statistical methods.
Supports Z-score, MAD (Median Absolute Deviation), and IQR methods.
"""

from __future__ import annotations

import math
import statistics
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class AnomalyResult:
    """Result of anomaly detection."""
    is_anomaly: bool
    score: float
    method: str
    threshold: float
    baseline_mean: float
    baseline_std: float
    deviation_percent: float
    severity: str  # low, medium, high, critical
    confidence: float


class AnomalyDetector:
    """
    Statistical anomaly detection for metrics.
    
    Methods:
    - Z-Score: Standard deviations from mean
    - MAD: Median Absolute Deviation (robust to outliers)
    - IQR: Interquartile Range
    - EWMA: Exponentially Weighted Moving Average
    """
    
    def __init__(
        self,
        method: str = "zscore",
        threshold: float = 3.0,
        min_baseline_points: int = 10
    ):
        self.method = method
        self.threshold = threshold
        self.min_baseline_points = min_baseline_points
    
    def detect(
        self,
        value: float,
        history: List[float]
    ) -> Optional[AnomalyResult]:
        """
        Detect if value is anomalous based on history.
        
        Args:
            value: Current value to check
            history: Historical values for baseline
        
        Returns:
            AnomalyResult or None if insufficient history
        """
        if len(history) < self.min_baseline_points:
            return None
        
        if self.method == "zscore":
            return self._detect_zscore(value, history)
        elif self.method == "mad":
            return self._detect_mad(value, history)
        elif self.method == "iqr":
            return self._detect_iqr(value, history)
        elif self.method == "ewma":
            return self._detect_ewma(value, history)
        else:
            logger.warning(f"Unknown method: {self.method}")
            return None
    
    def _detect_zscore(self, value: float, history: List[float]) -> AnomalyResult:
        """Z-score based detection."""
        mean = statistics.mean(history)
        std = statistics.stdev(history) if len(history) > 1 else 0.001
        
        if std == 0:
            std = 0.001  # Avoid division by zero
        
        zscore = abs(value - mean) / std
        is_anomaly = zscore > self.threshold
        
        # Calculate severity
        if zscore > self.threshold * 2:
            severity = "critical"
        elif zscore > self.threshold * 1.5:
            severity = "high"
        elif zscore > self.threshold:
            severity = "medium"
        else:
            severity = "low"
        
        # Confidence based on sample size
        confidence = min(1.0, len(history) / 100)
        
        deviation = ((value - mean) / mean * 100) if mean != 0 else 0
        
        return AnomalyResult(
            is_anomaly=is_anomaly,
            score=zscore,
            method="zscore",
            threshold=self.threshold,
            baseline_mean=mean,
            baseline_std=std,
            deviation_percent=deviation,
            severity=severity,
            confidence=confidence
        )
    
    def _detect_mad(self, value: float, history: List[float]) -> AnomalyResult:
        """MAD (Median Absolute Deviation) based detection."""
        median = statistics.median(history)
        
        # Calculate absolute deviations
        abs_deviations = [abs(x - median) for x in history]
        mad = statistics.median(abs_deviations)
        
        if mad == 0:
            mad = 0.001
        
        # Modified Z-score using MAD
        modified_zscore = 0.6745 * (value - median) / mad
        is_anomaly = abs(modified_zscore) > self.threshold
        
        # Calculate severity
        abs_score = abs(modified_zscore)
        if abs_score > self.threshold * 2:
            severity = "critical"
        elif abs_score > self.threshold * 1.5:
            severity = "high"
        elif abs_score > self.threshold:
            severity = "medium"
        else:
            severity = "low"
        
        confidence = min(1.0, len(history) / 100)
        
        # Estimate std from MAD for consistency
        estimated_std = mad / 0.6745
        deviation = ((value - median) / median * 100) if median != 0 else 0
        
        return AnomalyResult(
            is_anomaly=is_anomaly,
            score=abs(modified_zscore),
            method="mad",
            threshold=self.threshold,
            baseline_mean=median,
            baseline_std=estimated_std,
            deviation_percent=deviation,
            severity=severity,
            confidence=confidence
        )
    
    def _detect_iqr(self, value: float, history: List[float]) -> AnomalyResult:
        """IQR (Interquartile Range) based detection."""
        sorted_history = sorted(history)
        n = len(sorted_history)
        
        # Calculate quartiles
        q1_idx = n // 4
        q3_idx = 3 * n // 4
        q1 = sorted_history[q1_idx]
        q3 = sorted_history[q3_idx]
        
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        
        is_anomaly = value < lower_bound or value > upper_bound
        
        # Score based on distance from bounds
        if value < lower_bound:
            score = abs((value - lower_bound) / iqr) if iqr > 0 else 0
        elif value > upper_bound:
            score = abs((value - upper_bound) / iqr) if iqr > 0 else 0
        else:
            score = 0
        
        # Severity
        if score > 3:
            severity = "critical"
        elif score > 2:
            severity = "high"
        elif score > 1:
            severity = "medium"
        else:
            severity = "low"
        
        confidence = min(1.0, len(history) / 100)
        
        mean = statistics.mean(history)
        std = statistics.stdev(history) if len(history) > 1 else 0
        deviation = ((value - mean) / mean * 100) if mean != 0 else 0
        
        return AnomalyResult(
            is_anomaly=is_anomaly,
            score=score,
            method="iqr",
            threshold=self.threshold,
            baseline_mean=mean,
            baseline_std=std,
            deviation_percent=deviation,
            severity=severity,
            confidence=confidence
        )
    
    def _detect_ewma(self, value: float, history: List[float]) -> AnomalyResult:
        """EWMA (Exponentially Weighted Moving Average) based detection."""
        alpha = 0.3  # Smoothing factor
        
        # Calculate EWMA
        ewma = history[0]
        for x in history[1:]:
            ewma = alpha * x + (1 - alpha) * ewma
        
        # Calculate standard deviation of residuals
        residuals = [x - ewma for x in history]
        std = statistics.stdev(residuals) if len(residuals) > 1 else 0.001
        
        if std == 0:
            std = 0.001
        
        # Check current value
        residual = value - ewma
        score = abs(residual) / std
        is_anomaly = score > self.threshold
        
        # Severity
        if score > self.threshold * 2:
            severity = "critical"
        elif score > self.threshold * 1.5:
            severity = "high"
        elif score > self.threshold:
            severity = "medium"
        else:
            severity = "low"
        
        confidence = min(1.0, len(history) / 100)
        deviation = ((value - ewma) / ewma * 100) if ewma != 0 else 0
        
        return AnomalyResult(
            is_anomaly=is_anomaly,
            score=score,
            method="ewma",
            threshold=self.threshold,
            baseline_mean=ewma,
            baseline_std=std,
            deviation_percent=deviation,
            severity=severity,
            confidence=confidence
        )


class MultiMetricAnomalyDetector:
    """
    Detects anomalies across multiple related metrics.
    """
    
    def __init__(self):
        self.detectors: Dict[str, AnomalyDetector] = {}
    
    def add_metric(
        self,
        variable: str,
        method: str = "zscore",
        threshold: float = 3.0
    ) -> None:
        """Add metric to monitor."""
        self.detectors[variable] = AnomalyDetector(method, threshold)
    
    def detect_all(
        self,
        current_values: Dict[str, float],
        history: Dict[str, List[float]]
    ) -> Dict[str, AnomalyResult]:
        """
        Detect anomalies across all metrics.
        
        Returns:
            Dict mapping variable to AnomalyResult
        """
        results = {}
        
        for variable, value in current_values.items():
            if variable in self.detectors:
                detector = self.detectors[variable]
                hist = history.get(variable, [])
                result = detector.detect(value, hist)
                if result:
                    results[variable] = result
        
        return results
    
    def get_correlated_anomalies(
        self,
        results: Dict[str, AnomalyResult],
        correlation_threshold: float = 0.7
    ) -> List[List[str]]:
        """
        Find groups of correlated anomalies.
        
        Returns:
            List of anomaly groups
        """
        # Group by timing and severity
        high_severity = [
            v for v, r in results.items()
            if r.severity in ("high", "critical")
        ]
        
        if len(high_severity) > 1:
            return [high_severity]
        
        return []
