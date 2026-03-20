from typing import cast, get_args

from PySide6 import QtCore, QtGui
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pymodoro.metrics_io import ExerciseResult, FocusRating, Leverage

_OVERLAY_STYLESHEET = """
    #PromptOverlay QPushButton {
        font-size: 20px;
        font-weight: 600;
        padding: 18px 32px;
        background: palette(button);
        border: 1px solid palette(mid);
        border-radius: 12px;
        color: palette(button-text);
        text-align: center;
    }
    #PromptOverlay QPushButton:hover {
        background: palette(midlight);
        border-color: palette(dark);
    }
    #PromptOverlay QPushButton:checked {
        background: palette(highlight);
        border-color: palette(highlight);
        color: palette(highlighted-text);
    }
"""


class _PromptOverlay(QWidget):
    prompt_selected = QtCore.Signal(str)

    def __init__(self, prompts: list[str], current: str, parent: QWidget) -> None:
        super().__init__(parent)
        self._prompts = prompts
        self._highlighted = prompts.index(current) if current in prompts else 0
        self._buttons: list[QPushButton] = []

        self.setObjectName("PromptOverlay")
        self.setStyleSheet(_OVERLAY_STYLESHEET)
        self.setGeometry(parent.rect())
        self._build_ui()
        self.show()
        self.raise_()
        self.setFocus()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter(self)
        bg = self.palette().color(QtGui.QPalette.ColorRole.Window)
        bg.setAlpha(220)
        painter.fillRect(self.rect(), bg)

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        outer.setContentsMargins(200, 60, 200, 60)
        outer.setSpacing(0)

        for i, prompt in enumerate(self._prompts):
            btn = QPushButton(prompt, self)
            btn.setCheckable(True)
            btn.setAutoDefault(False)
            btn.setDefault(False)
            btn.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
            )
            btn.clicked.connect(self._make_click_handler(i))
            self._buttons.append(btn)
            outer.addWidget(btn)
            outer.addSpacing(10)

        self._update_highlight()

    def _make_click_handler(self, index: int):
        def handler() -> None:
            self.prompt_selected.emit(self._prompts[index])
            self.close()

        return handler

    def _update_highlight(self) -> None:
        for i, btn in enumerate(self._buttons):
            btn.setChecked(i == self._highlighted)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        key = event.key()
        if key == QtCore.Qt.Key.Key_Up:
            self._highlighted = (self._highlighted - 1) % len(self._prompts)
            self._update_highlight()
        elif key == QtCore.Qt.Key.Key_Down:
            self._highlighted = (self._highlighted + 1) % len(self._prompts)
            self._update_highlight()
        elif key in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter):
            self.prompt_selected.emit(self._prompts[self._highlighted])
            self.close()
        elif key == QtCore.Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if self.childAt(event.position().toPoint()) is None:
            self.close()
        else:
            super().mousePressEvent(event)


class _ClickableLabel(QLabel):
    clicked = QtCore.Signal()

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class PromptCard(QWidget):
    """Message label + text input in one block."""

    def __init__(
        self,
        prompt: str,
        prompts: list[str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._prompts = prompts or []

        self._check_in_prompt = _ClickableLabel(prompt, self)
        self._check_in_prompt.setObjectName("PromptLabel")
        self._check_in_prompt.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._check_in_prompt.setWordWrap(True)
        self._check_in_prompt.clicked.connect(self._on_prompt_clicked)

        self._input = QPlainTextEdit(self)
        self._input.setPlaceholderText("Click on the question to select another one")
        self._input.setTabChangesFocus(True)
        self._input.setVisible(True)

        layout = QVBoxLayout(self)
        layout.addWidget(self._check_in_prompt)
        layout.addSpacing(24)
        layout.addWidget(self._input)
        self.setLayout(layout)

    def _on_prompt_clicked(self) -> None:
        if not self._prompts:
            return
        overlay = _PromptOverlay(
            self._prompts, self._check_in_prompt.text(), self.window()
        )
        overlay.prompt_selected.connect(self._check_in_prompt.setText)

    def set_check_in_prompt(self, text: str) -> None:
        self._check_in_prompt.setText(text)

    @property
    def prompt(self) -> str:
        return self._check_in_prompt.text()

    @property
    def answer(self) -> str:
        return self._input.toPlainText().strip()

    def clear(self) -> None:
        self._input.setPlainText("")

    def focus_input(self) -> None:
        self._input.setFocus()

    def focus_input_widget(self) -> QPlainTextEdit:
        """Widget that receives key events when the card is the logical focus target."""
        return self._input


class _ExclusiveToggleRow(QWidget):
    """A row of exclusive toggle buttons. Click again to deselect."""

    def __init__(
        self,
        options: list[str],
        tooltips: dict[str, str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._selected: str | None = None
        self._buttons: list[QPushButton] = []

        layout = QHBoxLayout(self)
        layout.setSpacing(8)

        for option in options:
            btn = QPushButton(option.capitalize(), self)
            btn.setCheckable(True)
            btn.setAutoDefault(False)
            btn.setDefault(False)
            if tooltips and option in tooltips:
                btn.setToolTip(tooltips[option])
            btn.clicked.connect(self._make_handler(option, btn))
            btn.installEventFilter(self)
            self._buttons.append(btn)
            layout.addWidget(btn)

        layout.addStretch(1)
        self._update_tab_focus()

    def _update_tab_focus(self) -> None:
        """Make only the checked (or first) button tabbable."""
        target = None
        for btn in self._buttons:
            if btn.isChecked():
                target = btn
                break
        if target is None and self._buttons:
            target = self._buttons[0]
        for btn in self._buttons:
            btn.setFocusPolicy(
                QtCore.Qt.FocusPolicy.TabFocus
                if btn is target
                else QtCore.Qt.FocusPolicy.ClickFocus
            )

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if event.type() == QtCore.QEvent.Type.KeyPress:
            key = cast(QtGui.QKeyEvent, event).key()
            buttons = self._buttons
            tab_focus_reason = QtCore.Qt.FocusReason.TabFocusReason
            # Left/Right arrows: move focus between buttons
            if key in (QtCore.Qt.Key.Key_Left, QtCore.Qt.Key.Key_Right):
                try:
                    idx = buttons.index(cast(QPushButton, obj))
                except ValueError:
                    return False
                delta = -1 if key == QtCore.Qt.Key.Key_Left else 1
                buttons[(idx + delta) % len(buttons)].setFocus(tab_focus_reason)
                return True
            # Up/Down arrows: leave the row entirely
            if key in (QtCore.Qt.Key.Key_Up, QtCore.Qt.Key.Key_Down):
                for btn in buttons:
                    btn.setFocusPolicy(QtCore.Qt.FocusPolicy.ClickFocus)
                cast(QWidget, obj).focusNextPrevChild(key == QtCore.Qt.Key.Key_Down)
                self._update_tab_focus()
                return True
            # Number keys: select Nth button
            if QtCore.Qt.Key.Key_1 <= key <= QtCore.Qt.Key.Key_9:
                n = key - QtCore.Qt.Key.Key_1
                if n < len(buttons):
                    buttons[n].click()
                    buttons[n].setFocus(tab_focus_reason)
                return True
        return super().eventFilter(obj, event)

    def _make_handler(self, value: str, button: QPushButton):
        def handler() -> None:
            if self._selected == value:
                self._selected = None
                button.setChecked(False)
            else:
                self._selected = value
                for btn in self._buttons:
                    btn.setChecked(btn is button)
            self._update_tab_focus()

        return handler

    @property
    def selected(self) -> str | None:
        return self._selected

    def clear(self) -> None:
        self._selected = None
        for btn in self._buttons:
            btn.setChecked(False)
        self._update_tab_focus()


class FocusRatingWidget(_ExclusiveToggleRow):
    """Focus rating selector with 1-5 buttons."""

    _OPTIONS = [str(v) for v in range(1, 6)]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            self._OPTIONS,
            tooltips={"1": "Very distracted", "5": "Deep focus"},
            parent=parent,
        )

    @property
    def rating(self) -> FocusRating:
        return int(self.selected) if self.selected is not None else None


class ExerciseWidget(QWidget):
    def __init__(
        self,
        exercises: list[str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._rep_count_input = QSpinBox(self)
        self._rep_count_input.setRange(0, 999)
        self._rep_count_input.setValue(0)
        self._rep_count_input.setToolTip("How many reps you did")

        self._combo = QComboBox(self)
        self._combo.setEditable(True)
        self._combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._combo.addItems(exercises)
        self._combo.setCurrentIndex(-1)
        self._combo.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        if (line_edit := self._combo.lineEdit()) is not None:
            line_edit.setPlaceholderText("Select an exercise...")

        layout = QHBoxLayout(self)
        layout.addWidget(self._rep_count_input, 1)
        layout.addSpacing(8)
        layout.addWidget(self._combo, 3)

    @property
    def rep_count(self) -> int:
        return self._rep_count_input.value()

    @property
    def exercise_name(self) -> str:
        return self._combo.currentText().strip()

    @property
    def exercise_result(self) -> ExerciseResult:
        if self.exercise_name != "" and self.rep_count > 0:
            return self.exercise_name, self.rep_count

    def clear(self) -> None:
        self._rep_count_input.setValue(0)
        self._combo.setCurrentIndex(-1)


class ProjectWidget(QWidget):
    """Project selector with an editable combo box."""

    def __init__(
        self,
        projects: list[str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        layout = QHBoxLayout(self)

        self._combo = QComboBox(self)
        self._combo.setEditable(True)
        self._combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._combo.addItems(projects)
        self._combo.setCurrentIndex(-1)
        self._combo.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        if (line_edit := self._combo.lineEdit()) is not None:
            line_edit.setPlaceholderText("Select a project...")

        layout.addWidget(self._combo)

    @property
    def project(self) -> str | None:
        text = self._combo.currentText().strip()
        return text or None

    def clear(self) -> None:
        self._combo.setCurrentIndex(-1)


class ActivityWidget(_ExclusiveToggleRow):
    """Activity selector as exclusive toggle buttons."""

    def __init__(
        self,
        activities: list[str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(activities, parent=parent)

    @property
    def activity(self) -> str | None:
        return self.selected


class LeverageWidget(_ExclusiveToggleRow):
    """Leverage selector as exclusive toggle buttons."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(list[str](get_args(Leverage)), parent=parent)

    @property
    def leverage(self) -> Leverage | None:
        return cast(Leverage | None, self.selected)


class MetricsGrid(QWidget):
    """Two-column grid (label | widget)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._grid = QGridLayout(self)
        self._grid.setColumnStretch(0, 0)
        self._grid.setColumnStretch(1, 1)
        self._rows: list[QWidget] = []

    def add_row(self, label_text: str, widget: QWidget) -> None:
        row = len(self._rows)
        label = QLabel(label_text, self)
        self._grid.addWidget(
            label,
            row,
            0,
            QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter,
        )
        self._grid.addWidget(widget, row, 1)
        self._rows.append(widget)
