"""
Plugin Loader Module

Dynamic loading of device plugins for different vendors and OS types.
Supports hot-reloading and plugin registry.
"""

from __future__ import annotations

import os
import sys
import importlib
import importlib.util
from typing import Dict, List, Optional, Type, Any
from pathlib import Path
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class PluginInfo:
    """Plugin metadata."""
    name: str
    version: str
    author: str
    description: str
    supported_devices: List[str]
    entry_point: str
    path: str
    loaded: bool = False


class PluginLoader:
    """
    Dynamic plugin loader for device parsers and collectors.
    
    Features:
    - Load plugins from directories
    - Hot-reload support
    - Dependency checking
    - Plugin registry
    """
    
    def __init__(self, plugin_dirs: List[str]):
        self.plugin_dirs = [Path(d) for d in plugin_dirs]
        self._plugins: Dict[str, Any] = {}
        self._plugin_info: Dict[str, PluginInfo] = {}
        self._hooks: Dict[str, List] = {}
    
    def discover_plugins(self) -> List[PluginInfo]:
        """
        Discover available plugins in plugin directories.
        
        Returns:
            List of plugin info objects
        """
        discovered = []
        
        for plugin_dir in self.plugin_dirs:
            if not plugin_dir.exists():
                continue
            
            for item in plugin_dir.iterdir():
                if item.is_dir() and not item.name.startswith("_"):
                    # Check for plugin.py or __init__.py
                    plugin_file = item / "plugin.py"
                    init_file = item / "__init__.py"
                    
                    if plugin_file.exists() or init_file.exists():
                        info = self._parse_plugin_info(item)
                        if info:
                            discovered.append(info)
                            self._plugin_info[info.name] = info
        
        return discovered
    
    def _parse_plugin_info(self, plugin_path: Path) -> Optional[PluginInfo]:
        """Parse plugin metadata from directory."""
        # Look for plugin.yaml or __init__.py docstring
        meta_file = plugin_path / "plugin.yaml"
        
        if meta_file.exists():
            try:
                import yaml
                with open(meta_file) as f:
                    meta = yaml.safe_load(f)
                
                return PluginInfo(
                    name=meta.get("name", plugin_path.name),
                    version=meta.get("version", "1.0.0"),
                    author=meta.get("author", "Unknown"),
                    description=meta.get("description", ""),
                    supported_devices=meta.get("supported_devices", []),
                    entry_point=meta.get("entry_point", "plugin"),
                    path=str(plugin_path)
                )
            except Exception as e:
                logger.warning(f"Failed to parse plugin metadata for {plugin_path}: {e}")
        
        # Default info
        return PluginInfo(
            name=plugin_path.name,
            version="1.0.0",
            author="Unknown",
            description="",
            supported_devices=[],
            entry_point="plugin",
            path=str(plugin_path)
        )
    
    def load_plugin(self, name: str) -> Optional[Any]:
        """
        Load a plugin by name.
        
        Args:
            name: Plugin name
        
        Returns:
            Loaded plugin module or None
        """
        if name in self._plugins:
            return self._plugins[name]
        
        if name not in self._plugin_info:
            logger.error(f"Plugin not found: {name}")
            return None
        
        info = self._plugin_info[name]
        
        try:
            # Add plugin path to sys.path
            plugin_path = Path(info.path)
            if str(plugin_path.parent) not in sys.path:
                sys.path.insert(0, str(plugin_path.parent))
            
            # Load the module
            spec = importlib.util.spec_from_file_location(
                info.name,
                plugin_path / f"{info.entry_point}.py"
            )
            
            if spec is None or spec.loader is None:
                # Try package loading
                spec = importlib.util.spec_from_file_location(
                    info.name,
                    plugin_path / "__init__.py"
                )
            
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[info.name] = module
                spec.loader.exec_module(module)
                
                self._plugins[name] = module
                info.loaded = True
                
                logger.info(f"Loaded plugin: {name} v{info.version}")
                return module
            
        except Exception as e:
            logger.error(f"Failed to load plugin {name}: {e}")
            return None
    
    def unload_plugin(self, name: str) -> bool:
        """Unload a plugin."""
        if name not in self._plugins:
            return False
        
        # Remove from sys.modules
        if name in sys.modules:
            del sys.modules[name]
        
        del self._plugins[name]
        
        if name in self._plugin_info:
            self._plugin_info[name].loaded = False
        
        logger.info(f"Unloaded plugin: {name}")
        return True
    
    def reload_plugin(self, name: str) -> Optional[Any]:
        """Reload a plugin (hot-reload)."""
        self.unload_plugin(name)
        return self.load_plugin(name)
    
    def get_plugin(self, name: str) -> Optional[Any]:
        """Get loaded plugin."""
        return self._plugins.get(name)
    
    def list_plugins(self) -> List[str]:
        """List all available plugin names."""
        return list(self._plugin_info.keys())
    
    def list_loaded(self) -> List[str]:
        """List loaded plugin names."""
        return list(self._plugins.keys())
    
    def get_plugin_info(self, name: str) -> Optional[PluginInfo]:
        """Get plugin metadata."""
        return self._plugin_info.get(name)
    
    def register_hook(self, event: str, callback) -> None:
        """Register a hook for plugin events."""
        if event not in self._hooks:
            self._hooks[event] = []
        self._hooks[event].append(callback)
    
    def trigger_hook(self, event: str, *args, **kwargs) -> None:
        """Trigger hooks for an event."""
        for callback in self._hooks.get(event, []):
            try:
                callback(*args, **kwargs)
            except Exception as e:
                logger.error(f"Hook error: {e}")
    
    def load_all(self) -> Dict[str, Any]:
        """Load all discovered plugins."""
        self.discover_plugins()
        
        loaded = {}
        for name in self._plugin_info:
            plugin = self.load_plugin(name)
            if plugin:
                loaded[name] = plugin
        
        return loaded


class DevicePluginRegistry:
    """
    Registry for device-specific plugins.
    Maps device types to their handlers.
    """
    
    def __init__(self):
        self._handlers: Dict[str, Any] = {}
        self._parsers: Dict[str, Any] = {}
        self._collectors: Dict[str, Any] = {}
    
    def register_handler(self, device_type: str, handler) -> None:
        """Register a device handler."""
        self._handlers[device_type] = handler
    
    def register_parser(self, device_type: str, parser) -> None:
        """Register a parser for device type."""
        self._parsers[device_type] = parser
    
    def register_collector(self, device_type: str, collector) -> None:
        """Register a collector for device type."""
        self._collectors[device_type] = collector
    
    def get_handler(self, device_type: str) -> Optional[Any]:
        """Get handler for device type."""
        return self._handlers.get(device_type)
    
    def get_parser(self, device_type: str) -> Optional[Any]:
        """Get parser for device type."""
        return self._parsers.get(device_type)
    
    def get_collector(self, device_type: str) -> Optional[Any]:
        """Get collector for device type."""
        return self._collectors.get(device_type)
    
    def list_supported_types(self) -> List[str]:
        """List all registered device types."""
        return list(set(self._handlers.keys()) | set(self._parsers.keys()))
    
    def is_supported(self, device_type: str) -> bool:
        """Check if device type is supported."""
        return device_type in self._handlers or device_type in self._parsers


# Global registry instance
plugin_registry = DevicePluginRegistry()
