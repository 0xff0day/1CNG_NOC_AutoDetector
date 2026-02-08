from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List

import yaml

from autodetector.plugin.loader import load_plugin
from autodetector.plugin.schema import validate_plugin_docs


@dataclass(frozen=True)
class PluginInfo:
    os_name: str
    path: str


def builtin_plugins_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "plugins", "builtin"))


def list_builtin_plugins() -> List[PluginInfo]:
    root = builtin_plugins_root()
    if not os.path.isdir(root):
        return []

    items: List[PluginInfo] = []
    for name in sorted(os.listdir(root)):
        p = os.path.join(root, name)
        if os.path.isdir(p) and not name.startswith("_"):
            items.append(PluginInfo(os_name=name, path=p))
    return items


def validate_plugin(os_name: str) -> Dict[str, Any]:
    plugin = load_plugin(os_name)
    v1, v2 = validate_plugin_docs(plugin.command_map, plugin.variable_map)
    return {
        "os": os_name,
        "ok": bool(v1.ok and v2.ok),
        "command_map": {"ok": v1.ok, "errors": v1.errors},
        "variable_map": {"ok": v2.ok, "errors": v2.errors},
    }


def init_plugin(target_dir: str, os_name: str) -> str:
    base = os.path.join(target_dir, os_name)
    os.makedirs(base, exist_ok=True)

    cmd_path = os.path.join(base, "command_map.yaml")
    var_path = os.path.join(base, "variable_map.yaml")
    parser_path = os.path.join(base, "parser.py")
    help_path = os.path.join(base, "help.yaml")

    if not os.path.exists(cmd_path):
        with open(cmd_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(
                {
                    "session": {"mode": "exec"},
                    "commands": {"normal": {"cpu": ""}, "deep_audit": {}},
                },
                f,
                sort_keys=False,
            )

    if not os.path.exists(var_path):
        with open(var_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(
                {
                    "schema": {
                        "os": os_name,
                        "variables": {
                            "CPU_USAGE": {"type": "gauge", "unit": "percent", "source_command": "cpu"},
                        },
                    }
                },
                f,
                sort_keys=False,
            )

    if not os.path.exists(parser_path):
        with open(parser_path, "w", encoding="utf-8") as f:
            f.write(
                "from __future__ import annotations\n\n"
                "from typing import Any, Dict, List\n\n\n"
                "def parse(outputs: Dict[str, str], errors: Dict[str, str], device: Dict[str, Any]) -> Dict[str, Any]:\n"
                "    _ = device\n"
                "    _ = errors\n"
                "    metrics: List[Dict[str, Any]] = []\n"
                "    # TODO: parse CLI outputs into normalized variables\n"
                "    return {\"metrics\": metrics, \"raw\": {\"outputs\": outputs, \"errors\": errors}}\n"
            )

    if not os.path.exists(help_path):
        with open(help_path, "w", encoding="utf-8") as f:
            yaml.safe_dump({"topics": {}}, f, sort_keys=False)

    return base
