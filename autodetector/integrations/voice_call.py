from __future__ import annotations

import os
from typing import Any, List

import requests


def _env_or_value(v: Any) -> Any:
    if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
        return os.environ.get(v[2:-1], "")
    return v
    

def _twiml_message(summary: str) -> str:
    safe = summary.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe = safe[:900]
    return f"<Response><Say voice=\"alice\">{safe}</Say></Response>"


def _twilio_call(account_sid: str, auth_token: str, from_number: str, to_number: str, summary: str, timeout_sec: float = 10.0) -> None:
    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Calls.json"
    data = {
        "From": from_number,
        "To": to_number,
        "Twiml": _twiml_message(summary),
    }
    requests.post(url, data=data, auth=(account_sid, auth_token), timeout=timeout_sec)


def trigger_voice_call(cfg: Any, summary: str) -> None:
    raw_cfg = cfg.raw if hasattr(cfg, "raw") else cfg
    vcfg = ((raw_cfg.get("integrations") or {}).get("voice_call") or {})
    if not bool(vcfg.get("enabled", False)):
        return

    provider = str(vcfg.get("provider", "twilio"))
    if provider != "twilio":
        return

    account_sid = str(_env_or_value(vcfg.get("account_sid", "")) or "")
    auth_token = str(_env_or_value(vcfg.get("auth_token", "")) or "")
    from_number = str(_env_or_value(vcfg.get("from_number", "")) or "")
    to_numbers: List[str] = [str(_env_or_value(x)) for x in (vcfg.get("to_numbers") or []) if str(_env_or_value(x)).strip()]
    timeout_sec = float(vcfg.get("timeout_sec", 10.0))

    if not account_sid or not auth_token or not from_number or not to_numbers:
        return

    for to in to_numbers:
        try:
            _twilio_call(account_sid, auth_token, from_number, to, summary=summary, timeout_sec=timeout_sec)
        except Exception:
            pass
