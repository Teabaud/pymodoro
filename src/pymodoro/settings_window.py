from __future__ import annotations

from dataclasses import dataclass

from loguru import logger
from pydantic import ValidationError

from pymodoro.settings import AppSettings, MessagesSettings, TimersSettings, save_settings

# isort: split
from PySide6 import QtCore, QtGui
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

DRAG_HANDLE_CHAR = "\u22EE"
DELETE_CHAR = "\u00D7"


@dataclass
class SettingsDraft:
    work_duration: int
    break_duration: int
    snooze_duration: int
    prompts: list[str]

    @classmethod
    def from_settings(cls, settings: AppSettings) -> SettingsDraft:
        return cls(
            work_duration=settings.timers.work_duration,
            break_duration=settings.timers.break_duration,
            snooze_duration=settings.timers.snooze_duration,
            prompts=list(settings.messages.work_end_prompts),
        )


class PromptRowWidget(QFrame):
    textChanged = QtCore.Signal()
    deleteRequested = QtCore.Signal(object)

    def __init__(
        self,
        text: str,
        can_delete: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setLineWidth(1)
        self.setFixedHeight(32)
        self.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(6)

        drag_handle = QLabel(DRAG_HANDLE_CHAR)
        drag_handle.setToolTip("Drag to reorder")
        drag_handle.setCursor(QtCore.Qt.CursorShape.SizeAllCursor)
        drag_handle.setFixedWidth(18)
        layout.addWidget(drag_handle)

        self._line_edit = QLineEdit(text)
        self._line_edit.setPlaceholderText("Enter message...")
        self._line_edit.textChanged.connect(self.textChanged.emit)
        layout.addWidget(self._line_edit, 1)

        self._delete_btn = QPushButton(DELETE_CHAR)
        self._delete_btn.setToolTip("Delete message")
        self._delete_btn.setFixedSize(28, 28)
        self._delete_btn.clicked.connect(lambda: self.deleteRequested.emit(self))
        layout.addWidget(self._delete_btn)
        self.set_can_delete(can_delete)

    def text(self) -> str:
        return self._line_edit.text()

    def focus_editor(self) -> None:
        self._line_edit.setFocus()

    def set_can_delete(self, can_delete: bool) -> None:
        self._delete_btn.setVisible(can_delete)
        self._delete_btn.setEnabled(can_delete)


class PromptsEditor(QWidget):
    changed = QtCore.Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._list = QListWidget()
        self._list.setAlternatingRowColors(False)
        self._list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._list.setDragEnabled(True)
        self._list.setAcceptDrops(True)
        self._list.setDropIndicatorShown(True)
        self._list.setDefaultDropAction(QtCore.Qt.DropAction.MoveAction)
        self._list.setDragDropMode(QListWidget.DragDropMode.InternalMove)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._list)

        self._list.model().rowsMoved.connect(self._on_rows_moved)

    def set_prompts(self, prompts: list[str]) -> None:
        self._list.clear()
        initial_prompts = prompts if prompts else [""]
        for prompt in initial_prompts:
            self._append_prompt_row(prompt)
        self._sync_can_delete()

    def get_prompts(self) -> list[str]:
        prompts: list[str] = []
        for index in range(self._list.count()):
            item = self._list.item(index)
            row = self._row_widget(item)
            if row is not None:
                prompts.append(row.text())
        return prompts

    def add_prompt(self, text: str = "") -> None:
        item = self._append_prompt_row(text)
        self._sync_can_delete()
        self._list.setCurrentItem(item)
        row = self._row_widget(item)
        if row is not None:
            row.focus_editor()
        self.changed.emit()

    def move_prompt(self, from_index: int, to_index: int) -> None:
        prompts = self.get_prompts()
        count = len(prompts)
        if (
            from_index < 0
            or to_index < 0
            or from_index >= count
            or to_index >= count
            or from_index == to_index
        ):
            return

        prompt = prompts.pop(from_index)
        prompts.insert(to_index, prompt)
        self.set_prompts(prompts)
        self._list.setCurrentRow(to_index)
        self._sync_can_delete()
        self.changed.emit()

    def _append_prompt_row(self, text: str) -> QListWidgetItem:
        item = QListWidgetItem()
        row = PromptRowWidget(text=text, can_delete=self._list.count() > 0)
        row.deleteRequested.connect(self._remove_prompt_row)
        row.textChanged.connect(self.changed.emit)
        item.setSizeHint(row.sizeHint())
        self._list.addItem(item)
        self._list.setItemWidget(item, row)
        return item

    def _remove_prompt_row(self, row_widget: object) -> None:
        if self._list.count() <= 1:
            return

        for index in range(self._list.count()):
            item = self._list.item(index)
            row = self._row_widget(item)
            if row is row_widget:
                self._list.takeItem(index)
                break
        self._sync_can_delete()
        self.changed.emit()

    def _on_rows_moved(self, *_: object) -> None:
        self._sync_can_delete()
        self.changed.emit()

    def _sync_can_delete(self) -> None:
        can_delete = self._list.count() > 1
        for index in range(self._list.count()):
            row = self._row_widget(self._list.item(index))
            if row is not None:
                row.set_can_delete(can_delete)

    def _row_widget(self, item: QListWidgetItem) -> PromptRowWidget | None:
        widget = self._list.itemWidget(item)
        if isinstance(widget, PromptRowWidget):
            return widget
        return None


class SettingsWindow(QDialog):
    settingsSaved = QtCore.Signal()

    def __init__(
        self,
        settings: AppSettings,
        parent: QDialog | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._draft = SettingsDraft.from_settings(settings)
        self._dirty = False

        self.setWindowTitle("Pymodoro Settings")
        self.setMinimumSize(480, 400)
        self.resize(480, 450)

        self._timers_group = self._build_timers_section()
        self._messages_group = self._build_messages_section()
        self._button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        self._button_box.accepted.connect(self._on_save)
        self._button_box.rejected.connect(self._on_cancel)

        layout = QVBoxLayout(self)
        layout.addWidget(self._timers_group)
        layout.addWidget(self._messages_group)
        layout.addWidget(self._button_box)

    def _build_timers_section(self) -> QGroupBox:
        group = QGroupBox("Timers")
        form = QFormLayout(group)

        self._work_duration = QSpinBox()
        self._work_duration.setRange(1, 7200)
        self._work_duration.setSuffix(" s")
        self._work_duration.setValue(self._draft.work_duration)
        self._work_duration.valueChanged.connect(self._mark_dirty)
        form.addRow("Work duration:", self._work_duration)

        self._break_duration = QSpinBox()
        self._break_duration.setRange(1, 7200)
        self._break_duration.setSuffix(" s")
        self._break_duration.setValue(self._draft.break_duration)
        self._break_duration.valueChanged.connect(self._mark_dirty)
        form.addRow("Break duration:", self._break_duration)

        self._snooze_duration = QSpinBox()
        self._snooze_duration.setRange(1, 7200)
        self._snooze_duration.setSuffix(" s")
        self._snooze_duration.setValue(self._draft.snooze_duration)
        self._snooze_duration.valueChanged.connect(self._mark_dirty)
        form.addRow("Snooze duration:", self._snooze_duration)
        return group

    def _build_messages_section(self) -> QGroupBox:
        group = QGroupBox("Messages")
        layout = QVBoxLayout(group)

        self._prompts_editor = PromptsEditor()
        self._prompts_editor.set_prompts(self._draft.prompts)
        self._prompts_editor.changed.connect(self._mark_dirty)

        self._add_prompt_btn = QPushButton("Add")
        self._add_prompt_btn.clicked.connect(lambda: self._prompts_editor.add_prompt(""))

        buttons = QHBoxLayout()
        buttons.addWidget(self._add_prompt_btn)
        buttons.addStretch()

        layout.addWidget(self._prompts_editor)
        layout.addLayout(buttons)
        return group

    def _mark_dirty(self) -> None:
        self._dirty = True

    def _build_timers_from_form(self) -> TimersSettings:
        return TimersSettings(
            work_duration=self._work_duration.value(),
            break_duration=self._break_duration.value(),
            snooze_duration=self._snooze_duration.value(),
        )

    def _build_messages_from_form(self) -> MessagesSettings:
        return MessagesSettings(work_end_prompts=self._prompts_editor.get_prompts())

    def _show_validation_error(self, error: ValidationError) -> None:
        logger.exception("Validation failed")
        err = error.errors()[0]
        message = err.get("msg", str(error))
        if "ctx" in err and err["ctx"]:
            message = f"{message} ({err['ctx']})"
        QMessageBox.critical(self, "Validation Error", str(message))

    def _try_save(self) -> bool:
        try:
            timers = self._build_timers_from_form()
            messages = self._build_messages_from_form()
        except ValidationError as error:
            self._show_validation_error(error)
            return False

        self._settings.timers = timers
        self._settings.messages = messages
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
