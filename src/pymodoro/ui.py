from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

STYLESHEET = """
QDialog {
    background-color: #101113;
    color: #f0f0f0;
    font-family: "Inter", "Segoe UI", sans-serif;
}
QLabel {
    font-size: 32px;
    font-weight: 600;
}
QPlainTextEdit {
    font-size: 18px;
    padding: 12px;
    border: 1px solid #2d2f33;
    border-radius: 10px;
    background-color: #181a1d;
    color: #f0f0f0;
    min-height: 140px;
}
QPushButton {
    font-size: 18px;
    padding: 10px 26px;
    border-radius: 10px;
    background-color: #2b4fff;
    color: #ffffff;
}
QPushButton:hover {
    background-color: #4a6bff;
}
"""

SUBMIT_SHORTCUTS = [
    QtGui.QKeySequence("Ctrl+Return"),
    QtGui.QKeySequence("Ctrl+Enter"),
]


class PromptMessage(QtWidgets.QLabel):
    def __init__(self, message: str, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(message, parent)
        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.setWordWrap(True)


class PromptInput(QtWidgets.QPlainTextEdit):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setPlaceholderText("Type your answer here...")
        self.setVisible(True)


class PromptSubmitButton(QtWidgets.QPushButton):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__("Submit", parent)


class PromptSnoozeButton(QtWidgets.QPushButton):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__("Snooze", parent)


class FullScreenPrompt(QtWidgets.QDialog):
    submitted = QtCore.Signal(str)
    snoozed = QtCore.Signal()

    def __init__(
        self,
        message: str,
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

        self._message_label = PromptMessage(message, self)
        self._input = PromptInput(self)
        self._submit_button = PromptSubmitButton(self)
        self._snooze_button = PromptSnoozeButton(self)
        self._submit_button.clicked.connect(self._on_submit)
        self._snooze_button.clicked.connect(self._on_snooze)
        self._install_submit_shortcuts()

        self.setLayout(self._build_layout())
        self.setStyleSheet(STYLESHEET)

    def _install_submit_shortcuts(self) -> None:
        for shortcut in SUBMIT_SHORTCUTS:
            QtGui.QShortcut(shortcut, self).activated.connect(self._on_submit)

    def _build_layout(self) -> QtWidgets.QVBoxLayout:
        layout = QtWidgets.QVBoxLayout()
        layout.addStretch(2)
        layout.addWidget(self._message_label)
        layout.addSpacing(24)
        layout.addWidget(self._input)
        layout.addSpacing(24)
        buttons_layout = QtWidgets.QHBoxLayout()
        buttons_layout.addStretch(1)
        buttons_layout.addWidget(self._submit_button)
        buttons_layout.addWidget(self._snooze_button)
        buttons_layout.addStretch(1)
        layout.addLayout(buttons_layout)
        layout.addStretch(3)
        return layout

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        super().showEvent(event)
        self._answered = False
        self._input.setPlainText("")
        self.showFullScreen()
        self.raise_()
        self.activateWindow()
        self._input.setFocus()

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if self.focusWidget() is not self._input:
            self._input.setFocus(QtCore.Qt.FocusReason.ShortcutFocusReason)
            QtWidgets.QApplication.sendEvent(self._input, event)
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if self._answered:
            super().closeEvent(event)
        else:
            event.ignore()

    def _on_submit(self) -> None:
        text = self._input.toPlainText().strip()
        if text == "":
            return
        self._answered = True
        self.submitted.emit(text)

    def _on_snooze(self) -> None:
        self._answered = True
        self.snoozed.emit()
