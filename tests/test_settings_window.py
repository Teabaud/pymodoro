from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from PySide6 import QtGui
from PySide6.QtWidgets import QMessageBox

from pymodoro.settings import AppSettings, MessagesSettings, TimersSettings
from pymodoro.settings_window import SettingsWindow


@pytest.fixture
def settings(tmp_path: Path) -> AppSettings:
    return AppSettings(
        timers=TimersSettings(work_duration=10, break_duration=5, snooze_duration=3),
        messages=MessagesSettings(work_end_prompts=["One", "Two"]),
        settings_path=tmp_path / "settings.yaml",
    )


def test_add_prompt_marks_dialog_dirty(qcoreapp: Any, settings: AppSettings) -> None:
    window = SettingsWindow(settings)

    assert window._dirty is False
    window._prompts_editor.add_prompt("Three")

    assert window._dirty is True
    assert window._prompts_editor.get_prompts() == ["One", "Two", "Three"]


def test_prompts_editor_cannot_delete_last_prompt(
    qcoreapp: Any, settings: AppSettings
) -> None:
    window = SettingsWindow(settings)
    window._prompts_editor.set_prompts(["Only one"])
    first_row = window._prompts_editor._row_widget(window._prompts_editor._list.item(0))
    assert first_row is not None

    window._prompts_editor._remove_prompt_row(first_row)

    assert window._prompts_editor.get_prompts() == ["Only one"]


def test_prompts_editor_move_prompt_reorders_items(
    qcoreapp: Any, settings: AppSettings
) -> None:
    window = SettingsWindow(settings)
    window._prompts_editor.set_prompts(["A", "B", "C"])

    window._prompts_editor.move_prompt(2, 0)

    assert window._prompts_editor.get_prompts() == ["C", "A", "B"]


def test_save_updates_settings_and_emits_signal(
    qcoreapp: Any, monkeypatch: Any, settings: AppSettings
) -> None:
    window = SettingsWindow(settings)
    saved: list[bool] = []
    write_calls: list[AppSettings] = []
    window.settingsSaved.connect(lambda: saved.append(True))
    monkeypatch.setattr(
        "pymodoro.settings_window.save_settings",
        lambda cfg: write_calls.append(cfg),
    )

    window._work_duration.setValue(42)
    window._prompts_editor.set_prompts(["N1", "N2"])
    window._mark_dirty()

    result = window._try_save()

    assert result is True
    assert settings.timers.work_duration == 42
    assert settings.messages.work_end_prompts == ["N1", "N2"]
    assert write_calls == [settings]
    assert saved == [True]
    assert window._dirty is False


def test_close_event_cancel_keeps_window_open(
    qcoreapp: Any, monkeypatch: Any, settings: AppSettings
) -> None:
    window = SettingsWindow(settings)
    window._dirty = True
    monkeypatch.setattr(
        window,
        "_confirm_close_for_dirty_state",
        lambda: QMessageBox.StandardButton.Cancel,
    )
    close_event = QtGui.QCloseEvent()

    window.closeEvent(close_event)

    assert close_event.isAccepted() is False


def test_close_event_save_path_uses_try_save(
    qcoreapp: Any, monkeypatch: Any, settings: AppSettings
) -> None:
    window = SettingsWindow(settings)
    window._dirty = True
    save_attempts: list[bool] = []
    monkeypatch.setattr(
        window,
        "_confirm_close_for_dirty_state",
        lambda: QMessageBox.StandardButton.Save,
    )
    monkeypatch.setattr(window, "_try_save", lambda: save_attempts.append(True) or True)
    close_event = QtGui.QCloseEvent()

    window.closeEvent(close_event)

    assert save_attempts == [True]
    assert close_event.isAccepted() is True
