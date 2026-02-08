from __future__ import annotations

import random

from loguru import logger

from pymodoro.config import load_config
from pymodoro.session import SessionPhaseManager
from pymodoro.tray import TrayController
from pymodoro.ui import FullScreenPrompt

# isort: split
from PySide6 import QtCore, QtWidgets


def _get_qt_app() -> QtWidgets.QApplication:
    app = QtWidgets.QApplication([])
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("Pymodoro")
    app.setDesktopFileName("pymodoro")
    if not QtWidgets.QSystemTrayIcon.isSystemTrayAvailable():
        raise RuntimeError("System tray is not available in this session.")
    return app


class PomodoroApp(QtCore.QObject):
    def __init__(self) -> None:
        super().__init__()
        self._app = _get_qt_app()

        config = load_config()
        self._work_end_prompts = config.messages.work_end_prompts

        self._sp_manager = SessionPhaseManager(
            work_duration=config.timers.work_duration,
            break_duration=config.timers.break_duration,
            snooze_duration=config.timers.snooze_duration,
        )
        self._tray_controller = TrayController(self._app, self._sp_manager)

        self._sp_manager.phaseChanged.connect(self._tray_controller.refresh)
        self._sp_manager.workEnded.connect(self._show_break_window)
        self._tray_controller.pauseUntilRequested.connect(self._sp_manager.pause_until)
        self._tray_controller.resumeRequested.connect(self._sp_manager.resume)
        self._tray_controller.quitRequested.connect(QtWidgets.QApplication.quit)

        self._sp_manager.start()
        self._tray_controller.show()

        self._fullscreen_window: FullScreenPrompt | None = None

        self.launch = self._app.exec

    def _show_break_window(self) -> None:
        if self._fullscreen_window is None:
            prompt_message = self._select_work_end_prompt()
            self._fullscreen_window = FullScreenPrompt(prompt_message=prompt_message)
            self._fullscreen_window.submitted.connect(self._on_note_submit)
            self._fullscreen_window.snoozed.connect(self._on_break_snooze)
        if self._fullscreen_window.isVisible():
            return
        self._fullscreen_window.show()

    def _on_note_submit(self, text: str) -> None:
        logger.info("Note submitted: {}", text)
        self._close_break_window()

    def _on_break_snooze(self) -> None:
        self._close_break_window()
        self._sp_manager.snooze_break()

    def _close_break_window(self) -> None:
        if self._fullscreen_window is not None:
            self._fullscreen_window.close()

    def _select_work_end_prompt(self) -> str:
        return random.choice(self._work_end_prompts)
