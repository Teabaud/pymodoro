from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
import yaml
from pydantic import ValidationError

from pymodoro.config import DEFAULT_CONFIG_YAML, load_config


def test_load_config_creates_default_file(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"

    config = load_config(config_path)

    assert config_path.exists()
    assert config_path.read_text(encoding="utf-8") == DEFAULT_CONFIG_YAML
    assert config.timers.work_duration == 1500
    assert config.timers.break_duration == 300
    assert config.timers.snooze_duration == 60


def test_load_config_uses_existing_file(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(DEFAULT_CONFIG_YAML, encoding="utf-8")

    config = load_config(config_path)

    assert config_path.read_text(encoding="utf-8") == DEFAULT_CONFIG_YAML
    assert config.messages.work_end_prompts


def test_load_config_invalid_yaml_raises(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("timers: [1, 2\n", encoding="utf-8")

    with pytest.raises(yaml.YAMLError):
        load_config(config_path)


def test_load_config_invalid_schema_raises(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("timers: nope\n", encoding="utf-8")

    with pytest.raises(cast(type[BaseException], ValidationError)):
        load_config(config_path)
