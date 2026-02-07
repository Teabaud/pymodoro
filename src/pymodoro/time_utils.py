from __future__ import annotations

# isort: split
from PySide6 import QtCore


class TimeFormatter:
    @staticmethod
    def end_datetime_str(remaining_ms: int) -> str:
        end_date = QtCore.QDateTime.currentDateTime().addMSecs(remaining_ms)
        if end_date.date() == QtCore.QDate.currentDate():
            return end_date.toString("HH:mm")
        return end_date.toString("yyyy-MM-dd HH:mm")

    @staticmethod
    def countdown_str(remaining_ms: int) -> str:
        remaining_seconds = (remaining_ms + 400) // 1000
        hours, remainder = divmod(remaining_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
