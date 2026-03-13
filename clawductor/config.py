from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

CONFIG_PATH = Path.home() / ".clawductor" / "config.yaml"

_DEFAULTS: dict[str, Any] = {
    "model_config": {
        "task": "claude-sonnet-4-5",
        "admin": "claude-haiku-4-5-20251001",
        "plan": "claude-sonnet-4-5",
        "init": "claude-sonnet-4-5",
    },
    "notifications": {
        "enabled": True,
        "sound": True,
    },
    "cost": {
        "session_alert_usd": 2.00,
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


@dataclass
class ModelConfig:
    task: str
    admin: str
    plan: str
    init: str


@dataclass
class NotificationsConfig:
    enabled: bool
    sound: bool


@dataclass
class CostConfig:
    session_alert_usd: float


@dataclass
class ClawductorConfig:
    model_config: ModelConfig
    notifications: NotificationsConfig
    cost: CostConfig

    @classmethod
    def from_dict(cls, data: dict) -> "ClawductorConfig":
        mc = data["model_config"]
        notif = data["notifications"]
        cost = data["cost"]
        return cls(
            model_config=ModelConfig(
                task=mc["task"],
                admin=mc["admin"],
                plan=mc["plan"],
                init=mc["init"],
            ),
            notifications=NotificationsConfig(
                enabled=notif["enabled"],
                sound=notif["sound"],
            ),
            cost=CostConfig(
                session_alert_usd=cost["session_alert_usd"],
            ),
        )


def load_config(path: Path = CONFIG_PATH) -> ClawductorConfig:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            yaml.dump(_DEFAULTS, f, default_flow_style=False)
        merged = copy.deepcopy(_DEFAULTS)
    else:
        with open(path) as f:
            user_data = yaml.safe_load(f) or {}
        merged = _deep_merge(_DEFAULTS, user_data)

    return ClawductorConfig.from_dict(merged)
