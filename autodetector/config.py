import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import yaml


def _expand_env(value: Any) -> Any:
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        key = value[2:-1]
        return os.environ.get(key, "")
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    return value


@dataclass(frozen=True)
class SystemConfig:
    timezone: str
    data_dir: str
    db_path: str
    log_level: str


@dataclass(frozen=True)
class DeviceConfig:
    id: str
    name: str
    host: str
    transport: str
    os: str
    credential_ref: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    tags: Optional[List[str]] = None


@dataclass(frozen=True)
class AppConfig:
    raw: Dict[str, Any]
    system: SystemConfig
    devices: List[DeviceConfig]


def load_config(path: str) -> AppConfig:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    data = _expand_env(data)

    sys_cfg = data.get("system", {})
    system = SystemConfig(
        timezone=str(sys_cfg.get("timezone", "UTC")),
        data_dir=str(sys_cfg.get("data_dir", "./data")),
        db_path=str(sys_cfg.get("db_path", "./data/noc.db")),
        log_level=str(sys_cfg.get("log_level", "INFO")),
    )

    devices = []
    for d in data.get("devices", []) or []:
        devices.append(
            DeviceConfig(
                id=str(d.get("id")),
                name=str(d.get("name", d.get("id"))),
                host=str(d.get("host")),
                transport=str(d.get("transport", "ssh")),
                os=str(d.get("os")),
                credential_ref=d.get("credential_ref"),
                username=d.get("username"),
                password=d.get("password"),
                tags=d.get("tags") or [],
            )
        )

    return AppConfig(raw=data, system=system, devices=devices)
