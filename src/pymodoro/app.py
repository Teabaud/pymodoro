from __future__ import annotations

import random

from loguru import logger

from pymodoro.check_in_screen import CheckInScreen
from pymodoro.session import (
    SessionPhase,
    SessionPhaseManager,
)
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
        self._sp_manager.phaseEndingSoon.connect(self._on_phase_ending_soon)
        self._sp_manager.workEnded.connect(self._show_check_in_window)
        self._tray_controller.pauseUntilRequested.connect(self._sp_manager.pause_until)
        self._tray_controller.snoozeRequested.connect(self._on_snoozed_clicked)
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
        self._settings_window.startWorkRequested.connect(
            self._sp_manager.start_work_phase
        )
        self._settings_window.startBreakRequested.connect(
            self._sp_manager.start_break_phase
        )
        self._settings_window.set_paused(
            self._sp_manager.session_phase == SessionPhase.PAUSE
        )
        self._settings_window.show()

    def _on_settings_saved(self) -> None:
        self._tray_controller.refresh()

    def _on_phase_changed(self, _: SessionPhase, current_phase: SessionPhase) -> None:
        self._tray_controller.refresh()
        self._tray_controller.hide_phase_warning_toast()
        if self._settings_window and self._settings_window.isVisible():
            self._settings_window.set_paused(current_phase == SessionPhase.PAUSE)

    def _show_check_in_window(self) -> None:
        if self._check_in_screen and self._check_in_screen.isVisible():
            return
        check_in_prompt = self._select_check_in_prompt()
        if self._check_in_screen is None:
            self._check_in_screen = CheckInScreen(check_in_prompt=check_in_prompt)
            self._check_in_screen.submitted.connect(self._on_check_in_screen_submit)
        else:
            self._check_in_screen.set_check_in_prompt(check_in_prompt)
        self._check_in_screen.show()

    def _on_check_in_screen_submit(self, answer: str, focus_rating: int | None) -> None:
        logger.info("Answer: {} | focus_rating: {}", answer, focus_rating)
        self._close_check_in_window()

    def _on_phase_ending_soon(self, phase: SessionPhase) -> None:
        if phase != SessionPhase.WORK:
            return
        self._tray_controller.show_phase_warning_toast(
            text=f"{phase.value} ending soon"
        )

    def _on_snoozed_clicked(self) -> None:
        self._sp_manager.extend_current_phase()

    def _close_check_in_window(self) -> None:
        if self._check_in_screen is not None:
            self._check_in_screen.close()

    def _select_check_in_prompt(self) -> str:
        return random.choice(self._settings.check_in.prompts)
