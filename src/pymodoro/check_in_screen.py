from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from pymodoro.check_in_screen_widgets import FocusRatingWidget, PromptCard

STYLESHEET = """
QLabel {
    font-size: 32px;
    font-weight: 600;
}
QPlainTextEdit {
    font-size: 18px;
    padding: 12px;
    min-height: 140px;
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
    submitted = QtCore.Signal(str, object)

    def __init__(
        self,
        check_in_prompt: str,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._answered = False
        self.setWindowFlags(
            QtCore.Qt.WindowType.Window
            | QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.WindowStaysOnTopHint
        )
        self.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating, False)

        self._prompt_card = PromptCard(check_in_prompt, self)
        self._focus_rating_widget = FocusRatingWidget(self)
        self._submit_button = QtWidgets.QPushButton("Submit", self)
        self._submit_button.clicked.connect(self._on_submit)
        self._install_submit_shortcuts()

        self.setLayout(self._build_layout())
        self.setStyleSheet(STYLESHEET)

        self.set_check_in_prompt = self._prompt_card.set_check_in_prompt

    def _install_submit_shortcuts(self) -> None:
        for shortcut in SUBMIT_SHORTCUTS:
            QtGui.QShortcut(shortcut, self).activated.connect(self._on_submit)

    def _build_layout(self) -> QtWidgets.QVBoxLayout:
        layout = QtWidgets.QVBoxLayout()
        layout.addStretch(2)
        layout.addWidget(self._prompt_card)
        layout.addSpacing(16)
        layout.addWidget(self._focus_rating_widget)
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
        self._answered = False
        self._focus_rating_widget.set_rating(None)
        self._prompt_card.clear()
        self.showFullScreen()
        self.raise_()
        self.activateWindow()
        self._prompt_card.focus_input()

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        input_widget = self._prompt_card.focus_input_widget()
        if self.focusWidget() is not input_widget:
            self._prompt_card.focus_input()
            QtWidgets.QApplication.sendEvent(input_widget, event)
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if self._answered:
            super().closeEvent(event)
        else:
            event.ignore()

    def _on_submit(self) -> None:
        prompt_answer = self._prompt_card.answer()
        focus_rating = self._focus_rating_widget.rating
        if prompt_answer == "":
            return
        self._answered = True
        self.submitted.emit(prompt_answer, focus_rating)
