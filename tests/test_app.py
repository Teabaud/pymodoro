from __future__ import annotations

import sys
import types
from typing import TYPE_CHECKING, Any, Callable

import pytest

if TYPE_CHECKING:
    from pymodoro.app import PomodoroApp


class DummySignal:
    def __init__(self) -> None:
        self.callbacks: list[Callable[..., Any]] = []

    def connect(self, callback: Callable[..., Any]) -> None:
        self.callbacks.append(callback)

    def emit(self, *args: Any, **kwargs: Any) -> None:
        for callback in self.callbacks:
            callback(*args, **kwargs)


class DummyAction:
    def __init__(self, text: str) -> None:
        self.text = text
        self.triggered = DummySignal()

    def setText(self, text: str) -> None:
        self.text = text


class DummyMenu:
    def __init__(self) -> None:
        self.actions: list[DummyAction] = []

    def addAction(self, text: str) -> DummyAction:
        action = DummyAction(text)
        self.actions.append(action)
        return action


class DummyTray:
    def __init__(self, *_: Any, **__: Any) -> None:
        self.visible = False
        self.tooltip = ""
        self.icon = None
        self.menu = None

    def show(self) -> None:
        self.visible = True

    def setVisible(self, visible: bool) -> None:
        self.visible = visible

    def setToolTip(self, text: str) -> None:
        self.tooltip = text

    def setIcon(self, icon: object) -> None:
        self.icon = icon

    def setContextMenu(self, menu: DummyMenu) -> None:
        self.menu = menu


class DummyIcon:
    def __init__(self, pixmap: object) -> None:
        self.pixmap = pixmap


class DummyTimers:
    work_duration = 60
    break_duration = 120
    snooze_duration = 60


class DummyConfig:
    timers = DummyTimers()

    class messages:
        work_end_question = "What is one thing you learned today?"


class DummyApp:
    def exec(self) -> int:
        return 0

    def setQuitOnLastWindowClosed(self, value: bool) -> None:
        _ = value


def _install_pyside_stubs() -> None:
    qtcore = types.ModuleType("PySide6.QtCore")
    qtgui = types.ModuleType("PySide6.QtGui")
    qtwidgets = types.ModuleType("PySide6.QtWidgets")

    class QObject:
        pass

    class QTimer:
        def __init__(self, *_: Any, **__: Any) -> None:
            self.interval = 0
            self.started = False
            self.single_shot = False
            self.timeout = DummySignal()

        def setSingleShot(self, single_shot: bool) -> None:
            self.single_shot = single_shot

        def setInterval(self, interval: int) -> None:
            self.interval = interval

        def start(self) -> None:
            self.started = True

        def stop(self) -> None:
            self.started = False

        def remainingTime(self) -> int:
            return self.interval

    class Qt:
        class GlobalColor:
            transparent = 0

        class AlignmentFlag:
            AlignCenter = 0

        class BrushStyle:
            NoBrush = 0

        class WindowType:
            Window = 0
            FramelessWindowHint = 0
            WindowStaysOnTopHint = 0

        class WindowModality:
            WindowModal = 0

        class WidgetAttribute:
            WA_ShowWithoutActivating = 0

        class ShortcutContext:
            WidgetWithChildrenShortcut = 0

    class Signal:
        def __init__(self, *_: Any, **__: Any) -> None:
            self._callbacks: list[Callable[..., Any]] = []

        def connect(self, callback: Callable[..., Any]) -> None:
            self._callbacks.append(callback)

        def emit(self, *args: Any, **kwargs: Any) -> None:
            for callback in self._callbacks:
                callback(*args, **kwargs)

    class QRect:
        def __init__(self, *_: Any, **__: Any) -> None:
            pass

    class QPixmap:
        def __init__(self, *_: Any, **__: Any) -> None:
            pass

        def fill(self, *_: Any, **__: Any) -> None:
            pass

    class QPainter:
        class RenderHint:
            TextAntialiasing = 0

        def __init__(self, *_: Any, **__: Any) -> None:
            pass

        def setRenderHint(self, *_: Any, **__: Any) -> None:
            pass

        def setPen(self, *_: Any, **__: Any) -> None:
            pass

        def setBrush(self, *_: Any, **__: Any) -> None:
            pass

        def setFont(self, *_: Any, **__: Any) -> None:
            pass

        def drawText(self, *_: Any, **__: Any) -> None:
            pass

        def end(self) -> None:
            pass

    class QFont:
        class Weight:
            Bold = 0

        def __init__(self, *_: Any, **__: Any) -> None:
            pass

    class QPalette:
        class ColorRole:
            WindowText = 0

    class QApplication:
        def __init__(self, *_: Any, **__: Any) -> None:
            pass

        @staticmethod
        def palette() -> "QPalette":
            return QPalette()

        @staticmethod
        def quit() -> None:
            pass

        def setQuitOnLastWindowClosed(self, *_: Any, **__: Any) -> None:
            pass

    class QSystemTrayIcon:
        @staticmethod
        def isSystemTrayAvailable() -> bool:
            return True

    class QMenu:
        pass

    class QIcon:
        def __init__(self, *_: Any, **__: Any) -> None:
            pass

    class QKeySequence:
        def __init__(self, *_: Any, **__: Any) -> None:
            pass

    class QWidget:
        def __init__(self, *_: Any, **__: Any) -> None:
            self.title = ""
            self.fullscreen = False
            self.raised = False
            self.activated = False
            self.closed = False
            self.visible = False

        def setWindowTitle(self, title: str) -> None:
            self.title = title

        def showFullScreen(self) -> None:
            self.fullscreen = True
            self.visible = True

        def raise_(self) -> None:
            self.raised = True

        def activateWindow(self) -> None:
            self.activated = True

        def close(self) -> None:
            self.closed = True
            self.visible = False

        def show(self) -> None:
            self.visible = True

        def isVisible(self) -> bool:
            return self.visible

    class QLabel:
        def __init__(self, *_: Any, **__: Any) -> None:
            self.alignment = None

        def setAlignment(self, alignment: object) -> None:
            self.alignment = alignment

        def setWordWrap(self, *_: Any, **__: Any) -> None:
            pass

    class QDialog(QWidget):
        def setWindowFlags(self, *_: Any, **__: Any) -> None:
            pass

        def setWindowModality(self, *_: Any, **__: Any) -> None:
            pass

        def setAttribute(self, *_: Any, **__: Any) -> None:
            pass

        def grabKeyboard(self) -> None:
            pass

        def grabMouse(self) -> None:
            pass

        def releaseKeyboard(self) -> None:
            pass

        def releaseMouse(self) -> None:
            pass

        def setLayout(self, *_: Any, **__: Any) -> None:
            pass

        def setStyleSheet(self, *_: Any, **__: Any) -> None:
            pass

    class QVBoxLayout:
        def __init__(self, *_: Any, **__: Any) -> None:
            self.widgets: list[object] = []

        def addWidget(self, widget: object) -> None:
            self.widgets.append(widget)

        def addSpacing(self, *_: Any, **__: Any) -> None:
            pass

        def addStretch(self, *_: Any, **__: Any) -> None:
            pass

        def addLayout(self, *_: Any, **__: Any) -> None:
            pass

    class QHBoxLayout(QVBoxLayout):
        pass

    class QPlainTextEdit:
        def __init__(self, *_: Any, **__: Any) -> None:
            self._text = ""
            self._visible = True

        def setPlaceholderText(self, *_: Any, **__: Any) -> None:
            pass

        def setVisible(self, visible: bool) -> None:
            self._visible = visible

        def isVisible(self) -> bool:
            return self._visible

        def setFocus(self) -> None:
            pass

        def toPlainText(self) -> str:
            return self._text

        def setPlainText(self, text: str) -> None:
            self._text = text

    class QPushButton:
        def __init__(self, *_: Any, **__: Any) -> None:
            self.clicked = DummySignal()

        def setFocus(self) -> None:
            pass

    class QShortcut:
        def __init__(self, *_: Any, **__: Any) -> None:
            self.activated = DummySignal()

        def setContext(self, *_: Any, **__: Any) -> None:
            pass

    setattr(qtcore, "QObject", QObject)
    setattr(qtcore, "QTimer", QTimer)
    setattr(qtcore, "Qt", Qt)
    setattr(qtcore, "QRect", QRect)
    setattr(qtcore, "Signal", Signal)

    setattr(qtgui, "QPixmap", QPixmap)
    setattr(qtgui, "QPainter", QPainter)
    setattr(qtgui, "QFont", QFont)
    setattr(qtgui, "QPalette", QPalette)
    setattr(qtgui, "QIcon", QIcon)
    setattr(qtgui, "QKeySequence", QKeySequence)
    setattr(qtgui, "QShortcut", QShortcut)
    setattr(qtgui, "QShowEvent", object)
    setattr(qtgui, "QCloseEvent", object)

    setattr(qtwidgets, "QApplication", QApplication)
    setattr(qtwidgets, "QSystemTrayIcon", QSystemTrayIcon)
    setattr(qtwidgets, "QMenu", QMenu)
    setattr(qtwidgets, "QWidget", QWidget)
    setattr(qtwidgets, "QLabel", QLabel)
    setattr(qtwidgets, "QVBoxLayout", QVBoxLayout)
    setattr(qtwidgets, "QDialog", QDialog)
    setattr(qtwidgets, "QHBoxLayout", QHBoxLayout)
    setattr(qtwidgets, "QPlainTextEdit", QPlainTextEdit)
    setattr(qtwidgets, "QPushButton", QPushButton)

    pyside6 = types.ModuleType("PySide6")
    setattr(pyside6, "QtCore", qtcore)
    setattr(pyside6, "QtGui", qtgui)
    setattr(pyside6, "QtWidgets", qtwidgets)

    sys.modules["PySide6"] = pyside6
    sys.modules["PySide6.QtCore"] = qtcore
    sys.modules["PySide6.QtGui"] = qtgui
    sys.modules["PySide6.QtWidgets"] = qtwidgets


@pytest.fixture(scope="session")
def app_module():
    _install_pyside_stubs()
    from pymodoro import app as app_module

    return app_module


@pytest.fixture()
def pomodoro_app(monkeypatch: pytest.MonkeyPatch, app_module) -> "PomodoroApp":
    monkeypatch.setattr(app_module, "load_config", lambda: DummyConfig())
    monkeypatch.setattr(app_module, "_get_qt_app", lambda: DummyApp())
    monkeypatch.setattr(app_module.QtWidgets, "QSystemTrayIcon", DummyTray)
    monkeypatch.setattr(app_module.QtWidgets, "QMenu", DummyMenu)
    monkeypatch.setattr(app_module.QtGui, "QIcon", DummyIcon)
    monkeypatch.setattr(
        app_module.PomodoroApp,
        "_render_icon",
        lambda self, label: f"pixmap-{label}",
    )
    return app_module.PomodoroApp()


def test_init_sets_timers_and_tray(pomodoro_app, app_module) -> None:
    assert pomodoro_app._mode == app_module.Mode.WORK
    assert pomodoro_app._tray.visible is True
    assert pomodoro_app._tray_update_clock.interval == 1000
    assert pomodoro_app._tray_update_clock.started is True
    assert pomodoro_app._mode_timer.interval == 60 * 1000
    assert pomodoro_app._mode_timer.started is True
    assert pomodoro_app._tray.tooltip == "work 00:01:00"


def test_start_session_updates_mode_and_tray(pomodoro_app, app_module) -> None:
    pomodoro_app._start_session(mode=app_module.Mode.BREAK, duration_seconds=120)

    assert pomodoro_app._mode == app_module.Mode.BREAK
    assert pomodoro_app._mode_timer.interval == 120 * 1000
    assert pomodoro_app._tray.tooltip == "break 00:02:00"


def test_on_mode_timer_timeout_switches_modes(pomodoro_app, app_module) -> None:
    pomodoro_app._mode = app_module.Mode.WORK
    pomodoro_app.on_mode_timer_timeout()

    assert pomodoro_app._mode == app_module.Mode.BREAK
    assert pomodoro_app._mode_timer.interval == 120 * 1000

    pomodoro_app.on_mode_timer_timeout()

    assert pomodoro_app._mode == app_module.Mode.WORK
    assert pomodoro_app._mode_timer.interval == 60 * 1000


def test_on_pause_action_resumes_when_paused(pomodoro_app, app_module) -> None:
    pomodoro_app._mode = app_module.Mode.PAUSE

    pomodoro_app._on_pause_action()

    assert pomodoro_app._mode == app_module.Mode.WORK
    assert pomodoro_app._action_pause.text == "Pause until..."
