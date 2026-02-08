import importlib.util
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

import yaml


@dataclass(frozen=True)
class Plugin:
    os_name: str
    base_dir: str
    command_map: Dict[str, Any]
    variable_map: Dict[str, Any]
    parser_module: Any
    help_kb: Dict[str, Any]


def _load_yaml(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_plugin(os_name: str, plugins_root: Optional[str] = None) -> Plugin:
    if plugins_root is None:
        plugins_root = os.path.join(os.path.dirname(__file__), "..", "plugins", "builtin")
        plugins_root = os.path.abspath(plugins_root)

    base_dir = os.path.join(plugins_root, os_name)
    if not os.path.isdir(base_dir):
        raise FileNotFoundError(f"Plugin not found: {os_name} under {plugins_root}")

    command_map = _load_yaml(os.path.join(base_dir, "command_map.yaml"))
    variable_map = _load_yaml(os.path.join(base_dir, "variable_map.yaml"))
    help_kb = _load_yaml(os.path.join(base_dir, "help.yaml"))

    parser_path = os.path.join(base_dir, "parser.py")
    spec = importlib.util.spec_from_file_location(f"autodetector.plugins.{os_name}.parser", parser_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed loading parser module for {os_name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return Plugin(
        os_name=os_name,
        base_dir=base_dir,
        command_map=command_map,
        variable_map=variable_map,
        parser_module=module,
        help_kb=help_kb,
    )
