from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from loguru import logger
from pydantic import BaseModel, PositiveInt

DEFAULT_CONFIG_YAML = """timers:
  work_duration: 1500  # seconds (25 minutes)
  break_duration: 300  # seconds (5 minutes)
  snooze_duration: 60  # seconds (1 minute)

messages:
  work_end_question: "How do you feel rigth now?"
"""

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.yaml"


class TimersConfig(BaseModel):
    work_duration: PositiveInt
    break_duration: PositiveInt
    snooze_duration: PositiveInt


class MessagesConfig(BaseModel):
    work_end_question: str


class AppConfig(BaseModel):
    timers: TimersConfig
    messages: MessagesConfig


def _get_or_create_config_file(config_path: Path) -> dict[str, Any | dict[str, Any]]:
    if not config_path.exists():
        logger.info("Config file not found, creating: {}", config_path)
        config_path.write_text(DEFAULT_CONFIG_YAML, encoding="utf-8")
    return yaml.safe_load(config_path.read_text(encoding="utf-8"))


def load_config(config_path: Path = DEFAULT_CONFIG_PATH) -> AppConfig:
    logger.info("Loading config from: {}", config_path)
    raw_config = _get_or_create_config_file(config_path)
    return AppConfig.model_validate(raw_config)
