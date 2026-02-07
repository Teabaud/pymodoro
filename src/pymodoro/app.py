from __future__ import annotations

from enum import Enum

from loguru import logger

from pymodoro.config import load_config
from pymodoro.ui import FullScreenPrompt, PauseUntilDialog

# isort: split
from PySide6 import QtCore, QtGui, QtWidgets


class Mode(str, Enum):
    WORK = "work"
    BREAK = "break"
    PAUSE = "pause"


class TimePrinter:
    @staticmethod
    def end_datetime_str(timer: QtCore.QTimer) -> str:
        end_date = QtCore.QDateTime.currentDateTime().addMSecs(timer.remainingTime())
        if end_date.date() == QtCore.QDate.currentDate():
            return end_date.toString("HH:mm")
        return end_date.toString("yyyy-MM-dd HH:mm")

    @staticmethod
    def countdown_str(timer: QtCore.QTimer) -> str:
        remaining_seconds = (timer.remainingTime() + 400) // 1000
        hours, remainder = divmod(remaining_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _get_qt_app() -> QtWidgets.QApplication:
    app = QtWidgets.QApplication([])
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("Pymodoro")
    app.setDesktopFileName("pymodoro")
    if not QtWidgets.QSystemTrayIcon.isSystemTrayAvailable():
        raise RuntimeError("System tray is not available in this session.")
    return app


class PomodoroApp(QtCore.QObject):
    def __init__(self) -> None:
        super().__init__()
        self._app = _get_qt_app()

        config = load_config()
        self._work_duration = config.timers.work_duration
        self._break_duration = config.timers.break_duration
        self._snooze_seconds = config.timers.snooze_duration
        self._work_end_question = config.messages.work_end_question

        self._tray = QtWidgets.QSystemTrayIcon(self._app)

        self._menu = QtWidgets.QMenu()
        self._action_pause = self._menu.addAction("Pause until...")
        self._action_pause.triggered.connect(self._on_pause_action)
        self._action_quit = self._menu.addAction("Quit")
        self._action_quit.triggered.connect(QtWidgets.QApplication.quit)
        self._tray.setContextMenu(self._menu)

        self._mode = Mode.BREAK
        self._mode_timer = QtCore.QTimer(self)
        self._mode_timer.setSingleShot(True)
        self._mode_timer.timeout.connect(self.on_mode_timer_timeout)

        self._start_session(mode=Mode.WORK, duration_seconds=self._work_duration)
        self._tray.show()

        self._fullscreen_window: FullScreenPrompt | None = None

        self._tray_update_clock = QtCore.QTimer(self)
        self._tray_update_clock.setInterval(1000)
        self._tray_update_clock.timeout.connect(self._update_tray)
        self._tray_update_clock.start()

        self.launch = self._app.exec

    def _render_icon(self, label: str) -> QtGui.QPixmap:
        size = 124
        pixmap = QtGui.QPixmap(size, size)
        pixmap.fill(QtCore.Qt.GlobalColor.transparent)
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing)
        painter.setPen(
            QtWidgets.QApplication.palette().color(QtGui.QPalette.ColorRole.WindowText)
        )
        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)

        font = QtGui.QFont("Sans Serif", int(size * 0.8), QtGui.QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(
            QtCore.QRect(0, 0, size, size),
            QtCore.Qt.AlignmentFlag.AlignCenter,
            label,
        )

        painter.end()
        return pixmap

    def _update_tray(self) -> None:
        if self._mode == Mode.PAUSE:
            end_date_str = TimePrinter.end_datetime_str(self._mode_timer)
            self._tray.setToolTip(f"Pause until {end_date_str}")
            self._action_pause.setText("Resume")
        else:
            countdown_str = TimePrinter.countdown_str(self._mode_timer)
            self._tray.setToolTip(f"{self._mode.value} {countdown_str}")
            self._action_pause.setText("Pause until...")

        label = {Mode.WORK: "W", Mode.BREAK: "B", Mode.PAUSE: "P"}.get(self._mode, "?")
        pixmap = self._render_icon(label)
        self._tray.setIcon(QtGui.QIcon(pixmap))

    def _start_session(self, mode: Mode, duration_seconds: int) -> None:
        self._mode_timer.stop()
        self._mode_timer.setInterval(duration_seconds * 1000)
        self._mode_timer.start()
        self._mode = mode
        self._update_tray()
        self.log_state()

    def _start_work_session(self) -> None:
        self._start_session(mode=Mode.WORK, duration_seconds=self._work_duration)

    def _start_break_session(self) -> None:
        self._start_session(mode=Mode.BREAK, duration_seconds=self._break_duration)
    
    def _start_pause_session(self, duration_seconds: int) -> None:
        self._start_session(mode=Mode.PAUSE, duration_seconds=duration_seconds)

    def on_mode_timer_timeout(self) -> None:
        if self._mode == Mode.WORK:
            self._show_break_window()
            self._start_break_session()
        else:
            self._start_work_session()

    def _on_pause_action(self) -> None:
        if self._mode == Mode.PAUSE:
            self._start_work_session()
            return

        default_datetime = QtCore.QDateTime.currentDateTime().addSecs(3600)
        dialog = PauseUntilDialog(default_datetime)
        accepted_code = getattr(getattr(QtWidgets.QDialog, "DialogCode", None), "Accepted", 1)
        if dialog.exec() == accepted_code:
            pause_seconds = QtCore.QDateTime.currentDateTime().secsTo(dialog.selected_datetime())
            self._start_pause_session(duration_seconds=pause_seconds)

    def _show_break_window(self) -> None:
        if self._fullscreen_window is None:
            self._fullscreen_window = FullScreenPrompt(message=self._work_end_question)
            self._fullscreen_window.submitted.connect(self._on_note_submit)
            self._fullscreen_window.snoozed.connect(self._on_break_snooze)
        if self._fullscreen_window.isVisible():
            return
        self._fullscreen_window.show()

    def _on_note_submit(self, text: str) -> None:
        logger.info("Note submitted: {}", text)
        self._close_break_window()

    def _on_break_snooze(self) -> None:
        self._close_break_window()
        self._start_session(mode=Mode.WORK, duration_seconds=self._snooze_seconds)

    def _close_break_window(self) -> None:
        if self._fullscreen_window is not None:
            self._fullscreen_window.close()

    def log_state(self) -> None:
        if self._mode == Mode.PAUSE:
            time_str = TimePrinter.end_datetime_str(self._mode_timer)
            logger.info(f"State: {self._mode.value}. Resume at: {time_str}")
        else:
            time_str = TimePrinter.countdown_str(self._mode_timer)
            logger.info(f"State: {self._mode.value}. Timer: {time_str}")