from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from PySide6 import QtCore, QtGui
from PySide6.QtWidgets import QSizePolicy

from pymodoro.app_ui_widgets.settings_panel import AUTOSAVE_DEBOUNCE_MS, SettingsPanel
from pymodoro.settings import AppSettings, CheckInSettings, TimersSettings


@pytest.fixture
def settings(tmp_path: Path) -> AppSettings:
    return AppSettings(
        timers=TimersSettings(work_duration=10, break_duration=5, snooze_duration=3),
        check_in=CheckInSettings(prompts=["One", "Two"]),
        settings_path=tmp_path / "settings.yaml",
    )


def test_auto_save_debounces_and_persists(
    qcoreapp: Any, monkeypatch: Any, settings: AppSettings
) -> None:
    panel = SettingsPanel(settings)
    saved: list[bool] = []
    write_calls: list[AppSettings] = []
    panel.settingsSaved.connect(lambda: saved.append(True))
    monkeypatch.setattr(
        "pymodoro.app_ui_widgets.settings_panel.save_settings",
        lambda cfg: write_calls.append(cfg),
    )

    panel._timers_group.work_duration.setValue(42)
    panel._prompts_group.prompts_editor.set_prompts(["N1", "N2"])

    # Nothing saved yet (debounce pending)
    assert write_calls == []

    # Fire the debounce timer
    panel._debounce_timer.timeout.emit()

    assert settings.timers.work_duration == 42
    assert settings.check_in.prompts == ["N1", "N2"]
    assert write_calls == [settings]
    assert saved == [True]


def test_auto_save_skips_on_validation_failure(
    qcoreapp: Any, monkeypatch: Any, settings: AppSettings
) -> None:
    panel = SettingsPanel(settings)
    write_calls: list[AppSettings] = []
    monkeypatch.setattr(
        "pymodoro.app_ui_widgets.settings_panel.save_settings",
        lambda cfg: write_calls.append(cfg),
    )

    # Force a validation error by making to_timers_settings raise
    from pydantic import ValidationError

    monkeypatch.setattr(
        panel._timers_group,
        "to_timers_settings",
        lambda: (_ for _ in ()).throw(ValidationError.from_exception_data("test", [])),
    )

    panel._auto_save()

    assert write_calls == []


def test_add_prompt_schedules_auto_save(qcoreapp: Any, settings: AppSettings) -> None:
    panel = SettingsPanel(settings)

    panel._prompts_group.prompts_editor.add_prompt("Three")

    assert panel._debounce_timer.isActive()
    assert panel._prompts_group.prompts_editor.get_prompts() == [
        "One",
        "Two",
        "Three",
    ]


def test_prompts_editor_cannot_delete_last_prompt(
    qcoreapp: Any, settings: AppSettings
) -> None:
    panel = SettingsPanel(settings)
    panel._prompts_group.prompts_editor.set_prompts(["Only one"])
    first_row = panel._prompts_group.prompts_editor._row_widget(
        panel._prompts_group.prompts_editor._list.item(0)
    )
    assert first_row is not None

    panel._prompts_group.prompts_editor._remove_prompt_row(first_row)

    assert panel._prompts_group.prompts_editor.get_prompts() == ["Only one"]


def test_prompts_editor_move_prompt_reorders_items(
    qcoreapp: Any, settings: AppSettings
) -> None:
    panel = SettingsPanel(settings)
    panel._prompts_group.prompts_editor.set_prompts(["A", "B", "C"])

    panel._prompts_group.prompts_editor.move_prompt(2, 0)

    assert panel._prompts_group.prompts_editor.get_prompts() == [
        "C",
        "A",
        "B",
    ]


def test_only_one_empty_prompt_allowed_and_add_disabled(
    qcoreapp: Any, settings: AppSettings
) -> None:
    panel = SettingsPanel(settings)

    assert panel._prompts_group.add_prompt_button.isEnabled() is True

    panel._prompts_group.prompts_editor.add_prompt("")
    prompts_after_first_add = panel._prompts_group.prompts_editor.get_prompts()

    assert prompts_after_first_add.count("") == 1
    assert panel._prompts_group.add_prompt_button.isEnabled() is False

    panel._prompts_group.prompts_editor.add_prompt("")
    prompts_after_second_add = panel._prompts_group.prompts_editor.get_prompts()

    assert prompts_after_second_add == prompts_after_first_add
    assert prompts_after_second_add.count("") == 1


def test_add_reenabled_when_empty_prompt_gets_content(
    qcoreapp: Any, settings: AppSettings
) -> None:
    panel = SettingsPanel(settings)
    panel._prompts_group.prompts_editor.set_prompts(["One", ""])

    assert panel._prompts_group.add_prompt_button.isEnabled() is False

    empty_row = panel._prompts_group.prompts_editor._row_widget(
        panel._prompts_group.prompts_editor._list.item(1)
    )
    assert empty_row is not None
    empty_row._line_edit.setText("Now filled")

    assert panel._prompts_group.add_prompt_button.isEnabled() is True


def test_empty_prompt_auto_removed_on_blur_and_add_reenabled(
    qcoreapp: Any, settings: AppSettings
) -> None:
    panel = SettingsPanel(settings)
    panel._prompts_group.prompts_editor.set_prompts(["One", ""])

    assert panel._prompts_group.add_prompt_button.isEnabled() is False

    empty_row = panel._prompts_group.prompts_editor._row_widget(
        panel._prompts_group.prompts_editor._list.item(1)
    )
    assert empty_row is not None
    empty_row._line_edit.editingFinished.emit()

    assert panel._prompts_group.prompts_editor.get_prompts() == ["One"]
    assert panel._prompts_group.add_prompt_button.isEnabled() is True


def test_empty_prompt_removed_on_focus_out_event(
    qcoreapp: Any, settings: AppSettings
) -> None:
    panel = SettingsPanel(settings)
    panel._prompts_group.prompts_editor.set_prompts(["One", ""])

    empty_row = panel._prompts_group.prompts_editor._row_widget(
        panel._prompts_group.prompts_editor._list.item(1)
    )
    assert empty_row is not None

    focus_out = QtGui.QFocusEvent(QtCore.QEvent.Type.FocusOut)
    qcoreapp.sendEvent(empty_row._line_edit, focus_out)
    qcoreapp.processEvents()

    assert panel._prompts_group.prompts_editor.get_prompts() == ["One"]
    assert panel._prompts_group.add_prompt_button.isEnabled() is True


def test_pressing_enter_does_not_trigger_auto_save(
    qcoreapp: Any, monkeypatch: Any, settings: AppSettings
) -> None:
    panel = SettingsPanel(settings)
    save_attempts: list[bool] = []
    monkeypatch.setattr(panel, "_auto_save", lambda: save_attempts.append(True))

    key_press = QtGui.QKeyEvent(
        QtCore.QEvent.Type.KeyPress,
        QtCore.Qt.Key.Key_Return,
        QtCore.Qt.KeyboardModifier.NoModifier,
    )
    key_release = QtGui.QKeyEvent(
        QtCore.QEvent.Type.KeyRelease,
        QtCore.Qt.Key.Key_Return,
        QtCore.Qt.KeyboardModifier.NoModifier,
    )
    qcoreapp.sendEvent(panel, key_press)
    qcoreapp.sendEvent(panel, key_release)

    assert save_attempts == []


def test_add_button_full_width_and_compact_duration_inputs(
    qcoreapp: Any, settings: AppSettings
) -> None:
    panel = SettingsPanel(settings)

    assert (
        panel._prompts_group.add_prompt_button.sizePolicy().horizontalPolicy()
        == QSizePolicy.Policy.Expanding
    )
    assert panel._timers_group.work_duration.maximumWidth() == 120
    assert panel._timers_group.break_duration.maximumWidth() == 120
    assert panel._timers_group.snooze_duration.maximumWidth() == 120


def test_pause_resume_button_text_follows_paused_state(
    qcoreapp: Any, settings: AppSettings
) -> None:
    panel = SettingsPanel(settings)

    assert panel._session_group.pause_resume_button.text() == "Pause until..."

    panel.set_paused(True)
    assert panel._session_group.pause_resume_button.text() == "Resume"

    panel.set_paused(False)
    assert panel._session_group.pause_resume_button.text() == "Pause until..."


def test_session_group_exposes_start_work_and_start_break_buttons(
    qcoreapp: Any, settings: AppSettings
) -> None:
    panel = SettingsPanel(settings)

    assert panel._session_group.start_work_button.text() == "Start work"
    assert panel._session_group.start_break_button.text() == "Start break"


def test_pause_resume_button_emits_resume_when_paused(
    qcoreapp: Any, settings: AppSettings
) -> None:
    panel = SettingsPanel(settings)
    resumed: list[bool] = []
    panel.resumeRequested.connect(lambda: resumed.append(True))
    panel.set_paused(True)

    panel._on_pause_resume_clicked()

    assert resumed == [True]


def test_pause_resume_button_emits_pause_datetime_when_not_paused(
    qcoreapp: Any, monkeypatch: Any, settings: AppSettings
) -> None:
    panel = SettingsPanel(settings)
    emitted: list[QtCore.QDateTime] = []
    target = QtCore.QDateTime.fromString("2025-01-01 11:00", "yyyy-MM-dd HH:mm")
    monkeypatch.setattr(panel, "_prompt_pause_until", lambda: target)
    panel.pauseUntilRequested.connect(emitted.append)

    panel._on_pause_resume_clicked()

    assert emitted == [target]


def test_start_work_click_emits_seconds_when_duration_selected(
    qcoreapp: Any, monkeypatch: Any, settings: AppSettings
) -> None:
    panel = SettingsPanel(settings)
    emitted: list[int] = []
    panel.startWorkRequested.connect(emitted.append)
    monkeypatch.setattr(panel, "_prompt_duration", lambda *_: 25)

    panel._on_start_work_clicked()

    assert emitted == [25]


def test_start_break_click_emits_seconds_when_duration_selected(
    qcoreapp: Any, monkeypatch: Any, settings: AppSettings
) -> None:
    panel = SettingsPanel(settings)
    emitted: list[int] = []
    panel.startBreakRequested.connect(emitted.append)
    monkeypatch.setattr(panel, "_prompt_duration", lambda *_: 8)

    panel._on_start_break_clicked()

    assert emitted == [8]


def test_start_buttons_do_not_emit_when_duration_dialog_canceled(
    qcoreapp: Any, monkeypatch: Any, settings: AppSettings
) -> None:
    panel = SettingsPanel(settings)
    work_emitted: list[int] = []
    break_emitted: list[int] = []
    panel.startWorkRequested.connect(work_emitted.append)
    panel.startBreakRequested.connect(break_emitted.append)
    monkeypatch.setattr(panel, "_prompt_duration", lambda *_: None)

    panel._on_start_work_clicked()
    panel._on_start_break_clicked()

    assert work_emitted == []
    assert break_emitted == []
