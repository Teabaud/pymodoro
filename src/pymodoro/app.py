from __future__ import annotations

import random

from loguru import logger

from pymodoro.break_screen import BreakScreen
from pymodoro.session import SessionPhaseManager
from pymodoro.settings import AppSettings
from pymodoro.settings_window import SettingsWindow
from pymodoro.tray import TrayController

# isort: split
from PySide6 import QtCore
from PySide6.QtWidgets import QApplication, QSystemTrayIcon


def _get_qt_app() -> QApplication:
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("Pymodoro")
    app.setDesktopFileName("pymodoro")
    if not QSystemTrayIcon.isSystemTrayAvailable():
        raise RuntimeError("System tray is not available in this session.")
    return app


class PomodoroApp(QtCore.QObject):
    def __init__(self, settings: AppSettings, app: QApplication | None = None) -> None:
        super().__init__()
        self._app = app or _get_qt_app()
        self._settings = settings

        self._sp_manager = SessionPhaseManager(settings=settings)
        self._tray_controller = TrayController(self._app, self._sp_manager)

        self._sp_manager.phaseChanged.connect(self._tray_controller.refresh)
        self._sp_manager.workEnded.connect(self._show_break_window)
        self._tray_controller.pauseUntilRequested.connect(self._sp_manager.pause_until)
        self._tray_controller.resumeRequested.connect(self._sp_manager.resume)
        self._tray_controller.quitRequested.connect(self._app.quit)
        self._tray_controller.openAppRequested.connect(self._open_settings_window)

        self._sp_manager.start()
        self._tray_controller.show()

        self._break_screen: BreakScreen | None = None
        self._settings_window: SettingsWindow | None = None

        self.launch = self._app.exec

    def _open_settings_window(self) -> None:
        if self._settings_window is not None and self._settings_window.isVisible():
            self._settings_window.raise_()
            self._settings_window.activateWindow()
            return
        self._settings_window = SettingsWindow(self._settings)
        self._settings_window.settingsSaved.connect(self._on_settings_saved)
        self._settings_window.show()

    def _on_settings_saved(self) -> None:
        self._tray_controller.refresh()

    def _show_break_window(self) -> None:
        if self._break_screen and self._break_screen.isVisible():
            return
        prompt_message = self._select_work_end_prompt()
        if self._break_screen is None:
            self._break_screen = BreakScreen(prompt_message=prompt_message)
            self._break_screen.submitted.connect(self._on_break_screen_submit)
            self._break_screen.snoozed.connect(self._on_break_snooze)
        else:
            self._break_screen.set_prompt_message(prompt_message)
        self._break_screen.show()

    def _on_break_screen_submit(self, text: str, focus_rating: int | None) -> None:
        logger.info("Note: {} | focus_rating: {}", text, focus_rating)
        self._close_break_window()

    def _on_break_snooze(self) -> None:
        self._close_break_window()
        self._sp_manager.snooze_break()

    def _close_break_window(self) -> None:
        if self._break_screen is not None:
            self._break_screen.close()

    def _select_work_end_prompt(self) -> str:
        return random.choice(self._settings.messages.work_end_prompts)
