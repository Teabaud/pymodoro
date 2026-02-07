from __future__ import annotations

from typing import Any

from PySide6 import QtCore

import pymodoro.session as mode_module
from pymodoro.session import SessionPhase, SessionPhaseManager


def test_start_sets_work_mode_and_timer(qcoreapp: QtCore.QCoreApplication) -> None:
    sp_manager = SessionPhaseManager(
        work_duration=10, break_duration=5, snooze_duration=2
    )

    sp_manager.start()

    assert sp_manager.session_phase == SessionPhase.WORK
    assert sp_manager._phase_timer.interval() == 10_000


def test_pause_until_sets_pause_mode_and_interval(
    qcoreapp: QtCore.QCoreApplication, monkeypatch: Any
) -> None:
    sp_manager = SessionPhaseManager(
        work_duration=10, break_duration=5, snooze_duration=2
    )

    fixed_now = QtCore.QDateTime.fromString("2025-01-01 10:00", "yyyy-MM-dd HH:mm")
    monkeypatch.setattr(
        mode_module.QtCore.QDateTime, "currentDateTime", lambda: fixed_now
    )
    target = fixed_now.addSecs(90)

    sp_manager.pause_until(target)

    assert sp_manager.session_phase == SessionPhase.PAUSE
    assert sp_manager._phase_timer.interval() == 90_000


def test_snooze_break_uses_default_duration(
    qcoreapp: QtCore.QCoreApplication,
) -> None:
    sp_manager = SessionPhaseManager(
        work_duration=10, break_duration=5, snooze_duration=7
    )

    sp_manager.snooze_break()

    assert sp_manager.session_phase == SessionPhase.WORK
    assert sp_manager._phase_timer.interval() == 7_000


def test_timeout_transitions_and_emits_work_end(
    qcoreapp: QtCore.QCoreApplication,
) -> None:
    sp_manager = SessionPhaseManager(
        work_duration=10, break_duration=5, snooze_duration=2
    )
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
