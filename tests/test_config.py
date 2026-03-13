from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import yaml

from clawductor.config import ClawductorConfig, load_config


@pytest.fixture
def tmp_config(tmp_path) -> Path:
    return tmp_path / "config.yaml"


def test_default_config_created_if_missing(tmp_config):
    assert not tmp_config.exists()
    cfg = load_config(tmp_config)
    assert tmp_config.exists()
    assert isinstance(cfg, ClawductorConfig)


def test_default_values(tmp_config):
    cfg = load_config(tmp_config)
    assert cfg.notifications.enabled is True
    assert cfg.notifications.sound is True
    assert cfg.cost.session_alert_usd == 2.00


def test_default_model_names_are_non_empty(tmp_config):
    cfg = load_config(tmp_config)
    assert cfg.model_config.task
    assert cfg.model_config.admin
    assert cfg.model_config.plan
    assert cfg.model_config.init


def test_user_values_override_defaults(tmp_config):
    user_data = {
        "notifications": {
            "enabled": False,
        }
    }
    tmp_config.parent.mkdir(parents=True, exist_ok=True)
    with open(tmp_config, "w") as f:
        yaml.dump(user_data, f)

    cfg = load_config(tmp_config)
    assert cfg.notifications.enabled is False
    # sound should still be filled from defaults
    assert cfg.notifications.sound is True


def test_missing_keys_filled_from_defaults(tmp_config):
    user_data = {
        "cost": {
            "session_alert_usd": 5.00,
        }
    }
    tmp_config.parent.mkdir(parents=True, exist_ok=True)
    with open(tmp_config, "w") as f:
        yaml.dump(user_data, f)

    cfg = load_config(tmp_config)
    assert cfg.cost.session_alert_usd == 5.00
    # model_config should be filled from defaults
    assert cfg.model_config.task
    assert cfg.notifications.enabled is True


def test_model_config_can_be_overridden(tmp_config):
    user_data = {
        "model_config": {
            "task": "my-custom-model",
        }
    }
    tmp_config.parent.mkdir(parents=True, exist_ok=True)
    with open(tmp_config, "w") as f:
        yaml.dump(user_data, f)

    cfg = load_config(tmp_config)
    assert cfg.model_config.task == "my-custom-model"
    # other model fields filled from defaults
    assert cfg.model_config.admin
    assert cfg.model_config.plan
    assert cfg.model_config.init
