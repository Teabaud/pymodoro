from __future__ import annotations

from enum import Enum

from loguru import logger

from pymodoro.settings import AppSettings
from pymodoro.time_utils import TimeFormatter

# isort: split
from PySide6 import QtCore


class SessionPhase(str, Enum):
    WORK = "work"
    BREAK = "break"
    PAUSE = "pause"


class SessionPhaseManager(QtCore.QObject):
    phaseChanged = QtCore.Signal(SessionPhase, SessionPhase)
    workEnded = QtCore.Signal()

    def __init__(
        self,
        settings: AppSettings,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings

        self._phase = SessionPhase.BREAK
        self._phase_timer = QtCore.QTimer(self)
        self._phase_timer.setSingleShot(True)
        self._phase_timer.timeout.connect(self._on_phase_timer_timeout)

    @property
    def session_phase(self) -> SessionPhase:
        return self._phase

    def start(self) -> None:
        self.start_work_phase()

    def resume(self) -> None:
        if self._phase == SessionPhase.PAUSE:
            self.start_work_phase()

    def pause_until(self, target_datetime: QtCore.QDateTime) -> None:
        pause_seconds = QtCore.QDateTime.currentDateTime().secsTo(target_datetime)
        self._start_pause(pause_seconds)

    def snooze_break(self, seconds: int | None = None) -> None:
        seconds = seconds or self._settings.timers.snooze_duration
        self.start_work_phase(seconds)

    def _on_phase_timer_timeout(self) -> None:
        if self._phase == SessionPhase.WORK:
            self.workEnded.emit()
            self.start_break_phase()
        else:
            self.start_work_phase()

    def start_work_phase(self, seconds: int | None = None) -> None:
        seconds = seconds or self._settings.timers.work_duration
        self._start_phase(SessionPhase.WORK, seconds)

    def start_break_phase(self, seconds: int | None = None) -> None:
        seconds = seconds or self._settings.timers.break_duration
        self._start_phase(SessionPhase.BREAK, seconds)

    def _start_pause(self, seconds: int) -> None:
        self._start_phase(SessionPhase.PAUSE, seconds)

    def _start_phase(self, phase: SessionPhase, seconds: int) -> None:
        previous_phase = self._phase
        self._phase_timer.stop()
        self._phase_timer.setInterval(seconds * 1000)
        self._phase_timer.start()
        self._phase = phase
        self.phaseChanged.emit(previous_phase, phase)
        self._log_phase()

    def remaining_ms(self) -> int:
        return self._phase_timer.remainingTime()

    def _log_phase(self) -> None:
        if self._phase == SessionPhase.PAUSE:
            time_str = TimeFormatter.end_datetime_str(self.remaining_ms())
            logger.info(f"State: {self._phase.value}. Resume at: {time_str}")
        else:
            time_str = TimeFormatter.countdown_str(self.remaining_ms())
            logger.info(f"State: {self._phase.value}. Timer: {time_str}")
