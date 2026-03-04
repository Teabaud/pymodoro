from __future__ import annotations

from dataclasses import dataclass

from loguru import logger
from pydantic import ValidationError

from pymodoro.app_ui_widgets.settings_panel_widgets import (
    DurationSelectionDialog,
    NotificationsSectionWidget,
    PromptsSectionWidget,
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
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

StandardButton = QDialogButtonBox.StandardButton


@dataclass
class SettingsDraft:
    work_duration: int
    break_duration: int
    snooze_duration: int
    check_in_prompts: list[str]
    notification_sound_enabled: bool

    @classmethod
    def from_settings(cls, settings: AppSettings) -> SettingsDraft:
        return cls(
            work_duration=settings.timers.work_duration,
            break_duration=settings.timers.break_duration,
            snooze_duration=settings.timers.snooze_duration,
            check_in_prompts=settings.check_in.prompts,
            notification_sound_enabled=settings.notification_sound_enabled,
        )


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
        self._draft = SettingsDraft.from_settings(settings)
        self._dirty = False
        self._is_paused = False

        self._session_group = SessionSectionWidget(self)
        self._timers_group = TimersSectionWidget(
            work_duration=self._draft.work_duration,
            break_duration=self._draft.break_duration,
            snooze_duration=self._draft.snooze_duration,
            parent=self,
        )
        self._prompts_group = PromptsSectionWidget(
            check_in_prompts=self._draft.check_in_prompts,
            parent=self,
        )
        self._notifications_group = NotificationsSectionWidget(
            notification_sound_enabled=self._draft.notification_sound_enabled,
            parent=self,
        )
        self._save_button = QPushButton("Save")
        self._reset_button = QPushButton("Reset")

        self._session_group.pauseResumeClicked.connect(self._on_pause_resume_clicked)
        self._session_group.startWorkClicked.connect(self._on_start_work_clicked)
        self._session_group.startBreakClicked.connect(self._on_start_break_clicked)
        self._timers_group.changed.connect(self._mark_dirty)
        self._prompts_group.changed.connect(self._mark_dirty)
        self._notifications_group.changed.connect(self._mark_dirty)
        self._save_button.clicked.connect(self._save_settings)
        self._reset_button.clicked.connect(self._reset_settings)

        content = QWidget(self)
        layout = QVBoxLayout(content)
        layout.addWidget(self._session_group)
        layout.addWidget(self._timers_group)
        layout.addWidget(self._notifications_group)
        layout.addWidget(self._prompts_group)
        button_layout = QHBoxLayout(content)
        button_layout.addWidget(self._reset_button)
        button_layout.addStretch()
        button_layout.addWidget(self._save_button)
        layout.addLayout(button_layout)

        scroll = QScrollArea(self)
        scroll.setWidget(content)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        root = QVBoxLayout(self)
        root.addWidget(scroll)

        self.setStyleSheet("""
            SettingsPanel {
                background-color: palette(base);
                border-radius: 10px;
                margin: 12px 0px 0px 0px;
            }
        """)

        self.setMaximumWidth(600)

    def set_paused(self, paused: bool) -> None:
        self._is_paused = paused
        self._session_group.set_paused(paused)

    def has_unsaved_changes(self) -> bool:
        return self._dirty

    def prepare_leave(self) -> bool:
        """Return True if it's OK to leave (no dirty, or user saved/discarded)."""
        if not self._dirty:
            return True
        match self._confirm_close_for_dirty_state():
            case QMessageBox.StandardButton.Save:
                return self._save_settings()
            case QMessageBox.StandardButton.Cancel:
                return False
            case QMessageBox.StandardButton.Discard:
                return self._reset_settings()
            case _:
                return False

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

    def _mark_dirty(self) -> None:
        self._dirty = True

    def _show_validation_error(self, error: ValidationError) -> None:
        logger.exception("Validation failed")
        err = error.errors()[0]
        message = err.get("msg", str(error))
        if "ctx" in err and err["ctx"]:
            message = f"{message} ({err['ctx']})"
        QMessageBox.critical(self, "Validation Error", str(message))

    def _save_settings(self) -> bool:
        if self._validate_settings():
            save_settings(self._settings)
            self._draft = SettingsDraft.from_settings(self._settings)
            self._dirty = False
            self.settingsSaved.emit()
            return True
        return False

    def _validate_settings(self) -> bool:
        try:
            timers = self._timers_group.to_timers_settings()
            check_in_prompts = self._prompts_group.prompts_editor.get_prompts()
            sound_enabled = self._notifications_group.is_sound_enabled()
        except ValidationError as error:
            self._show_validation_error(error)
            return False
        self._settings.timers = timers
        self._settings.check_in.prompts = check_in_prompts
        self._settings.notification_sound_enabled = sound_enabled
        return True

    def _reset_settings(self) -> bool:
        """Revert UI to last saved settings (e.g. on Cancel)."""
        self._draft = SettingsDraft.from_settings(self._settings)
        self._dirty = False

        self._timers_group.work_duration.blockSignals(True)
        self._timers_group.break_duration.blockSignals(True)
        self._timers_group.snooze_duration.blockSignals(True)
        try:
            self._timers_group.work_duration.setValue(self._draft.work_duration)
            self._timers_group.break_duration.setValue(self._draft.break_duration)
            self._timers_group.snooze_duration.setValue(self._draft.snooze_duration)
        finally:
            self._timers_group.work_duration.blockSignals(False)
            self._timers_group.break_duration.blockSignals(False)
            self._timers_group.snooze_duration.blockSignals(False)

        self._prompts_group.prompts_editor.set_prompts(self._draft.check_in_prompts)
        self._notifications_group.set_sound_enabled(
            self._draft.notification_sound_enabled
        )
        return True

    def _confirm_close_for_dirty_state(self) -> QMessageBox.StandardButton:
        message_box = QMessageBox(self)
        message_box.setWindowTitle("Unsaved Changes")
        message_box.setText("Settings have been modified. Save changes?")
        message_box.setStandardButtons(
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel
        )
        message_box.setDefaultButton(QMessageBox.StandardButton.Save)
        message_box.setEscapeButton(QMessageBox.StandardButton.Cancel)
        return QMessageBox.StandardButton(message_box.exec())
