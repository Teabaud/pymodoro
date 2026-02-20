from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Callable, cast

from PySide6 import QtCore

import pymodoro.tray as tray_module
from pymodoro.session import SessionPhase
from pymodoro.tray import TrayController


class DummySignal:
    def __init__(self) -> None:
        self._callbacks: list[Callable[..., None]] = []

    def connect(self, callback: Callable[..., None]) -> None:
        self._callbacks.append(callback)

    def emit(self, *args: Any, **kwargs: Any) -> None:
        for callback in list[Callable[..., None]](self._callbacks):
            callback(*args, **kwargs)


class DummyAction:
    def __init__(self, text: str) -> None:
        self.text = text
        self.visible = True
        self.triggered = DummySignal()

    def setText(self, text: str) -> None:
        self.text = text

    def setVisible(self, visible: bool) -> None:
        self.visible = visible


class DummyMenu:
    def __init__(self) -> None:
        self.actions: list[DummyAction] = []
        self.popup_called_with: Any | None = None

    def addAction(self, text: str) -> DummyAction:
        action = DummyAction(text)
        self.actions.append(action)
        return action

    def popup(self, pos: Any) -> None:
        self.popup_called_with = pos


class DummyTray:
    ActivationReason = SimpleNamespace(Trigger="trigger")
    MessageIcon = SimpleNamespace(Information="info", NoIcon="none")

    def __init__(self, app: Any) -> None:
        self.app = app
        self.activated = DummySignal()
        self.tooltip: str | None = None
        self.icon: Any | None = None
        self.menu: DummyMenu | None = None
        self.show_called = False
        self.messages: list[tuple[str, str, Any, int]] = []

    def setContextMenu(self, menu: DummyMenu) -> None:
        self.menu = menu

    def setToolTip(self, text: str) -> None:
        self.tooltip = text

    def setIcon(self, icon: Any) -> None:
        self.icon = icon

    def show(self) -> None:
        self.show_called = True

    def showMessage(self, title: str, message: str, icon: Any, timeout_ms: int) -> None:
        self.messages.append((title, message, icon, timeout_ms))


class DummySessionPhaseManager:
    def __init__(self, phase: SessionPhase, remaining_ms: int) -> None:
        self.session_phase = phase
        self._remaining_ms = remaining_ms

    def remaining_ms(self) -> int:
        return self._remaining_ms

    def ends_at_str(self) -> str:
        return "12:00"

    def time_left_str(self) -> str:
        return QtCore.QTime(0, 0).addMSecs(self._remaining_ms).toString("hh:mm:ss")


class DummySnackbar:
    def __init__(self, *_: Any, **__: Any) -> None:
        self.snoozeRequested = DummySignal()
        self.show_calls: list[str] = []
        self.hide_calls = 0

    def show_toast(self, text: str) -> None:
        self.show_calls.append(text)

    def hide_toast(self) -> None:
        self.hide_calls += 1


def test_refresh_updates_pause_tooltip_and_icon(
    qcoreapp: QtCore.QCoreApplication, monkeypatch: Any
) -> None:
    monkeypatch.setattr(tray_module.QtWidgets, "QSystemTrayIcon", DummyTray)
    monkeypatch.setattr(tray_module.QtWidgets, "QMenu", DummyMenu)
    monkeypatch.setattr(
        tray_module.QtGui,
        "QIcon",
        lambda icon_path: f"icon-file:{icon_path}",
    )

    sp_manager = DummySessionPhaseManager(SessionPhase.PAUSE, remaining_ms=3_600_000)
    tray = TrayController(
        app=cast(Any, SimpleNamespace()),
        session_phase_manager=cast(Any, sp_manager),
    )

    tray.refresh()

    assert tray._action_pause.text == "Resume"
    tray_icon = cast(DummyTray, tray._tray)
    assert tray_icon.tooltip is not None
    assert tray_icon.tooltip.startswith("Pause until ")
    assert tray_icon.icon is not None
    assert "icon-paused.svg" in tray_icon.icon


def test_refresh_updates_work_tooltip_and_icon(
    qcoreapp: QtCore.QCoreApplication, monkeypatch: Any
) -> None:
    monkeypatch.setattr(tray_module.QtWidgets, "QSystemTrayIcon", DummyTray)
    monkeypatch.setattr(tray_module.QtWidgets, "QMenu", DummyMenu)
    monkeypatch.setattr(
        tray_module.QtGui,
        "QIcon",
        lambda icon_path: f"icon-file:{icon_path}",
    )

    sp_manager = DummySessionPhaseManager(SessionPhase.WORK, remaining_ms=5_000)
    tray = TrayController(
        app=cast(Any, SimpleNamespace()),
        session_phase_manager=cast(Any, sp_manager),
    )

    tray.refresh()

    assert tray._action_pause.text == "Pause until..."
    tray_icon = cast(DummyTray, tray._tray)
    assert tray_icon.tooltip == "Work - 00:00:05"
    assert tray_icon.icon is not None
    assert "icon-work.svg" in tray_icon.icon


def test_refresh_updates_break_tooltip_and_icon(
    qcoreapp: QtCore.QCoreApplication, monkeypatch: Any
) -> None:
    monkeypatch.setattr(tray_module.QtWidgets, "QSystemTrayIcon", DummyTray)
    monkeypatch.setattr(tray_module.QtWidgets, "QMenu", DummyMenu)
    monkeypatch.setattr(
        tray_module.QtGui,
        "QIcon",
        lambda icon_path: f"icon-file:{icon_path}",
    )

    sp_manager = DummySessionPhaseManager(SessionPhase.BREAK, remaining_ms=12_000)
    tray = TrayController(
        app=cast(Any, SimpleNamespace()),
        session_phase_manager=cast(Any, sp_manager),
    )

    tray.refresh()

    assert tray._action_pause.text == "Pause until..."
    tray_icon = cast(DummyTray, tray._tray)
    assert tray_icon.tooltip == "Break - 00:00:12"
    assert tray_icon.icon is not None
    assert "icon-break.svg" in tray_icon.icon


def test_pause_action_emits_resume_when_paused(
    qcoreapp: QtCore.QCoreApplication, monkeypatch: Any
) -> None:
    monkeypatch.setattr(tray_module.QtWidgets, "QSystemTrayIcon", DummyTray)
    monkeypatch.setattr(tray_module.QtWidgets, "QMenu", DummyMenu)

    sp_manager = DummySessionPhaseManager(SessionPhase.PAUSE, remaining_ms=0)
    tray = TrayController(
        app=cast(Any, SimpleNamespace()),
        session_phase_manager=cast(Any, sp_manager),
    )
    resumed: list[bool] = []

    tray.resumeRequested.connect(lambda: resumed.append(True))
    tray._on_pause_action()

    assert resumed == [True]


def test_pause_action_emits_datetime_when_working(
    qcoreapp: QtCore.QCoreApplication, monkeypatch: Any
) -> None:
    monkeypatch.setattr(tray_module.QtWidgets, "QSystemTrayIcon", DummyTray)
    monkeypatch.setattr(tray_module.QtWidgets, "QMenu", DummyMenu)

    sp_manager = DummySessionPhaseManager(SessionPhase.WORK, remaining_ms=0)
    tray = TrayController(
        app=cast(Any, SimpleNamespace()),
        session_phase_manager=cast(Any, sp_manager),
    )
    emitted: list[QtCore.QDateTime] = []
    target = QtCore.QDateTime.fromString("2025-01-01 11:00", "yyyy-MM-dd HH:mm")

    monkeypatch.setattr(TrayController, "_prompt_pause_until", lambda self: target)
    tray.pauseUntilRequested.connect(emitted.append)
    tray._on_pause_action()

    assert emitted == [target]


def test_tray_activation_requests_open_app(
    qcoreapp: QtCore.QCoreApplication, monkeypatch: Any
) -> None:
    monkeypatch.setattr(tray_module.QtWidgets, "QSystemTrayIcon", DummyTray)
    monkeypatch.setattr(tray_module.QtWidgets, "QMenu", DummyMenu)

    sp_manager = DummySessionPhaseManager(SessionPhase.WORK, remaining_ms=0)
    tray = TrayController(
        app=cast(Any, SimpleNamespace()),
        session_phase_manager=cast(Any, sp_manager),
    )
    opened: list[bool] = []
    tray.openAppRequested.connect(lambda: opened.append(True))

    tray._on_tray_activated(DummyTray.ActivationReason.Trigger)

    assert opened == [True]


def test_check_in_action_emits_request(
    qcoreapp: QtCore.QCoreApplication, monkeypatch: Any
) -> None:
    monkeypatch.setattr(tray_module.QtWidgets, "QSystemTrayIcon", DummyTray)
    monkeypatch.setattr(tray_module.QtWidgets, "QMenu", DummyMenu)

    sp_manager = DummySessionPhaseManager(SessionPhase.WORK, remaining_ms=0)
    tray = TrayController(
        app=cast(Any, SimpleNamespace()),
        session_phase_manager=cast(Any, sp_manager),
    )
    emitted: list[bool] = []
    tray.checkInRequested.connect(lambda: emitted.append(True))
    assert tray._action_check_in.text == "Check in"

    tray._action_check_in.triggered.emit()

    assert emitted == [True]


def test_show_phase_warning_toast_enables_snooze_action(
    qcoreapp: QtCore.QCoreApplication, monkeypatch: Any
) -> None:
    monkeypatch.setattr(tray_module.QtWidgets, "QSystemTrayIcon", DummyTray)
    monkeypatch.setattr(tray_module.QtWidgets, "QMenu", DummyMenu)
    monkeypatch.setattr(tray_module, "PhaseWarningToast", DummySnackbar)

    sp_manager = DummySessionPhaseManager(SessionPhase.WORK, remaining_ms=0)
    tray = TrayController(
        app=cast(Any, SimpleNamespace()),
        session_phase_manager=cast(Any, sp_manager),
    )
    snoozed: list[bool] = []
    tray.snoozeRequested.connect(lambda: snoozed.append(True))
    tray.show_phase_warning_toast(text="Session ending soon")
    snackbar = cast(DummySnackbar, tray._phase_warning_toast)
    assert snackbar.show_calls == ["Session ending soon"]

    snackbar.snoozeRequested.emit()
    assert snoozed == [True]


def test_hide_phase_warning_toast_hides_active_toast(
    qcoreapp: QtCore.QCoreApplication, monkeypatch: Any
) -> None:
    monkeypatch.setattr(tray_module.QtWidgets, "QSystemTrayIcon", DummyTray)
    monkeypatch.setattr(tray_module.QtWidgets, "QMenu", DummyMenu)
    monkeypatch.setattr(tray_module, "PhaseWarningToast", DummySnackbar)

    sp_manager = DummySessionPhaseManager(SessionPhase.WORK, remaining_ms=0)
    tray = TrayController(
        app=cast(Any, SimpleNamespace()),
        session_phase_manager=cast(Any, sp_manager),
    )
    tray.show_phase_warning_toast(text="Session ending soon")

    tray.hide_phase_warning_toast()

    snackbar = cast(DummySnackbar, tray._phase_warning_toast)
    assert snackbar.hide_calls == 1
