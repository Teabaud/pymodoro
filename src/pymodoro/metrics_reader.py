from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Iterable, Iterator


def _parse_timestamp(timestamp_iso: str) -> datetime:
    # MetricsLogger stores timestamps like "2026-03-03T10:48:51.956717Z"
    # Python's fromisoformat does not understand the "Z" suffix directly.
    if timestamp_iso.endswith("Z"):
        timestamp_iso = timestamp_iso[:-1] + "+00:00"
    dt = datetime.fromisoformat(timestamp_iso)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


@dataclass(slots=True)
class SessionDurationRecord:
    timestamp: datetime
    session_type: str
    duration_sec: int

    @property
    def end(self) -> datetime:
        return self.timestamp

    @property
    def start(self) -> datetime:
        # Guard against negative durations; MetricsLogger already clamps to >= 0
        return self.timestamp - timedelta(seconds=max(0, self.duration_sec))


@dataclass(slots=True)
class CheckInRecord:
    timestamp: datetime
    prompt: str
    answer: str
    focus_rating: int | None
    exercise_name: str | None
    exercise_rep_count: int | None


@dataclass(slots=True)
class WorkSession:
    start: datetime
    end: datetime
    duration_sec: int
    check_in: CheckInRecord | None

    @property
    def day(self) -> date:
        return self.start.date()


@dataclass(slots=True)
class MetricsData:
    work_sessions: list[WorkSession]
    check_ins: list[CheckInRecord]

    def work_sessions_by_day(self) -> dict[date, list[WorkSession]]:
        grouped: dict[date, list[WorkSession]] = {}
        for session in self.work_sessions:
            grouped.setdefault(session.day, []).append(session)
        for sessions in grouped.values():
            sessions.sort(key=lambda s: s.start)
        return grouped

    def all_days(self) -> list[date]:
        days = {session.day for session in self.work_sessions}
        return sorted(days)


def _iter_raw_records(log_path: Path) -> Iterator[dict]:
    if not log_path.exists():
        return iter(())
    with log_path.open("r", encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict):
                continue
            yield record


def _load_session_records(records: Iterable[dict]) -> list[SessionDurationRecord]:
    sessions: list[SessionDurationRecord] = []
    for record in records:
        if record.get("record_type") != "session_duration":
            continue
        timestamp_iso = record.get("timestamp_iso")
        session_type = record.get("session_type")
        duration = record.get("duration_sec")
        if not isinstance(timestamp_iso, str) or not isinstance(session_type, str):
            continue
        if not isinstance(duration, int):
            continue
        sessions.append(
            SessionDurationRecord(
                timestamp=_parse_timestamp(timestamp_iso),
                session_type=session_type,
                duration_sec=max(0, duration),
            )
        )
    return sessions


def _load_check_in_records(records: Iterable[dict]) -> list[CheckInRecord]:
    check_ins: list[CheckInRecord] = []
    for record in records:
        if record.get("record_type") != "check_in":
            continue
        timestamp_iso = record.get("timestamp_iso")
        if not isinstance(timestamp_iso, str):
            continue
        check_ins.append(
            CheckInRecord(
                timestamp=_parse_timestamp(timestamp_iso),
                prompt=str(record.get("prompt") or ""),
                answer=str(record.get("answer") or ""),
                focus_rating=(
                    int(record["focus_rating"])
                    if isinstance(record.get("focus_rating"), int)
                    else None
                ),
                exercise_name=(
                    str(record["exercise_name"])
                    if isinstance(record.get("exercise_name"), str)
                    and record.get("exercise_name") != ""
                    else None
                ),
                exercise_rep_count=(
                    int(record["exercise_rep_count"])
                    if isinstance(record.get("exercise_rep_count"), int)
                    else None
                ),
            )
        )
    check_ins.sort(key=lambda c: c.timestamp)
    return check_ins


def _link_work_sessions_to_check_ins(
    work_sessions: list[SessionDurationRecord],
    check_ins: list[CheckInRecord],
    max_link_gap: timedelta = timedelta(minutes=30),
) -> list[WorkSession]:
    work_sessions = [s for s in work_sessions if s.session_type.lower() == "work"]
    work_sessions.sort(key=lambda s: s.start)

    linked: list[WorkSession] = []
    for session in work_sessions:
        best_ci: CheckInRecord | None = None
        best_delta: float | None = None
        for ci in check_ins:
            delta_sec = (ci.timestamp - session.end).total_seconds()
            if abs(delta_sec) > max_link_gap.total_seconds():
                continue
            if best_delta is None or abs(delta_sec) < best_delta:
                best_ci = ci
                best_delta = abs(delta_sec)
        linked.append(
            WorkSession(
                start=session.start,
                end=session.end,
                duration_sec=session.duration_sec,
                check_in=best_ci,
            )
        )
    return linked


def load_metrics(log_path: Path) -> MetricsData:
    """
    Load metrics from the JSONL log file and return structured data
    for use by the dashboard.
    """
    log_path = Path(log_path)
    raw_records = list(_iter_raw_records(log_path))
    session_records = _load_session_records(raw_records)
    check_in_records = _load_check_in_records(raw_records)
    work_sessions = _link_work_sessions_to_check_ins(session_records, check_in_records)
    return MetricsData(work_sessions=work_sessions, check_ins=check_in_records)
