import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(slots=True)
class CheckInSubmission:
    prompt: str
    answer: str
    focus_rating: int | None
    exercise_name: str | None
    exercise_rep_count: int | None


class MetricsLogger:
    def __init__(self, log_path: Path) -> None:
        self._log_path = Path(log_path)
        self._ensure_log_file_exists()

    def log_check_in(self, submission: CheckInSubmission) -> None:
        self._append_record(
            {
                "timestamp_iso": self._timestamp_iso(),
                "record_type": "check_in",
                "prompt": submission.prompt,
                "answer": submission.answer,
                "focus_rating": submission.focus_rating,
                "exercise_name": submission.exercise_name,
                "exercise_rep_count": submission.exercise_rep_count,
                "session_type": None,
                "duration_sec": None,
            }
        )

    def log_phase_duration(self, session_type: str, duration_sec: int) -> None:
        self._append_record(
            {
                "timestamp_iso": self._timestamp_iso(),
                "record_type": "session_duration",
                "prompt": None,
                "answer": None,
                "focus_rating": None,
                "exercise_name": None,
                "exercise_rep_count": None,
                "session_type": session_type,
                "duration_sec": max(0, duration_sec),
            }
        )

    def _append_record(self, record: dict[str, str | int | None]) -> None:
        self._ensure_log_file_exists()
        with self._log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _ensure_log_file_exists(self) -> None:
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log_path.touch(exist_ok=True)

    @staticmethod
    def _timestamp_iso() -> str:
        return datetime.now(timezone.utc).isoformat()
