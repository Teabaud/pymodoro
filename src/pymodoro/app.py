from __future__ import annotations

import random

from loguru import logger

from pymodoro.check_in_screen import CheckInScreen
from pymodoro.session import SessionPhase, SessionPhaseManager
from pymodoro.settings import AppSettings
from pymodoro.settings_window import SettingsWindow
from pymodoro.tray import TrayController

# isort: split
from PySide6 import QtCore, QtGui
from PySide6.QtWidgets import QApplication, QSystemTrayIcon


def _apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    palette = QtGui.QPalette()
    palette.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor(37, 37, 38))
    palette.setColor(QtGui.QPalette.ColorRole.Base, QtGui.QColor(30, 30, 30))
    palette.setColor(QtGui.QPalette.ColorRole.Button, QtGui.QColor(45, 45, 48))
    palette.setColor(QtGui.QPalette.ColorRole.Text, QtGui.QColor(235, 235, 235))
    palette.setColor(QtGui.QPalette.ColorRole.ButtonText, QtGui.QColor(235, 235, 235))
    palette.setColor(QtGui.QPalette.ColorRole.Highlight, QtGui.QColor(0, 122, 204))
    app.setPalette(palette)


def _get_qt_app() -> QApplication:
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("Pymodoro")
    app.setDesktopFileName("pymodoro")
    _apply_theme(app)
    if not QSystemTrayIcon.isSystemTrayAvailable():
        raise RuntimeError("System tray is not available in this session.")
    return app


class PomodoroApp(QtCore.QObject):
    def __init__(self, settings: AppSettings, app: QApplication | None = None) -> None:
        super().__init__()
        self._app = app or _get_qt_app()
        self._settings = settings

        self._check_in_screen: CheckInScreen | None = None
        self._settings_window: SettingsWindow | None = None

        self._sp_manager = SessionPhaseManager(settings=settings)
        self._tray_controller = TrayController(self._app, self._sp_manager)

        self._sp_manager.phaseChanged.connect(self._on_phase_changed)
        self._sp_manager.workEnded.connect(self._show_check_in_window)
        self._tray_controller.pauseUntilRequested.connect(self._sp_manager.pause_until)
        self._tray_controller.resumeRequested.connect(self._sp_manager.resume)
        self._tray_controller.quitRequested.connect(self._app.quit)
        self._tray_controller.openAppRequested.connect(self._open_settings_window)
        self._tray_controller.checkInRequested.connect(self._show_check_in_window)

        self._sp_manager.start()
        self._tray_controller.show()

        self.launch = self._app.exec

    def _open_settings_window(self) -> None:
        if self._settings_window and self._settings_window.isVisible():
            self._settings_window.set_paused(
                self._sp_manager.session_phase == SessionPhase.PAUSE
            )
            self._settings_window.raise_()
            self._settings_window.activateWindow()
            return
        self._settings_window = SettingsWindow(self._settings)
        self._settings_window.settingsSaved.connect(self._on_settings_saved)
        self._settings_window.pauseUntilRequested.connect(self._sp_manager.pause_until)
        self._settings_window.resumeRequested.connect(self._sp_manager.resume)
        self._settings_window.startWorkRequested.connect(self._sp_manager.start_work_phase)
        self._settings_window.startBreakRequested.connect(self._sp_manager.start_break_phase)
        self._settings_window.set_paused(
            self._sp_manager.session_phase == SessionPhase.PAUSE
        )
        self._settings_window.show()

    def _on_settings_saved(self) -> None:
        self._tray_controller.refresh()

    def _on_phase_changed(
        self, _: SessionPhase, current_phase: SessionPhase
    ) -> None:
        self._tray_controller.refresh()
        if self._settings_window and self._settings_window.isVisible():
            self._settings_window.set_paused(current_phase == SessionPhase.PAUSE)

    def _show_check_in_window(self) -> None:
        if self._check_in_screen and self._check_in_screen.isVisible():
            return
        prompt_message = self._select_work_end_prompt()
        if self._check_in_screen is None:
            self._check_in_screen = CheckInScreen(prompt_message=prompt_message)
            self._check_in_screen.submitted.connect(self._on_check_in_screen_submit)
            self._check_in_screen.snoozed.connect(self._on_check_in_snooze)
        else:
            self._check_in_screen.set_prompt_message(prompt_message)
        self._check_in_screen.show()

    def _on_check_in_screen_submit(self, text: str, focus_rating: int | None) -> None:
        logger.info("Note: {} | focus_rating: {}", text, focus_rating)
        self._close_check_in_window()

    def _on_check_in_snooze(self) -> None:
        self._close_check_in_window()
        self._sp_manager.snooze_break()

    def _close_check_in_window(self) -> None:
        if self._check_in_screen is not None:
            self._check_in_screen.close()

    def _select_work_end_prompt(self) -> str:
        return random.choice(self._settings.messages.work_end_prompts)
