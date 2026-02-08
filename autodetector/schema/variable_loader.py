"""
Variable Schema Loader

Loads and manages variable schemas for device metric normalization.
Maps vendor-specific variables to normalized schema.
"""

from __future__ import annotations

import yaml
import re
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


@dataclass
class VariableSchema:
    """Schema definition for a normalized variable."""
    name: str
    type: str  # float, int, str, bool, enum
    unit: str = ""
    description: str = ""
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    warn_threshold: Optional[float] = None
    crit_threshold: Optional[float] = None
    weight: float = 1.0  # Health score weight
    enum_values: List[str] = field(default_factory=list)
    patterns: List[str] = field(default_factory=list)  # Regex patterns for parsing


@dataclass
class VendorMapping:
    """Mapping from vendor-specific to normalized variable."""
    vendor_os: str
    vendor_variable: str
    normalized_name: str
    transform: Optional[str] = None  # Transform function (e.g., "divide_by_100")
    parser_type: str = "regex"  # regex, json, xml, delimiter


class VariableSchemaLoader:
    """
    Loads and manages variable schemas from YAML files.
    
    Provides:
    - Schema validation
    - Vendor variable mapping
    - Transformation functions
    - Metric normalization
    """
    
    # Built-in transforms
    TRANSFORMS = {
        "divide_by_100": lambda x: float(x) / 100.0,
        "multiply_by_100": lambda x: float(x) * 100.0,
        "bytes_to_mb": lambda x: float(x) / (1024 * 1024),
        "bytes_to_gb": lambda x: float(x) / (1024 * 1024 * 1024),
        "kb_to_mb": lambda x: float(x) / 1024,
        "mb_to_gb": lambda x: float(x) / 1024,
        "to_int": lambda x: int(float(x)),
        "to_float": lambda x: float(x),
        "strip_percent": lambda x: float(str(x).rstrip("%")),
        "invert_percent": lambda x: 100.0 - float(x),
    }
    
    def __init__(self, schema_dir: str = "schemas"):
        self.schema_dir = Path(schema_dir)
        self._schemas: Dict[str, VariableSchema] = {}
        self._vendor_mappings: Dict[str, Dict[str, VendorMapping]] = {}
        self._loaded = False
    
    def load_schemas(self) -> None:
        """Load all schema files from directory."""
        if self._loaded:
            return
        
        if not self.schema_dir.exists():
            logger.warning(f"Schema directory not found: {self.schema_dir}")
            return
        
        for schema_file in self.schema_dir.glob("*.yaml"):
            try:
                self._load_schema_file(schema_file)
            except Exception as e:
                logger.error(f"Failed to load schema {schema_file}: {e}")
        
        self._loaded = True
        logger.info(f"Loaded {len(self._schemas)} variable schemas")
    
    def _load_schema_file(self, filepath: Path) -> None:
        """Load a single schema YAML file."""
        with open(filepath, 'r') as f:
            data = yaml.safe_load(f)
        
        if not data:
            return
        
        # Load variable schemas
        for var_data in data.get("variables", []):
            schema = VariableSchema(
                name=var_data["name"],
                type=var_data.get("type", "float"),
                unit=var_data.get("unit", ""),
                description=var_data.get("description", ""),
                min_value=var_data.get("min"),
                max_value=var_data.get("max"),
                warn_threshold=var_data.get("thresholds", {}).get("warn"),
                crit_threshold=var_data.get("thresholds", {}).get("crit"),
                weight=var_data.get("weight", 1.0),
                enum_values=var_data.get("enum", []),
                patterns=var_data.get("patterns", []),
            )
            self._schemas[schema.name] = schema
        
        # Load vendor mappings
        for mapping_data in data.get("vendor_mappings", []):
            mapping = VendorMapping(
                vendor_os=mapping_data["vendor_os"],
                vendor_variable=mapping_data["vendor_variable"],
                normalized_name=mapping_data["normalized_name"],
                transform=mapping_data.get("transform"),
                parser_type=mapping_data.get("parser_type", "regex"),
            )
            
            if mapping.vendor_os not in self._vendor_mappings:
                self._vendor_mappings[mapping.vendor_os] = {}
            
            self._vendor_mappings[mapping.vendor_os][mapping.vendor_variable] = mapping
    
    def get_schema(self, variable_name: str) -> Optional[VariableSchema]:
        """Get schema for normalized variable."""
        self.load_schemas()
        return self._schemas.get(variable_name)
    
    def get_vendor_mapping(
        self,
        vendor_os: str,
        vendor_variable: str
    ) -> Optional[VendorMapping]:
        """Get mapping for vendor-specific variable."""
        self.load_schemas()
        
        vendor_maps = self._vendor_mappings.get(vendor_os, {})
        return vendor_maps.get(vendor_variable)
    
    def normalize_value(
        self,
        value: Any,
        schema: VariableSchema,
        transform: Optional[str] = None
    ) -> Union[float, int, str, bool]:
        """
        Normalize a value according to schema.
        
        Args:
            value: Raw value from device
            schema: Target variable schema
            transform: Optional transform to apply
        
        Returns:
            Normalized value
        """
        # Apply transform if specified
        if transform and transform in self.TRANSFORMS:
            try:
                value = self.TRANSFORMS[transform](value)
            except Exception as e:
                logger.warning(f"Transform {transform} failed: {e}")
        
        # Type conversion
        try:
            if schema.type == "float":
                return float(value)
            elif schema.type == "int":
                return int(float(value))
            elif schema.type == "bool":
                if isinstance(value, str):
                    return value.lower() in ("true", "1", "yes", "up", "active")
                return bool(value)
            elif schema.type == "enum":
                str_val = str(value).lower()
                for enum_val in schema.enum_values:
                    if str_val == enum_val.lower():
                        return enum_val
                return str(value)
            else:
                return str(value)
        except Exception as e:
            logger.warning(f"Type conversion failed for {schema.name}: {e}")
            return value
    
    def validate_value(self, value: Any, schema: VariableSchema) -> bool:
        """Validate a value against schema constraints."""
        try:
            if schema.type in ("float", "int"):
                num_val = float(value)
                if schema.min_value is not None and num_val < schema.min_value:
                    return False
                if schema.max_value is not None and num_val > schema.max_value:
                    return False
            
            if schema.type == "enum" and schema.enum_values:
                return str(value).lower() in [e.lower() for e in schema.enum_values]
            
            return True
        except Exception:
            return False
    
    def check_threshold(
        self,
        value: float,
        schema: VariableSchema
    ) -> tuple:
        """
        Check value against thresholds.
        
        Returns:
            (status, severity) where status is one of "ok", "warn", "crit"
        """
        if schema.crit_threshold is not None:
            if schema.crit_threshold > schema.warn_threshold:
                # High is bad (e.g., CPU)
                if value >= schema.crit_threshold:
                    return ("crit", "critical")
                elif value >= schema.warn_threshold:
                    return ("warn", "warning")
            else:
                # Low is bad (e.g., free memory)
                if value <= schema.crit_threshold:
                    return ("crit", "critical")
                elif value <= schema.warn_threshold:
                    return ("warn", "warning")
        
        return ("ok", None)
    
    def list_schemas(self) -> List[str]:
        """List all available schema names."""
        self.load_schemas()
        return list(self._schemas.keys())
    
    def list_vendor_mappings(self, vendor_os: str) -> List[str]:
        """List mapped variables for a vendor OS."""
        self.load_schemas()
        vendor_maps = self._vendor_mappings.get(vendor_os, {})
        return list(vendor_maps.keys())
    
    def create_default_schemas(self, output_dir: str) -> None:
        """Create default schema YAML files."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        default_schemas = {
            "core_metrics.yaml": self._get_core_metrics_schema(),
            "interface_metrics.yaml": self._get_interface_schema(),
            "hardware_metrics.yaml": self._get_hardware_schema(),
        }
        
        for filename, content in default_schemas.items():
            filepath = output_path / filename
            with open(filepath, 'w') as f:
                yaml.dump(content, f, default_flow_style=False)
            logger.info(f"Created schema file: {filepath}")
    
    def _get_core_metrics_schema(self) -> Dict:
        """Generate core metrics schema."""
        return {
            "variables": [
                {
                    "name": "CPU_USAGE",
                    "type": "float",
                    "unit": "%",
                    "description": "CPU utilization percentage",
                    "min": 0,
                    "max": 100,
                    "thresholds": {"warn": 70, "crit": 90},
                    "weight": 0.3,
                    "patterns": [r"(\d+(?:\.\d+)?)%?\s*cpu", r"cpu:\s*(\d+)"],
                },
                {
                    "name": "MEMORY_USAGE",
                    "type": "float",
                    "unit": "%",
                    "description": "Memory utilization percentage",
                    "min": 0,
                    "max": 100,
                    "thresholds": {"warn": 80, "crit": 95},
                    "weight": 0.25,
                    "patterns": [r"(\d+(?:\.\d+)?)%?\s*memory", r"mem:\s*(\d+)"],
                },
                {
                    "name": "DISK_USAGE",
                    "type": "float",
                    "unit": "%",
                    "description": "Disk utilization percentage",
                    "min": 0,
                    "max": 100,
                    "thresholds": {"warn": 85, "crit": 95},
                    "weight": 0.2,
                    "patterns": [r"(\d+(?:\.\d+)?)%?\s*disk", r"capacity:\s*(\d+)"],
                },
            ]
        }
    
    def _get_interface_schema(self) -> Dict:
        """Generate interface metrics schema."""
        return {
            "variables": [
                {
                    "name": "INTERFACE_STATUS",
                    "type": "enum",
                    "description": "Interface operational status",
                    "enum": ["up", "down", "admin_down", "unknown"],
                    "weight": 0.15,
                },
                {
                    "name": "INTERFACE_ERRORS",
                    "type": "int",
                    "unit": "errors",
                    "description": "Interface error count",
                    "min": 0,
                    "thresholds": {"warn": 10, "crit": 100},
                    "weight": 0.1,
                },
            ]
        }
    
    def _get_hardware_schema(self) -> Dict:
        """Generate hardware metrics schema."""
        return {
            "variables": [
                {
                    "name": "TEMPERATURE",
                    "type": "float",
                    "unit": "°C",
                    "description": "Device temperature",
                    "thresholds": {"warn": 65, "crit": 80},
                    "weight": 0.1,
                },
                {
                    "name": "POWER_STATUS",
                    "type": "enum",
                    "description": "Power supply status",
                    "enum": ["ok", "failed", "redundant", "single"],
                    "weight": 0.15,
                },
                {
                    "name": "FAN_STATUS",
                    "type": "enum",
                    "description": "Fan status",
                    "enum": ["ok", "failed", "degraded"],
                    "weight": 0.1,
                },
            ]
        }
