from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Tuple

from concurrent.futures import ThreadPoolExecutor, as_completed

import yaml

from autodetector.ai.detectors import analyze_device
from autodetector.alerting.engine import build_dedupe_key, should_emit_alert
from autodetector.alerting.dispatcher import dispatch_alerts
from autodetector.collector.ssh_collector import SshCollector
from autodetector.collector.telnet_collector import TelnetCollector
from autodetector.config import AppConfig, DeviceConfig
from autodetector.correlation.engine import correlate_alerts
from autodetector.plugin.loader import load_plugin
from autodetector.storage.sqlite_store import SqliteStore


@dataclass(frozen=True)
class Credentials:
    username: str
    password: str


def _load_vault(path: str) -> Dict[str, Dict[str, str]]:
    if not path or not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _get_creds(cfg: AppConfig, device: DeviceConfig) -> Credentials:
    if device.username and device.password:
        return Credentials(username=device.username, password=device.password)

    vault_file = (((cfg.raw.get("credentials") or {}).get("vault_file")) or "")
    vault = _load_vault(vault_file)

    ref = device.credential_ref or ""
    entry = vault.get(ref) or {}
    username = entry.get("username")
    password = entry.get("password")
    if not username or not password:
        raise ValueError(f"Missing credentials for device {device.id} (ref={ref})")
    return Credentials(username=str(username), password=str(password))


def _select_commands(plugin: Any, deep: bool) -> Dict[str, str]:
    cmds = plugin.command_map.get("commands") or {}
    group = "deep_audit" if deep else "normal"
    out = cmds.get(group) or {}
    return {str(k): str(v) for k, v in out.items()}


def _collect_device(cfg: AppConfig, device: DeviceConfig, deep: bool) -> Tuple[Dict[str, str], Dict[str, str]]:
    plugin = load_plugin(device.os)
    commands = _select_commands(plugin, deep=deep)
    creds = _get_creds(cfg, device)

    coll_cfg = cfg.raw.get("collector") or {}
    retries = int((coll_cfg.get("retries") or {}).get("attempts", 2))
    retry_sleep_sec = float((coll_cfg.get("retries") or {}).get("sleep_sec", 0.5))

    last_outputs: Dict[str, str] = {}
    last_errors: Dict[str, str] = {}

    session_cfg = (plugin.command_map.get("session") or {}) if isinstance(plugin.command_map, dict) else {}
    session_mode = str(session_cfg.get("mode", "exec"))
    pre_commands = [str(x) for x in (session_cfg.get("pre_commands") or [])]
    prompt_regex = str(session_cfg.get("prompt_regex", r"[>#]\\s*$"))

    for attempt in range(max(1, retries)):
        if device.transport == "telnet":
            tcfg = coll_cfg.get("telnet") or {}
            collector = TelnetCollector(
                connect_timeout_sec=int(tcfg.get("connect_timeout_sec", 10)),
                command_timeout_sec=int(tcfg.get("command_timeout_sec", 20)),
            )
            outputs, errors = collector.run_commands(device.host, creds.username, creds.password, commands)
        else:
            scfg = coll_cfg.get("ssh") or {}
            collector = SshCollector(
                connect_timeout_sec=int(scfg.get("connect_timeout_sec", 10)),
                command_timeout_sec=int(scfg.get("command_timeout_sec", 15)),
            )
            if session_mode == "shell":
                outputs, errors = collector.run_commands_shell(
                    device.host,
                    creds.username,
                    creds.password,
                    commands,
                    pre_commands=pre_commands,
                    prompt_regex=prompt_regex,
                )
            else:
                outputs, errors = collector.run_commands(device.host, creds.username, creds.password, commands)

        last_outputs, last_errors = outputs, errors
        if any((outputs.get(k) or "").strip() for k in commands.keys()):
            return outputs, errors

        if attempt < retries - 1:
            import time

            time.sleep(retry_sleep_sec * (2**attempt))

    return last_outputs, last_errors


def _poll_one_device(cfg: AppConfig, store: SqliteStore, device: DeviceConfig, now: datetime, deep: bool) -> Dict[str, Any]:
    plugin = load_plugin(device.os)
    allowed_vars = set((((plugin.variable_map or {}).get("schema") or {}).get("variables") or {}).keys())

    outputs, errors = _collect_device(cfg, device, deep=deep)
    parsed = plugin.parser_module.parse(outputs=outputs, errors=errors, device={"id": device.id, "name": device.name, "host": device.host})
    if isinstance(parsed, dict):
        parsed.setdefault("os", device.os)

    if allowed_vars:
        parsed["metrics"] = [m for m in (parsed.get("metrics", []) or []) if m.get("variable") in allowed_vars]

    metrics = []
    for m in parsed.get("metrics", []) or []:
        metrics.append(
            {
                "ts": now.isoformat(),
                "device_id": device.id,
                "variable": m.get("variable"),
                "value": m.get("value"),
                "value_text": m.get("value_text"),
                "labels": m.get("labels") or {},
            }
        )
    store.insert_metrics(metrics)

    analysis = analyze_device(cfg, store, device_id=device.id, snapshot=parsed, now=now)
    return {"device": device, "plugin": plugin, "errors": errors, "parsed": parsed, "analysis": analysis}


def run_poll_once(cfg: AppConfig, store: SqliteStore, now: datetime, deep: bool = False) -> Dict[str, Any]:
    results: Dict[str, Any] = {"ts": now.isoformat(), "devices": []}

    cooldown_sec = int((cfg.raw.get("alerting") or {}).get("cooldown_sec", 300))
    dedupe_fields = (cfg.raw.get("alerting") or {}).get("dedupe_key_fields") or ["device_id", "variable", "alert_type"]

    all_alerts: List[Dict[str, Any]] = []

    max_workers = int(((cfg.raw.get("collector") or {}).get("ssh") or {}).get("max_sessions", 50))
    if max_workers < 1:
        max_workers = 1

    futures = []
    with ThreadPoolExecutor(max_workers=min(max_workers, max(1, len(cfg.devices)))) as ex:
        for device in cfg.devices:
            futures.append(ex.submit(_poll_one_device, cfg, store, device, now, deep))

        for f in as_completed(futures):
            r = f.result()
            device = r["device"]
            errors = r["errors"]
            parsed = r["parsed"]
            analysis = r["analysis"]

            emitted_alerts: List[Dict[str, Any]] = []

            offline = (not parsed.get("metrics")) and any(str(e).lower().find("failed") >= 0 for e in (errors or {}).values())
            if offline:
                analysis.setdefault("alerts", []).append(
                    {
                        "severity": "critical",
                        "variable": "DEVICE_STATUS",
                        "alert_type": "offline",
                        "message": "Device unreachable or command collection failed",
                    }
                )

            for a in analysis.get("alerts", []) or []:
                a["ts"] = now.isoformat()
                a["device_id"] = device.id
                a["dedupe_key"] = build_dedupe_key(a, dedupe_fields)

                sev_cd = int(((cfg.raw.get("alerting") or {}).get("cooldown_by_severity") or {}).get(str(a.get("severity", "")), cooldown_sec))
                if should_emit_alert(store, a, cooldown_sec=sev_cd):
                    saved = store.upsert_alert(a)
                    emitted_alerts.append(saved)
                    all_alerts.append(saved)

            dispatch_alerts(
                cfg,
                store,
                device={"id": device.id, "name": device.name, "tags": device.tags or [], "os": device.os},
                alerts=emitted_alerts,
                now=now,
            )

            store.set_device_state(
                device.id,
                last_seen_ts=now.isoformat(),
                health_score=float(analysis.get("health_score", 100.0)),
                snapshot=parsed,
            )

            results["devices"].append(
                {
                    "device_id": device.id,
                    "os": device.os,
                    "transport": device.transport,
                    "errors": errors,
                    "snapshot": parsed,
                    "health_score": analysis.get("health_score"),
                    "alerts": emitted_alerts,
                    "analysis": {k: v for k, v in analysis.items() if k not in {"alerts"}},
                }
            )

    correlations = correlate_alerts(cfg, all_alerts)
    results["correlations"] = correlations

    return results
