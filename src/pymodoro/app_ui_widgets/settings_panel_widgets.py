from __future__ import annotations

from pymodoro.settings import TimersSettings

# isort: split
from PySide6 import QtCore
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

DELETE_CHAR = "\u00d7"
DURATION_INPUT_MAX_WIDTH = 120


class ListEditorRow(QWidget):
    deleteClicked = QtCore.Signal()

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        row_layout = QHBoxLayout(self)
        row_layout.setContentsMargins(4, 2, 4, 2)
        row_layout.setSpacing(6)

        self._label = QLabel(text)
        self._label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        row_layout.addWidget(self._label, 1)

        delete_btn = QPushButton(DELETE_CHAR)
        delete_btn.setFixedSize(24, 24)
        delete_btn.clicked.connect(self.deleteClicked.emit)
        row_layout.addWidget(delete_btn)

    def text(self) -> str:
        return self._label.text()


class ListEditor(QWidget):
    changed = QtCore.Signal()

    def __init__(
        self,
        placeholder: str = "Add item and press Enter...",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._items_layout = QVBoxLayout()
        self._items_layout.setContentsMargins(0, 0, 0, 0)
        self._items_layout.setSpacing(2)
        layout.addLayout(self._items_layout)

        self._input = QLineEdit()
        self._input.setPlaceholderText(placeholder)
        self._input.returnPressed.connect(self._on_return_pressed)
        layout.addWidget(self._input)

    def set_items(self, items: list[str]) -> None:
        while self._items_layout.count():
            item = self._items_layout.takeAt(0)
            if item and (widget := item.widget()):
                widget.deleteLater()
        for text in items:
            if text.strip():
                self._add_row(text)

    def get_items(self) -> list[str]:
        items: list[str] = []
        for i in range(self._items_layout.count()):
            if row := self._get_row(i):
                items.append(row.text())
        return items

    def _get_row(self, index: int) -> ListEditorRow | None:
        child = self._items_layout.itemAt(index)
        if not child:
            return None
        row = child.widget()
        if isinstance(row, ListEditorRow):
            return row

    def _on_return_pressed(self) -> None:
        text = self._input.text().strip()
        if not text:
            return
        self._add_row(text)
        self._input.clear()
        self.changed.emit()

    def _add_row(self, text: str) -> None:
        row = ListEditorRow(text)
        row.deleteClicked.connect(lambda: self._remove_row(row))
        self._items_layout.addWidget(row)

    def _remove_row(self, row: ListEditorRow) -> None:
        self._items_layout.removeWidget(row)
        row.deleteLater()
        self.changed.emit()


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
        default_seconds: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self._minutes_input = QSpinBox(self)
        self._minutes_input.setMinimum(1)
        self._minutes_input.setSuffix(" min")
        self._minutes_input.setValue(max(1, round(default_seconds / 60)))
        form.addRow("Duration:", self._minutes_input)
        layout.addLayout(form)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def value(self) -> int:
        return self._minutes_input.value() * 60


class DurationInputWidget(QSpinBox):
    def __init__(self, value: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setRange(1, 9999)
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


class ListSectionWidget(QGroupBox):
    changed = QtCore.Signal()

    def __init__(
        self,
        title: str,
        items: list[str],
        placeholder: str = "Add item and press Enter...",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(title, parent)
        layout = QVBoxLayout(self)

        self.list_editor = ListEditor(placeholder=placeholder)
        self.list_editor.set_items(items)
        self.list_editor.changed.connect(self.changed.emit)
        layout.addWidget(self.list_editor)


class NotificationsSectionWidget(QGroupBox):
    changed = QtCore.Signal()

    def __init__(
        self, notification_sound_enabled: bool, parent: QWidget | None = None
    ) -> None:
        super().__init__("Notifications", parent)
        layout = QVBoxLayout(self)
        self._sound_checkbox = QCheckBox("Enable notification sound")
        self._sound_checkbox.setChecked(notification_sound_enabled)
        self._sound_checkbox.checkStateChanged.connect(lambda _: self.changed.emit())
        layout.addWidget(self._sound_checkbox)

    def is_sound_enabled(self) -> bool:
        return self._sound_checkbox.isChecked()

    def set_sound_enabled(self, enabled: bool) -> None:
        self._sound_checkbox.setChecked(enabled)
