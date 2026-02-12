from __future__ import annotations

import random
from typing import Any, Callable, cast

import pytest

import pymodoro.app as app_module
from pymodoro.settings import AppSettings, MessagesSettings, TimersSettings


class DummySignal:
    def __init__(self) -> None:
        self._callbacks: list[Callable[..., None]] = []

    def connect(self, callback: Callable[..., None]) -> None:
        self._callbacks.append(callback)

    def emit(self, *args: Any, **kwargs: Any) -> None:
        for callback in list[Callable[..., None]](self._callbacks):
            callback(*args, **kwargs)


class DummySessionPhaseManager:
    def __init__(self, *_: Any, **__: Any) -> None:
        self.phaseChanged = DummySignal()
        self.workEnded = DummySignal()
        self.start_called = False
        self.pause_until_called: list[Any] = []
        self.resume_called = False
        self.snooze_break_called = False

    def start(self) -> None:
        self.start_called = True

    def pause_until(self, target: Any) -> None:
        self.pause_until_called.append(target)

    def resume(self) -> None:
        self.resume_called = True

    def snooze_break(self) -> None:
        self.snooze_break_called = True


class DummyTrayController:
    def __init__(self, *_: Any, **__: Any) -> None:
        self.openAppRequested = DummySignal()
        self.pauseUntilRequested = DummySignal()
        self.resumeRequested = DummySignal()
        self.quitRequested = DummySignal()
        self.refresh_called = False
        self.show_called = False

    def refresh(self) -> None:
        self.refresh_called = True

    def show(self) -> None:
        self.show_called = True


class DummyPrompt:
    def __init__(self, *_: Any, **__: Any) -> None:
        self.submitted = DummySignal()
        self.snoozed = DummySignal()
        self.visible = False
        self.show_called = 0
        self.closed = False
        self.prompt_message: str | None = None

    def isVisible(self) -> bool:
        return self.visible

    def show(self) -> None:
        self.visible = True
        self.show_called += 1

    def close(self) -> None:
        self.visible = False
        self.closed = True

    def set_prompt_message(self, prompt_message: str) -> None:
        self.prompt_message = prompt_message


class DummyApp:
    def __init__(self) -> None:
        self.exec_called = False
        self.quit_called = False

    def exec(self) -> int:
        self.exec_called = True
        return 0

    def quit(self) -> None:
        self.quit_called = True


class DummySettingsWindow:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self.settingsSaved = DummySignal()
        self.show_called = False
        self._visible = False

    def isVisible(self) -> bool:
        return self._visible

    def raise_(self) -> None:
        self._visible = True

    def activateWindow(self) -> None:
        self._visible = True

    def show(self) -> None:
        self.show_called = True
        self._visible = True


@pytest.fixture
def settings(tmp_path: Any) -> AppSettings:
    return AppSettings(
        messages=MessagesSettings(work_end_prompts=["Break time?"]),
        timers=TimersSettings(work_duration=10, break_duration=5, snooze_duration=3),
        settings_path=tmp_path / "settings.yaml",
    )


def test_pomodoro_app_wires_controllers(monkeypatch: Any, settings: AppSettings) -> None:
    monkeypatch.setattr(app_module, "SessionPhaseManager", DummySessionPhaseManager)
    monkeypatch.setattr(app_module, "TrayController", DummyTrayController)
    monkeypatch.setattr(app_module, "BreakScreen", DummyPrompt)

    dummy_app = DummyApp()
    app = app_module.PomodoroApp(settings, app=cast(Any, dummy_app))

    phase_manager = cast(DummySessionPhaseManager, app._sp_manager)
    tray_controller = cast(DummyTrayController, app._tray_controller)

    assert phase_manager.start_called is True
    assert tray_controller.show_called is True
    assert tray_controller.refresh in phase_manager.phaseChanged._callbacks
    assert app._show_break_window in phase_manager.workEnded._callbacks
    assert phase_manager.pause_until in tray_controller.pauseUntilRequested._callbacks
    assert phase_manager.resume in tray_controller.resumeRequested._callbacks
    assert dummy_app.quit in tray_controller.quitRequested._callbacks
    app.launch()
    assert dummy_app.exec_called is True


def test_show_break_window_reuses_prompt(monkeypatch: Any, settings: AppSettings) -> None:
    monkeypatch.setattr(app_module, "SessionPhaseManager", DummySessionPhaseManager)
    monkeypatch.setattr(app_module, "TrayController", DummyTrayController)
    monkeypatch.setattr(app_module, "BreakScreen", DummyPrompt)

    app = app_module.PomodoroApp(settings, app=cast(Any, DummyApp()))

    app._show_break_window()
    prompt = app._break_screen
    assert prompt is not None
    dummy_prompt = cast(DummyPrompt, prompt)
    assert dummy_prompt.show_called == 1

    app._show_break_window()
    assert app._break_screen is prompt
    assert dummy_prompt.show_called == 1


def test_break_snooze_closes_prompt_and_snoozes(
    monkeypatch: Any, settings: AppSettings
) -> None:
    monkeypatch.setattr(app_module, "SessionPhaseManager", DummySessionPhaseManager)
    monkeypatch.setattr(app_module, "TrayController", DummyTrayController)
    monkeypatch.setattr(app_module, "BreakScreen", DummyPrompt)

    app = app_module.PomodoroApp(settings, app=cast(Any, DummyApp()))
    prompt = DummyPrompt()
    app_any = cast(Any, app)
    app_any._break_screen = prompt

    app._on_break_snooze()

    assert prompt.closed is True
    phase_manager = cast(DummySessionPhaseManager, app._sp_manager)
    assert phase_manager.snooze_break_called is True


def test_note_submit_closes_prompt(monkeypatch: Any, settings: AppSettings) -> None:
    monkeypatch.setattr(app_module, "SessionPhaseManager", DummySessionPhaseManager)
    monkeypatch.setattr(app_module, "TrayController", DummyTrayController)
    monkeypatch.setattr(app_module, "BreakScreen", DummyPrompt)

    app = app_module.PomodoroApp(settings, app=cast(Any, DummyApp()))
    prompt = DummyPrompt()
    app_any = cast(Any, app)
    app_any._break_screen = prompt

    app._on_break_screen_submit("done", None)

    assert prompt.closed is True


def test_work_end_prompt_selection_not_constant(monkeypatch: Any, tmp_path: Any) -> None:
    monkeypatch.setattr(app_module, "SessionPhaseManager", DummySessionPhaseManager)
    monkeypatch.setattr(app_module, "TrayController", DummyTrayController)
    rng = random.Random(0)
    monkeypatch.setattr(app_module.random, "choice", rng.choice)

    prompts = [f"Prompt {index}" for index in range(10)]
    settings = AppSettings(
        messages=MessagesSettings(work_end_prompts=prompts),
        timers=TimersSettings(work_duration=10, break_duration=5, snooze_duration=3),
        settings_path=tmp_path / "settings.yaml",
    )
    app = app_module.PomodoroApp(settings, app=cast(Any, DummyApp()))

    selections = [app._select_work_end_prompt() for _ in range(10)]

    assert selections == [
        "Prompt 6",
        "Prompt 6",
        "Prompt 0",
        "Prompt 4",
        "Prompt 8",
        "Prompt 7",
        "Prompt 6",
        "Prompt 4",
        "Prompt 7",
        "Prompt 5",
    ]


def test_settings_saved_refreshes_tray(monkeypatch: Any, settings: AppSettings) -> None:
    monkeypatch.setattr(app_module, "SessionPhaseManager", DummySessionPhaseManager)
    monkeypatch.setattr(app_module, "TrayController", DummyTrayController)
    monkeypatch.setattr(app_module, "BreakScreen", DummyPrompt)
    monkeypatch.setattr(app_module, "SettingsWindow", DummySettingsWindow)

    app = app_module.PomodoroApp(settings, app=cast(Any, DummyApp()))
    tray_controller = cast(DummyTrayController, app._tray_controller)
    tray_controller.refresh_called = False

    app._open_settings_window()
    settings_window = cast(DummySettingsWindow, app._settings_window)
    settings_window.settingsSaved.emit()

    assert settings_window.show_called is True
    assert tray_controller.refresh_called is True
