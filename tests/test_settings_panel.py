from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from PySide6 import QtCore, QtGui

from pymodoro.app_ui_widgets.settings_panel import AUTOSAVE_DEBOUNCE_MS, SettingsPanel
from pymodoro.app_ui_widgets.settings_panel_widgets import ListEditor, ListEditorRow
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

    panel._timers_group.work_duration.setValue(42 * 60)
    panel._prompts_group.list_editor.set_items(["N1", "N2"])

    # Nothing saved yet (debounce pending)
    assert write_calls == []

    # Fire the debounce timer
    panel._debounce_timer.timeout.emit()

    assert settings.timers.work_duration == 42 * 60
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


# -- ListEditor tests --


def test_list_editor_set_and_get_items(qcoreapp: Any) -> None:
    editor = ListEditor()
    editor.set_items(["A", "B", "C"])

    assert editor.get_items() == ["A", "B", "C"]


def test_list_editor_ignores_blank_items_on_set(qcoreapp: Any) -> None:
    editor = ListEditor()
    editor.set_items(["A", "", "  ", "B"])

    assert editor.get_items() == ["A", "B"]


def test_list_editor_add_via_return_pressed(qcoreapp: Any) -> None:
    editor = ListEditor()
    editor.set_items(["One"])
    changed: list[bool] = []
    editor.changed.connect(lambda: changed.append(True))

    editor._input.setText("Two")
    editor._input.returnPressed.emit()

    assert editor.get_items() == ["One", "Two"]
    assert editor._input.text() == ""
    assert changed == [True]


def test_list_editor_ignores_empty_return(qcoreapp: Any) -> None:
    editor = ListEditor()
    editor.set_items(["One"])
    changed: list[bool] = []
    editor.changed.connect(lambda: changed.append(True))

    editor._input.setText("")
    editor._input.returnPressed.emit()

    assert editor.get_items() == ["One"]
    assert changed == []


def test_list_editor_delete_row(qcoreapp: Any) -> None:
    editor = ListEditor()
    editor.set_items(["A", "B", "C"])
    changed: list[bool] = []
    editor.changed.connect(lambda: changed.append(True))

    # Delete the second row
    row = editor._items_layout.itemAt(1)
    assert row is not None
    row_widget = row.widget()
    assert isinstance(row_widget, ListEditorRow)
    editor._remove_row(row_widget)

    assert editor.get_items() == ["A", "C"]
    assert changed == [True]


def test_list_editor_set_items_clears_previous(qcoreapp: Any) -> None:
    editor = ListEditor()
    editor.set_items(["A", "B"])
    editor.set_items(["X"])

    assert editor.get_items() == ["X"]


def test_add_via_enter_schedules_auto_save(
    qcoreapp: Any, settings: AppSettings
) -> None:
    panel = SettingsPanel(settings)

    panel._prompts_group.list_editor._input.setText("Three")
    panel._prompts_group.list_editor._input.returnPressed.emit()

    assert panel._debounce_timer.isActive()
    assert panel._prompts_group.list_editor.get_items() == ["One", "Two", "Three"]


# -- Tests for other settings panel functionality (unchanged) --


def test_compact_duration_inputs(qcoreapp: Any, settings: AppSettings) -> None:
    panel = SettingsPanel(settings)

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
