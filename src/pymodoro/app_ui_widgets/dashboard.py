from datetime import date, datetime, timedelta
from typing import Iterable, cast

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt

from pymodoro.app_ui_widgets.dashboard_widgets import (
    CalendarContainer,
    DateRangeLabel,
    FocusTrendWidget,
    TorusChartWidget,
    VisibleRange,
)
from pymodoro.metrics_reader import MetricsData, load_metrics
from pymodoro.settings import AppSettings
from pymodoro.tray import get_app_icon


class ViewMode:
    DAY = "day"
    THREE_DAYS = "3days"
    WEEK = "week"
    MONTH = "month"


def _today() -> date:
    return datetime.now().date()


def _make_initial_range() -> VisibleRange:
    today = _today()
    return VisibleRange(start=today, end=today)


class Toolbar(QtWidgets.QFrame):
    """Toolbar for the dashboard."""

    view_changed = QtCore.Signal(int)
    prev_clicked = QtCore.Signal()
    next_clicked = QtCore.Signal()
    today_clicked = QtCore.Signal()
    show_date_picker = QtCore.Signal()
    load_metrics_and_refresh = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self._layout = QtWidgets.QHBoxLayout(self)

        self._view_combo = QtWidgets.QComboBox(self)
        self._view_combo.addItem("Day", ViewMode.DAY)
        self._view_combo.addItem("3 days", ViewMode.THREE_DAYS)
        self._view_combo.addItem("Week", ViewMode.WEEK)
        self._view_combo.addItem("Month", ViewMode.MONTH)
        self._view_combo.currentIndexChanged.connect(self.view_changed.emit)
        self._layout.addWidget(self._view_combo)

        self._layout.addSpacing(16)

        self._prev_button = QtWidgets.QToolButton(self)
        self._prev_button.setText("◀")
        self._prev_button.clicked.connect(self.prev_clicked.emit)
        self._layout.addWidget(self._prev_button)

        self._next_button = QtWidgets.QToolButton(self)
        self._next_button.setText("▶")
        self._next_button.clicked.connect(self.next_clicked.emit)
        self._layout.addWidget(self._next_button)

        self._today_button = QtWidgets.QPushButton("Today", self)
        self._today_button.clicked.connect(self.today_clicked.emit)
        self._layout.addWidget(self._today_button)

        self._layout.addSpacing(12)

        self._range_label = DateRangeLabel(self)
        self._range_label.clickedForCalendar.connect(self.show_date_picker.emit)
        self._layout.addWidget(self._range_label, 1)

        self._refresh_button = QtWidgets.QToolButton(self)
        self._refresh_button.setText("⟳")
        self._refresh_button.setToolTip("Reload metrics from log file")
        self._refresh_button.clicked.connect(self.load_metrics_and_refresh.emit)
        self._layout.addWidget(self._refresh_button)

        self.setMaximumHeight(50)


class Logo(QtWidgets.QToolButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        icon = get_app_icon()
        self.setIcon(icon)
        self.setIconSize(QtCore.QSize(70, 70))
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            "Logo { background: transparent; border: none; padding: 0px 16px; }"
        )


class NavItem(QtWidgets.QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        for label in [
            "Reports",
            "Library",
            "People",
            "Activities",
            "Get Started",
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


class Sidebar(QtWidgets.QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(150)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(0)

        layout.addWidget(Logo(self))
        layout.addWidget(NavItem(self))


class FilterBar(QtWidgets.QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(48)
        self.setStyleSheet("""
            FilterBar {
                border-bottom: 1px solid palette(mid);
            }
            QComboBox { padding: 4px 10px; border-radius: 6px; font-size: 12px; }
        """)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)

        for label in ["Timeframe: All-time", "People: All", "Topic: All"]:
            combo = QtWidgets.QComboBox()
            combo.addItem(label)
            layout.addWidget(combo)

        layout.addStretch(1)


class Content(QtWidgets.QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        placeholder = QtWidgets.QLabel("Charts, tables and metrics go here")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet("color: palette(window-text); font-size: 14px;")
        layout.addWidget(placeholder)


class MainArea(QtWidgets.QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)

        layout.addWidget(Toolbar(self))
        layout.addWidget(FilterBar(self))
        layout.addWidget(Content(self), 1)
        self.setStyleSheet("""
            MainArea {
                background-color: palette(alternate-base);
                border-radius: 10px;
                margin: 16px 0px 0px 0px;
            }
        """)


class DashboardWindow(QtWidgets.QMainWindow):
    """Main dashboard window with calendar views and analytics."""

    def __init__(
        self,
        settings: AppSettings,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._settings = settings

        self._qt_settings = QtCore.QSettings("Pymodoro", "Dashboard")
        self.restore_geometry()

        self.setWindowTitle("Pymodoro Dashboard")
        self.setWindowIcon(get_app_icon())
        self.setMinimumSize(800, 500)

        self._build_ui()
        # self._load_metrics_and_refresh()

    # ---- UI construction -------------------------------------------------
    def _build_ui(self) -> None:
        container = QtWidgets.QWidget()
        root = QtWidgets.QHBoxLayout(container)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(Sidebar(container))
        root.addWidget(MainArea(container))

        self.setCentralWidget(container)

    # ---- State restoration ------------------------------------------------
    def restore_geometry(self):
        geometry = self._qt_settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        else:
            self.resize(980, 640)

    def closeEvent(self, event):
        self._qt_settings.setValue("geometry", self.saveGeometry())
        super().closeEvent(event)

    # ---- UI construction -------------------------------------------------
    def __build_ui(self) -> None:
        root_layout = QtWidgets.QVBoxLayout(self)

        # Toolbar
        toolbar = QtWidgets.QHBoxLayout()

        self._view_combo = QtWidgets.QComboBox(self)
        self._view_combo.addItem("Day", ViewMode.DAY)
        self._view_combo.addItem("3 days", ViewMode.THREE_DAYS)
        self._view_combo.addItem("Week", ViewMode.WEEK)
        self._view_combo.addItem("Month", ViewMode.MONTH)
        self._view_combo.currentIndexChanged.connect(self._on_view_changed)
        toolbar.addWidget(self._view_combo)

        toolbar.addSpacing(16)

        self._prev_button = QtWidgets.QToolButton(self)
        self._prev_button.setText("◀")
        self._prev_button.clicked.connect(self._on_prev_clicked)
        toolbar.addWidget(self._prev_button)

        self._next_button = QtWidgets.QToolButton(self)
        self._next_button.setText("▶")
        self._next_button.clicked.connect(self._on_next_clicked)
        toolbar.addWidget(self._next_button)

        self._today_button = QtWidgets.QPushButton("Today", self)
        self._today_button.clicked.connect(self._on_today_clicked)
        toolbar.addWidget(self._today_button)

        toolbar.addSpacing(12)

        self._range_label = DateRangeLabel(self)
        self._range_label.clickedForCalendar.connect(self._show_date_picker)
        toolbar.addWidget(self._range_label, 1)

        self._refresh_button = QtWidgets.QToolButton(self)
        self._refresh_button.setText("⟳")
        self._refresh_button.setToolTip("Reload metrics from log file")
        self._refresh_button.clicked.connect(self._load_metrics_and_refresh)
        toolbar.addWidget(self._refresh_button)

        root_layout.addLayout(toolbar)

        # Main content: calendar on the left, torus chart on the right
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal, self)

        self._calendar = CalendarContainer(splitter)
        splitter.addWidget(self._calendar)

        right_panel = QtWidgets.QWidget(splitter)
        right_layout = QtWidgets.QVBoxLayout(right_panel)
        right_layout.setContentsMargins(8, 8, 8, 8)
        right_layout.setSpacing(8)

        torus_label = QtWidgets.QLabel("Sessions per day (Work)")
        bold = torus_label.font()
        bold.setBold(True)
        torus_label.setFont(bold)
        right_layout.addWidget(torus_label)

        self._torus_chart = TorusChartWidget(right_panel)
        right_layout.addWidget(self._torus_chart, 0)

        self._summary_label = QtWidgets.QLabel(right_panel)
        self._summary_label.setWordWrap(True)
        right_layout.addWidget(self._summary_label)

        focus_label = QtWidgets.QLabel("Focus rating trend", right_panel)
        focus_label.setFont(bold)
        right_layout.addWidget(focus_label)

        self._focus_trend = FocusTrendWidget(right_panel)
        right_layout.addWidget(self._focus_trend, 0)

        history_label = QtWidgets.QLabel("Check-in history", right_panel)
        history_label.setFont(bold)
        right_layout.addWidget(history_label)

        history_controls = QtWidgets.QHBoxLayout()
        self._history_search = QtWidgets.QLineEdit(right_panel)
        self._history_search.setPlaceholderText("Search answers...")
        self._history_search.textChanged.connect(self._apply_history_filters)
        history_controls.addWidget(self._history_search, 2)

        self._history_prompt_filter = QtWidgets.QComboBox(right_panel)
        self._history_prompt_filter.currentIndexChanged.connect(
            self._apply_history_filters
        )
        history_controls.addWidget(self._history_prompt_filter, 1)

        right_layout.addLayout(history_controls)

        self._history_list = QtWidgets.QListWidget(right_panel)
        right_layout.addWidget(self._history_list, 1)

        self._history_all_items: list[tuple[date, str, str, int | None]] = []

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        root_layout.addWidget(splitter, 1)

        self._update_range_label()

    # ---- Metrics + view updates -----------------------------------------
    def _load_metrics_and_refresh(self) -> None:
        self._metrics = load_metrics(self._settings.metrics_log_path)
        self._ensure_visible_range_has_data_fallback()
        self._refresh_calendar()
        self._refresh_torus_chart()
        self._refresh_stats()
        self._refresh_history()

    def _ensure_visible_range_has_data_fallback(self) -> None:
        if self._metrics is None or not self._metrics.work_sessions:
            self._visible_range = _make_initial_range()
            return
        # If current range has no work sessions, snap to the nearest day with data.
        by_day = self._metrics.work_sessions_by_day()
        day = self._visible_range.start
        has_data = any(
            day in by_day
            for day in _iter_days(self._visible_range.start, self._visible_range.end)
        )
        if has_data:
            return
        all_days = sorted(by_day.keys())
        if not all_days:
            return
        closest = min(all_days, key=lambda d: abs((d - self._visible_range.start).days))
        self._visible_range = VisibleRange(start=closest, end=closest)

    def _refresh_calendar(self) -> None:
        if self._metrics is None:
            return
        self._calendar.set_days(self._visible_range, self._metrics)
        self._update_range_label()

    def _refresh_torus_chart(self) -> None:
        if self._metrics is None:
            self._torus_chart.set_values({})
            return
        by_day = self._metrics.work_sessions_by_day()
        values: dict[date, float] = {}
        for day in _iter_days(self._visible_range.start, self._visible_range.end):
            sessions = by_day.get(day, [])
            if not sessions:
                continue
            total = sum(session.duration_sec for session in sessions)
            values[day] = total / 60.0  # minutes of work
        self._torus_chart.set_values(values)

    def _refresh_stats(self) -> None:
        if self._metrics is None or not self._metrics.work_sessions:
            self._summary_label.setText("No work data in the selected range.")
            self._focus_trend.set_data([], [])
            return

        by_day = self._metrics.work_sessions_by_day()
        total_sec = 0
        total_sessions = 0
        daily_totals: dict[date, int] = {}
        for day in _iter_days(self._visible_range.start, self._visible_range.end):
            sessions = by_day.get(day, [])
            if not sessions:
                continue
            day_total = sum(s.duration_sec for s in sessions)
            daily_totals[day] = day_total
            total_sec += day_total
            total_sessions += len(sessions)

        if not daily_totals:
            self._summary_label.setText("No work data in the selected range.")
            self._focus_trend.set_data([], [])
            return

        def _day_total(day: date) -> int:
            return daily_totals[day]

        best_day = max(daily_totals, key=_day_total)
        worst_day = min(daily_totals, key=_day_total)

        total_hours = total_sec / 3600.0
        summary = (
            f"Total work: {total_hours:.1f} h "
            f"across {total_sessions} sessions. "
            f"Best day: {best_day.strftime('%a %d %b')} "
            f"({daily_totals[best_day] // 60} min). "
            f"Worst day: {worst_day.strftime('%a %d %b')} "
            f"({daily_totals[worst_day] // 60} min)."
        )
        self._summary_label.setText(summary)

        # Focus rating trend: average daily rating from check-ins in range.
        dates: list[date] = []
        averages: list[float] = []
        if self._metrics.check_ins:
            ratings_by_day: dict[date, list[int]] = {}
            for check_in in self._metrics.check_ins:
                day = check_in.timestamp.date()
                if not (self._visible_range.start <= day <= self._visible_range.end):
                    continue
                if check_in.focus_rating is None:
                    continue
                ratings_by_day.setdefault(day, []).append(check_in.focus_rating)

            for day in sorted(ratings_by_day.keys()):
                values = ratings_by_day[day]
                dates.append(day)
                averages.append(sum(values) / len(values))

        self._focus_trend.set_data(dates, averages)

    def _update_range_label(self) -> None:
        self._range_label.set_range(self._visible_range)

    # ---- Navigation ------------------------------------------------------
    def _on_view_changed(self, index: int) -> None:
        mode = self._view_combo.currentData()
        if mode not in (
            ViewMode.DAY,
            ViewMode.THREE_DAYS,
            ViewMode.WEEK,
            ViewMode.MONTH,
        ):
            return
        self._view_mode = mode
        self._adjust_range_for_view(anchor=_today())
        self._refresh_calendar()
        self._refresh_torus_chart()

    def _on_prev_clicked(self) -> None:
        self._shift_range(-1)

    def _on_next_clicked(self) -> None:
        self._shift_range(1)

    def _on_today_clicked(self) -> None:
        anchor = _today()
        self._adjust_range_for_view(anchor=anchor)
        self._refresh_calendar()
        self._refresh_torus_chart()
        self._refresh_stats()
        self._refresh_history()

    def _shift_range(self, direction: int) -> None:
        if self._view_mode == ViewMode.DAY:
            delta = 1
        elif self._view_mode == ViewMode.THREE_DAYS:
            delta = 3
        elif self._view_mode == ViewMode.WEEK:
            delta = 7
        else:
            # Month view
            start = self._visible_range.start
            month_delta = direction
            year = start.year + (start.month + month_delta - 1) // 12
            month = (start.month + month_delta - 1) % 12 + 1
            new_start = date(year, month, 1)
            new_end = _end_of_month(new_start)
            self._visible_range = VisibleRange(start=new_start, end=new_end)
            self._refresh_calendar()
            self._refresh_torus_chart()
            return

        shift = timedelta(days=delta * direction)
        self._visible_range = VisibleRange(
            start=self._visible_range.start + shift,
            end=self._visible_range.end + shift,
        )
        self._refresh_calendar()
        self._refresh_torus_chart()
        self._refresh_stats()
        self._refresh_history()

    def _adjust_range_for_view(self, anchor: date) -> None:
        if self._view_mode == ViewMode.DAY:
            self._visible_range = VisibleRange(start=anchor, end=anchor)
        elif self._view_mode == ViewMode.THREE_DAYS:
            self._visible_range = VisibleRange(
                start=anchor, end=anchor + timedelta(days=2)
            )
        elif self._view_mode == ViewMode.WEEK:
            self._visible_range = VisibleRange(
                start=anchor, end=anchor + timedelta(days=6)
            )
        else:
            start = date(anchor.year, anchor.month, 1)
            end = _end_of_month(start)
            self._visible_range = VisibleRange(start=start, end=end)

    # ---- Date picker -----------------------------------------------------
    def _show_date_picker(self) -> None:
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Select date")
        layout = QtWidgets.QVBoxLayout(dialog)
        calendar = QtWidgets.QCalendarWidget(dialog)
        calendar.setGridVisible(True)
        layout.addWidget(calendar)

        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Close
        )
        layout.addWidget(button_box)
        button_box.rejected.connect(dialog.reject)

        calendar.clicked.connect(self._on_date_picker_clicked)
        calendar.activated.connect(self._on_date_picker_activated)

        dialog.resize(360, 320)
        dialog.exec()

    def _on_date_picker_clicked(self, qdate: QtCore.QDate) -> None:
        # Single click: update anchor date but keep range size (e.g. 7 days).
        anchor = cast(date, qdate.toPython())
        days = self._visible_range.days
        if self._view_mode == ViewMode.MONTH:
            self._adjust_range_for_view(anchor=anchor)
        else:
            self._visible_range = VisibleRange(
                start=anchor,
                end=anchor + timedelta(days=days - 1),
            )
        self._refresh_calendar()
        self._refresh_torus_chart()
        self._refresh_stats()
        self._refresh_history()

    def _on_date_picker_activated(self, qdate: QtCore.QDate) -> None:
        # Double click: focus day view for the selected date.
        anchor = cast(date, qdate.toPython())
        self._view_mode = ViewMode.DAY
        # Update combo box to match
        index = self._view_combo.findData(ViewMode.DAY)
        if index != -1:
            self._view_combo.setCurrentIndex(index)
        self._visible_range = VisibleRange(start=anchor, end=anchor)
        self._refresh_calendar()
        self._refresh_torus_chart()
        self._refresh_stats()
        self._refresh_history()

    # ---- Keyboard shortcuts ----------------------------------------------
    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if event.key() == QtCore.Qt.Key.Key_Left:
            self._on_prev_clicked()
            event.accept()
            return
        if event.key() == QtCore.Qt.Key.Key_Right:
            self._on_next_clicked()
            event.accept()
            return
        if event.key() == QtCore.Qt.Key.Key_T:
            self._on_today_clicked()
            event.accept()
            return
        super().keyPressEvent(event)

    # ---- Check-in history -----------------------------------------------
    def _refresh_history(self) -> None:
        self._history_all_items.clear()
        self._history_prompt_filter.blockSignals(True)
        self._history_prompt_filter.clear()
        self._history_prompt_filter.addItem("All prompts", None)

        if self._metrics is None or not self._metrics.check_ins:
            self._history_prompt_filter.blockSignals(False)
            self._history_list.clear()
            return

        prompts_seen: set[str] = set()
        for check_in in self._metrics.check_ins:
            day = check_in.timestamp.date()
            if not (self._visible_range.start <= day <= self._visible_range.end):
                continue
            self._history_all_items.append(
                (day, check_in.prompt, check_in.answer, check_in.focus_rating)
            )
            if check_in.prompt and check_in.prompt not in prompts_seen:
                prompts_seen.add(check_in.prompt)
                self._history_prompt_filter.addItem(check_in.prompt, check_in.prompt)

        self._history_prompt_filter.blockSignals(False)
        self._apply_history_filters()

    def _apply_history_filters(self) -> None:
        search = self._history_search.text().strip().lower()
        prompt_filter = self._history_prompt_filter.currentData()
        self._history_list.clear()

        for day, prompt, answer, rating in self._history_all_items:
            if prompt_filter and prompt != prompt_filter:
                continue
            haystack = f"{prompt} {answer}".lower()
            if search and search not in haystack:
                continue
            parts = [day.strftime("%Y-%m-%d")]
            if rating is not None:
                parts.append(f"[{rating}★]")
            if prompt:
                parts.append(prompt)
            if answer:
                parts.append(f"— {answer}")
            item_text = " ".join(parts)
            self._history_list.addItem(item_text)


def _iter_days(start: date, end: date) -> Iterable[date]:
    day = start
    while day <= end:
        yield day
        day += timedelta(days=1)


def _end_of_month(first_of_month: date) -> date:
    if first_of_month.month == 12:
        next_month = date(first_of_month.year + 1, 1, 1)
    else:
        next_month = date(first_of_month.year, first_of_month.month + 1, 1)
    return next_month - timedelta(days=1)
