from __future__ import annotations

from PySide6 import QtCore
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class PromptCard(QWidget):
    """Message label + text input in one block."""

    def __init__(
        self,
        prompt: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._check_in_prompt = QLabel(prompt, self)
        self._check_in_prompt.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._check_in_prompt.setWordWrap(True)

        self._input = QPlainTextEdit(self)
        self._input.setPlaceholderText("Type your answer here...")
        self._input.setVisible(True)

        layout = QVBoxLayout(self)
        layout.addWidget(self._check_in_prompt)
        layout.addSpacing(24)
        layout.addWidget(self._input)
        self.setLayout(layout)

    def set_check_in_prompt(self, text: str) -> None:
        self._check_in_prompt.setText(text)

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
