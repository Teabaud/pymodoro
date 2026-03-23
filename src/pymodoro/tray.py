from __future__ import annotations

from pymodoro.session import SessionPhase, SessionPhaseManager

# isort: split
from PySide6 import QtCore, QtGui, QtWidgets

ActivationReason = QtWidgets.QSystemTrayIcon.ActivationReason
AlignVCenter = QtCore.Qt.AlignmentFlag.AlignVCenter


class TrayController(QtCore.QObject):
    openAppRequested = QtCore.Signal()
    openSettingsRequested = QtCore.Signal()
    checkInRequested = QtCore.Signal()
    startBreakRequested = QtCore.Signal()
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

        self.tray = QtWidgets.QSystemTrayIcon(app)
        self._menu = QtWidgets.QMenu()
        self._action_open_app = self._menu.addAction("Open App")
        self._action_open_app.triggered.connect(self.openAppRequested.emit)
        self._action_check_in = self._menu.addAction("Check in")
        self._action_check_in.triggered.connect(self.checkInRequested.emit)
        self._action_pause = self._menu.addAction("Pause until...")
        self._action_pause.triggered.connect(self._on_pause_action)
        self._action_quit = self._menu.addAction("Quit")
        self._action_quit.triggered.connect(self.quitRequested.emit)
        self.tray.setContextMenu(self._menu)
        self.tray.activated.connect(self._on_tray_activated)

        self._update_timer = QtCore.QTimer(self)
        self._update_timer.setInterval(1000)
        self._update_timer.timeout.connect(self.refresh)
        self._phase_end_toast: PhaseEndToast | None = None

    def show(self) -> None:
        self.tray.show()
        self._update_timer.start()
        self.refresh()

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

        self.tray.setToolTip(tooltip_str)

    def show_phase_end_toast(self, text: str) -> None:
        self._ensure_phase_end_toast().show_toast(text=text)

    def hide_phase_end_toast(self) -> None:
        if self._phase_end_toast is not None:
            self._phase_end_toast.hide()

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

    def _on_tray_activated(self, reason: ActivationReason) -> None:
        if reason == ActivationReason.Trigger:
            self.openSettingsRequested.emit()

    def _ensure_phase_end_toast(self) -> PhaseEndToast:
        if self._phase_end_toast is None:
            self._phase_end_toast = PhaseEndToast(self)
            self._phase_end_toast.snoozeRequested.connect(self.snoozeRequested.emit)
            self._phase_end_toast.checkInRequested.connect(self.checkInRequested.emit)
            self._phase_end_toast.startBreakRequested.connect(
                self.startBreakRequested.emit
            )
        return self._phase_end_toast


class PhaseEndToast(QtWidgets.QFrame):
    snoozeRequested = QtCore.Signal()
    checkInRequested = QtCore.Signal()
    startBreakRequested = QtCore.Signal()

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(None)
        self.setObjectName("PhaseEndToast")
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
        self._check_in_button = QtWidgets.QPushButton("Start break", self)
        self._check_in_button.clicked.connect(self.startBreakRequested.emit)
        self._check_in_button.clicked.connect(self.hide)
        self._snooze_button = QtWidgets.QPushButton("Snooze", self)
        self._snooze_button.clicked.connect(self.snoozeRequested.emit)
        self._snooze_button.clicked.connect(self.hide)

        content_layout = QtWidgets.QHBoxLayout()
        content_layout.setContentsMargins(14, 12, 14, 12)
        content_layout.setSpacing(14)
        content_layout.addWidget(self._text_label, 1, AlignVCenter)
        content_layout.addWidget(self._check_in_button, 0, AlignVCenter)
        content_layout.addWidget(self._snooze_button, 0, AlignVCenter)
        self.setLayout(content_layout)

    def show_toast(self, text: str) -> None:
        self._text_label.setText(text)
        self.adjustSize()
        self._position_bottom_right()
        self.show()
        self.raise_()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        super().mousePressEvent(event)
        self.hide()
        event.accept()

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
