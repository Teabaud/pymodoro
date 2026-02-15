from __future__ import annotations

from pymodoro.session import SessionPhase, SessionPhaseManager
from pymodoro.time_utils import TimeFormatter

# isort: split
from PySide6 import QtCore, QtGui, QtWidgets

TRAY_ICON_LABELS = {
    SessionPhase.WORK: "W",
    SessionPhase.BREAK: "☕",
    SessionPhase.PAUSE: "⏸",
}


class TrayController(QtCore.QObject):
    openAppRequested = QtCore.Signal()
    pauseUntilRequested = QtCore.Signal(object)
    resumeRequested = QtCore.Signal()
    quitRequested = QtCore.Signal()

    def __init__(
        self,
        app: QtWidgets.QApplication,
        session_phase_manager: SessionPhaseManager,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._session_phase_manager = session_phase_manager

        self._tray = QtWidgets.QSystemTrayIcon(app)
        self._menu = QtWidgets.QMenu()
        self._action_open_app = self._menu.addAction("Open App")
        self._action_open_app.triggered.connect(self.openAppRequested.emit)
        self._action_pause = self._menu.addAction("Pause until...")
        self._action_pause.triggered.connect(self._on_pause_action)
        self._action_quit = self._menu.addAction("Quit")
        self._action_quit.triggered.connect(self.quitRequested.emit)
        self._tray.setContextMenu(self._menu)
        self._tray.activated.connect(self._on_tray_activated)

        self._update_timer = QtCore.QTimer(self)
        self._update_timer.setInterval(1000)
        self._update_timer.timeout.connect(self.refresh)

    def show(self) -> None:
        self._tray.show()
        self._update_timer.start()
        self.refresh()

    def _render_icon(self, label: str) -> QtGui.QPixmap:
        size = 124
        pixmap = QtGui.QPixmap(size, size)
        pixmap.fill(QtCore.Qt.GlobalColor.transparent)
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing)
        palette = QtWidgets.QApplication.palette()
        if self._session_phase_manager.session_phase == SessionPhase.PAUSE:
            color = QtGui.QColor("#b53131")
        else:
            color = palette.color(QtGui.QPalette.ColorRole.WindowText)
        painter.setPen(color)
        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        font = QtGui.QFont("Sans Serif", int(size * 0.7), QtGui.QFont.Weight.ExtraBold)
        painter.setFont(font)
        painter.drawText(
            QtCore.QRect(0, 0, size, size),
            QtCore.Qt.AlignmentFlag.AlignCenter,
            label,
        )

        painter.end()
        return pixmap

    def refresh(self) -> None:
        phase = self._session_phase_manager.session_phase
        remaining_ms = self._session_phase_manager.remaining_ms()
        if phase == SessionPhase.PAUSE:
            end_date_str = TimeFormatter.end_datetime_str(remaining_ms)
            self._tray.setToolTip(f"Pause until {end_date_str}")
            self._action_pause.setText("Resume")
        else:
            countdown_label = TimeFormatter.countdown_str(remaining_ms)
            self._tray.setToolTip(f"{phase.value} {countdown_label}")
            self._action_pause.setText("Pause until...")

        label = TRAY_ICON_LABELS.get(phase, "?")
        pixmap = self._render_icon(label)
        self._tray.setIcon(QtGui.QIcon(pixmap))

    def _prompt_pause_until(self) -> QtCore.QDateTime | None:
        default_datetime = QtCore.QDateTime.currentDateTime().addSecs(3600)
        dialog = PauseUntilDialog(default_datetime)
        accepted_code = getattr(
            getattr(QtWidgets.QDialog, "DialogCode", None), "Accepted", 1
        )
        if dialog.exec() == accepted_code:
            return dialog.selected_datetime()
        return None

    def _on_pause_action(self) -> None:
        if self._session_phase_manager.session_phase == SessionPhase.PAUSE:
            self.resumeRequested.emit()
            return

        pause_datetime = self._prompt_pause_until()
        if pause_datetime is not None:
            self.pauseUntilRequested.emit(pause_datetime)

    def _on_tray_activated(
        self, reason: QtWidgets.QSystemTrayIcon.ActivationReason
    ) -> None:
        if reason == QtWidgets.QSystemTrayIcon.ActivationReason.Trigger:
            self.openAppRequested.emit()


class PauseUntilDialog(QtWidgets.QDialog):
    def __init__(
        self,
        default_datetime: QtCore.QDateTime,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Pause until...")
        self.setModal(True)
        self._time_picker = QtWidgets.QDateTimeEdit(default_datetime, self)
        self._time_picker.setCalendarPopup(True)
        self._time_picker.setDisplayFormat("yyyy-MM-dd HH:mm")

        form_layout = QtWidgets.QFormLayout()
        form_layout.addRow("Resume at:", self._time_picker)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(form_layout)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def selected_datetime(self) -> QtCore.QDateTime:
        return self._time_picker.dateTime()
