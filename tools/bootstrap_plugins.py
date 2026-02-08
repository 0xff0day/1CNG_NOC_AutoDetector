#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os

import yaml

from autodetector.plugin.manager import builtin_plugins_root, init_plugin


def main() -> None:
    ap = argparse.ArgumentParser(description="Bootstrap builtin plugin skeletons from _registry.yaml")
    ap.add_argument("--root", default=builtin_plugins_root())
    args = ap.parse_args()

    reg_path = os.path.join(args.root, "_registry.yaml")
    if not os.path.exists(reg_path):
        raise SystemExit(f"Missing registry: {reg_path}")

    with open(reg_path, "r", encoding="utf-8") as f:
        reg = yaml.safe_load(f) or {}

    created = 0
    for grp in ["network", "server", "hypervisor"]:
        for os_name in reg.get(grp, []) or []:
            os_name = str(os_name)
            p = os.path.join(args.root, os_name)
            if os.path.isdir(p):
                continue
            init_plugin(args.root, os_name)
            created += 1

    print(f"Created {created} plugin skeletons under {args.root}")


if __name__ == "__main__":
    main()
