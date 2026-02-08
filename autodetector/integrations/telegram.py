from __future__ import annotations

from typing import Any

import requests


def send_telegram_message(cfg: Any, text: str) -> None:
    raw_cfg = cfg.raw if hasattr(cfg, "raw") else cfg
    tcfg = ((raw_cfg.get("integrations") or {}).get("telegram") or {})

    bot_token = str(tcfg.get("bot_token", ""))
    chat_id = str(tcfg.get("chat_id", ""))
    if not bot_token or not chat_id:
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception:  # noqa: BLE001
        return
