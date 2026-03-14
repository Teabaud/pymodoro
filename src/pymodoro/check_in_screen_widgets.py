from __future__ import annotations

from PySide6 import QtCore, QtGui
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

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


type FocusRating = int | None
type ExerciseResult = tuple[str, int] | None


class FocusRatingWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rating: FocusRating = None

        label = QLabel("Focus (1–5)", self)

        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(8)

        self._buttons: list[QPushButton] = []
        for value in range(1, 6):
            button = QPushButton(str(value), self)
            button.setCheckable(True)
            button.setAutoDefault(False)
            button.setDefault(False)
            if value == 1:
                button.setToolTip("Very distracted")
            elif value == 5:
                button.setToolTip("Deep focus")
            button.clicked.connect(self._make_button_handler(value, button))
            self._buttons.append(button)
            buttons_layout.addWidget(button)

        layout = QHBoxLayout(self)
        layout.addStretch(1)
        layout.addWidget(label)
        layout.addSpacing(12)
        layout.addLayout(buttons_layout)
        layout.addStretch(1)
        self.setLayout(layout)

    def _make_button_handler(self, value: int, button: QPushButton):
        def handler() -> None:
            if self._rating == value:
                # Clicking the same value again clears the rating (skip)
                self._rating = None
                button.setChecked(False)
            else:
                self._rating = value
                for btn in self._buttons:
                    btn.setChecked(btn is button)

        return handler

    @property
    def rating(self) -> FocusRating:
        return self._rating

    def set_rating(self, rating: FocusRating) -> None:
        self._rating = rating
        for index, button in enumerate[QPushButton](self._buttons, start=1):
            button.setChecked(index == rating)


class ExerciseWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        label = QLabel("Exercise", self)

        self._rep_count_input = QSpinBox(self)
        self._rep_count_input.setRange(0, 999)
        self._rep_count_input.setValue(0)
        self._rep_count_input.setToolTip("How many reps you did")

        self._exercise_name_input = QLineEdit(self)
        self._exercise_name_input.setPlaceholderText("name of the exercise")

        layout = QHBoxLayout(self)
        layout.addStretch(1)
        layout.addWidget(label)
        layout.addSpacing(12)
        layout.addWidget(self._rep_count_input, 1)
        layout.addSpacing(8)
        layout.addWidget(self._exercise_name_input, 3)
        layout.addStretch(1)
        self.setLayout(layout)

    @property
    def rep_count(self) -> int:
        return self._rep_count_input.value()

    @property
    def exercise_name(self) -> str:
        return self._exercise_name_input.text().strip()

    @property
    def exercise_result(self) -> ExerciseResult:
        if self.exercise_name != "" and self.rep_count > 0:
            return self.exercise_name, self.rep_count

    def clear(self) -> None:
        self._rep_count_input.setValue(0)
        self._exercise_name_input.clear()
