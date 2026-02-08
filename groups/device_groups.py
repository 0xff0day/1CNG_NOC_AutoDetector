"""
Device Grouping Module

Manages device groups for organized monitoring and alerting.
Supports hierarchical groups and dynamic membership.
"""

from __future__ import annotations

from typing import List, Dict, Set, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path
import yaml
import logging

logger = logging.getLogger(__name__)


@dataclass
class DeviceGroup:
    """Device group definition."""
    name: str
    description: str = ""
    devices: Set[str] = field(default_factory=set)
    criteria: Dict[str, Any] = field(default_factory=dict)
    parent: Optional[str] = None
    children: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    
    def add_device(self, device_id: str) -> None:
        """Add device to group."""
        self.devices.add(device_id)
    
    def remove_device(self, device_id: str) -> bool:
        """Remove device from group."""
        if device_id in self.devices:
            self.devices.remove(device_id)
            return True
        return False
    
    def has_device(self, device_id: str) -> bool:
        """Check if device is in group."""
        return device_id in self.devices
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "devices": list(self.devices),
            "criteria": self.criteria,
            "parent": self.parent,
            "children": self.children,
            "metadata": self.metadata,
        }


class DeviceGroupingManager:
    """
    Manages device groups and membership.
    
    Features:
    - Static groups (manual assignment)
    - Dynamic groups (criteria-based)
    - Hierarchical groups
    - Group inheritance
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self.groups: Dict[str, DeviceGroup] = {}
        self.config_path = Path(config_path) if config_path else None
        
        if self.config_path and self.config_path.exists():
            self.load_groups()
    
    def create_group(
        self,
        name: str,
        description: str = "",
        criteria: Optional[Dict] = None,
        parent: Optional[str] = None
    ) -> DeviceGroup:
        """
        Create a new device group.
        
        Args:
            name: Group name
            description: Group description
            criteria: Criteria for dynamic membership
            parent: Parent group name
        
        Returns:
            Created DeviceGroup
        """
        if name in self.groups:
            raise ValueError(f"Group '{name}' already exists")
        
        group = DeviceGroup(
            name=name,
            description=description,
            criteria=criteria or {},
            parent=parent
        )
        
        self.groups[name] = group
        
        # Register with parent
        if parent and parent in self.groups:
            self.groups[parent].children.append(name)
        
        logger.info(f"Created group: {name}")
        return group
    
    def delete_group(self, name: str, remove_devices: bool = False) -> bool:
        """
        Delete a group.
        
        Args:
            name: Group name
            remove_devices: Also remove devices from system
        
        Returns:
            True if deleted
        """
        if name not in self.groups:
            return False
        
        group = self.groups[name]
        
        # Handle children
        for child_name in group.children:
            if child_name in self.groups:
                self.groups[child_name].parent = None
        
        # Handle parent
        if group.parent and group.parent in self.groups:
            parent = self.groups[group.parent]
            if name in parent.children:
                parent.children.remove(name)
        
        del self.groups[name]
        logger.info(f"Deleted group: {name}")
        return True
    
    def add_device_to_group(self, device_id: str, group_name: str) -> bool:
        """Add device to a group."""
        if group_name not in self.groups:
            return False
        
        self.groups[group_name].add_device(device_id)
        return True
    
    def remove_device_from_group(self, device_id: str, group_name: str) -> bool:
        """Remove device from a group."""
        if group_name not in self.groups:
            return False
        
        return self.groups[group_name].remove_device(device_id)
    
    def get_device_groups(self, device_id: str) -> List[str]:
        """
        Get all groups that contain a device.
        
        Returns:
            List of group names
        """
        groups = []
        
        for name, group in self.groups.items():
            if group.has_device(device_id):
                groups.append(name)
        
        return groups
    
    def get_group_devices(self, group_name: str) -> List[str]:
        """
        Get all devices in a group (including children).
        
        Returns:
            List of device IDs
        """
        if group_name not in self.groups:
            return []
        
        devices = set(self.groups[group_name].devices)
        
        # Add devices from children
        for child_name in self.groups[group_name].children:
            devices.update(self.get_group_devices(child_name))
        
        return list(devices)
    
    def evaluate_dynamic_membership(
        self,
        device_id: str,
        device_attributes: Dict[str, Any]
    ) -> List[str]:
        """
        Evaluate which dynamic groups a device should belong to.
        
        Args:
            device_id: Device identifier
            device_attributes: Device properties
        
        Returns:
            List of matching group names
        """
        matching = []
        
        for name, group in self.groups.items():
            if not group.criteria:
                continue
            
            if self._matches_criteria(device_attributes, group.criteria):
                matching.append(name)
                group.add_device(device_id)
        
        return matching
    
    def _matches_criteria(
        self,
        attributes: Dict[str, Any],
        criteria: Dict[str, Any]
    ) -> bool:
        """Check if attributes match criteria."""
        for key, expected in criteria.items():
            actual = attributes.get(key)
            
            if isinstance(expected, list):
                if actual not in expected:
                    return False
            elif isinstance(expected, dict):
                # Range check
                if "min" in expected and actual < expected["min"]:
                    return False
                if "max" in expected and actual > expected["max"]:
                    return False
            else:
                if actual != expected:
                    return False
        
        return True
    
    def create_default_groups(self) -> None:
        """Create default system groups."""
        defaults = [
            ("all_devices", "All managed devices", {}),
            ("critical_devices", "Critical infrastructure", {"priority": "critical"}),
            ("routers", "Network routers", {"device_type": "router"}),
            ("switches", "Network switches", {"device_type": "switch"}),
            ("firewalls", "Security firewalls", {"device_type": "firewall"}),
            ("servers", "Compute servers", {"device_type": "server"}),
            ("hypervisors", "Virtualization hosts", {"device_type": "hypervisor"}),
        ]
        
        for name, desc, criteria in defaults:
            try:
                self.create_group(name, desc, criteria)
            except ValueError:
                pass  # Already exists
    
    def load_groups(self) -> None:
        """Load groups from YAML file."""
        if not self.config_path or not self.config_path.exists():
            return
        
        try:
            with open(self.config_path, 'r') as f:
                data = yaml.safe_load(f)
            
            for group_data in data.get("groups", []):
                group = DeviceGroup(
                    name=group_data["name"],
                    description=group_data.get("description", ""),
                    devices=set(group_data.get("devices", [])),
                    criteria=group_data.get("criteria", {}),
                    parent=group_data.get("parent"),
                    children=group_data.get("children", []),
                    metadata=group_data.get("metadata", {}),
                )
                self.groups[group.name] = group
            
            logger.info(f"Loaded {len(self.groups)} groups")
            
        except Exception as e:
            logger.error(f"Failed to load groups: {e}")
    
    def save_groups(self) -> None:
        """Save groups to YAML file."""
        if not self.config_path:
            return
        
        data = {
            "groups": [g.to_dict() for g in self.groups.values()]
        }
        
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.config_path, 'w') as f:
            yaml.dump(data, f, default_flow_style=False)
        
        logger.info(f"Saved {len(self.groups)} groups")
    
    def list_groups(self) -> List[str]:
        """List all group names."""
        return list(self.groups.keys())
    
    def get_group_info(self, group_name: str) -> Optional[Dict]:
        """Get detailed group information."""
        if group_name not in self.groups:
            return None
        
        group = self.groups[group_name]
        
        return {
            "name": group.name,
            "description": group.description,
            "device_count": len(group.devices),
            "devices": list(group.devices)[:100],  # Limit for display
            "criteria": group.criteria,
            "parent": group.parent,
            "children": group.children,
            "all_devices": self.get_group_devices(group_name),
        }
