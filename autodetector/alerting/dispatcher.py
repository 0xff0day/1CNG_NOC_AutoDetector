from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from autodetector.alerting.maintenance import is_suppressed
from autodetector.alerting.routing import contact_group, route_alert
from autodetector.integrations.telegram import send_telegram_message
from autodetector.integrations.voice_call import trigger_voice_call
from autodetector.storage.sqlite_store import SqliteStore


def _cooldown_sec(cfg: Any, severity: str) -> int:
    raw_cfg = cfg.raw if hasattr(cfg, "raw") else cfg
    c = ((raw_cfg.get("alerting") or {}).get("cooldown_by_severity") or {})
    return int(c.get(severity, (raw_cfg.get("alerting") or {}).get("cooldown_sec", 300)))


def _critical_after_n(cfg: Any, alert: Dict[str, Any], saved_alert: Dict[str, Any]) -> Dict[str, Any]:
    raw_cfg = cfg.raw if hasattr(cfg, "raw") else cfg
    pol = ((raw_cfg.get("alerting") or {}).get("critical_after_n") or {})
    n = int(pol.get(str(alert.get("alert_type", "")), pol.get("default", 0)) or 0)
    if n > 0 and int(saved_alert.get("count", 1)) >= n:
        saved_alert["severity"] = "critical"
        saved_alert["message"] = f"(Escalated after {n} repeats) {saved_alert.get('message', '')}"
    return saved_alert


def dispatch_alerts(
    cfg: Any,
    store: SqliteStore,
    device: Dict[str, Any],
    alerts: List[Dict[str, Any]],
    now: datetime,
) -> List[Dict[str, Any]]:
    device_tags = device.get("tags") or []

    delivered: List[Dict[str, Any]] = []

    for a in alerts:
        dec = is_suppressed(cfg, a, device_tags=device_tags, now=now)
        if dec.suppressed:
            store.insert_alert_event(alert_id=a.get("id", ""), action="suppressed", actor="system", note=dec.reason)
            continue

        cd = _cooldown_sec(cfg, str(a.get("severity", "info")))
        a["cooldown_sec"] = cd

        rt = route_alert(cfg, a, device_tags=device_tags)
        grp = contact_group(cfg, rt.contact_group)

        a = _critical_after_n(cfg, a, a)

        msg = f"[{a.get('severity')}] {a.get('device_id')} {a.get('variable')} {a.get('alert_type')}\n{a.get('message')}"

        if "telegram" in rt.channels:
            chat_id = grp.get("telegram_chat_id")
            bot_token = ((cfg.raw.get("integrations") or {}).get("telegram") or {}).get("bot_token")
            if chat_id and bot_token:
                cfg2 = cfg
                cfg2.raw.setdefault("integrations", {}).setdefault("telegram", {})["chat_id"] = chat_id
                send_telegram_message(cfg2, msg)
            else:
                send_telegram_message(cfg, msg)

        if "voice_call" in rt.channels and str(a.get("severity")) == "critical":
            trigger_voice_call(cfg, msg)

        store.insert_alert_event(alert_id=a.get("id", ""), action="dispatched", actor="system", note=f"group={rt.contact_group} channels={','.join(rt.channels)}")
        delivered.append(a)

    return delivered
