from datetime import datetime, timezone

from PySide6 import QtCore, QtGui, QtWidgets

from pymodoro.check_in_screen_widgets import (
    ActivityWidget,
    ExerciseWidget,
    FocusRatingWidget,
    LeverageWidget,
    MetricsGrid,
    ProjectWidget,
    PromptCard,
)
from pymodoro.metrics_io import CheckInRecord
from pymodoro.settings import AppSettings
from pymodoro.tray import get_app_icon

STYLESHEET = """
#PromptLabel {
    font-size: 32px;
    font-weight: 600;
}
QPlainTextEdit {
    font-size: 18px;
    padding: 12px;
    min-height: 140px;
}
MetricsGrid QLabel {
    font-size: 18px;
    font-weight: 600;
}
QLineEdit, QSpinBox, QComboBox {
    font-size: 18px;
    padding: 8px;
}
QPushButton {
    font-size: 18px;
    padding: 10px 26px;
}
"""


SUBMIT_SHORTCUTS = [
    QtGui.QKeySequence("Ctrl+Return"),
    QtGui.QKeySequence("Ctrl+Enter"),
]


class CheckInScreen(QtWidgets.QDialog):
    submitted = QtCore.Signal(object)

    def __init__(
        self,
        check_in_prompt: str,
        settings: AppSettings,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            QtCore.Qt.WindowType.Window
            | QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.WindowStaysOnTopHint
        )
        self.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
        self.setWindowIcon(get_app_icon())

        self._prompt_card = PromptCard(
            check_in_prompt, prompts=settings.check_in.prompts, parent=self
        )
        self._project_widget = ProjectWidget(settings.check_in.projects, self)
        self._activity_widget = ActivityWidget(settings.check_in.activities, self)
        self._leverage_widget = LeverageWidget(self)
        self._focus_rating_widget = FocusRatingWidget(self)
        self._exercise_widget = ExerciseWidget(settings.check_in.exercises, self)
        self._submit_button = QtWidgets.QPushButton("Submit", self)
        self._submit_button.clicked.connect(self._on_submit)
        self._install_submit_shortcuts()

        self.setLayout(self._build_layout())
        self.setStyleSheet(STYLESHEET)

    def _install_submit_shortcuts(self) -> None:
        for shortcut in SUBMIT_SHORTCUTS:
            QtGui.QShortcut(shortcut, self).activated.connect(self._on_submit)

    def _build_layout(self) -> QtWidgets.QVBoxLayout:
        layout = QtWidgets.QVBoxLayout()
        layout.addStretch(2)
        layout.addWidget(self._prompt_card)
        layout.addSpacing(16)

        metrics_grid = MetricsGrid(self)
        metrics_grid.add_row("Project", self._project_widget)
        metrics_grid.add_row("Activity", self._activity_widget)
        metrics_grid.add_row("Leverage", self._leverage_widget)
        metrics_grid.add_row("Focus", self._focus_rating_widget)
        metrics_grid.add_row("Exercise", self._exercise_widget)

        centered_layout = QtWidgets.QHBoxLayout()
        centered_layout.addStretch(1)
        centered_layout.addWidget(metrics_grid, 2)
        centered_layout.addStretch(1)

        layout.addLayout(centered_layout, 1)
        layout.addSpacing(24)
        buttons_layout = QtWidgets.QHBoxLayout()
        buttons_layout.addStretch(1)
        buttons_layout.addWidget(self._submit_button)
        buttons_layout.addStretch(1)
        layout.addLayout(buttons_layout)
        layout.addStretch(3)
        return layout

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        super().showEvent(event)
        self.showFullScreen()
        self.raise_()
        self.activateWindow()
        self._prompt_card.focus_input()

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        focused_widget = self.focusWidget()
        input_widget = self._prompt_card.focus_input_widget()
        if focused_widget in (None, self):
            self._prompt_card.focus_input()
            QtWidgets.QApplication.sendEvent(input_widget, event)
        else:
            super().keyPressEvent(event)

    def _on_submit(self) -> None:
        if self._prompt_card.answer == "":
            return
        record = CheckInRecord(
            timestamp=datetime.now(timezone.utc),
            prompt=self._prompt_card.prompt,
            answer=self._prompt_card.answer,
            focus_rating=self._focus_rating_widget.rating,
            exercise_name=self._exercise_widget.exercise_name,
            exercise_rep_count=self._exercise_widget.rep_count,
            project=self._project_widget.project,
            activity=self._activity_widget.activity,
            leverage=self._leverage_widget.leverage,
        )
        self.submitted.emit(record)
