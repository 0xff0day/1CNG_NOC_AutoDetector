from __future__ import annotations

from typing import Any
import logging

import requests


logger = logging.getLogger(__name__)


def send_telegram_message(cfg: Any, text: str) -> None:
    raw_cfg = cfg.raw if hasattr(cfg, "raw") else cfg
    tcfg = ((raw_cfg.get("integrations") or {}).get("telegram") or {})

    bot_token = str(tcfg.get("bot_token", ""))
    chat_id = str(tcfg.get("chat_id", ""))
    if not bot_token or not chat_id:
        logger.debug("Telegram not configured (missing bot_token/chat_id). Message not sent.")
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code >= 400:
            logger.warning("Telegram send failed: HTTP %s: %s", r.status_code, (r.text or "")[:200])
    except Exception as e:  # noqa: BLE001
        logger.warning("Telegram send failed: %s", e)
        return
