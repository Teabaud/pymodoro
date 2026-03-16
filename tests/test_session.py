from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, cast

from PySide6 import QtCore
from PySide6.QtCore import QDateTime

from pymodoro.session import (
    LATE_FINISH_RESTART_THRESHOLD_SEC,
    PHASE_CHANGE_WARNING_SEC,
    SLEEP_GAP_THRESHOLD_SEC,
    PhaseTransition,
    SessionPhase,
    SessionPhaseManager,
    SleepRecoveryTimer,
)
from pymodoro.settings import AppSettings, CheckInSettings, TimersSettings


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _make_settings(
    work_duration: int = 10,
    break_duration: int = 5,
    snooze_duration: int = 2,
) -> AppSettings:
    return AppSettings(
        timers=TimersSettings(
            work_duration=work_duration,
            break_duration=break_duration,
            snooze_duration=snooze_duration,
        ),
        check_in=CheckInSettings(prompts=["Prompt"]),
        settings_path=Path("/tmp/settings.yaml"),
    )


def test_start_sets_work_mode_and_timer() -> None:
    settings = _make_settings(work_duration=10, break_duration=5, snooze_duration=2)
    sp_manager = SessionPhaseManager(settings=settings)

    sp_manager.start()

    assert sp_manager.session_phase == SessionPhase.WORK
    assert sp_manager._timer._phase_timer.interval() == 10_000


def test_pause_until_sets_pause_mode_and_interval(monkeypatch: Any) -> None:
    settings = _make_settings(work_duration=10, break_duration=5, snooze_duration=2)
    sp_manager = SessionPhaseManager(settings=settings)

    fixed_now = QDateTime.fromString("2025-01-01 10:00", "yyyy-MM-dd HH:mm")
    monkeypatch.setattr(QDateTime, "currentDateTime", lambda: fixed_now)
    target = fixed_now.addSecs(90)

    sp_manager.pause_until(target)

    assert sp_manager.session_phase == SessionPhase.PAUSE
    assert sp_manager._timer._phase_timer.interval() == 90_000


def test_snooze_break_extends_current_work_phase(monkeypatch: Any) -> None:
    settings = _make_settings(work_duration=120, break_duration=5, snooze_duration=7)
    sp_manager = SessionPhaseManager(settings=settings)
    fixed_now = QDateTime.fromString("2025-01-01 10:00", "yyyy-MM-dd HH:mm")
    monkeypatch.setattr(QDateTime, "currentDateTime", lambda: fixed_now)
    sp_manager.start_work_phase()
    initial_ends_at = sp_manager.ends_at()
    assert initial_ends_at is not None

    sp_manager.extend_current_phase()

    snoozed_ends_at = sp_manager.ends_at()
    assert snoozed_ends_at is not None
    assert sp_manager.session_phase == SessionPhase.WORK
    assert sp_manager._timer._phase_timer.interval() == 127_000


def test_timeout_work_phase_transitions_to_break_and_emits_work_ended() -> None:
    settings = _make_settings(work_duration=10, break_duration=5, snooze_duration=2)
    sp_manager = SessionPhaseManager(settings=settings)
    work_ended: list[bool] = []

    sp_manager.workEnded.connect(lambda: work_ended.append(True))

    sp_manager.start()
    sp_manager._on_timer_finished(_now_utc())

    assert work_ended == [True]
    assert sp_manager.session_phase == SessionPhase.BREAK
    assert sp_manager._timer._phase_timer.interval() == 5_000


def test_timeout_break_phase_emits_break_ended_and_stays_frozen() -> None:
    settings = _make_settings(work_duration=10, break_duration=5, snooze_duration=2)
    sp_manager = SessionPhaseManager(settings=settings)
    break_ended: list[bool] = []

    sp_manager.breakEnded.connect(lambda: break_ended.append(True))

    sp_manager.start_break_phase()
    sp_manager._on_timer_finished(_now_utc())

    assert break_ended == [True]
    assert sp_manager.session_phase == SessionPhase.BREAK


def test_start_work_phase_uses_default_when_seconds_not_provided() -> None:
    settings = _make_settings(work_duration=11, break_duration=5, snooze_duration=2)
    sp_manager = SessionPhaseManager(settings=settings)

    sp_manager.start_work_phase()

    assert sp_manager.session_phase == SessionPhase.WORK
    assert sp_manager._timer._phase_timer.interval() == 11_000


def test_start_break_phase_uses_default_when_seconds_not_provided() -> None:
    settings = _make_settings(work_duration=10, break_duration=7, snooze_duration=2)
    sp_manager = SessionPhaseManager(settings=settings)

    sp_manager.start_break_phase()

    assert sp_manager.session_phase == SessionPhase.BREAK
    assert sp_manager._timer._phase_timer.interval() == 7_000


def test_manual_start_methods_override_duration() -> None:
    settings = _make_settings(work_duration=10, break_duration=5, snooze_duration=2)
    sp_manager = SessionPhaseManager(settings=settings)

    sp_manager.start_work_phase(seconds=3)
    assert sp_manager.session_phase == SessionPhase.WORK
    assert sp_manager._timer._phase_timer.interval() == 3_000

    sp_manager.start_break_phase(seconds=2)
    assert sp_manager.session_phase == SessionPhase.BREAK
    assert sp_manager._timer._phase_timer.interval() == 2_000


def test_manual_start_methods_force_switch_from_pause_and_other_phase(
    monkeypatch: Any,
) -> None:
    settings = _make_settings(work_duration=10, break_duration=5, snooze_duration=2)
    sp_manager = SessionPhaseManager(settings=settings)
    fixed_now = QDateTime.fromString("2025-01-01 10:00", "yyyy-MM-dd HH:mm")
    monkeypatch.setattr(QDateTime, "currentDateTime", lambda: fixed_now)

    target = fixed_now.addSecs(120)
    sp_manager.pause_until(target)
    assert sp_manager.session_phase == SessionPhase.PAUSE

    sp_manager.start_break_phase(seconds=1)
    assert sp_manager.session_phase == SessionPhase.BREAK
    assert sp_manager._timer._phase_timer.interval() == 1_000

    sp_manager.start_work_phase(seconds=2)
    assert sp_manager.session_phase == SessionPhase.WORK
    assert sp_manager._timer._phase_timer.interval() == 2_000


def test_sleep_recovery_timer_emits_effective_end_on_normal_timeout() -> None:
    timer = SleepRecoveryTimer()
    completed: list[datetime] = []
    timer.finished.connect(completed.append)

    timer.start(1)
    timer._on_phase_timer_timeout()

    assert len(completed) == 1
    assert isinstance(completed[0], datetime)
    assert (datetime.now(timezone.utc) - completed[0]).total_seconds() < 2


def test_sleep_recovery_timer_emits_fell_asleep_time_when_sleep_passes_deadline(
    monkeypatch: Any,
) -> None:
    timer = SleepRecoveryTimer()
    fixed_now = QDateTime.fromString("2025-01-01 10:00", "yyyy-MM-dd HH:mm")
    now_box = {"current": fixed_now}
    monkeypatch.setattr(QDateTime, "currentDateTime", lambda: now_box["current"])
    completed: list[datetime] = []
    timer.finished.connect(completed.append)

    timer.start(120)
    now_box["current"] = fixed_now.addSecs(8 * 3600)
    timer._on_heartbeat_timeout()

    assert len(completed) == 1
    # The emitted time should be the fell-asleep time (10:00), not wake-up time (18:00)
    fell_asleep = completed[0]
    expected = cast(datetime, fixed_now.toPython()).astimezone(timezone.utc)
    assert fell_asleep == expected
    assert timer.remaining_seconds() == -1


def test_sleep_recovery_timer_does_not_resync_for_short_heartbeat_gap(
    monkeypatch: Any,
) -> None:
    timer = SleepRecoveryTimer()
    fixed_now = QDateTime.fromString("2025-01-01 10:00", "yyyy-MM-dd HH:mm")
    now_box = {"current": fixed_now}
    monkeypatch.setattr(QDateTime, "currentDateTime", lambda: now_box["current"])
    completed: list[int] = []
    timer.finished.connect(completed.append)

    timer.start(180)
    now_box["current"] = fixed_now.addSecs(SLEEP_GAP_THRESHOLD_SEC - 1)
    timer._on_heartbeat_timeout()

    assert completed == []
    assert timer._phase_timer.interval() == 180_000


def test_sleep_recovery_timer_resyncs_when_sleep_gap_detected(
    monkeypatch: Any,
) -> None:
    timer = SleepRecoveryTimer()
    fixed_now = QDateTime.fromString("2025-01-01 10:00", "yyyy-MM-dd HH:mm")
    now_box = {"current": fixed_now}
    monkeypatch.setattr(QDateTime, "currentDateTime", lambda: now_box["current"])
    completed: list[int] = []
    timer.finished.connect(completed.append)

    timer.start(900)
    now_box["current"] = fixed_now.addSecs(8 * 60)
    timer._on_heartbeat_timeout()

    assert completed == []
    assert timer._phase_timer.interval() == 420_000


def test_manager_reads_are_pure(monkeypatch: Any) -> None:
    settings = _make_settings(work_duration=10, break_duration=5, snooze_duration=2)
    sp_manager = SessionPhaseManager(settings=settings)
    fixed_end = QDateTime.fromString("2025-01-01 11:00", "yyyy-MM-dd HH:mm")
    monkeypatch.setattr(sp_manager._timer, "ends_at", lambda: fixed_end)
    monkeypatch.setattr(sp_manager._timer, "remaining_seconds", lambda: 42)

    assert sp_manager.remaining_seconds() == 42
    assert sp_manager.ends_at() == fixed_end


def test_manager_transitions_on_late_finish_and_emits_work_end() -> None:
    settings = _make_settings(work_duration=10, break_duration=5, snooze_duration=2)
    sp_manager = SessionPhaseManager(settings=settings)
    work_ended: list[bool] = []
    sp_manager.workEnded.connect(lambda: work_ended.append(True))

    sp_manager.start_work_phase(seconds=1)
    sp_manager._on_timer_finished(_now_utc())

    assert work_ended == [True]
    assert sp_manager.session_phase == SessionPhase.BREAK


def test_manager_restarts_fresh_session_when_finish_is_far_too_late() -> None:
    settings = _make_settings(work_duration=10, break_duration=5, snooze_duration=2)
    sp_manager = SessionPhaseManager(settings=settings)
    work_ended: list[bool] = []
    sp_manager.workEnded.connect(lambda: work_ended.append(True))

    sp_manager.start_work_phase(seconds=1)
    long_ago = _now_utc() - timedelta(seconds=LATE_FINISH_RESTART_THRESHOLD_SEC + 1)
    sp_manager._on_timer_finished(long_ago)

    assert work_ended == []
    assert sp_manager.session_phase == SessionPhase.WORK
    assert sp_manager._timer._phase_timer.interval() == 10_000


def test_overnight_sleep_logs_fell_asleep_time_not_wake_time(
    monkeypatch: Any,
) -> None:
    """When the computer sleeps overnight, the logged session should end
    at the fell-asleep time, not the wake-up time."""
    settings = _make_settings(work_duration=1500, break_duration=5, snooze_duration=2)
    sp_manager = SessionPhaseManager(settings=settings)
    fixed_now = QDateTime.fromString("2025-01-15 22:00", "yyyy-MM-dd HH:mm")
    now_box = {"current": fixed_now}
    monkeypatch.setattr(QDateTime, "currentDateTime", lambda: now_box["current"])
    transitions: list[PhaseTransition] = []
    sp_manager.phaseChanged.connect(lambda t: transitions.append(t))

    sp_manager.start_work_phase(seconds=1500)  # 25-minute work session
    # Computer goes to sleep at 22:10, wakes at 06:00
    now_box["current"] = fixed_now.addSecs(8 * 3600)  # 06:00 next day
    sp_manager._timer._on_heartbeat_timeout()

    # The restart should have emitted a phaseChanged transition
    restart_transition = transitions[-1]
    assert restart_transition.previous_phase == SessionPhase.WORK
    assert restart_transition.current_phase == SessionPhase.WORK
    # end_timestamp should be ~22:00 (fell-asleep time), not 06:00 (wake-up time)
    expected_fell_asleep = cast(datetime, fixed_now.toPython()).astimezone(timezone.utc)
    assert restart_transition.end_timestamp == expected_fell_asleep


def test_manager_time_left_str_uses_remaining_seconds(monkeypatch: Any) -> None:
    settings = _make_settings(work_duration=10, break_duration=5, snooze_duration=2)
    sp_manager = SessionPhaseManager(settings=settings)
    sp_manager.start_work_phase(seconds=10)
    monkeypatch.setattr(sp_manager._timer, "remaining_seconds", lambda: 5)

    assert sp_manager.time_left_str() == "00:00:05"


def test_manager_ends_at_str_formats_today(monkeypatch: Any) -> None:
    settings = _make_settings(work_duration=10, break_duration=5, snooze_duration=2)
    sp_manager = SessionPhaseManager(settings=settings)
    now = QtCore.QDateTime.fromString("2025-01-01 10:00", "yyyy-MM-dd HH:mm")
    end_today = now.addSecs(1800)
    monkeypatch.setattr(QtCore.QDate, "currentDate", lambda: now.date())
    monkeypatch.setattr(sp_manager._timer, "ends_at", lambda: end_today)

    assert sp_manager.ends_at_str() == f"10:30"


def test_phase_ending_warning_fires_after_delay_for_long_phase() -> None:
    settings = _make_settings(work_duration=120, break_duration=5, snooze_duration=2)
    sp_manager = SessionPhaseManager(settings=settings)
    warnings: list[SessionPhase] = []
    sp_manager.phaseEndingSoon.connect(warnings.append)

    sp_manager.start_work_phase()
    assert (
        sp_manager._timer._phase_warning_timer.interval()
        == 120_000 - PHASE_CHANGE_WARNING_SEC * 1000
    )
    sp_manager._timer._phase_warning_timer.timeout.emit()

    assert warnings == [SessionPhase.WORK]


def test_phase_ending_warning_fires_immediately_for_short_phase() -> None:
    settings = _make_settings(work_duration=45, break_duration=5, snooze_duration=2)
    sp_manager = SessionPhaseManager(settings=settings)
    warnings: list[SessionPhase] = []
    sp_manager.phaseEndingSoon.connect(warnings.append)

    sp_manager.start_work_phase()

    assert warnings == [SessionPhase.WORK]


def test_phase_changed_emits_previous_phase_duration(monkeypatch: Any) -> None:
    settings = _make_settings(work_duration=10, break_duration=5, snooze_duration=2)
    sp_manager = SessionPhaseManager(settings=settings)
    fixed_now = QDateTime.fromString("2025-01-01 10:00", "yyyy-MM-dd HH:mm")
    now_box = {"current": fixed_now}
    monkeypatch.setattr(QDateTime, "currentDateTime", lambda: now_box["current"])
    transitions: list[PhaseTransition] = []
    sp_manager.phaseChanged.connect(lambda t: transitions.append(t))

    sp_manager.start_work_phase(seconds=100)
    now_box["current"] = fixed_now.addSecs(42)
    sp_manager.start_break_phase(seconds=100)

    t = transitions[-1]
    assert t.previous_phase == SessionPhase.WORK
    assert t.current_phase == SessionPhase.BREAK
    duration = int((t.end_timestamp - t.start_timestamp).total_seconds())
    assert duration == 42


def test_phase_changed_end_timestamp_is_wall_clock(monkeypatch: Any) -> None:
    settings = _make_settings(work_duration=900, break_duration=5, snooze_duration=2)
    sp_manager = SessionPhaseManager(settings=settings)
    fixed_now = QDateTime.fromString("2025-01-01 10:00", "yyyy-MM-dd HH:mm")
    now_box = {"current": fixed_now}
    monkeypatch.setattr(QDateTime, "currentDateTime", lambda: now_box["current"])
    transitions: list[PhaseTransition] = []
    sp_manager.phaseChanged.connect(lambda t: transitions.append(t))

    sp_manager.start_work_phase(seconds=900)
    now_box["current"] = fixed_now.addSecs(45)
    sp_manager._timer._on_heartbeat_timeout()  # 45s sleep gap detected
    now_box["current"] = fixed_now.addSecs(900)
    sp_manager.start_break_phase(seconds=100)

    t = transitions[-1]
    assert t.previous_phase == SessionPhase.WORK
    assert t.current_phase == SessionPhase.BREAK
    duration = int((t.end_timestamp - t.start_timestamp).total_seconds())
    assert duration == 900  # wall-clock time, sleep not subtracted


def test_elapsed_seconds_excludes_sleep_gaps(monkeypatch: Any) -> None:
    timer = SleepRecoveryTimer()
    fixed_now = QDateTime.fromString("2025-01-01 10:00", "yyyy-MM-dd HH:mm")
    now_box = {"current": fixed_now}
    monkeypatch.setattr(QDateTime, "currentDateTime", lambda: now_box["current"])

    timer.start(900)
    now_box["current"] = fixed_now.addSecs(45)
    timer._on_heartbeat_timeout()  # sleep gap of 45s detected
    now_box["current"] = fixed_now.addSecs(200)

    assert timer.elapsed_seconds() == 200 - 45


def test_elapsed_seconds_returns_zero_before_start() -> None:
    timer = SleepRecoveryTimer()

    assert timer.elapsed_seconds() == 0


def test_elapsed_seconds_resets_on_new_start(monkeypatch: Any) -> None:
    timer = SleepRecoveryTimer()
    fixed_now = QDateTime.fromString("2025-01-01 10:00", "yyyy-MM-dd HH:mm")
    now_box = {"current": fixed_now}
    monkeypatch.setattr(QDateTime, "currentDateTime", lambda: now_box["current"])

    timer.start(900)
    now_box["current"] = fixed_now.addSecs(45)
    timer._on_heartbeat_timeout()  # accumulate 45s of sleep

    now_box["current"] = fixed_now.addSecs(100)
    timer.start(900)  # new start resets everything

    now_box["current"] = fixed_now.addSecs(150)
    assert timer.elapsed_seconds() == 50  # 50s since new start, no sleep


def test_phase_ending_warning_emits_for_break_phase_too() -> None:
    settings = _make_settings(work_duration=120, break_duration=120, snooze_duration=2)
    sp_manager = SessionPhaseManager(settings=settings)
    warnings: list[SessionPhase] = []
    sp_manager.phaseEndingSoon.connect(warnings.append)

    sp_manager.start_break_phase()
    sp_manager._timer._phase_warning_timer.timeout.emit()

    assert warnings == [SessionPhase.BREAK]
