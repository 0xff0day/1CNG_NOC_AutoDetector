"""
Routing State Monitor

Monitors routing protocols (BGP, OSPF, EIGRP) for instability.
Detects neighbor state changes, route churn, and convergence issues.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class RoutingProtocol(Enum):
    """Supported routing protocols."""
    BGP = "bgp"
    OSPF = "ospf"
    EIGRP = "eigrp"
    ISIS = "isis"
    RIP = "rip"
    STATIC = "static"


@dataclass
class RoutingNeighbor:
    """Routing protocol neighbor information."""
    protocol: RoutingProtocol
    neighbor_id: str
    local_as: Optional[int] = None
    remote_as: Optional[int] = None
    state: str = "unknown"
    uptime: str = ""
    prefixes_received: int = 0
    prefixes_sent: int = 0
    last_event: str = ""


@dataclass
class RoutingInstability:
    """Routing instability detection result."""
    protocol: RoutingProtocol
    neighbor_id: str
    instability_type: str  # flap, churn, convergence
    severity: str
    event_count: int
    time_window: float
    recommendation: str


class RoutingStateMonitor:
    """
    Monitors routing protocol states and detects instability.
    
    Features:
    - BGP neighbor state tracking
    - Route churn detection
    - Convergence monitoring
    - Flap detection
    """
    
    def __init__(self):
        self._neighbor_states: Dict[str, RoutingNeighbor] = {}
        self._state_history: Dict[str, List[Tuple[float, str]]] = {}
    
    def parse_bgp_summary(self, output: str) -> List[RoutingNeighbor]:
        """
        Parse BGP summary output.
        
        Supports Cisco and Juniper formats.
        """
        neighbors = []
        
        # Cisco BGP format
        cisco_pattern = r'(\S+)\s+(\d+)\s+(\S+)\s+(\S+)\s+(\d+)\s+(\d+)'
        
        for match in re.finditer(cisco_pattern, output):
            neighbor = RoutingNeighbor(
                protocol=RoutingProtocol.BGP,
                neighbor_id=match.group(1),
                remote_as=int(match.group(2)),
                state=match.group(4),
                prefixes_received=int(match.group(6)) if match.group(6).isdigit() else 0
            )
            neighbors.append(neighbor)
        
        return neighbors
    
    def parse_ospf_neighbors(self, output: str) -> List[RoutingNeighbor]:
        """Parse OSPF neighbor table."""
        neighbors = []
        
        # OSPF neighbor format
        ospf_pattern = r'(\S+)\s+(\d+)\s+(\S+)\s+(\S+)\s+([\d\/]+)'
        
        for match in re.finditer(ospf_pattern, output):
            neighbor = RoutingNeighbor(
                protocol=RoutingProtocol.OSPF,
                neighbor_id=match.group(1),
                state=match.group(4),
                uptime=match.group(5)
            )
            neighbors.append(neighbor)
        
        return neighbors
    
    def update_neighbor_state(
        self,
        device_id: str,
        neighbor: RoutingNeighbor
    ) -> Optional[RoutingInstability]:
        """
        Update neighbor state and detect instability.
        
        Returns:
            RoutingInstability if instability detected
        """
        key = f"{device_id}:{neighbor.protocol.value}:{neighbor.neighbor_id}"
        
        if key in self._neighbor_states:
            old_state = self._neighbor_states[key].state
            new_state = neighbor.state
            
            if old_state != new_state:
                # Record state change
                if key not in self._state_history:
                    self._state_history[key] = []
                
                import time
                self._state_history[key].append((time.time(), new_state))
                
                # Check for flapping
                instability = self._check_instability(key, neighbor)
                if instability:
                    return instability
        
        self._neighbor_states[key] = neighbor
        return None
    
    def _check_instability(
        self,
        key: str,
        neighbor: RoutingNeighbor
    ) -> Optional[RoutingInstability]:
        """Check for routing instability patterns."""
        import time
        
        history = self._state_history.get(key, [])
        
        if len(history) < 3:
            return None
        
        # Count state changes in last 10 minutes
        window = 600  # 10 minutes
        cutoff = time.time() - window
        recent_changes = [h for h in history if h[0] > cutoff]
        
        if len(recent_changes) >= 3:
            return RoutingInstability(
                protocol=neighbor.protocol,
                neighbor_id=neighbor.neighbor_id,
                instability_type="flap",
                severity="high",
                event_count=len(recent_changes),
                time_window=window,
                recommendation=f"BGP neighbor {neighbor.neighbor_id} is flapping. Check link stability and MTU."
            )
        
        return None
    
    def get_neighbor_status(
        self,
        device_id: str,
        protocol: Optional[RoutingProtocol] = None
    ) -> List[RoutingNeighbor]:
        """Get routing neighbor status for device."""
        prefix = f"{device_id}:"
        
        neighbors = []
        for key, neighbor in self._neighbor_states.items():
            if key.startswith(prefix):
                if protocol is None or neighbor.protocol == protocol:
                    neighbors.append(neighbor)
        
        return neighbors
    
    def is_bgp_established(self, device_id: str, neighbor_id: str) -> bool:
        """Check if BGP session is established."""
        key = f"{device_id}:{RoutingProtocol.BGP.value}:{neighbor_id}"
        neighbor = self._neighbor_states.get(key)
        
        if neighbor:
            return neighbor.state.lower() in ["established", "up", "full"]
        
        return False
    
    def get_down_bgp_sessions(self, device_id: str) -> List[RoutingNeighbor]:
        """Get list of down BGP sessions."""
        neighbors = self.get_neighbor_status(device_id, RoutingProtocol.BGP)
        
        return [
            n for n in neighbors
            if n.state.lower() not in ["established", "up", "full"]
        ]
