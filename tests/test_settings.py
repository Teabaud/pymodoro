from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
import yaml
from pydantic import ValidationError

from pymodoro.settings import DEFAULT_SETTINGS_YAML, load_settings, save_settings


def test_load_settings_creates_default_file(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.yaml"

    settings = load_settings(settings_path)

    assert settings_path.exists()
    assert settings_path.read_text(encoding="utf-8") == DEFAULT_SETTINGS_YAML
    assert settings.timers.work_duration == 1500
    assert settings.timers.break_duration == 300
    assert settings.timers.snooze_duration == 60


def test_load_settings_uses_existing_file(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.yaml"
    settings_path.write_text(DEFAULT_SETTINGS_YAML, encoding="utf-8")

    settings = load_settings(settings_path)

    assert settings_path.read_text(encoding="utf-8") == DEFAULT_SETTINGS_YAML
    assert settings.messages.work_end_prompts


def test_load_settings_invalid_yaml_raises(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.yaml"
    settings_path.write_text("timers: [1, 2\n", encoding="utf-8")

    with pytest.raises(yaml.YAMLError):
        load_settings(settings_path)


def test_load_settings_invalid_schema_raises(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.yaml"
    settings_path.write_text("timers: nope\n", encoding="utf-8")

    with pytest.raises(cast(type[BaseException], ValidationError)):
        load_settings(settings_path)


def test_load_settings_sets_settings_path(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.yaml"
    settings_path.write_text(DEFAULT_SETTINGS_YAML, encoding="utf-8")

    settings = load_settings(settings_path)

    assert settings.settings_path == settings_path


def test_save_settings_writes_file(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.yaml"
    settings_path.write_text(DEFAULT_SETTINGS_YAML, encoding="utf-8")
    settings = load_settings(settings_path)

    settings.timers.work_duration = 999
    save_settings(settings)

    loaded = load_settings(settings_path)
    assert loaded.timers.work_duration == 999
