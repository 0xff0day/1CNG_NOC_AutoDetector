from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import yaml


@dataclass(frozen=True)
class Registry:
    network: List[str]
    server: List[str]
    hypervisor: List[str]

    def group_for_os(self, os_name: str) -> str:
        o = os_name.lower()
        if o in set(x.lower() for x in self.network):
            return "network"
        if o in set(x.lower() for x in self.server):
            return "server"
        if o in set(x.lower() for x in self.hypervisor):
            return "hypervisor"
        return "unknown"


def load_builtin_registry(plugins_root: Optional[str] = None) -> Registry:
    if plugins_root is None:
        plugins_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "plugins", "builtin"))

    reg_path = os.path.join(plugins_root, "_registry.yaml")
    if not os.path.exists(reg_path):
        return Registry(network=[], server=[], hypervisor=[])

    with open(reg_path, "r", encoding="utf-8") as f:
        doc = yaml.safe_load(f) or {}

    return Registry(
        network=[str(x) for x in (doc.get("network") or [])],
        server=[str(x) for x in (doc.get("server") or [])],
        hypervisor=[str(x) for x in (doc.get("hypervisor") or [])],
    )
