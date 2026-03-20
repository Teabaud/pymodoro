from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, cast

import pytest

import pymodoro.app as app_module
from pymodoro.app_ui_widgets.pages import Page
from pymodoro.metrics_io import CheckInRecord, MetricsLogger, SessionRecord
from pymodoro.session import PhaseTransition, SessionPhase
from pymodoro.settings import AppSettings, CheckInSettings, TimersSettings


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
        self.phaseEndingSoon = DummySignal()
        self.workEnded = DummySignal()
        self.breakEnded = DummySignal()
        self.start_called = False
        self.pause_until_called: list[Any] = []
        self.resume_called = False
        self.extend_current_phase_called = 0
        self.extend_current_phase_seconds: int | None = None
        self.start_work_phase_called: list[Any] = []
        self.start_break_phase_called: list[Any] = []
        self.session_phase = SessionPhase.WORK

    def start(self) -> None:
        self.start_called = True

    def pause_until(self, target: Any) -> None:
        self.pause_until_called.append(target)

    def resume(self) -> None:
        self.resume_called = True

    def extend_current_phase(self, seconds: int | None = None) -> None:
        self.extend_current_phase_called += 1
        self.extend_current_phase_seconds = seconds

    def start_work_phase(self, seconds: int | None = None) -> None:
        self.start_work_phase_called.append(seconds)

    def start_break_phase(self, seconds: int | None = None) -> None:
        self.start_break_phase_called.append(seconds)

    def remaining_seconds(self) -> int:
        return 45


class DummyTrayController:
    def __init__(self, *_: Any, **__: Any) -> None:
        self.openAppRequested = DummySignal()
        self.openSettingsRequested = DummySignal()
        self.checkInRequested = DummySignal()
        self.startBreakRequested = DummySignal()
        self.pauseUntilRequested = DummySignal()
        self.snoozeRequested = DummySignal()
        self.resumeRequested = DummySignal()
        self.quitRequested = DummySignal()
        self.refresh_called = False
        self.show_called = False
        self.toast_messages: list[dict[str, Any]] = []
        self.hide_phase_end_toast_called = 0

    def refresh(self) -> None:
        self.refresh_called = True

    def show(self) -> None:
        self.show_called = True

    def show_phase_end_toast(self, text: str) -> None:
        self.toast_messages.append({"text": text})

    def hide_phase_end_toast(self) -> None:
        self.hide_phase_end_toast_called += 1


class DummyPrompt:
    def __init__(self, *_: Any, **__: Any) -> None:
        self.submitted = DummySignal()
        self.finished = DummySignal()
        self.visible = False
        self.show_called = 0
        self.closed = False
        self.accepted = False
        self.check_in_prompt: str | None = None

    def isVisible(self) -> bool:
        return self.visible

    def show(self) -> None:
        self.visible = True
        self.show_called += 1

    def close(self) -> None:
        self.visible = False
        self.closed = True

    def accept(self) -> None:
        self.visible = False
        self.accepted = True
        self.finished.emit(1)

    def set_check_in_prompt(self, check_in_prompt: str) -> None:
        self.check_in_prompt = check_in_prompt


class DummyApp:
    def __init__(self) -> None:
        self.exec_called = False
        self.quit_called = False

    def exec(self) -> int:
        self.exec_called = True
        return 0

    def quit(self) -> None:
        self.quit_called = True


class DummySettingsPanel:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self.settingsSaved = DummySignal()
        self.pauseUntilRequested = DummySignal()
        self.resumeRequested = DummySignal()
        self.startWorkRequested = DummySignal()
        self.startBreakRequested = DummySignal()
        self.show_called = False
        self._visible = False
        self.paused_states: list[bool] = []

    def isVisible(self) -> bool:
        return self._visible

    def raise_(self) -> None:
        self._visible = True

    def activateWindow(self) -> None:
        self._visible = True

    def show(self) -> None:
        self.show_called = True
        self._visible = True

    def set_paused(self, paused: bool) -> None:
        self.paused_states.append(paused)


class DummyAppWindow:
    def __init__(self, settings: AppSettings, *_: Any, **__: Any) -> None:
        self.visible = False
        self._settings_panel = DummySettingsPanel(settings)
        self.last_navigated_page: Page | None = None

    def isVisible(self) -> bool:
        return self.visible

    def raise_(self) -> None:
        self.visible = True

    def activateWindow(self) -> None:
        self.visible = True

    def show(self) -> None:
        self.visible = True

    def get_settings_panel(self) -> DummySettingsPanel:
        return self._settings_panel

    def navigate_to_page(self, page: Page, *_: Any, **__: Any) -> None:
        self.last_navigated_page = page


class DummyNotificationSoundPlayer:
    def __init__(self, *_: Any, **__: Any) -> None:
        self.play_calls = 0

    def play(self) -> None:
        self.play_calls += 1


class DummyMetricsLogger:
    def __init__(self, *_: Any, **__: Any) -> None:
        self.check_in_events: list[dict[str, Any]] = []
        self.session_events: list[dict[str, Any]] = []

    def log_record(self, record: CheckInRecord | SessionRecord) -> None:
        if isinstance(record, CheckInRecord):
            self.check_in_events.append(
                {
                    "prompt": record.prompt,
                    "answer": record.answer,
                    "focus_rating": record.focus_rating,
                    "exercise_name": record.exercise_name,
                    "exercise_rep_count": record.exercise_rep_count,
                }
            )
        elif isinstance(record, SessionRecord):
            self.session_events.append(
                {
                    "session_type": record.session_type,
                    "start_timestamp": record.start_timestamp,
                    "end_timestamp": record.end_timestamp,
                }
            )


@pytest.fixture(autouse=True)
def patch_metrics_logger(monkeypatch: Any) -> None:
    monkeypatch.setattr(app_module, "MetricsLogger", DummyMetricsLogger)


@pytest.fixture
def settings(tmp_path: Any) -> AppSettings:
    return AppSettings(
        check_in=CheckInSettings(prompts=["Break time?"]),
        timers=TimersSettings(work_duration=10, break_duration=5, snooze_duration=3),
        settings_path=tmp_path / "settings.yaml",
        metrics_log_path=tmp_path / "metrics.jsonl",
    )


def test_pomodoro_app_wires_controllers(
    monkeypatch: Any, settings: AppSettings
) -> None:
    monkeypatch.setattr(app_module, "SessionPhaseManager", DummySessionPhaseManager)
    monkeypatch.setattr(app_module, "TrayController", DummyTrayController)
    monkeypatch.setattr(app_module, "CheckInScreen", DummyPrompt)
    monkeypatch.setattr(app_module, "AppWindow", DummyAppWindow)

    dummy_app = DummyApp()
    app = app_module.PomodoroApp(settings, app=cast(Any, dummy_app))

    phase_manager = cast(DummySessionPhaseManager, app._sp_manager)
    tray_controller = cast(DummyTrayController, app._tray_controller)

    assert phase_manager.start_called is True
    assert tray_controller.show_called is True
    assert app._on_phase_changed in phase_manager.phaseChanged._callbacks
    assert app._on_phase_ending_soon in phase_manager.phaseEndingSoon._callbacks
    assert app._show_check_in_window in phase_manager.workEnded._callbacks
    assert app._on_break_ended in phase_manager.breakEnded._callbacks
    assert app._show_check_in_window in tray_controller.checkInRequested._callbacks
    assert phase_manager.pause_until in tray_controller.pauseUntilRequested._callbacks
    assert app._on_snoozed_clicked in tray_controller.snoozeRequested._callbacks
    assert phase_manager.resume in tray_controller.resumeRequested._callbacks
    app._open_settings_panel()
    app_window = cast(DummyAppWindow, app._app_window)
    settings_panel = cast(DummySettingsPanel, app_window.get_settings_panel())
    assert phase_manager.pause_until in settings_panel.pauseUntilRequested._callbacks
    assert phase_manager.resume in settings_panel.resumeRequested._callbacks
    assert (
        phase_manager.start_work_phase in settings_panel.startWorkRequested._callbacks
    )
    assert (
        phase_manager.start_break_phase in settings_panel.startBreakRequested._callbacks
    )
    assert dummy_app.quit in tray_controller.quitRequested._callbacks
    app.launch()
    assert dummy_app.exec_called is True


def test_show_check_in_window_reuses_prompt(
    monkeypatch: Any, settings: AppSettings
) -> None:
    monkeypatch.setattr(app_module, "SessionPhaseManager", DummySessionPhaseManager)
    monkeypatch.setattr(app_module, "TrayController", DummyTrayController)
    monkeypatch.setattr(app_module, "CheckInScreen", DummyPrompt)

    app = app_module.PomodoroApp(settings, app=cast(Any, DummyApp()))

    app._show_check_in_window()
    prompt = app._check_in_screen
    assert prompt is not None
    dummy_prompt = cast(DummyPrompt, prompt)
    assert dummy_prompt.show_called == 1


def test_check_in_from_tray_opens_check_in_window(
    monkeypatch: Any, settings: AppSettings
) -> None:
    monkeypatch.setattr(app_module, "SessionPhaseManager", DummySessionPhaseManager)
    monkeypatch.setattr(app_module, "TrayController", DummyTrayController)
    monkeypatch.setattr(app_module, "CheckInScreen", DummyPrompt)

    app = app_module.PomodoroApp(settings, app=cast(Any, DummyApp()))
    tray_controller = cast(DummyTrayController, app._tray_controller)

    tray_controller.checkInRequested.emit()

    prompt = app._check_in_screen
    assert prompt is not None
    dummy_prompt = cast(DummyPrompt, prompt)
    assert dummy_prompt.show_called == 1

    app._show_check_in_window()
    assert app._check_in_screen is prompt
    assert dummy_prompt.show_called == 1


def test_start_break_from_settings_starts_break(
    monkeypatch: Any, settings: AppSettings
) -> None:
    monkeypatch.setattr(app_module, "SessionPhaseManager", DummySessionPhaseManager)
    monkeypatch.setattr(app_module, "TrayController", DummyTrayController)
    monkeypatch.setattr(app_module, "CheckInScreen", DummyPrompt)
    monkeypatch.setattr(app_module, "AppWindow", DummyAppWindow)

    app = app_module.PomodoroApp(settings, app=cast(Any, DummyApp()))
    app._open_settings_panel()
    app_window = cast(DummyAppWindow, app._app_window)
    settings_panel = cast(DummySettingsPanel, app_window.get_settings_panel())

    settings_panel.startBreakRequested.emit(12)

    phase_manager = cast(DummySessionPhaseManager, app._sp_manager)
    assert phase_manager.start_break_phase_called == [12]


def test_toast_check_in_opens_check_in_window(
    monkeypatch: Any, settings: AppSettings
) -> None:
    monkeypatch.setattr(app_module, "SessionPhaseManager", DummySessionPhaseManager)
    monkeypatch.setattr(app_module, "TrayController", DummyTrayController)
    monkeypatch.setattr(app_module, "CheckInScreen", DummyPrompt)

    app = app_module.PomodoroApp(settings, app=cast(Any, DummyApp()))
    tray_controller = cast(DummyTrayController, app._tray_controller)

    tray_controller.checkInRequested.emit()

    assert app._check_in_screen is not None
    assert cast(DummyPrompt, app._check_in_screen).show_called == 1


def test_work_phase_ending_warning_allows_tray_snooze(
    monkeypatch: Any, settings: AppSettings
) -> None:
    monkeypatch.setattr(app_module, "SessionPhaseManager", DummySessionPhaseManager)
    monkeypatch.setattr(app_module, "TrayController", DummyTrayController)
    monkeypatch.setattr(app_module, "CheckInScreen", DummyPrompt)
    sound_player = DummyNotificationSoundPlayer()
    monkeypatch.setattr(
        app_module,
        "NotificationSoundPlayer",
        lambda *args, **kwargs: sound_player,
    )

    app = app_module.PomodoroApp(settings, app=cast(Any, DummyApp()))
    phase_manager = cast(DummySessionPhaseManager, app._sp_manager)
    tray_controller = cast(DummyTrayController, app._tray_controller)

    phase_manager.phaseEndingSoon.emit(SessionPhase.WORK)

    assert tray_controller.toast_messages == [
        {
            "text": "Work ending soon",
        }
    ]
    assert sound_player.play_calls == 1
    tray_controller.snoozeRequested.emit()
    assert phase_manager.extend_current_phase_called == 1
    assert phase_manager.extend_current_phase_seconds is None


def test_non_work_phase_warning_does_not_show_message(
    monkeypatch: Any, settings: AppSettings
) -> None:
    monkeypatch.setattr(app_module, "SessionPhaseManager", DummySessionPhaseManager)
    monkeypatch.setattr(app_module, "TrayController", DummyTrayController)
    monkeypatch.setattr(app_module, "CheckInScreen", DummyPrompt)
    sound_player = DummyNotificationSoundPlayer()
    monkeypatch.setattr(
        app_module,
        "NotificationSoundPlayer",
        lambda *args, **kwargs: sound_player,
    )

    app = app_module.PomodoroApp(settings, app=cast(Any, DummyApp()))
    phase_manager = cast(DummySessionPhaseManager, app._sp_manager)
    tray_controller = cast(DummyTrayController, app._tray_controller)

    phase_manager.phaseEndingSoon.emit(SessionPhase.BREAK)

    assert tray_controller.toast_messages == []
    assert sound_player.play_calls == 0


def test_phase_change_hides_warning_toast(
    monkeypatch: Any, settings: AppSettings
) -> None:
    """When a new phase starts, the phase-end toast is hidden."""
    monkeypatch.setattr(app_module, "SessionPhaseManager", DummySessionPhaseManager)
    monkeypatch.setattr(app_module, "TrayController", DummyTrayController)
    monkeypatch.setattr(app_module, "CheckInScreen", DummyPrompt)
    sound_player = DummyNotificationSoundPlayer()
    monkeypatch.setattr(
        app_module,
        "NotificationSoundPlayer",
        lambda *args, **kwargs: sound_player,
    )

    app = app_module.PomodoroApp(settings, app=cast(Any, DummyApp()))
    tray_controller = cast(DummyTrayController, app._tray_controller)

    now = datetime.now(timezone.utc)
    app._sp_manager.phaseChanged.emit(
        PhaseTransition(
            previous_phase=SessionPhase.WORK,
            current_phase=SessionPhase.BREAK,
            start_timestamp=now - timedelta(seconds=120),
            end_timestamp=now,
        )
    )

    assert tray_controller.hide_phase_end_toast_called == 1
    assert sound_player.play_calls == 0


def test_pause_to_work_phase_change_plays_sound(
    monkeypatch: Any, settings: AppSettings
) -> None:
    monkeypatch.setattr(app_module, "SessionPhaseManager", DummySessionPhaseManager)
    monkeypatch.setattr(app_module, "TrayController", DummyTrayController)
    monkeypatch.setattr(app_module, "CheckInScreen", DummyPrompt)
    sound_player = DummyNotificationSoundPlayer()
    monkeypatch.setattr(
        app_module,
        "NotificationSoundPlayer",
        lambda *args, **kwargs: sound_player,
    )

    app = app_module.PomodoroApp(settings, app=cast(Any, DummyApp()))

    now = datetime.now(timezone.utc)
    app._sp_manager.phaseChanged.emit(
        PhaseTransition(
            previous_phase=SessionPhase.BREAK,
            current_phase=SessionPhase.WORK,
            start_timestamp=now - timedelta(seconds=120),
            end_timestamp=now,
        )
    )

    assert sound_player.play_calls == 1


def test_note_submit_closes_prompt(monkeypatch: Any, settings: AppSettings) -> None:
    monkeypatch.setattr(app_module, "SessionPhaseManager", DummySessionPhaseManager)
    monkeypatch.setattr(app_module, "TrayController", DummyTrayController)
    monkeypatch.setattr(app_module, "CheckInScreen", DummyPrompt)

    app = app_module.PomodoroApp(settings, app=cast(Any, DummyApp()))
    prompt = DummyPrompt()
    app_any = cast(Any, app)
    app_any._check_in_screen = prompt

    app._on_check_in_screen_submit(
        CheckInRecord(
            timestamp=datetime.now(timezone.utc),
            prompt="Break time?",
            answer="done",
            focus_rating=None,
            exercise_name=None,
            exercise_rep_count=None,
        )
    )

    assert prompt.accepted is True


def test_check_in_submit_creates_jsonl_log_record(
    monkeypatch: Any, settings: AppSettings
) -> None:
    monkeypatch.setattr(app_module, "SessionPhaseManager", DummySessionPhaseManager)
    monkeypatch.setattr(app_module, "TrayController", DummyTrayController)
    monkeypatch.setattr(app_module, "CheckInScreen", DummyPrompt)

    monkeypatch.setattr(app_module, "MetricsLogger", MetricsLogger)
    app = app_module.PomodoroApp(settings, app=cast(Any, DummyApp()))
    app._on_check_in_screen_submit(
        CheckInRecord(
            timestamp=datetime.now(timezone.utc),
            prompt="Break time?",
            answer="done",
            focus_rating=None,
            exercise_name=None,
            exercise_rep_count=None,
        )
    )

    assert settings.metrics_log_path.exists() is True

    lines = settings.metrics_log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1

    record = json.loads(lines[0])
    assert record["record_type"] == "check_in"
    assert record["prompt"] == "Break time?"
    assert record["answer"] == "done"
    assert "focus_rating" not in record
    assert "exercise_name" not in record
    assert "exercise_rep_count" not in record
    assert record["timestamp"].endswith("Z") or record["timestamp"].endswith("+00:00")


def test_check_in_submit_appends_multiple_jsonl_records(
    monkeypatch: Any, settings: AppSettings
) -> None:
    monkeypatch.setattr(app_module, "SessionPhaseManager", DummySessionPhaseManager)
    monkeypatch.setattr(app_module, "TrayController", DummyTrayController)
    monkeypatch.setattr(app_module, "CheckInScreen", DummyPrompt)

    monkeypatch.setattr(app_module, "MetricsLogger", MetricsLogger)
    app = app_module.PomodoroApp(settings, app=cast(Any, DummyApp()))
    app._on_check_in_screen_submit(
        CheckInRecord(
            timestamp=datetime.now(timezone.utc),
            prompt="Break time?",
            answer="first",
            focus_rating=4,
            exercise_name="squats",
            exercise_rep_count=12,
        )
    )
    app._on_check_in_screen_submit(
        CheckInRecord(
            timestamp=datetime.now(timezone.utc),
            prompt="Break time?",
            answer="second",
            focus_rating=None,
            exercise_name=None,
            exercise_rep_count=None,
        )
    )

    lines = settings.metrics_log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2

    first_record = json.loads(lines[0])
    second_record = json.loads(lines[1])
    assert first_record["record_type"] == "check_in"
    assert first_record["answer"] == "first"
    assert first_record["focus_rating"] == 4
    assert first_record["exercise_name"] == "squats"
    assert first_record["exercise_rep_count"] == 12
    assert second_record["record_type"] == "check_in"
    assert second_record["answer"] == "second"
    assert "focus_rating" not in second_record
    assert "exercise_name" not in second_record
    assert "exercise_rep_count" not in second_record


def test_phase_change_logs_session_record(
    monkeypatch: Any, settings: AppSettings
) -> None:
    monkeypatch.setattr(app_module, "SessionPhaseManager", DummySessionPhaseManager)
    monkeypatch.setattr(app_module, "TrayController", DummyTrayController)
    monkeypatch.setattr(app_module, "CheckInScreen", DummyPrompt)
    monkeypatch.setattr(
        app_module, "NotificationSoundPlayer", DummyNotificationSoundPlayer
    )

    monkeypatch.setattr(app_module, "MetricsLogger", MetricsLogger)
    now = datetime.now(timezone.utc)
    duration = app_module.MIN_SESSION_DURATION_SEC + 1
    start = now - timedelta(seconds=duration)
    app = app_module.PomodoroApp(settings, app=cast(Any, DummyApp()))
    app._on_phase_changed(
        PhaseTransition(
            previous_phase=SessionPhase.BREAK,
            current_phase=SessionPhase.WORK,
            start_timestamp=start,
            end_timestamp=now,
        )
    )

    lines = settings.metrics_log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1

    record = json.loads(lines[0])
    assert record["record_type"] == "session"
    assert record["session_type"] == "Break"
    assert "start_timestamp" in record
    assert "end_timestamp" in record
    assert "duration_sec" not in record
    assert "prompt" not in record
    assert "answer" not in record
    assert "focus_rating" not in record
    assert "exercise_name" not in record
    assert "exercise_rep_count" not in record


def test_check_in_prompt_selection_not_constant(
    monkeypatch: Any, tmp_path: Any
) -> None:
    monkeypatch.setattr(app_module, "SessionPhaseManager", DummySessionPhaseManager)
    monkeypatch.setattr(app_module, "TrayController", DummyTrayController)
    rng = random.Random(0)
    monkeypatch.setattr(app_module.random, "choice", rng.choice)

    prompts = [f"Prompt {index}" for index in range(10)]
    settings = AppSettings(
        check_in=CheckInSettings(prompts=prompts),
        timers=TimersSettings(work_duration=10, break_duration=5, snooze_duration=3),
        settings_path=tmp_path / "settings.yaml",
    )
    app = app_module.PomodoroApp(settings, app=cast(Any, DummyApp()))

    selections = [app._select_check_in_prompt() for _ in range(10)]

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
    monkeypatch.setattr(app_module, "CheckInScreen", DummyPrompt)
    monkeypatch.setattr(app_module, "AppWindow", DummyAppWindow)

    app = app_module.PomodoroApp(settings, app=cast(Any, DummyApp()))
    tray_controller = cast(DummyTrayController, app._tray_controller)
    tray_controller.refresh_called = False

    app._open_settings_panel()
    app_window = cast(DummyAppWindow, app._app_window)
    settings_panel = cast(DummySettingsPanel, app_window.get_settings_panel())
    settings_panel.settingsSaved.emit()

    assert tray_controller.refresh_called is True


def test_phase_change_updates_open_settings_paused_state(
    monkeypatch: Any, settings: AppSettings
) -> None:
    monkeypatch.setattr(app_module, "SessionPhaseManager", DummySessionPhaseManager)
    monkeypatch.setattr(app_module, "TrayController", DummyTrayController)
    monkeypatch.setattr(app_module, "CheckInScreen", DummyPrompt)
    monkeypatch.setattr(app_module, "AppWindow", DummyAppWindow)
    monkeypatch.setattr(
        app_module,
        "NotificationSoundPlayer",
        DummyNotificationSoundPlayer,
    )

    app = app_module.PomodoroApp(settings, app=cast(Any, DummyApp()))
    app._open_settings_panel()
    app_window = cast(DummyAppWindow, app._app_window)
    settings_panel = cast(DummySettingsPanel, app_window.get_settings_panel())

    now = datetime.now(timezone.utc)
    app._sp_manager.phaseChanged.emit(
        PhaseTransition(
            previous_phase=SessionPhase.WORK,
            current_phase=SessionPhase.PAUSE,
            start_timestamp=now - timedelta(seconds=300),
            end_timestamp=now,
        )
    )
    app._sp_manager.phaseChanged.emit(
        PhaseTransition(
            previous_phase=SessionPhase.PAUSE,
            current_phase=SessionPhase.WORK,
            start_timestamp=now,
            end_timestamp=now + timedelta(seconds=60),
        )
    )

    assert settings_panel.paused_states == [False, True, False]


def test_break_ended_starts_work_immediately_when_check_in_not_visible(
    monkeypatch: Any, settings: AppSettings
) -> None:
    monkeypatch.setattr(app_module, "SessionPhaseManager", DummySessionPhaseManager)
    monkeypatch.setattr(app_module, "TrayController", DummyTrayController)
    monkeypatch.setattr(app_module, "CheckInScreen", DummyPrompt)

    app = app_module.PomodoroApp(settings, app=cast(Any, DummyApp()))
    phase_manager = cast(DummySessionPhaseManager, app._sp_manager)

    phase_manager.breakEnded.emit()

    assert phase_manager.start_work_phase_called == [None]
    assert app._awaiting_check_in_close is False


def test_break_ended_freezes_session_when_check_in_still_visible(
    monkeypatch: Any, settings: AppSettings
) -> None:
    monkeypatch.setattr(app_module, "SessionPhaseManager", DummySessionPhaseManager)
    monkeypatch.setattr(app_module, "TrayController", DummyTrayController)
    monkeypatch.setattr(app_module, "CheckInScreen", DummyPrompt)

    app = app_module.PomodoroApp(settings, app=cast(Any, DummyApp()))
    phase_manager = cast(DummySessionPhaseManager, app._sp_manager)
    check_in = DummyPrompt()
    check_in.visible = True
    app_any = cast(Any, app)
    app_any._check_in_screen = check_in

    phase_manager.breakEnded.emit()

    assert app._awaiting_check_in_close is True
    assert phase_manager.start_work_phase_called == []


def test_check_in_closed_starts_work_and_clears_flag_when_awaiting(
    monkeypatch: Any, settings: AppSettings
) -> None:
    monkeypatch.setattr(app_module, "SessionPhaseManager", DummySessionPhaseManager)
    monkeypatch.setattr(app_module, "TrayController", DummyTrayController)
    monkeypatch.setattr(app_module, "CheckInScreen", DummyPrompt)

    app = app_module.PomodoroApp(settings, app=cast(Any, DummyApp()))
    phase_manager = cast(DummySessionPhaseManager, app._sp_manager)
    app_any = cast(Any, app)
    app_any._awaiting_check_in_close = True

    app._on_check_in_finished(1)

    assert phase_manager.start_work_phase_called == [None]
    assert app._awaiting_check_in_close is False


def test_check_in_closed_does_nothing_when_not_awaiting(
    monkeypatch: Any, settings: AppSettings
) -> None:
    monkeypatch.setattr(app_module, "SessionPhaseManager", DummySessionPhaseManager)
    monkeypatch.setattr(app_module, "TrayController", DummyTrayController)
    monkeypatch.setattr(app_module, "CheckInScreen", DummyPrompt)

    app = app_module.PomodoroApp(settings, app=cast(Any, DummyApp()))
    phase_manager = cast(DummySessionPhaseManager, app._sp_manager)

    app._on_check_in_finished(0)

    assert phase_manager.start_work_phase_called == []


def test_open_settings_panel_navigates_app_window_to_settings(
    monkeypatch: Any, settings: AppSettings
) -> None:
    monkeypatch.setattr(app_module, "SessionPhaseManager", DummySessionPhaseManager)
    monkeypatch.setattr(app_module, "TrayController", DummyTrayController)
    monkeypatch.setattr(app_module, "CheckInScreen", DummyPrompt)
    monkeypatch.setattr(app_module, "AppWindow", DummyAppWindow)

    app = app_module.PomodoroApp(settings, app=cast(Any, DummyApp()))

    app._open_settings_panel()
    app_window = cast(DummyAppWindow, app._app_window)

    assert app_window.last_navigated_page == Page.SETTINGS


def test_show_check_in_window_passes_settings_to_screen(
    monkeypatch: Any, settings: AppSettings
) -> None:
    monkeypatch.setattr(app_module, "SessionPhaseManager", DummySessionPhaseManager)
    monkeypatch.setattr(app_module, "TrayController", DummyTrayController)

    captured_kwargs: dict[str, Any] = {}

    class SpyPrompt(DummyPrompt):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            captured_kwargs.update(kwargs)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(app_module, "CheckInScreen", SpyPrompt)

    app = app_module.PomodoroApp(settings, app=cast(Any, DummyApp()))
    app._show_check_in_window()

    assert "settings" in captured_kwargs
    assert captured_kwargs["settings"] is settings
