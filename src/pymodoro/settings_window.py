from __future__ import annotations

from dataclasses import dataclass

from loguru import logger
from pydantic import ValidationError

from pymodoro.settings import (
    AppSettings,
    save_settings,
)
from pymodoro.settings_window_widgets import (
    DurationSelectionDialog,
    CheckInPromptsSectionWidget,
    SessionSectionWidget,
    TimersSectionWidget,
)
from pymodoro.tray import PauseUntilDialog

# isort: split
from PySide6 import QtCore, QtGui
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QMessageBox,
    QVBoxLayout,
)

@dataclass
class SettingsDraft:
    work_duration: int
    break_duration: int
    snooze_duration: int
    check_in_prompts: list[str]

    @classmethod
    def from_settings(cls, settings: AppSettings) -> SettingsDraft:
        return cls(
            work_duration=settings.timers.work_duration,
            break_duration=settings.timers.break_duration,
            snooze_duration=settings.timers.snooze_duration,
            check_in_prompts=list(settings.check_in.prompts),
        )


class SettingsWindow(QDialog):
    settingsSaved = QtCore.Signal()
    pauseUntilRequested = QtCore.Signal(object)
    resumeRequested = QtCore.Signal()
    startWorkRequested = QtCore.Signal(int)
    startBreakRequested = QtCore.Signal(int)

    def __init__(
        self,
        settings: AppSettings,
        parent: QDialog | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._draft = SettingsDraft.from_settings(settings)
        self._dirty = False
        self._is_paused = False

        self.setWindowTitle("Pymodoro Settings")
        self.setMinimumSize(480, 400)
        self.resize(480, 450)

        self._session_group = SessionSectionWidget()
        self._timers_group = TimersSectionWidget(
            work_duration=self._draft.work_duration,
            break_duration=self._draft.break_duration,
            snooze_duration=self._draft.snooze_duration,
        )
        self._check_in_prompts_section_widget: CheckInPromptsSectionWidget = CheckInPromptsSectionWidget(
            check_in_prompts=self._draft.check_in_prompts
        )

        self._session_group.pauseResumeClicked.connect(self._on_pause_resume_clicked)
        self._session_group.startWorkClicked.connect(self._on_start_work_clicked)
        self._session_group.startBreakClicked.connect(self._on_start_break_clicked)
        self._timers_group.changed.connect(self._mark_dirty)
        self._check_in_prompts_section_widget.changed.connect(self._mark_dirty)

        self._button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        self._button_box.accepted.connect(self._on_save)
        self._button_box.rejected.connect(self._on_cancel)

        layout = QVBoxLayout(self)
        layout.addWidget(self._session_group)
        layout.addWidget(self._timers_group)
        layout.addWidget(self._check_in_prompts_section_widget)
        layout.addWidget(self._button_box)

    def set_paused(self, paused: bool) -> None:
        self._is_paused = paused
        self._session_group.set_paused(paused)

    def _prompt_pause_until(self) -> QtCore.QDateTime | None:
        default_datetime = QtCore.QDateTime.currentDateTime().addSecs(3600)
        dialog = PauseUntilDialog(default_datetime, self)
        accepted_code = getattr(getattr(QDialog, "DialogCode", None), "Accepted", 1)
        if dialog.exec() == accepted_code:
            return dialog.selected_datetime()

    def _on_pause_resume_clicked(self) -> None:
        if self._is_paused:
            self.resumeRequested.emit()
            return
        pause_datetime = self._prompt_pause_until()
        if pause_datetime is not None:
            self.pauseUntilRequested.emit(pause_datetime)

    def _prompt_duration(self, title: str, default_seconds: int) -> int | None:
        dialog = DurationSelectionDialog(title, default_seconds // 60, self)
        accepted_code = getattr(getattr(QDialog, "DialogCode", None), "Accepted", 1)
        if dialog.exec() == accepted_code:
            return dialog.selected_minutes() * 60

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

    def _try_save(self) -> bool:
        try:
            timers = self._timers_group.to_timers_settings()
            check_in_prompts = (
                self._check_in_prompts_section_widget.prompts_editor.get_prompts()
            )
        except ValidationError as error:
            self._show_validation_error(error)
            return False

        self._settings.timers = timers
        self._settings.check_in.prompts = check_in_prompts
        save_settings(self._settings)
        self._draft = SettingsDraft.from_settings(self._settings)
        self._dirty = False
        self.settingsSaved.emit()
        return True

    def _on_save(self) -> None:
        if self._try_save():
            self.accept()

    def _on_cancel(self) -> None:
        self.close()

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if event.key() in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter):
            event.ignore()
            return
        super().keyPressEvent(event)

    def _confirm_close_for_dirty_state(self) -> QMessageBox.StandardButton:
        message_box = QMessageBox(self)
        message_box.setWindowTitle("Unsaved Changes")
        message_box.setText("Settings have been modified. Save changes?")
        message_box.setIcon(QMessageBox.Icon.Question)
        message_box.setStandardButtons(
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel
        )
        message_box.setDefaultButton(QMessageBox.StandardButton.Save)
        message_box.setEscapeButton(QMessageBox.StandardButton.Cancel)
        return QMessageBox.StandardButton(message_box.exec())

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if not self._dirty:
            super().closeEvent(event)
            return

        result = self._confirm_close_for_dirty_state()
        if result == QMessageBox.StandardButton.Cancel:
            event.ignore()
            return
        if result == QMessageBox.StandardButton.Save and not self._try_save():
            event.ignore()
            return
        event.accept()
