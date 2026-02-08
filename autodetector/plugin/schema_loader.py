from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from autodetector.plugin.loader import load_plugin


@dataclass(frozen=True)
class VariableDef:
    name: str
    type: str
    unit: str
    source_command: str
    weight: float


@dataclass(frozen=True)
class Schema:
    os_name: str
    variables: Dict[str, VariableDef]


def load_schema(os_name: str) -> Schema:
    plugin = load_plugin(os_name)
    schema = (plugin.variable_map or {}).get("schema") or {}
    vars_doc = schema.get("variables") or {}

    variables: Dict[str, VariableDef] = {}
    for k, v in (vars_doc.items() if isinstance(vars_doc, dict) else []):
        if not isinstance(v, dict):
            continue
        variables[str(k)] = VariableDef(
            name=str(k),
            type=str(v.get("type", "gauge")),
            unit=str(v.get("unit", "")),
            source_command=str(v.get("source_command", "")),
            weight=float(v.get("weight", 1.0)),
        )

    return Schema(os_name=os_name, variables=variables)


def allowed_variables(os_name: str) -> List[str]:
    s = load_schema(os_name)
    return sorted(list(s.variables.keys()))


def variable_weight(os_name: str, variable: str, default: float = 1.0) -> float:
    s = load_schema(os_name)
    vd = s.variables.get(variable)
    if not vd:
        return float(default)
    return float(vd.weight)
