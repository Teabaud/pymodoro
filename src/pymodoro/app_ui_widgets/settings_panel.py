from __future__ import annotations

from loguru import logger
from pydantic import ValidationError

from pymodoro.app_ui_widgets.settings_panel_widgets import (
    DurationSelectionDialog,
    ListSectionWidget,
    NotificationsSectionWidget,
    SessionSectionWidget,
    TimersSectionWidget,
)
from pymodoro.settings import (
    AppSettings,
    save_settings,
)
from pymodoro.tray import PauseUntilDialog

# isort: split
from PySide6 import QtCore
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

AUTOSAVE_DEBOUNCE_MS = 300


class SettingsPanel(QWidget):
    settingsSaved = QtCore.Signal()
    pauseUntilRequested = QtCore.Signal(object)
    resumeRequested = QtCore.Signal()
    startWorkRequested = QtCore.Signal(int)
    startBreakRequested = QtCore.Signal(int)

    def __init__(
        self,
        settings: AppSettings,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._is_paused = False

        self._debounce_timer = QtCore.QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(AUTOSAVE_DEBOUNCE_MS)
        self._debounce_timer.timeout.connect(self._auto_save)

        self._session_group = SessionSectionWidget(self)
        self._timers_group = TimersSectionWidget(
            work_duration=settings.timers.work_duration,
            break_duration=settings.timers.break_duration,
            snooze_duration=settings.timers.snooze_duration,
            parent=self,
        )
        self._prompts_group = ListSectionWidget(
            title="Check-in Prompts",
            items=settings.check_in.prompts,
            placeholder="Add prompt and press Enter...",
            parent=self,
        )
        self._projects_group = ListSectionWidget(
            title="Projects",
            items=settings.check_in.projects,
            placeholder="Add project and press Enter...",
            parent=self,
        )
        self._exercises_group = ListSectionWidget(
            title="Exercises",
            items=settings.check_in.exercises,
            placeholder="Add exercise and press Enter...",
            parent=self,
        )
        self._activities_group = ListSectionWidget(
            title="Activities",
            items=settings.check_in.activities,
            placeholder="Add activity and press Enter...",
            parent=self,
        )
        self._notifications_group = NotificationsSectionWidget(
            notification_sound_enabled=settings.notification_sound_enabled,
            parent=self,
        )

        self._session_group.pauseResumeClicked.connect(self._on_pause_resume_clicked)
        self._session_group.startWorkClicked.connect(self._on_start_work_clicked)
        self._session_group.startBreakClicked.connect(self._on_start_break_clicked)
        self._timers_group.changed.connect(self._schedule_auto_save)
        self._prompts_group.changed.connect(self._schedule_auto_save)
        self._projects_group.changed.connect(self._schedule_auto_save)
        self._exercises_group.changed.connect(self._schedule_auto_save)
        self._activities_group.changed.connect(self._schedule_auto_save)
        self._notifications_group.changed.connect(self._schedule_auto_save)

        content = QWidget(self)
        layout = QVBoxLayout(content)
        layout.addWidget(self._session_group)
        layout.addWidget(self._timers_group)
        layout.addWidget(self._notifications_group)
        layout.addWidget(self._prompts_group)
        layout.addWidget(self._projects_group)
        layout.addWidget(self._exercises_group)
        layout.addWidget(self._activities_group)

        scroll = QScrollArea(self)
        scroll.setWidget(content)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        root = QVBoxLayout(self)
        root.addWidget(scroll)

    def set_paused(self, paused: bool) -> None:
        self._is_paused = paused
        self._session_group.set_paused(paused)

    def _prompt_pause_until(self) -> QtCore.QDateTime | None:
        default_datetime = QtCore.QDateTime.currentDateTime().addSecs(3600)
        dialog = PauseUntilDialog(default_datetime, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.selected_datetime()

    def _on_pause_resume_clicked(self) -> None:
        if self._is_paused:
            self.resumeRequested.emit()
            return
        pause_datetime = self._prompt_pause_until()
        if pause_datetime is not None:
            self.pauseUntilRequested.emit(pause_datetime)

    def _prompt_duration(self, title: str, default_seconds: int) -> int | None:
        dialog = DurationSelectionDialog(title, default_seconds, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.value()

    def _on_start_work_clicked(self) -> None:
        seconds = self._prompt_duration(
            "Start work phase", self._settings.timers.work_duration
        )
        if seconds is not None:
            self.startWorkRequested.emit(seconds)

    def _on_start_break_clicked(self) -> None:
        seconds = self._prompt_duration(
            "Start break phase", self._settings.timers.break_duration
        )
        if seconds is not None:
            self.startBreakRequested.emit(seconds)

    def _schedule_auto_save(self) -> None:
        self._debounce_timer.start()

    def _auto_save(self) -> None:
        try:
            timers = self._timers_group.to_timers_settings()
            check_in_prompts = self._prompts_group.list_editor.get_items()
            check_in_projects = self._projects_group.list_editor.get_items()
            check_in_exercises = self._exercises_group.list_editor.get_items()
            check_in_activities = self._activities_group.list_editor.get_items()
            sound_enabled = self._notifications_group.is_sound_enabled()
        except ValidationError:
            logger.debug("Skipping auto-save: validation failed")
            return
        self._settings.timers = timers
        self._settings.check_in.prompts = check_in_prompts
        self._settings.check_in.projects = check_in_projects
        self._settings.check_in.exercises = check_in_exercises
        self._settings.check_in.activities = check_in_activities
        self._settings.notification_sound_enabled = sound_enabled
        save_settings(self._settings)
        self.settingsSaved.emit()
