"""
Device Profile Manager

Manages device profiles for quick configuration and deployment.
Supports templates, inheritance, and bulk operations.
"""

from __future__ import annotations

import yaml
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


@dataclass
class DeviceProfile:
    """Device profile template."""
    name: str
    description: str = ""
    device_type: str = ""
    os_type: str = ""
    credentials_id: str = ""
    variables: List[str] = field(default_factory=list)
    polling_interval: int = 300
    timeout: int = 30
    retry_count: int = 3
    groups: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    parent_profile: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "device_type": self.device_type,
            "os_type": self.os_type,
            "credentials_id": self.credentials_id,
            "variables": self.variables,
            "polling_interval": self.polling_interval,
            "timeout": self.timeout,
            "retry_count": self.retry_count,
            "groups": self.groups,
            "metadata": self.metadata,
            "parent_profile": self.parent_profile,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "DeviceProfile":
        """Create from dictionary."""
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            device_type=data.get("device_type", ""),
            os_type=data.get("os_type", ""),
            credentials_id=data.get("credentials_id", ""),
            variables=data.get("variables", []),
            polling_interval=data.get("polling_interval", 300),
            timeout=data.get("timeout", 30),
            retry_count=data.get("retry_count", 3),
            groups=data.get("groups", []),
            metadata=data.get("metadata", {}),
            parent_profile=data.get("parent_profile"),
        )


class DeviceProfileManager:
    """
    Manages device profiles for standardized configurations.
    
    Features:
    - Profile templates
    - Profile inheritance
    - Bulk device creation from profiles
    - Import/export
    """
    
    def __init__(self, profiles_dir: str = "profiles"):
        self.profiles_dir = Path(profiles_dir)
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        self._profiles: Dict[str, DeviceProfile] = {}
        self._load_builtin_profiles()
        self._load_custom_profiles()
    
    def _load_builtin_profiles(self) -> None:
        """Load built-in default profiles."""
        builtin_profiles = [
            DeviceProfile(
                name="cisco_router",
                description="Default profile for Cisco routers",
                device_type="router",
                os_type="cisco_ios",
                variables=["cpu_usage", "memory_usage", "interface_status", "bgp_peers", "temperature"],
                polling_interval=300,
                groups=["network", "routers"],
            ),
            DeviceProfile(
                name="cisco_switch",
                description="Default profile for Cisco switches",
                device_type="switch",
                os_type="cisco_ios",
                variables=["cpu_usage", "memory_usage", "interface_status", "vlan_status", "spanning_tree"],
                polling_interval=300,
                groups=["network", "switches"],
            ),
            DeviceProfile(
                name="linux_server",
                description="Default profile for Linux servers",
                device_type="server",
                os_type="linux",
                variables=["cpu_usage", "memory_usage", "disk_usage", "load_average", "process_count"],
                polling_interval=60,
                groups=["servers", "linux"],
            ),
            DeviceProfile(
                name="windows_server",
                description="Default profile for Windows servers",
                device_type="server",
                os_type="windows",
                variables=["cpu_usage", "memory_usage", "disk_usage", "service_status"],
                polling_interval=60,
                groups=["servers", "windows"],
            ),
            DeviceProfile(
                name="vmware_esxi",
                description="Default profile for VMware ESXi hosts",
                device_type="hypervisor",
                os_type="vmware_esxi",
                variables=["cpu_usage", "memory_usage", "datastore_usage", "vm_count", "host_status"],
                polling_interval=300,
                groups=["virtualization", "vmware"],
            ),
            DeviceProfile(
                name="firewall",
                description="Default profile for firewalls",
                device_type="firewall",
                os_type="fortios",
                variables=["cpu_usage", "memory_usage", "session_count", "interface_status", "vpn_status"],
                polling_interval=300,
                groups=["security", "firewalls"],
            ),
        ]
        
        for profile in builtin_profiles:
            self._profiles[profile.name] = profile
    
    def _load_custom_profiles(self) -> None:
        """Load custom profiles from directory."""
        if not self.profiles_dir.exists():
            return
        
        for profile_file in self.profiles_dir.glob("*.yaml"):
            try:
                with open(profile_file) as f:
                    data = yaml.safe_load(f)
                
                if data and "name" in data:
                    profile = DeviceProfile.from_dict(data)
                    self._profiles[profile.name] = profile
                    
            except Exception as e:
                logger.warning(f"Failed to load profile {profile_file}: {e}")
    
    def create_profile(
        self,
        name: str,
        description: str = "",
        device_type: str = "",
        os_type: str = "",
        parent: Optional[str] = None
    ) -> DeviceProfile:
        """
        Create a new device profile.
        
        Args:
            name: Profile name
            description: Profile description
            device_type: Type of device
            os_type: Operating system
            parent: Parent profile for inheritance
        
        Returns:
            Created DeviceProfile
        """
        if name in self._profiles:
            raise ValueError(f"Profile '{name}' already exists")
        
        profile = DeviceProfile(
            name=name,
            description=description,
            device_type=device_type,
            os_type=os_type,
            parent_profile=parent,
        )
        
        # Inherit from parent if specified
        if parent and parent in self._profiles:
            parent_profile = self._profiles[parent]
            profile.variables = parent_profile.variables.copy()
            profile.polling_interval = parent_profile.polling_interval
            profile.timeout = parent_profile.timeout
            profile.retry_count = parent_profile.retry_count
            profile.groups = parent_profile.groups.copy()
        
        self._profiles[name] = profile
        self._save_profile(profile)
        
        logger.info(f"Created profile: {name}")
        return profile
    
    def update_profile(self, name: str, **kwargs) -> Optional[DeviceProfile]:
        """
        Update an existing profile.
        
        Args:
            name: Profile name
            **kwargs: Fields to update
        
        Returns:
            Updated profile or None
        """
        if name not in self._profiles:
            return None
        
        profile = self._profiles[name]
        
        for key, value in kwargs.items():
            if hasattr(profile, key):
                setattr(profile, key, value)
        
        self._save_profile(profile)
        logger.info(f"Updated profile: {name}")
        
        return profile
    
    def delete_profile(self, name: str) -> bool:
        """Delete a profile."""
        if name not in self._profiles:
            return False
        
        # Check if any profiles inherit from this
        inheritors = [
            p.name for p in self._profiles.values()
            if p.parent_profile == name
        ]
        
        if inheritors:
            logger.warning(f"Cannot delete profile '{name}' - inherited by: {inheritors}")
            return False
        
        del self._profiles[name]
        
        # Delete file
        profile_file = self.profiles_dir / f"{name}.yaml"
        if profile_file.exists():
            profile_file.unlink()
        
        logger.info(f"Deleted profile: {name}")
        return True
    
    def get_profile(self, name: str) -> Optional[DeviceProfile]:
        """Get a profile by name."""
        return self._profiles.get(name)
    
    def list_profiles(self, device_type: Optional[str] = None) -> List[str]:
        """
        List available profiles.
        
        Args:
            device_type: Filter by device type
        
        Returns:
            List of profile names
        """
        if device_type:
            return [
                name for name, p in self._profiles.items()
                if p.device_type == device_type
            ]
        return list(self._profiles.keys())
    
    def apply_profile(
        self,
        profile_name: str,
        hostname: str,
        overrides: Optional[Dict] = None
    ) -> Dict:
        """
        Apply a profile to create device configuration.
        
        Args:
            profile_name: Profile to apply
            hostname: Device hostname
            overrides: Field overrides
        
        Returns:
            Device configuration dict
        """
        profile = self._profiles.get(profile_name)
        if not profile:
            raise ValueError(f"Profile not found: {profile_name}")
        
        config = {
            "device_id": hostname,
            "hostname": hostname,
            "device_type": profile.device_type,
            "os_type": profile.os_type,
            "credentials_id": profile.credentials_id,
            "variables": profile.variables,
            "polling_interval": profile.polling_interval,
            "timeout": profile.timeout,
            "retry_count": profile.retry_count,
            "groups": profile.groups.copy(),
            "profile_applied": profile_name,
        }
        
        # Apply overrides
        if overrides:
            config.update(overrides)
        
        return config
    
    def bulk_create_devices(
        self,
        profile_name: str,
        hostnames: List[str]
    ) -> List[Dict]:
        """
        Create device configurations for multiple hostnames.
        
        Args:
            profile_name: Profile to apply
            hostnames: List of hostnames
        
        Returns:
            List of device configurations
        """
        devices = []
        for hostname in hostnames:
            try:
                config = self.apply_profile(profile_name, hostname)
                devices.append(config)
            except Exception as e:
                logger.error(f"Failed to create device config for {hostname}: {e}")
        
        return devices
    
    def _save_profile(self, profile: DeviceProfile) -> None:
        """Save profile to file."""
        profile_file = self.profiles_dir / f"{profile.name}.yaml"
        
        with open(profile_file, 'w') as f:
            yaml.dump(profile.to_dict(), f, default_flow_style=False)
    
    def export_profile(self, name: str, filepath: str) -> bool:
        """Export profile to JSON file."""
        profile = self._profiles.get(name)
        if not profile:
            return False
        
        with open(filepath, 'w') as f:
            json.dump(profile.to_dict(), f, indent=2)
        
        return True
    
    def import_profile(self, filepath: str) -> Optional[DeviceProfile]:
        """Import profile from JSON/YAML file."""
        try:
            with open(filepath) as f:
                if filepath.endswith('.json'):
                    data = json.load(f)
                else:
                    data = yaml.safe_load(f)
            
            profile = DeviceProfile.from_dict(data)
            self._profiles[profile.name] = profile
            self._save_profile(profile)
            
            return profile
            
        except Exception as e:
            logger.error(f"Failed to import profile: {e}")
            return None
