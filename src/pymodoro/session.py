from __future__ import annotations

from enum import Enum

from loguru import logger

from pymodoro.settings import AppSettings

# isort: split
from PySide6 import QtCore

SECONDS = 1000
MINUTES = 60 * SECONDS
HOURS = 60 * MINUTES

LATE_FINISH_RESTART_THRESHOLD_MS = 10 * SECONDS
PHASE_CHANGE_WARNING_MS = 1 * MINUTES
SLEEP_GAP_THRESHOLD_MS = 5 * MINUTES


class SessionPhase(str, Enum):
    WORK = "Work"
    BREAK = "Break"
    PAUSE = "Pause"


class SleepRecoveryTimer(QtCore.QObject):
    finished = QtCore.Signal(int)
    phaseEndingSoon = QtCore.Signal()

    def __init__(
        self,
        heartbeat_interval_ms: int = 10 * SECONDS,
        sleep_gap_threshold_ms: int = SLEEP_GAP_THRESHOLD_MS,
        phase_change_warning_ms: int = PHASE_CHANGE_WARNING_MS,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._sleep_gap_threshold_ms = sleep_gap_threshold_ms
        self._phase_change_warning_ms = phase_change_warning_ms

        self._phase_timer = QtCore.QTimer(self)
        self._phase_timer.setSingleShot(True)
        self._phase_timer.timeout.connect(self._on_phase_timer_timeout)

        self._heartbeat_timer = QtCore.QTimer(self)
        self._heartbeat_timer.setInterval(heartbeat_interval_ms)
        self._heartbeat_timer.timeout.connect(self._on_heartbeat_timeout)

        self._phase_warning_timer = QtCore.QTimer(self)
        self._phase_warning_timer.setSingleShot(True)
        self._phase_warning_timer.timeout.connect(self.phaseEndingSoon.emit)

        self._ends_at: QtCore.QDateTime | None = None
        self._last_heartbeat_at: QtCore.QDateTime | None = None

    def start(self, seconds: int) -> None:
        duration_ms = max(0, seconds * 1000)
        now = QtCore.QDateTime.currentDateTime()
        self._ends_at = now.addMSecs(duration_ms)
        self._last_heartbeat_at = now

        self._phase_timer.stop()
        self._phase_timer.setInterval(duration_ms)
        self._phase_timer.start()
        self._schedule_phase_warning(now)

        if not self._heartbeat_timer.isActive():
            self._heartbeat_timer.start()

    def stop(self) -> None:
        self._phase_timer.stop()
        self._heartbeat_timer.stop()
        self._phase_warning_timer.stop()
        self._ends_at = None
        self._last_heartbeat_at = None

    def extend(self, seconds: int) -> None:
        if self._ends_at is None:
            return

        now = QtCore.QDateTime.currentDateTime()
        self._ends_at = self._ends_at.addSecs(seconds)
        remaining_ms = max(0, now.msecsTo(self._ends_at))
        self._phase_timer.stop()
        self._phase_timer.setInterval(remaining_ms)
        self._phase_timer.start()
        self._schedule_phase_warning(now)

        if not self._heartbeat_timer.isActive():
            self._heartbeat_timer.start()

    def remaining_ms(self) -> int:
        return self._phase_timer.remainingTime()

    def ends_at(self) -> QtCore.QDateTime | None:
        return self._ends_at

    def detect_sleep_gap(self, now: QtCore.QDateTime) -> bool:
        if self._last_heartbeat_at is None:
            return False
        return self._last_heartbeat_at.msecsTo(now) > self._sleep_gap_threshold_ms

    def _on_phase_timer_timeout(self) -> None:
        self._phase_warning_timer.stop()
        self.finished.emit(0)

    def _on_heartbeat_timeout(self) -> None:
        now = QtCore.QDateTime.currentDateTime()
        sleep_gap_detected = self.detect_sleep_gap(now)
        self._last_heartbeat_at = now
        if sleep_gap_detected:
            self._recover_after_sleep(now)

    def _recover_after_sleep(self, now: QtCore.QDateTime) -> None:
        if self._ends_at is None:
            return

        remaining_ms = now.msecsTo(self._ends_at)
        if remaining_ms <= 0:
            missed_by_ms = abs(remaining_ms)
            self._phase_timer.stop()
            self._phase_warning_timer.stop()
            self.finished.emit(missed_by_ms)
            return

        self._phase_timer.stop()
        self._phase_timer.setInterval(remaining_ms)
        self._phase_timer.start()
        self._schedule_phase_warning(now)

    def _schedule_phase_warning(self, now: QtCore.QDateTime) -> None:
        if self._ends_at is None:
            return
        self._phase_warning_timer.stop()
        warning_at = self._ends_at.addMSecs(-self._phase_change_warning_ms)
        warning_delay_ms = now.msecsTo(warning_at)
        if warning_delay_ms <= 0:
            self.phaseEndingSoon.emit()
            return
        self._phase_warning_timer.start(warning_delay_ms)


class SessionPhaseManager(QtCore.QObject):
    phaseChanged = QtCore.Signal(SessionPhase, SessionPhase)
    phaseEndingSoon = QtCore.Signal(SessionPhase)
    workEnded = QtCore.Signal()

    def __init__(
        self,
        settings: AppSettings,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings

        self._phase = SessionPhase.BREAK
        self._timer = SleepRecoveryTimer(parent=self)
        self._timer.finished.connect(self._on_timer_finished)
        self._timer.phaseEndingSoon.connect(self._on_phase_ending_soon)

    @property
    def session_phase(self) -> SessionPhase:
        return self._phase

    def start(self) -> None:
        self.start_work_phase()

    def resume(self) -> None:
        if self._phase == SessionPhase.PAUSE:
            self.start_work_phase()

    def _on_timer_finished(self, missed_by_ms: int) -> None:
        if missed_by_ms > LATE_FINISH_RESTART_THRESHOLD_MS:
            logger.warning(f"Phase late by {missed_by_ms}ms. Restarting.")
            self.start()
            return

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

    def pause_until(self, target_datetime: QtCore.QDateTime) -> None:
        seconds = QtCore.QDateTime.currentDateTime().secsTo(target_datetime)
        self._start_phase(SessionPhase.PAUSE, seconds)

    def extend_current_phase(self, seconds: int | None = None) -> None:
        seconds = seconds or self._settings.timers.snooze_duration
        self._timer.extend(seconds)
        logger.info(str(self))

    def _start_phase(self, phase: SessionPhase, seconds: int) -> None:
        previous_phase = self._phase
        self._phase = phase
        self.phaseChanged.emit(previous_phase, phase)
        self._timer.start(seconds)
        logger.info(str(self))

    def _on_phase_ending_soon(self) -> None:
        self.phaseEndingSoon.emit(self._phase)

    def ends_at(self) -> QtCore.QDateTime | None:
        return self._timer.ends_at()

    def remaining_ms(self) -> int:
        return self._timer.remaining_ms()

    def ends_at_str(self) -> str:
        ends_at = self.ends_at()
        if ends_at is None:
            return "no end datetime"
        phase_ends_today: bool = ends_at.date() == QtCore.QDate.currentDate()
        datetime_str: str = "HH:mm" if phase_ends_today else "yyyy-MM-dd HH:mm"
        return ends_at.toString(datetime_str)

    def time_left_str(self) -> str:
        remaining_ms = self.remaining_ms()
        if remaining_ms < 0:
            return "no end datetime"
        return QtCore.QTime(0, 0).addMSecs(remaining_ms).toString("hh:mm:ss")

    def __str__(self) -> str:
        if self._phase == SessionPhase.PAUSE:
            return f"Paused until {self.ends_at_str()}"
        return f"{self._phase.value} - {self.time_left_str()}"
