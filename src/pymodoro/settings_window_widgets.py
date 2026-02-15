from __future__ import annotations

from pymodoro.settings import TimersSettings

# isort: split
from PySide6 import QtCore
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
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

DRAG_HANDLE_CHAR = "\u22ee"
DELETE_CHAR = "\u00d7"
DURATION_INPUT_MAX_WIDTH = 120


class CheckInPromptRowWidget(QFrame):
    textChanged = QtCore.Signal()
    deleteRequested = QtCore.Signal(object)
    blurRequested = QtCore.Signal(object)

    def __init__(
        self,
        check_in_prompt: str,
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

        self._line_edit = QLineEdit(check_in_prompt)
        self._line_edit.setPlaceholderText("Enter check-in prompt...")
        self._line_edit.textChanged.connect(lambda _: self.textChanged.emit())
        self._line_edit.installEventFilter(self)
        self._line_edit.editingFinished.connect(lambda: self.blurRequested.emit(self))
        layout.addWidget(self._line_edit, 1)

        self._delete_btn = QPushButton(DELETE_CHAR)
        self._delete_btn.setToolTip("Delete check-in prompt")
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

    def eventFilter(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if watched is self._line_edit and event.type() == QtCore.QEvent.Type.FocusOut:
            QtCore.QTimer.singleShot(0, lambda: self.blurRequested.emit(self))
        return super().eventFilter(watched, event)


class PromptsEditor(QWidget):
    changed = QtCore.Signal()
    canAddChanged = QtCore.Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._list = QListWidget()
        self._has_empty_prompt = False
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
        self._sync_ui_state()

    def get_prompts(self) -> list[str]:
        prompts: list[str] = []
        for index in range(self._list.count()):
            item = self._list.item(index)
            row = self._row_widget(item)
            if row is not None:
                prompts.append(row.text())
        return prompts

    def add_prompt(self, text: str = "") -> None:
        if not text.strip() and self._has_empty_prompt:
            self._focus_first_empty_prompt()
            return
        item = self._append_prompt_row(text)
        self._sync_ui_state()
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
        self._sync_ui_state()
        self.changed.emit()

    def can_add_prompt(self) -> bool:
        return not self._has_empty_prompt

    def _append_prompt_row(self, check_in_prompt: str) -> QListWidgetItem:
        item = QListWidgetItem()
        row = CheckInPromptRowWidget(check_in_prompt=check_in_prompt, can_delete=self._list.count() > 0)
        row.deleteRequested.connect(self._remove_prompt_row)
        row.textChanged.connect(self._on_row_text_changed)
        row.blurRequested.connect(self._on_row_blur)
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
        self._sync_ui_state()
        self.changed.emit()

    def _on_rows_moved(self, *_: object) -> None:
        self._sync_ui_state()
        self.changed.emit()

    def _on_row_text_changed(self) -> None:
        self._sync_ui_state()
        self.changed.emit()

    def _on_row_blur(self, row_widget: object) -> None:
        if self._list.count() <= 1:
            return
        for index in range(self._list.count()):
            item = self._list.item(index)
            row = self._row_widget(item)
            if row is not None and row is row_widget and not row.text().strip():
                self._list.takeItem(index)
                self._sync_ui_state()
                self.changed.emit()
                break

    def _focus_first_empty_prompt(self) -> None:
        for index in range(self._list.count()):
            item = self._list.item(index)
            row = self._row_widget(item)
            if row is not None and not row.text().strip():
                self._list.setCurrentItem(item)
                row.focus_editor()
                return

    def _sync_ui_state(self) -> None:
        self._sync_can_delete()
        has_empty_prompt = False
        for index in range(self._list.count()):
            item = self._list.item(index)
            row = self._row_widget(item)
            if row is not None and not row.text().strip():
                has_empty_prompt = True
                break
        if has_empty_prompt != self._has_empty_prompt:
            self._has_empty_prompt = has_empty_prompt
            self.canAddChanged.emit(not has_empty_prompt)

    def _sync_can_delete(self) -> None:
        can_delete = self._list.count() > 1
        for index in range(self._list.count()):
            row = self._row_widget(self._list.item(index))
            if row is not None:
                row.set_can_delete(can_delete)

    def _row_widget(self, item: QListWidgetItem) -> CheckInPromptRowWidget | None:
        widget = self._list.itemWidget(item)
        if isinstance(widget, CheckInPromptRowWidget):
            return widget
        return None


class SessionSectionWidget(QGroupBox):
    startWorkClicked = QtCore.Signal()
    startBreakClicked = QtCore.Signal()
    pauseResumeClicked = QtCore.Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Session", parent)
        layout = QHBoxLayout(self)
        self.start_work_button = QPushButton("Start work")
        self.start_work_button.clicked.connect(self.startWorkClicked.emit)
        layout.addWidget(self.start_work_button)

        self.start_break_button = QPushButton("Start break")
        self.start_break_button.clicked.connect(self.startBreakClicked.emit)
        layout.addWidget(self.start_break_button)

        self.pause_resume_button = QPushButton("Pause until...")
        self.pause_resume_button.clicked.connect(self.pauseResumeClicked.emit)
        layout.addWidget(self.pause_resume_button)

    def set_paused(self, paused: bool) -> None:
        self.pause_resume_button.setText("Resume" if paused else "Pause until...")


class DurationSelectionDialog(QDialog):
    def __init__(
        self,
        title: str,
        default_minutes: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self._minutes_input = QSpinBox(self)
        self._minutes_input.setRange(1, 720)
        self._minutes_input.setSuffix(" min")
        self._minutes_input.setValue(default_minutes)
        form.addRow("Duration:", self._minutes_input)
        layout.addLayout(form)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def selected_minutes(self) -> int:
        return self._minutes_input.value()


class DurationInputWidget(QSpinBox):
    def __init__(self, value: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setRange(1, 7200)
        self.setSuffix(" s")
        self.setValue(value)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setMaximumWidth(DURATION_INPUT_MAX_WIDTH)

class TimersSectionWidget(QGroupBox):
    changed = QtCore.Signal()

    def __init__(
        self,
        work_duration: int,
        break_duration: int,
        snooze_duration: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("Timers", parent)
        form = QFormLayout(self)

        self.work_duration = DurationInputWidget(work_duration, self)
        form.addRow("Work duration:", self.work_duration)
        self.work_duration.valueChanged.connect(self.on_duration_changed)

        self.break_duration = DurationInputWidget(break_duration, self)
        form.addRow("Break duration:", self.break_duration)
        self.break_duration.valueChanged.connect(self.on_duration_changed)

        self.snooze_duration = DurationInputWidget(snooze_duration, self)
        form.addRow("Snooze duration:", self.snooze_duration)
        self.snooze_duration.valueChanged.connect(self.on_duration_changed)

    def to_timers_settings(self) -> TimersSettings:
        return TimersSettings(
            work_duration=self.work_duration.value(),
            break_duration=self.break_duration.value(),
            snooze_duration=self.snooze_duration.value(),
        )

    def on_duration_changed(self, _: int) -> None:
        self.changed.emit()

class CheckInPromptsSectionWidget(QGroupBox):
    changed = QtCore.Signal()

    def __init__(self, check_in_prompts: list[str], parent: QWidget | None = None) -> None:
        super().__init__("Check-in Prompts", parent)
        layout = QVBoxLayout(self)

        self.prompts_editor = PromptsEditor()
        self.prompts_editor.set_prompts(check_in_prompts)
        self.prompts_editor.changed.connect(self.changed.emit)

        self.add_prompt_button = QPushButton("Add")
        self.add_prompt_button.clicked.connect(lambda: self.prompts_editor.add_prompt(""))
        self.add_prompt_button.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.add_prompt_button.setEnabled(self.prompts_editor.can_add_prompt())
        self.prompts_editor.canAddChanged.connect(self.add_prompt_button.setEnabled)

        layout.addWidget(self.prompts_editor)
        layout.addWidget(self.add_prompt_button)

    def to_check_in_prompts(self) -> list[str]:
        return self.prompts_editor.get_prompts()
