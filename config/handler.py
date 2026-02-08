"""
Config Handler Module

Handles YAML and JSON configuration files.
Provides validation, schema checking, and migration.
"""

from __future__ import annotations

import yaml
import json
from typing import Dict, Any, Optional, List
from pathlib import Path
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class ConfigSchema:
    """Configuration schema definition."""
    name: str
    required: bool = True
    type: str = "string"
    default: Any = None
    allowed_values: Optional[List] = None


class ConfigHandler:
    """
    Handles configuration file operations.
    
    Features:
    - Load/save YAML and JSON
    - Schema validation
    - Default value handling
    - Config migration
    """
    
    def __init__(self, config_path: str):
        self.config_path = Path(config_path)
        self._config: Dict[str, Any] = {}
        self._schema: Dict[str, ConfigSchema] = {}
        self._setup_default_schema()
    
    def _setup_default_schema(self) -> None:
        """Setup default configuration schema."""
        defaults = [
            ConfigSchema("version", required=True, type="string", default="1.0"),
            ConfigSchema("polling_interval", required=False, type="int", default=300),
            ConfigSchema("timeout", required=False, type="int", default=30),
            ConfigSchema("retry_count", required=False, type="int", default=3),
            ConfigSchema("log_level", required=False, type="string", default="INFO", 
                      allowed_values=["DEBUG", "INFO", "WARNING", "ERROR"]),
            ConfigSchema("data_retention_days", required=False, type="int", default=90),
        ]
        
        for schema in defaults:
            self._schema[schema.name] = schema
    
    def load(self) -> Dict[str, Any]:
        """
        Load configuration from file.
        
        Supports both YAML and JSON formats.
        Auto-detects format from extension.
        """
        if not self.config_path.exists():
            logger.warning(f"Config file not found: {self.config_path}")
            return self._create_default_config()
        
        try:
            content = self.config_path.read_text()
            
            if self.config_path.suffix in ['.yaml', '.yml']:
                self._config = yaml.safe_load(content) or {}
            elif self.config_path.suffix == '.json':
                self._config = json.loads(content)
            else:
                # Try YAML first, then JSON
                try:
                    self._config = yaml.safe_load(content) or {}
                except:
                    self._config = json.loads(content)
            
            # Apply defaults for missing values
            self._apply_defaults()
            
            logger.info(f"Loaded config from {self.config_path}")
            return self._config
            
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return self._create_default_config()
    
    def save(self, config: Optional[Dict] = None) -> bool:
        """
        Save configuration to file.
        
        Args:
            config: Config to save (uses loaded config if None)
        
        Returns:
            True if saved successfully
        """
        if config is not None:
            self._config = config
        
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            if self.config_path.suffix == '.json':
                content = json.dumps(self._config, indent=2)
            else:
                content = yaml.dump(self._config, default_flow_style=False, sort_keys=False)
            
            self.config_path.write_text(content)
            logger.info(f"Saved config to {self.config_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            return False
    
    def validate(self) -> List[str]:
        """
        Validate configuration against schema.
        
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        for name, schema in self._schema.items():
            if schema.required and name not in self._config:
                errors.append(f"Missing required field: {name}")
                continue
            
            if name in self._config:
                value = self._config[name]
                
                # Type validation
                if schema.type == "int" and not isinstance(value, int):
                    errors.append(f"Field {name} should be integer")
                elif schema.type == "bool" and not isinstance(value, bool):
                    errors.append(f"Field {name} should be boolean")
                elif schema.type == "list" and not isinstance(value, list):
                    errors.append(f"Field {name} should be list")
                
                # Allowed values validation
                if schema.allowed_values and value not in schema.allowed_values:
                    errors.append(
                        f"Field {name} value '{value}' not in allowed: {schema.allowed_values}"
                    )
        
        return errors
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any) -> None:
        """Set configuration value."""
        keys = key.split('.')
        config = self._config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
    
    def _apply_defaults(self) -> None:
        """Apply default values for missing fields."""
        for name, schema in self._schema.items():
            if name not in self._config and schema.default is not None:
                self._config[name] = schema.default
    
    def _create_default_config(self) -> Dict[str, Any]:
        """Create default configuration."""
        self._config = {}
        self._apply_defaults()
        return self._config
    
    def merge(self, other_config: Dict) -> Dict[str, Any]:
        """Merge another config into current."""
        self._config = self._deep_merge(self._config, other_config)
        return self._config
    
    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """Deep merge two dictionaries."""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result


class ConfigMigration:
    """
    Handles configuration migrations between versions.
    """
    
    def __init__(self):
        self._migrations: Dict[str, callable] = {}
    
    def register_migration(
        self,
        from_version: str,
        to_version: str,
        migration_func: callable
    ) -> None:
        """Register a migration function."""
        key = f"{from_version}->{to_version}"
        self._migrations[key] = migration_func
    
    def migrate(
        self,
        config: Dict,
        target_version: str
    ) -> Dict:
        """
        Migrate config to target version.
        
        Args:
            config: Current configuration
            target_version: Target version
        
        Returns:
            Migrated configuration
        """
        current_version = config.get('version', '1.0')
        
        while current_version != target_version:
            key = f"{current_version}->{target_version}"
            
            if key in self._migrations:
                config = self._migrations[key](config)
                # Extract new version from key
                current_version = target_version
            else:
                # No direct migration, try incremental
                break
        
        config['version'] = target_version
        return config
