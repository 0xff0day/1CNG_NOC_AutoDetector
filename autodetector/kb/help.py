from __future__ import annotations

from typing import Any

from autodetector.plugin.loader import load_plugin


def render_help(cfg: Any, os_name: str, topic: str) -> str:
    _ = cfg
    plugin = load_plugin(os_name)
    kb = plugin.help_kb or {}
    t = (kb.get("topics") or {}).get(topic) or {}

    lines = []
    lines.append(f"OS: {os_name}")
    lines.append(f"Topic: {topic}")
    lines.append("")

    title = t.get("title")
    if title:
        lines.append(str(title))
        lines.append("")

    cmds = t.get("recommended_commands") or []
    if cmds:
        lines.append("Recommended commands:")
        for c in cmds:
            lines.append(f"- {c}")
        lines.append("")

    notes = t.get("notes") or []
    if notes:
        lines.append("Notes:")
        for n in notes:
            lines.append(f"- {n}")

    return "\n".join(lines).rstrip()
