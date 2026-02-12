from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from loguru import logger
from pydantic import BaseModel, PositiveInt

DEFAULT_SETTINGS_YAML = """timers:
  work_duration: 1500  # seconds (25 minutes)
  break_duration: 300  # seconds (5 minutes)
  snooze_duration: 60  # seconds (1 minute)

messages:
  work_end_prompts:
    - "How present are you in what you do?"
    - "What do you want to focus on next?"
    - "What is your goal for the day?"
"""

DEFAULT_SETTINGS_PATH = Path(__file__).resolve().parents[2] / "settings.yaml"


class TimersSettings(BaseModel):
    work_duration: PositiveInt
    break_duration: PositiveInt
    snooze_duration: PositiveInt


class MessagesSettings(BaseModel):
    work_end_prompts: list[str]


class AppSettings(BaseModel):
    timers: TimersSettings
    messages: MessagesSettings
    settings_path: Path


def _get_or_create_settings_file(
    settings_path: Path,
) -> dict[str, Any | dict[str, Any]]:
    if not settings_path.exists():
        logger.info("Settings file not found, creating: {}", settings_path)
        settings_path.write_text(DEFAULT_SETTINGS_YAML, encoding="utf-8")
    return yaml.safe_load(settings_path.read_text(encoding="utf-8"))


def load_settings(
    settings_path: Path = DEFAULT_SETTINGS_PATH,
) -> AppSettings:
    logger.info("Loading settings from: {}", settings_path)
    raw_settings = _get_or_create_settings_file(settings_path)
    return AppSettings.model_validate({**raw_settings, "settings_path": settings_path})


def save_settings(settings: AppSettings) -> None:
    logger.info("Saving settings to: {}", settings.settings_path)
    data = settings.model_dump(exclude={"settings_path"}, exclude_none=True)
    settings.settings_path.write_text(
        yaml.dump(data, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )
