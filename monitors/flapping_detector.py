"""
Flapping Detection Module

Detects oscillating/flapping states in devices and interfaces.
Identifies unstable conditions that trigger rapid state changes.
"""

from __future__ import annotations

import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from collections import deque
import logging

logger = logging.getLogger(__name__)


@dataclass
class FlapEvent:
    """Single flap event record."""
    timestamp: float
    old_state: str
    new_state: str


@dataclass
class FlapAnalysis:
    """Flapping analysis result."""
    is_flapping: bool
    flap_count: int
    flap_rate: float  # flaps per minute
    time_window: float
    stability_score: float  # 0-1, higher is more stable
    recommendation: str


class FlappingDetector:
    """
    Detects flapping conditions in network devices and interfaces.
    
    Flapping occurs when a state oscillates rapidly between
    two or more values (e.g., interface up/down, BGP up/down).
    """
    
    def __init__(
        self,
        flap_threshold: int = 3,
        time_window_seconds: float = 300,  # 5 minutes
        min_stability_period: float = 600  # 10 minutes stable to reset
    ):
        self.flap_threshold = flap_threshold
        self.time_window = time_window_seconds
        self.min_stability_period = min_stability_period
        
        # Store state history per entity
        self._history: Dict[str, deque] = {}
        self._current_state: Dict[str, str] = {}
        self._last_change: Dict[str, float] = {}
        self._last_stable: Dict[str, float] = {}
    
    def record_state_change(
        self,
        entity_id: str,
        new_state: str,
        timestamp: Optional[float] = None
    ) -> FlapAnalysis:
        """
        Record a state change and analyze for flapping.
        
        Args:
            entity_id: Entity identifier (device:interface)
            new_state: New state value
            timestamp: Event timestamp (default: now)
        
        Returns:
            FlapAnalysis with results
        """
        if timestamp is None:
            timestamp = time.time()
        
        # Initialize history
        if entity_id not in self._history:
            self._history[entity_id] = deque(maxlen=100)
            self._current_state[entity_id] = new_state
            self._last_change[entity_id] = timestamp
            self._last_stable[entity_id] = timestamp
            
            return FlapAnalysis(
                is_flapping=False,
                flap_count=0,
                flap_rate=0.0,
                time_window=0,
                stability_score=1.0,
                recommendation="New entity, monitoring started"
            )
        
        old_state = self._current_state.get(entity_id)
        
        # Only count if state actually changed
        if old_state != new_state:
            # Record the flap
            flap_event = FlapEvent(
                timestamp=timestamp,
                old_state=old_state or "unknown",
                new_state=new_state
            )
            self._history[entity_id].append(flap_event)
            
            self._current_state[entity_id] = new_state
            self._last_change[entity_id] = timestamp
        
        return self._analyze_flapping(entity_id, timestamp)
    
    def _analyze_flapping(
        self,
        entity_id: str,
        current_time: float
    ) -> FlapAnalysis:
        """Analyze flap history for flapping condition."""
        history = self._history.get(entity_id, deque())
        
        if len(history) < 2:
            return FlapAnalysis(
                is_flapping=False,
                flap_count=0,
                flap_rate=0.0,
                time_window=0,
                stability_score=1.0,
                recommendation="Insufficient history"
            )
        
        # Count flaps in time window
        window_start = current_time - self.time_window
        recent_flaps = [
            e for e in history
            if e.timestamp >= window_start
        ]
        
        flap_count = len(recent_flaps)
        
        if len(recent_flaps) >= 2:
            time_span = recent_flaps[-1].timestamp - recent_flaps[0].timestamp
            flap_rate = (flap_count / time_span) * 60 if time_span > 0 else 0
        else:
            flap_rate = 0.0
            time_span = 0
        
        # Determine if flapping
        is_flapping = flap_count >= self.flap_threshold
        
        # Calculate stability score
        if is_flapping:
            stability_score = max(0, 1.0 - (flap_count / (self.flap_threshold * 2)))
        else:
            stability_score = min(1.0, 0.5 + (1.0 - flap_count / self.flap_threshold) * 0.5)
        
        # Generate recommendation
        if is_flapping:
            if flap_rate > 10:
                recommendation = "CRITICAL: Severe flapping detected. Check physical connection immediately."
            elif flap_rate > 5:
                recommendation = "WARNING: Significant flapping. Investigate link stability."
            else:
                recommendation = "Moderate flapping detected. Monitor for patterns."
        else:
            time_since_last = current_time - self._last_change.get(entity_id, current_time)
            if time_since_last > self.min_stability_period:
                recommendation = "Entity is stable."
            else:
                recommendation = "Monitoring for stability..."
        
        return FlapAnalysis(
            is_flapping=is_flapping,
            flap_count=flap_count,
            flap_rate=round(flap_rate, 2),
            time_window=self.time_window,
            stability_score=round(stability_score, 2),
            recommendation=recommendation
        )
    
    def is_flapping(self, entity_id: str) -> bool:
        """Quick check if entity is currently flapping."""
        analysis = self._analyze_flapping(entity_id, time.time())
        return analysis.is_flapping
    
    def get_flap_history(
        self,
        entity_id: str,
        hours: int = 24
    ) -> List[Dict]:
        """Get flap history for entity."""
        since = time.time() - (hours * 3600)
        history = self._history.get(entity_id, deque())
        
        return [
            {
                "timestamp": e.timestamp,
                "old_state": e.old_state,
                "new_state": e.new_state
            }
            for e in history
            if e.timestamp >= since
        ]
    
    def reset(self, entity_id: str) -> None:
        """Reset flapping history for entity."""
        if entity_id in self._history:
            self._history[entity_id].clear()
        self._last_stable[entity_id] = time.time()
        logger.info(f"Reset flapping history for {entity_id}")
    
    def get_flapping_entities(self) -> List[str]:
        """Get list of currently flapping entities."""
        current_time = time.time()
        flapping = []
        
        for entity_id in self._history:
            analysis = self._analyze_flapping(entity_id, current_time)
            if analysis.is_flapping:
                flapping.append(entity_id)
        
        return flapping


class InterfaceFlapMonitor:
    """
    Specialized monitor for interface flapping.
    """
    
    def __init__(self, detector: FlappingDetector):
        self.detector = detector
    
    def record_interface_status(
        self,
        device_id: str,
        interface: str,
        admin_status: str,
        oper_status: str
    ) -> FlapAnalysis:
        """
        Record interface status change.
        
        Args:
            device_id: Device identifier
            interface: Interface name
            admin_status: Administrative status (up/down)
            oper_status: Operational status (up/down)
        
        Returns:
            FlapAnalysis
        """
        # Create composite state
        state = f"{admin_status}/{oper_status}"
        entity_id = f"{device_id}:{interface}"
        
        return self.detector.record_state_change(entity_id, state)
    
    def record_bgp_session(
        self,
        device_id: str,
        neighbor: str,
        state: str
    ) -> FlapAnalysis:
        """Record BGP session state change."""
        entity_id = f"{device_id}:bgp:{neighbor}"
        return self.detector.record_state_change(entity_id, state)


class RoutingFlapDetector:
    """
    Detects routing instability and route flapping.
    """
    
    def __init__(self, detector: FlappingDetector):
        self.detector = detector
    
    def record_route_count(
        self,
        device_id: str,
        routing_table: str,
        route_count: int
    ) -> Optional[FlapAnalysis]:
        """
        Record route count and detect churn.
        
        Uses route count changes as indicator of routing instability.
        """
        # Quantize route count to reduce noise
        quantized = (route_count // 100) * 100
        state = f"{routing_table}:{quantized}"
        entity_id = f"{device_id}:routes:{routing_table}"
        
        return self.detector.record_state_change(entity_id, state)
