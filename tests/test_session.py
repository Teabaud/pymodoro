from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QDateTime

from pymodoro.session import SessionPhase, SessionPhaseManager
from pymodoro.settings import AppSettings, MessagesSettings, TimersSettings


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
        messages=MessagesSettings(work_end_prompts=["Prompt"]),
        settings_path=Path("/tmp/settings.yaml"),
    )


def test_start_sets_work_mode_and_timer() -> None:
    settings = _make_settings(work_duration=10, break_duration=5, snooze_duration=2)
    sp_manager = SessionPhaseManager(settings=settings)

    sp_manager.start()

    assert sp_manager.session_phase == SessionPhase.WORK
    assert sp_manager._phase_timer.interval() == 10_000


def test_pause_until_sets_pause_mode_and_interval(monkeypatch: Any) -> None:
    settings = _make_settings(work_duration=10, break_duration=5, snooze_duration=2)
    sp_manager = SessionPhaseManager(settings=settings)

    fixed_now = QDateTime.fromString("2025-01-01 10:00", "yyyy-MM-dd HH:mm")
    monkeypatch.setattr(QDateTime, "currentDateTime", lambda: fixed_now)
    target = fixed_now.addSecs(90)

    sp_manager.pause_until(target)

    assert sp_manager.session_phase == SessionPhase.PAUSE
    assert sp_manager._phase_timer.interval() == 90_000


def test_snooze_break_uses_default_duration() -> None:
    settings = _make_settings(work_duration=10, break_duration=5, snooze_duration=7)
    sp_manager = SessionPhaseManager(settings=settings)

    sp_manager.snooze_break()

    assert sp_manager.session_phase == SessionPhase.WORK
    assert sp_manager._phase_timer.interval() == 7_000


def test_timeout_transitions_and_emits_work_end() -> None:
    settings = _make_settings(work_duration=10, break_duration=5, snooze_duration=2)
    sp_manager = SessionPhaseManager(settings=settings)
    work_ended: list[bool] = []

    sp_manager.workEnded.connect(lambda: work_ended.append(True))

    sp_manager.start()
    sp_manager._on_phase_timer_timeout()

    assert work_ended == [True]
    assert sp_manager.session_phase == SessionPhase.BREAK
    assert sp_manager._phase_timer.interval() == 5_000

    sp_manager._on_phase_timer_timeout()
    assert sp_manager.session_phase == SessionPhase.WORK
    assert sp_manager._phase_timer.interval() == 10_000
