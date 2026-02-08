from __future__ import annotations

import json
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class BenchmarkResult:
    device_id: str
    metric_name: str
    timestamp: str
    samples: int
    min_val: float
    max_val: float
    avg_val: float
    p95_val: float
    p99_val: float
    unit: str


class PerformanceBenchmark:
    """Benchmark and baseline performance metrics for devices."""
    
    COMMON_BENCHMARKS = {
        "cpu_response_time": {
            "description": "CPU metric collection response time",
            "unit": "seconds",
        },
        "memory_collection_time": {
            "description": "Memory metric collection response time",
            "unit": "seconds",
        },
        "interface_scan_time": {
            "description": "Interface status scan time",
            "unit": "seconds",
        },
        "command_execution_time": {
            "description": "SSH command execution time",
            "unit": "seconds",
        },
        "connection_establishment": {
            "description": "SSH connection establishment time",
            "unit": "seconds",
        },
    }
    
    def __init__(self):
        self.results: Dict[str, List[BenchmarkResult]] = {}
        self.baselines: Dict[str, BenchmarkResult] = {}
    
    def run_benchmark(
        self,
        device_id: str,
        metric_name: str,
        samples: List[float],
        unit: str = "seconds"
    ) -> BenchmarkResult:
        """Run a benchmark with collected samples."""
        if not samples:
            raise ValueError("No samples provided")
        
        # Calculate statistics
        avg_val = statistics.mean(samples)
        min_val = min(samples)
        max_val = max(samples)
        p95_val = self._percentile(samples, 95)
        p99_val = self._percentile(samples, 99)
        
        result = BenchmarkResult(
            device_id=device_id,
            metric_name=metric_name,
            timestamp=datetime.now(timezone.utc).isoformat(),
            samples=len(samples),
            min_val=round(min_val, 4),
            max_val=round(max_val, 4),
            avg_val=round(avg_val, 4),
            p95_val=round(p95_val, 4),
            p99_val=round(p99_val, 4),
            unit=unit
        )
        
        # Store result
        key = f"{device_id}:{metric_name}"
        if key not in self.results:
            self.results[key] = []
        self.results[key].append(result)
        
        return result
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile value."""
        sorted_data = sorted(data)
        index = (percentile / 100) * (len(sorted_data) - 1)
        lower = int(index)
        upper = min(lower + 1, len(sorted_data) - 1)
        
        if lower == upper:
            return sorted_data[lower]
        
        weight = index - lower
        return sorted_data[lower] * (1 - weight) + sorted_data[upper] * weight
    
    def set_baseline(
        self,
        device_id: str,
        metric_name: str,
        result: BenchmarkResult
    ):
        """Set a baseline for future comparison."""
        key = f"{device_id}:{metric_name}"
        self.baselines[key] = result
    
    def compare_to_baseline(
        self,
        device_id: str,
        metric_name: str,
        current_result: BenchmarkResult,
        threshold_pct: float = 20.0
    ) -> Dict[str, Any]:
        """Compare current result to baseline."""
        key = f"{device_id}:{metric_name}"
        baseline = self.baselines.get(key)
        
        if not baseline:
            return {
                "has_baseline": False,
                "regression_detected": False,
                "message": "No baseline set for comparison",
            }
        
        # Calculate change
        baseline_avg = baseline.avg_val
        current_avg = current_result.avg_val
        
        if baseline_avg == 0:
            change_pct = 100.0 if current_avg > 0 else 0.0
        else:
            change_pct = ((current_avg - baseline_avg) / baseline_avg) * 100.0
        
        regression = abs(change_pct) > threshold_pct
        
        return {
            "has_baseline": True,
            "baseline_timestamp": baseline.timestamp,
            "current_timestamp": current_result.timestamp,
            "baseline_avg": baseline_avg,
            "current_avg": current_avg,
            "change_pct": round(change_pct, 2),
            "regression_detected": regression,
            "regression_direction": "worse" if change_pct > 0 else "better",
            "threshold_pct": threshold_pct,
        }
    
    def get_trend_analysis(
        self,
        device_id: str,
        metric_name: str,
        window: int = 10
    ) -> Dict[str, Any]:
        """Analyze trend over time for a metric."""
        key = f"{device_id}:{metric_name}"
        results = self.results.get(key, [])
        
        if len(results) < 2:
            return {
                "sufficient_data": False,
                "message": f"Need at least 2 samples, have {len(results)}",
            }
        
        # Take last N results
        recent = results[-window:]
        avgs = [r.avg_val for r in recent]
        
        # Simple trend analysis
        first_half = statistics.mean(avgs[:len(avgs)//2])
        second_half = statistics.mean(avgs[len(avgs)//2:])
        
        trend = "stable"
        if second_half > first_half * 1.1:
            trend = "degrading"
        elif second_half < first_half * 0.9:
            trend = "improving"
        
        return {
            "sufficient_data": True,
            "samples": len(recent),
            "trend": trend,
            "first_half_avg": round(first_half, 4),
            "second_half_avg": round(second_half, 4),
            "overall_avg": round(statistics.mean(avgs), 4),
        }


class CapacityPlanner:
    """Plan capacity based on trends and forecasts."""
    
    def __init__(self):
        self.forecasts: Dict[str, Any] = {}
    
    def forecast_resource(
        self,
        device_id: str,
        resource_type: str,  # 'cpu', 'memory', 'disk', 'bandwidth'
        historical_data: List[Tuple[str, float]],  # [(timestamp, value), ...]
        forecast_days: int = 30
    ) -> Dict[str, Any]:
        """Simple linear forecast for resource utilization."""
        if len(historical_data) < 3:
            return {
                "sufficient_data": False,
                "message": "Need at least 3 data points for forecasting",
            }
        
        # Simple linear regression
        n = len(historical_data)
        x = list(range(n))  # Time indices
        y = [point[1] for point in historical_data]
        
        x_mean = statistics.mean(x)
        y_mean = statistics.mean(y)
        
        # Calculate slope
        numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            slope = 0
        else:
            slope = numerator / denominator
        
        intercept = y_mean - slope * x_mean
        
        # Forecast future values
        last_x = n - 1
        forecast_values = []
        for i in range(forecast_days):
            forecast_x = last_x + i
            forecast_y = slope * forecast_x + intercept
            forecast_values.append(max(0.0, min(100.0, forecast_y)))
        
        # Find when we hit critical thresholds
        critical_threshold = 90.0
        warning_threshold = 80.0
        
        days_to_critical = None
        days_to_warning = None
        
        for i, val in enumerate(forecast_values):
            if days_to_warning is None and val >= warning_threshold:
                days_to_warning = i
            if days_to_critical is None and val >= critical_threshold:
                days_to_critical = i
                break
        
        forecast_key = f"{device_id}:{resource_type}"
        result = {
            "device_id": device_id,
            "resource_type": resource_type,
            "sufficient_data": True,
            "slope_per_day": round(slope, 4),
            "current_avg": round(y[-1], 2),
            "forecast_horizon_days": forecast_days,
            "days_to_warning": days_to_warning,
            "days_to_critical": days_to_critical,
            "forecast_generated_at": datetime.now(timezone.utc).isoformat(),
        }
        
        self.forecasts[forecast_key] = result
        return result
    
    def get_capacity_recommendations(
        self,
        device_id: str
    ) -> List[Dict[str, Any]]:
        """Get capacity recommendations based on forecasts."""
        recommendations = []
        
        for resource in ["cpu", "memory", "disk", "bandwidth"]:
            key = f"{device_id}:{resource}"
            forecast = self.forecasts.get(key)
            
            if not forecast:
                continue
            
            if forecast.get("days_to_critical") and forecast["days_to_critical"] <= 7:
                recommendations.append({
                    "severity": "critical",
                    "resource": resource,
                    "message": f"{resource.upper()} will reach critical threshold in {forecast['days_to_critical']} days",
                    "action": f"Plan {resource} upgrade immediately",
                })
            elif forecast.get("days_to_warning") and forecast["days_to_warning"] <= 14:
                recommendations.append({
                    "severity": "warning",
                    "resource": resource,
                    "message": f"{resource.upper()} will reach warning threshold in {forecast['days_to_warning']} days",
                    "action": f"Monitor {resource} closely and plan upgrade",
                })
        
        return recommendations
