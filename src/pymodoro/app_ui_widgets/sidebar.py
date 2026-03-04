from PySide6 import QtCore, QtWidgets

from pymodoro.tray import get_app_icon


class Logo(QtWidgets.QToolButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        icon = get_app_icon()
        self.setIcon(icon)
        self.setIconSize(QtCore.QSize(70, 70))
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("Logo { background: transparent; border: none; }")


class NavItem(QtWidgets.QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        for label in [
            "Dashboard",
            "Settings",
        ]:
            self.addItem(label)

        self.setStyleSheet("""
            QListWidget {
                border: none;
                outline: 0;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 10px 16px;
                border-radius: 6px;
            }
            QListWidget::item:hover {
                background-color: palette(midlight);
            }
            QListWidget::item:selected {
                background-color: palette(highlight);
                color: palette(highlighted-text);
            }
        """)


class Separator(QtWidgets.QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        self.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)


class Sidebar(QtWidgets.QFrame):
    navigate = QtCore.Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(150)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        self._logo = Logo(self)
        self._logo.clicked.connect(self._go_to_dashboard)

        self._nav_item = NavItem(self)
        self._nav_item.itemClicked.connect(self._on_nav_item_clicked)

        layout.addWidget(self._logo, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(Separator(self))
        layout.addWidget(self._nav_item)

        self._go_to_dashboard()

    def _on_nav_item_clicked(self, item: QtWidgets.QListWidgetItem) -> None:
        self.navigate.emit(item.text().lower())

    def _go_to_dashboard(self) -> None:
        self._nav_item.setCurrentItem(self._nav_item.item(0))
        self.navigate.emit("dashboard")
