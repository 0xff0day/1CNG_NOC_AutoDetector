from __future__ import annotations

from typing import Any

from autodetector.integrations.voice_call import trigger_voice_call


def speak_via_voice_call(cfg: Any, summary: str) -> None:
    trigger_voice_call(cfg, summary)
