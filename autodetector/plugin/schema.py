from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple


REQUIRED_COMMAND_MAP_KEYS = {"commands"}
REQUIRED_VARIABLE_MAP_KEYS = {"schema"}


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    errors: List[str]


def validate_command_map(doc: Dict[str, Any]) -> ValidationResult:
    errors: List[str] = []
    if not isinstance(doc, dict):
        return ValidationResult(False, ["command_map must be a mapping"])

    missing = REQUIRED_COMMAND_MAP_KEYS - set(doc.keys())
    if missing:
        errors.append(f"command_map missing keys: {sorted(missing)}")

    cmds = doc.get("commands")
    if cmds is None or not isinstance(cmds, dict):
        errors.append("command_map.commands must be a mapping")
    else:
        for group in ["normal", "deep_audit"]:
            if group in cmds and not isinstance(cmds[group], dict):
                errors.append(f"command_map.commands.{group} must be a mapping")

    sess = doc.get("session")
    if sess is not None:
        if not isinstance(sess, dict):
            errors.append("command_map.session must be a mapping")
        else:
            if sess.get("mode") not in (None, "exec", "shell"):
                errors.append("command_map.session.mode must be exec or shell")

    return ValidationResult(len(errors) == 0, errors)


def validate_variable_map(doc: Dict[str, Any]) -> ValidationResult:
    errors: List[str] = []
    if not isinstance(doc, dict):
        return ValidationResult(False, ["variable_map must be a mapping"])

    missing = REQUIRED_VARIABLE_MAP_KEYS - set(doc.keys())
    if missing:
        errors.append(f"variable_map missing keys: {sorted(missing)}")

    schema = doc.get("schema")
    if not isinstance(schema, dict):
        errors.append("variable_map.schema must be a mapping")
        return ValidationResult(False, errors)

    os_name = schema.get("os")
    if not os_name:
        errors.append("variable_map.schema.os is required")

    variables = schema.get("variables")
    if not isinstance(variables, dict) or not variables:
        errors.append("variable_map.schema.variables must be a non-empty mapping")
    else:
        for var, meta in variables.items():
            if not isinstance(meta, dict):
                errors.append(f"variable {var} must map to a dict")
                continue
            if meta.get("type") not in {"gauge", "counter", "state"}:
                errors.append(f"variable {var}.type must be gauge|counter|state")

    return ValidationResult(len(errors) == 0, errors)


def validate_plugin_docs(command_map: Dict[str, Any], variable_map: Dict[str, Any]) -> Tuple[ValidationResult, ValidationResult]:
    return validate_command_map(command_map), validate_variable_map(variable_map)
