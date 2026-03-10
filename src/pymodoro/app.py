# import os
# os.environ["QT_NO_GLIB"] = "1"
import random

from loguru import logger

from pymodoro.app_ui import AppWindow
from pymodoro.app_ui_widgets.pages import Page
from pymodoro.app_ui_widgets.settings_panel import SettingsPanel
from pymodoro.check_in_screen import CheckInScreen
from pymodoro.metrics_logger import CheckInSubmission, MetricsLogger
from pymodoro.notification_sound import NotificationSoundPlayer
from pymodoro.session import (
    SessionPhase,
    SessionPhaseManager,
)
from pymodoro.settings import AppSettings
from pymodoro.tray import TrayController

# isort: split
from PySide6 import QtCore
from PySide6.QtWidgets import QApplication, QSystemTrayIcon


def _get_qt_app() -> QApplication:
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("Pymodoro")
    if not QSystemTrayIcon.isSystemTrayAvailable():
        raise RuntimeError("System tray is not available in this session.")
    return app


class PomodoroApp(QtCore.QObject):
    def __init__(self, settings: AppSettings, app: QApplication | None = None) -> None:
        super().__init__()
        self._app = app or _get_qt_app()
        self._settings = settings
        self._metrics_logger = MetricsLogger(self._settings.metrics_log_path)

        self._check_in_screen: CheckInScreen | None = None
        self._app_window: AppWindow | None = None
        self._notification_sound_player = NotificationSoundPlayer()
        self._awaiting_check_in_close: bool = False

        self._sp_manager = SessionPhaseManager(settings=settings)
        self._tray_controller = TrayController(self._app, self._sp_manager)

        self._sp_manager.phaseChanged.connect(self._on_phase_changed)
        self._sp_manager.phaseEndingSoon.connect(self._on_phase_ending_soon)
        self._sp_manager.workEnded.connect(self._show_check_in_window)
        self._sp_manager.breakEnded.connect(self._on_break_ended)
        self._tray_controller.pauseUntilRequested.connect(self._sp_manager.pause_until)
        self._tray_controller.snoozeRequested.connect(self._on_snoozed_clicked)
        self._tray_controller.resumeRequested.connect(self._sp_manager.resume)
        self._tray_controller.quitRequested.connect(self._app.quit)
        self._tray_controller.openAppRequested.connect(self._open_app_window)
        self._tray_controller.checkInRequested.connect(self._show_check_in_window)
        self._tray_controller.startBreakRequested.connect(self._on_start_break_from_toast)
        self._tray_controller.openSettingsRequested.connect(self._open_settings_panel)

        self._sp_manager.start()
        self._tray_controller.show()

        self.launch = self._app.exec

    def _open_app_window(self) -> AppWindow:
        if self._app_window is None:
            self._app_window = AppWindow(self._settings)
            self._connect_settings_signals(self._app_window.get_settings_panel())
        self._app_window.show()
        self._app_window.raise_()
        self._app_window.activateWindow()
        return self._app_window

    def _connect_settings_signals(self, settings_ui: SettingsPanel) -> None:
        settings_ui.settingsSaved.connect(self._on_settings_saved)
        settings_ui.pauseUntilRequested.connect(self._sp_manager.pause_until)
        settings_ui.resumeRequested.connect(self._sp_manager.resume)
        settings_ui.startWorkRequested.connect(self._sp_manager.start_work_phase)
        settings_ui.startBreakRequested.connect(self._sp_manager.start_break_phase)
        settings_ui.set_paused(self._sp_manager.session_phase == SessionPhase.PAUSE)

    def _open_settings_panel(self) -> None:
        self._open_app_window().navigate_to_page(Page.SETTINGS)

    def _on_settings_saved(self) -> None:
        self._tray_controller.refresh()

    def _play_notification_sound(self) -> None:
        if self._settings.notification_sound_enabled:
            self._notification_sound_player.play()

    def _on_phase_changed(
        self,
        previous_phase: SessionPhase,
        current_phase: SessionPhase,
        previous_phase_duration: int,
    ) -> None:
        self._tray_controller.refresh()
        self._tray_controller.hide_phase_end_toast()
        if previous_phase == SessionPhase.BREAK and current_phase == SessionPhase.WORK:
            self._play_notification_sound()
        if self._app_window:
            settings_panel = self._app_window.get_settings_panel()
            settings_panel.set_paused(current_phase == SessionPhase.PAUSE)
        self._metrics_logger.log_phase_duration(previous_phase, previous_phase_duration)

    def _on_start_break_from_toast(self) -> None:
        self._sp_manager.start_break_phase()
        self._show_check_in_window()

    def _show_check_in_window(self) -> None:
        if self._check_in_screen and self._check_in_screen.isVisible():
            return
        check_in_prompt = self._select_check_in_prompt()
        if self._check_in_screen is None:
            self._check_in_screen = CheckInScreen(check_in_prompt=check_in_prompt, settings=self._settings)
            self._check_in_screen.submitted.connect(self._on_check_in_screen_submit)
            self._check_in_screen.finished.connect(self._on_check_in_finished)
        else:
            self._check_in_screen.set_check_in_prompt(check_in_prompt)
        self._check_in_screen.show()

    def _on_check_in_screen_submit(self, submission: CheckInSubmission) -> None:
        self._metrics_logger.log_check_in(submission)
        logger.info(
            "Answer: {} | focus_rating: {} | exercise_result: ({}, {})",
            submission.answer,
            submission.focus_rating,
            submission.exercise_name,
            submission.exercise_rep_count,
        )
        if self._check_in_screen is not None:
            self._check_in_screen.accept()

    def _on_phase_ending_soon(self, phase: SessionPhase) -> None:
        if phase != SessionPhase.WORK:
            return
        self._tray_controller.show_phase_end_toast(text=f"{phase.value} ending soon")
        self._play_notification_sound()

    def _on_snoozed_clicked(self) -> None:
        self._sp_manager.extend_current_phase()

    def _on_break_ended(self) -> None:
        if self._check_in_screen and self._check_in_screen.isVisible():
            self._awaiting_check_in_close = True
        else:
            self._play_notification_sound()
            self._sp_manager.start_work_phase()

    def _on_check_in_finished(self, _: int) -> None:
        if self._awaiting_check_in_close:
            self._awaiting_check_in_close = False
            self._sp_manager.start_work_phase()

    def _select_check_in_prompt(self) -> str:
        return random.choice(self._settings.check_in.prompts)
