from PySide6 import QtCore, QtWidgets

from pymodoro.settings import AppSettings


class Content(QtWidgets.QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        placeholder = QtWidgets.QLabel("Charts, tables and metrics go here")
        placeholder.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet("color: palette(window-text); font-size: 14px;")
        layout.addWidget(placeholder)


class Dashboard(QtWidgets.QWidget):
    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.addWidget(Content(self))
