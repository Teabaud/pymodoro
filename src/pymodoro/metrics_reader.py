from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from loguru import logger


# ---------------------------------------------------------------------------
# Raw record dataclasses
# ---------------------------------------------------------------------------

@dataclass(slots=True, frozen=True)
class CheckInRecord:
    timestamp: datetime
    prompt: str
    answer: str
    focus_rating: int | None
    exercise_name: str | None
    exercise_rep_count: int | None


@dataclass(slots=True, frozen=True)
class SessionDurationRecord:
    timestamp: datetime
    session_type: str
    duration_sec: int


# ---------------------------------------------------------------------------
# Aggregation result dataclasses
# ---------------------------------------------------------------------------

@dataclass(slots=True, frozen=True)
class WeeklyFocusPoint:
    week_start: date
    average_rating: float


@dataclass(slots=True, frozen=True)
class HourFocusPoint:
    hour: int
    average_rating: float
    sample_count: int


@dataclass(slots=True, frozen=True)
class ExerciseSummary:
    exercise_name: str
    total_reps: int


@dataclass(slots=True, frozen=True)
class BreakRoutineStats:
    pct_with_exercise_this_week: float
    pct_with_exercise_all_time: float
    top_exercises: list[ExerciseSummary]


@dataclass(slots=True, frozen=True)
class DailyWorkMinutes:
    day: date
    minutes: float


@dataclass(slots=True, frozen=True)
class WorkTimeStats:
    daily: list[DailyWorkMinutes]
    today_minutes: float
    this_week_minutes: float


# ---------------------------------------------------------------------------
# MetricsReader
# ---------------------------------------------------------------------------

class MetricsReader:
    def __init__(self, log_path: Path) -> None:
        self._log_path = Path(log_path)

    def read_all(self) -> tuple[list[CheckInRecord], list[SessionDurationRecord]]:
        if not self._log_path.exists():
            return [], []

        check_ins: list[CheckInRecord] = []
        sessions: list[SessionDurationRecord] = []

        lines = self._log_path.read_text(encoding="utf-8").splitlines()
        stripped_lines = [line.strip() for line in lines if line.strip()]
        for line_no, line in enumerate(stripped_lines):
            try:
                obj = json.loads(line)
                ts = datetime.fromisoformat(obj["timestamp_iso"]).astimezone()

                record_type = obj.get("record_type")
                if record_type == "check_in":
                    check_ins.append(
                        CheckInRecord(
                            timestamp=ts,
                            prompt=obj.get("prompt") or "",
                            answer=obj.get("answer") or "",
                            focus_rating=obj.get("focus_rating"),
                            exercise_name=obj.get("exercise_name"),
                            exercise_rep_count=obj.get("exercise_rep_count"),
                        )
                    )
                elif record_type == "session_duration":
                    sessions.append(
                        SessionDurationRecord(
                            timestamp=ts,
                            session_type=obj.get("session_type") or "",
                            duration_sec=int(obj.get("duration_sec") or 0),
                        )
                    )
                else:
                    logger.warning("metrics_reader: unknown record_type on line {}", line_no)
            except Exception as exc:
                logger.warning("metrics_reader: skipping malformed line {}: {}", line_no, exc)

        return check_ins, sessions

    # -----------------------------------------------------------------------
    # Aggregation helpers
    # -----------------------------------------------------------------------

    def weekly_focus_trend(self, weeks: int = 8) -> list[WeeklyFocusPoint]:
        check_ins, _ = self.read_all()
        today = date.today()
        # Monday of the current week
        current_week_start = today - timedelta(days=today.weekday())

        buckets: dict[date, list[int]] = {}
        for r in check_ins:
            if r.focus_rating is None:
                continue
            rec_date = r.timestamp.date()
            rec_week_start = rec_date - timedelta(days=rec_date.weekday())
            cutoff = current_week_start - timedelta(weeks=weeks - 1)
            if rec_week_start < cutoff:
                continue
            buckets.setdefault(rec_week_start, []).append(r.focus_rating)

        points = [
            WeeklyFocusPoint(
                week_start=ws,
                average_rating=sum(ratings) / len(ratings),
            )
            for ws, ratings in sorted(buckets.items())
            if ratings
        ]
        return points

    def focus_by_hour(self) -> list[HourFocusPoint]:
        check_ins, _ = self.read_all()
        buckets: dict[int, list[int]] = {}
        for r in check_ins:
            if r.focus_rating is None:
                continue
            hour = r.timestamp.hour
            buckets.setdefault(hour, []).append(r.focus_rating)

        points = [
            HourFocusPoint(
                hour=h,
                average_rating=sum(ratings) / len(ratings),
                sample_count=len(ratings),
            )
            for h, ratings in sorted(buckets.items())
        ]
        return points

    def break_routine_stats(self) -> BreakRoutineStats:
        check_ins, _ = self.read_all()
        today = date.today()
        week_start = today - timedelta(days=today.weekday())

        total_all = 0
        with_ex_all = 0
        total_week = 0
        with_ex_week = 0
        exercise_totals: dict[str, int] = {}

        for r in check_ins:
            total_all += 1
            has_exercise = bool(r.exercise_name and (r.exercise_rep_count or 0) > 0)
            if has_exercise:
                with_ex_all += 1
                name = r.exercise_name.lower().strip()  # type: ignore[union-attr]
                reps = r.exercise_rep_count or 0
                exercise_totals[name] = exercise_totals.get(name, 0) + reps

            if r.timestamp.date() >= week_start:
                total_week += 1
                if has_exercise:
                    with_ex_week += 1

        pct_all = (with_ex_all / total_all * 100) if total_all > 0 else float("nan")
        pct_week = (with_ex_week / total_week * 100) if total_week > 0 else float("nan")

        top_exercises = sorted(
            [ExerciseSummary(name, reps) for name, reps in exercise_totals.items()],
            key=lambda e: e.total_reps,
            reverse=True,
        )[:10]

        return BreakRoutineStats(
            pct_with_exercise_this_week=pct_week,
            pct_with_exercise_all_time=pct_all,
            top_exercises=top_exercises,
        )

    def work_time_stats(self, days: int = 14) -> WorkTimeStats:
        _, sessions = self.read_all()
        today = date.today()

        daily_seconds: dict[date, float] = {
            today - timedelta(days=i): 0.0 for i in range(days - 1, -1, -1)
        }

        for r in sessions:
            if r.session_type.lower() != "work":
                continue
            d = r.timestamp.date()
            if d in daily_seconds:
                daily_seconds[d] += r.duration_sec

        daily = [
            DailyWorkMinutes(day=d, minutes=secs / 60.0)
            for d, secs in sorted(daily_seconds.items())
        ]

        today_minutes = daily_seconds.get(today, 0.0) / 60.0

        week_start = today - timedelta(days=today.weekday())
        this_week_minutes = sum(
            secs / 60.0
            for d, secs in daily_seconds.items()
            if d >= week_start
        )

        return WorkTimeStats(
            daily=daily,
            today_minutes=today_minutes,
            this_week_minutes=this_week_minutes,
        )

    def all_check_ins(self) -> list[CheckInRecord]:
        check_ins, _ = self.read_all()
        return sorted(check_ins, key=lambda r: r.timestamp, reverse=True)
