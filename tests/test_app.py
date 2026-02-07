from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Callable, cast

import pymodoro.app as app_module


class DummySignal:
    def __init__(self) -> None:
        self._callbacks: list[Callable[..., None]] = []

    def connect(self, callback: Callable[..., None]) -> None:
        self._callbacks.append(callback)

    def emit(self, *args: Any, **kwargs: Any) -> None:
        for callback in list(self._callbacks):
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

    def isVisible(self) -> bool:
        return self.visible

    def show(self) -> None:
        self.visible = True
        self.show_called += 1

    def close(self) -> None:
        self.visible = False
        self.closed = True


class DummyApp:
    def __init__(self) -> None:
        self.exec_called = False

    def exec(self) -> int:
        self.exec_called = True
        return 0


def test_pomodoro_app_wires_controllers(monkeypatch: Any) -> None:
    config = SimpleNamespace(
        messages=SimpleNamespace(work_end_question="Break time?"),
        timers=SimpleNamespace(work_duration=10, break_duration=5, snooze_duration=3),
    )
    dummy_quit_called: list[bool] = []

    def dummy_quit() -> None:
        dummy_quit_called.append(True)

    monkeypatch.setattr(app_module, "_get_qt_app", lambda: DummyApp())
    monkeypatch.setattr(app_module, "SessionPhaseManager", DummySessionPhaseManager)
    monkeypatch.setattr(app_module, "TrayController", DummyTrayController)
    monkeypatch.setattr(app_module, "FullScreenPrompt", DummyPrompt)
    monkeypatch.setattr(app_module, "load_config", lambda: config)
    monkeypatch.setattr(app_module.QtWidgets.QApplication, "quit", dummy_quit)

    app = app_module.PomodoroApp()

    phase_manager = cast(DummySessionPhaseManager, app._sp_manager)
    tray_controller = cast(DummyTrayController, app._tray_controller)

    assert phase_manager.start_called is True
    assert tray_controller.show_called is True
    assert tray_controller.refresh in phase_manager.phaseChanged._callbacks
    assert app._show_break_window in phase_manager.workEnded._callbacks
    assert phase_manager.pause_until in tray_controller.pauseUntilRequested._callbacks
    assert phase_manager.resume in tray_controller.resumeRequested._callbacks
    assert dummy_quit in tray_controller.quitRequested._callbacks
    app.launch()
    dummy_app = cast(DummyApp, app._app)
    assert dummy_app.exec_called is True


def test_show_break_window_reuses_prompt(monkeypatch: Any) -> None:
    monkeypatch.setattr(app_module, "_get_qt_app", lambda: DummyApp())
    monkeypatch.setattr(app_module, "SessionPhaseManager", DummySessionPhaseManager)
    monkeypatch.setattr(app_module, "TrayController", DummyTrayController)
    monkeypatch.setattr(app_module, "FullScreenPrompt", DummyPrompt)
    monkeypatch.setattr(
        app_module,
        "load_config",
        lambda: SimpleNamespace(
            messages=SimpleNamespace(work_end_question="Break time?"),
            timers=SimpleNamespace(
                work_duration=10, break_duration=5, snooze_duration=3
            ),
        ),
    )

    app = app_module.PomodoroApp()

    app._show_break_window()
    prompt = app._fullscreen_window
    assert prompt is not None
    dummy_prompt = cast(DummyPrompt, prompt)
    assert dummy_prompt.show_called == 1

    app._show_break_window()
    assert app._fullscreen_window is prompt
    assert dummy_prompt.show_called == 1


def test_break_snooze_closes_prompt_and_snoozes(monkeypatch: Any) -> None:
    monkeypatch.setattr(app_module, "_get_qt_app", lambda: DummyApp())
    monkeypatch.setattr(app_module, "SessionPhaseManager", DummySessionPhaseManager)
    monkeypatch.setattr(app_module, "TrayController", DummyTrayController)
    monkeypatch.setattr(app_module, "FullScreenPrompt", DummyPrompt)
    monkeypatch.setattr(
        app_module,
        "load_config",
        lambda: SimpleNamespace(
            messages=SimpleNamespace(work_end_question="Break time?"),
            timers=SimpleNamespace(
                work_duration=10, break_duration=5, snooze_duration=3
            ),
        ),
    )

    app = app_module.PomodoroApp()
    prompt = DummyPrompt()
    app_any = cast(Any, app)
    app_any._fullscreen_window = prompt

    app._on_break_snooze()

    assert prompt.closed is True
    phase_manager = cast(DummySessionPhaseManager, app._sp_manager)
    assert phase_manager.snooze_break_called is True


def test_note_submit_closes_prompt(monkeypatch: Any) -> None:
    monkeypatch.setattr(app_module, "_get_qt_app", lambda: DummyApp())
    monkeypatch.setattr(app_module, "SessionPhaseManager", DummySessionPhaseManager)
    monkeypatch.setattr(app_module, "TrayController", DummyTrayController)
    monkeypatch.setattr(app_module, "FullScreenPrompt", DummyPrompt)
    monkeypatch.setattr(
        app_module,
        "load_config",
        lambda: SimpleNamespace(
            messages=SimpleNamespace(work_end_question="Break time?"),
            timers=SimpleNamespace(
                work_duration=10, break_duration=5, snooze_duration=3
            ),
        ),
    )

    app = app_module.PomodoroApp()
    prompt = DummyPrompt()
    app_any = cast(Any, app)
    app_any._fullscreen_window = prompt

    app._on_note_submit("done")

    assert prompt.closed is True
