from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Literal

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

# ---------------------------------------------------------------------------
# Domain models (Pydantic, frozen)
# ---------------------------------------------------------------------------


class CheckInRecord(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)
    record_type: Literal["check_in"] = "check_in"
    timestamp: datetime = Field()
    prompt: str = ""
    answer: str = ""
    focus_rating: int | None = None
    exercise_name: str | None = None
    exercise_rep_count: int | None = None


class SessionDurationRecord(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)
    record_type: Literal["session_duration"] = "session_duration"
    timestamp: datetime = Field()
    session_type: str
    duration_sec: int


# ---------------------------------------------------------------------------
# Discriminated union for deserialization
# ---------------------------------------------------------------------------

RawRecord = Annotated[
    SessionDurationRecord | CheckInRecord,
    Field(discriminator="record_type"),
]

_record_adapter: TypeAdapter[SessionDurationRecord | CheckInRecord] = TypeAdapter(
    RawRecord
)


# ---------------------------------------------------------------------------
# Derived type — built by SessionBlockBuilder, not a stored record
# ---------------------------------------------------------------------------


@dataclass
class SessionBlock:
    start: datetime
    end: datetime
    session_type: str
    check_ins: list[CheckInRecord] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Submission type (used by CheckInScreen → MetricsWriter)
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class CheckInSubmission:
    prompt: str
    answer: str
    focus_rating: int | None
    exercise_name: str | None
    exercise_rep_count: int | None


# ---------------------------------------------------------------------------
# Layer 1 — RawRecordReader
# ---------------------------------------------------------------------------


def read_records(log_path: Path) -> list[SessionDurationRecord | CheckInRecord]:
    """Parse NDJSON file into typed records, skipping invalid lines."""
    if not log_path.exists():
        return []
    records: list[SessionDurationRecord | CheckInRecord] = []
    with log_path.open("r", encoding="utf-8") as fp:
        for line_no, raw_line in enumerate(fp, 1):
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                record = _record_adapter.validate_json(raw_line)
            except (ValidationError, ValueError) as exc:
                logger.warning(
                    "metrics_io: skipping invalid record at line {}: {}", line_no, exc
                )
                continue
            records.append(record)
    return records


# ---------------------------------------------------------------------------
# Writer — replaces the old MetricsLogger
# ---------------------------------------------------------------------------


class MetricsLogger:
    def __init__(self, log_path: Path) -> None:
        self._log_path = Path(log_path)
        self._ensure_log_file_exists()

    def log_check_in(self, submission: CheckInSubmission) -> None:
        record = CheckInRecord(
            timestamp=datetime.now(timezone.utc),
            prompt=submission.prompt,
            answer=submission.answer,
            focus_rating=submission.focus_rating,
            exercise_name=submission.exercise_name,
            exercise_rep_count=submission.exercise_rep_count,
        )
        self._append_record(record)

    def log_phase_duration(
        self, session_type: str, duration_sec: int, timestamp: datetime | None = None
    ) -> None:
        record = SessionDurationRecord(
            timestamp=timestamp or datetime.now(timezone.utc),
            session_type=session_type,
            duration_sec=max(0, duration_sec),
        )
        self._append_record(record)

    def _append_record(self, record: SessionDurationRecord | CheckInRecord) -> None:
        self._ensure_log_file_exists()
        with self._log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(
                record.model_dump_json(by_alias=True, exclude_none=True) + "\n"
            )

    def _ensure_log_file_exists(self) -> None:
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log_path.touch(exist_ok=True)
