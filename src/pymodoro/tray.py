from __future__ import annotations

from pathlib import Path

from pymodoro.session import SessionPhase, SessionPhaseManager

# isort: split
from PySide6 import QtCore, QtGui, QtWidgets

_ICON_DIR = Path(__file__).parent / "icons"
_PHASE_ICON_FILES = {
    SessionPhase.WORK: _ICON_DIR / "icon-work.svg",
    SessionPhase.BREAK: _ICON_DIR / "icon-break.svg",
    SessionPhase.PAUSE: _ICON_DIR / "icon-paused.svg",
}


class TrayController(QtCore.QObject):
    openAppRequested = QtCore.Signal()
    checkInRequested = QtCore.Signal()
    pauseUntilRequested = QtCore.Signal(object)
    snoozeRequested = QtCore.Signal()
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
        self._action_check_in = self._menu.addAction("Check in")
        self._action_check_in.triggered.connect(self.checkInRequested.emit)
        self._action_pause = self._menu.addAction("Pause until...")
        self._action_pause.triggered.connect(self._on_pause_action)
        self._action_quit = self._menu.addAction("Quit")
        self._action_quit.triggered.connect(self.quitRequested.emit)
        self._tray.setContextMenu(self._menu)
        self._tray.activated.connect(self._on_tray_activated)

        self._update_timer = QtCore.QTimer(self)
        self._update_timer.setInterval(1000)
        self._update_timer.timeout.connect(self.refresh)
        self._current_icon_phase: SessionPhase | None = None
        self._phase_warning_toast: PhaseWarningToast | None = None

    def show(self) -> None:
        self._tray.show()
        self._update_timer.start()
        self.refresh()

    def _render_phase_icon(self, phase: SessionPhase) -> None:
        if phase == self._current_icon_phase:
            return
        svg_path = _PHASE_ICON_FILES.get(phase, _PHASE_ICON_FILES[SessionPhase.WORK])
        icon = QtGui.QIcon(str(svg_path))
        self._tray.setIcon(icon)
        self._current_icon_phase = phase

    def refresh(self) -> None:
        phase = self._session_phase_manager.session_phase
        if phase == SessionPhase.PAUSE:
            tooltip_str = f"Pause until {self._session_phase_manager.ends_at_str()}"
            self._action_pause.setText("Resume")
        else:
            tooltip_str = (
                f"{phase.value} - {self._session_phase_manager.time_left_str()}"
            )
            self._action_pause.setText("Pause until...")

        self._tray.setToolTip(tooltip_str)
        self._render_phase_icon(phase)

    def show_phase_warning_toast(self, text: str) -> None:
        self._ensure_phase_warning_toast().show_toast(text=text)

    def hide_phase_warning_toast(self) -> None:
        if self._phase_warning_toast is not None:
            self._phase_warning_toast.hide_toast()

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

    def _ensure_phase_warning_toast(self) -> PhaseWarningToast:
        if self._phase_warning_toast is None:
            self._phase_warning_toast = PhaseWarningToast(self)
            self._phase_warning_toast.snoozeRequested.connect(self.snoozeRequested.emit)
        return self._phase_warning_toast


class PhaseWarningToast(QtWidgets.QFrame):
    snoozeRequested = QtCore.Signal()

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(None)
        self.setObjectName("PhaseWarningToast")
        self.setWindowFlags(
            QtCore.Qt.WindowType.Tool
            | QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        self.setFrameShadow(QtWidgets.QFrame.Shadow.Raised)

        self._text_label = QtWidgets.QLabel(self)
        self._text_label.setWordWrap(False)
        text_font = self._text_label.font()
        text_font.setBold(True)
        text_font.setPointSize(text_font.pointSize() + 1)
        self._text_label.setFont(text_font)
        self._snooze_button = QtWidgets.QPushButton("Snooze", self)
        self._snooze_button.clicked.connect(self._on_snooze_clicked)

        content_layout = QtWidgets.QHBoxLayout()
        content_layout.setContentsMargins(14, 12, 14, 12)
        content_layout.setSpacing(14)
        content_layout.addWidget(
            self._text_label, 1, QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        content_layout.addWidget(
            self._snooze_button, 0, QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        self.setLayout(content_layout)

    def show_toast(self, text: str) -> None:
        self._text_label.setText(text)
        self.adjustSize()
        self._position_bottom_right()
        self.show()
        self.raise_()

    def hide_toast(self) -> None:
        self.hide()

    def _on_snooze_clicked(self) -> None:
        self.snoozeRequested.emit()
        self.hide_toast()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if not self._snooze_button.geometry().contains(event.pos()):
            self.hide_toast()
            event.accept()
            return
        super().mousePressEvent(event)

    def _position_bottom_right(self) -> None:
        screen = QtWidgets.QApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        x = available.right() - self.width() - 16
        y = available.bottom() - self.height() - 16
        self.move(x, y)


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
