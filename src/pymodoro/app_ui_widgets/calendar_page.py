from __future__ import annotations

from datetime import date, datetime, time, timedelta

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView, QGraphicsItem, QGraphicsEllipseItem, QGraphicsPathItem, QGraphicsLineItem, QGraphicsRectItem, QGraphicsTextItem

from pymodoro.metrics_reader import CheckInRecord, MetricsReader, SessionDurationRecord
from pymodoro.settings import AppSettings


_DAY_ABBR = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")  # weekday() 0=Mon


def _accent(palette: QtGui.QPalette) -> QColor:
    return palette.color(QtGui.QPalette.ColorRole.Highlight)


def _alpha_hex(color: QColor, alpha: int) -> str:
    """Return color as #AARRGGBB hex string with the given alpha (0–255)."""
    c = QColor(color)
    c.setAlpha(alpha)
    return c.name(QColor.NameFormat.HexArgb)


def _time_frac(t: time) -> float:
    """Return time as fractional hours (e.g. 14:30 → 14.5)."""
    return t.hour + t.minute / 60.0




# ─── Custom Graphics Items ────────────────────────────────────────────────────

class SessionCard(QGraphicsPathItem):
    """A session card rendered as a rounded rectangle with tooltip."""

    def __init__(self, path: QPainterPath, duration_min: int, start_time: time, end_time: time, parent=None):
        super().__init__(path, parent)
        self.duration_min = duration_min
        self.start_time = start_time
        self.end_time = end_time
        self.setAcceptHoverEvents(True)
        self._update_tooltip()

    def _update_tooltip(self) -> None:
        tooltip = f"Work — {self.duration_min} min\n{self.start_time.strftime('%H:%M')} → {self.end_time.strftime('%H:%M')}"
        self.setToolTip(tooltip)

    def hoverEnterEvent(self, event) -> None:
        # Increase opacity on hover
        brush = self.brush()
        color = brush.color()
        color.setAlpha(min(255, color.alpha() + 30))
        self.setBrush(color)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        # Restore original opacity
        brush = self.brush()
        color = brush.color()
        color.setAlpha(max(0, color.alpha() - 30))
        self.setBrush(color)
        super().hoverLeaveEvent(event)


class CheckInDot(QGraphicsEllipseItem):
    """A check-in marker rendered as a small circle with tooltip."""

    def __init__(self, check_time: time, parent=None):
        super().__init__(parent)
        self.check_time = check_time
        self.setAcceptHoverEvents(True)
        self._update_tooltip()

    def _update_tooltip(self) -> None:
        self.setToolTip(f"Check-in at {self.check_time.strftime('%H:%M')}")

    def hoverEnterEvent(self, event) -> None:
        # Increase size on hover
        brush = self.brush()
        color = brush.color()
        color.setAlpha(min(255, color.alpha() + 30))
        self.setBrush(color)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        # Restore original opacity
        brush = self.brush()
        color = brush.color()
        color.setAlpha(max(0, color.alpha() - 30))
        self.setBrush(color)
        super().hoverLeaveEvent(event)


# ─── CalWeekHeader ────────────────────────────────────────────────────────────

class CalWeekHeader(QtWidgets.QWidget):
    """Fixed header showing day abbreviations and date numbers."""
    HEADER_H = 60
    TIME_COL_W = 52

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(self.HEADER_H)
        self._days: list[date] = []
        self._col_w: float = 100.0

    def set_days(self, days: list[date], col_w: float) -> None:
        """Update the days to display and column width."""
        self._days = days
        self._col_w = col_w
        self.update()

    def paintEvent(self, event) -> None:
        """Paint the header with day labels."""
        if not self._days:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        palette = self.palette()
        fg = palette.color(QtGui.QPalette.ColorRole.WindowText)
        bg = palette.color(QtGui.QPalette.ColorRole.Window)
        accent = _accent(palette)
        today = date.today()

        # Background
        painter.fillRect(self.rect(), bg)

        # Bottom separator line
        sep = QColor(fg)
        sep.setAlpha(30)
        painter.setPen(QtGui.QPen(sep, 1))
        painter.drawLine(0, self.HEADER_H - 1, self.width(), self.HEADER_H - 1)

        for i, d in enumerate(self._days):
            cx = self.TIME_COL_W + i * self._col_w + self._col_w / 2
            is_today = d == today

            # Day abbreviation (MON, TUE, ...)
            abbr_color = QColor(accent) if is_today else QColor(fg)
            if not is_today:
                abbr_color.setAlpha(160)
            painter.setPen(abbr_color)
            abbr_font = QFont(self.font())
            abbr_font.setPointSize(max(7, self.font().pointSize() - 2))
            abbr_font.setWeight(QtGui.QFont.Weight.Medium)
            painter.setFont(abbr_font)
            painter.drawText(cx - 20, 6, 40, 16, Qt.AlignmentFlag.AlignCenter, _DAY_ABBR[d.weekday()])

            # Day number circle
            num_font = QFont(self.font())
            num_font.setPointSize(self.font().pointSize() + 1)
            num_font.setWeight(QtGui.QFont.Weight.Bold)
            painter.setFont(num_font)

            circle_r = QtCore.QRect(cx - 14, 24, 28, 28)
            if is_today:
                painter.setPen(QtGui.QPen(Qt.PenStyle.NoPen))
                painter.setBrush(accent)
                painter.drawEllipse(circle_r)
                painter.setPen(QColor("white"))
            else:
                num_color = QColor(fg)
                num_color.setAlpha(80 if d.month != today.month else 210)
                painter.setPen(num_color)
                painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawText(circle_r, Qt.AlignmentFlag.AlignCenter, str(d.day))


# ─── CalWeekGrid ──────────────────────────────────────────────────────────────

class CalWeekGrid(QGraphicsView):
    TIME_COL_W = 52
    _DEFAULT_START = time(7, 0)
    _DEFAULT_END = time(21, 0)
    _PX_PER_HOUR = 40

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._range_start = date.today()
        self._range_end = date.today()
        self._check_ins: list[CheckInRecord] = []
        self._sessions: list[SessionDurationRecord] = []
        self._t_start = self._DEFAULT_START
        self._t_end = self._DEFAULT_END

        self._current_time_line: QGraphicsLineItem | None = None
        self._current_time_dot: QGraphicsEllipseItem | None = None
        self._col_w: float = 100.0  # stored for timer updates
        self._day_index: dict[date, int] = {}
        self._days: list[date] = []  # stored for drawForeground

        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )

        # Refresh current-time line every minute
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(60_000)
        self._timer.timeout.connect(self._update_current_time_line_position)
        self._timer.start()

    def set_data(
        self,
        range_start: date,
        range_end: date,
        check_ins: list[CheckInRecord],
        sessions: list[SessionDurationRecord],
    ) -> None:
        self._range_start = range_start
        self._range_end = range_end
        self._check_ins = check_ins
        self._sessions = sessions
        self._t_start, self._t_end = self._compute_time_range()
        self.updateGeometry()
        self._rebuild_scene()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        """Rebuild scene when view is resized to compute correct column widths."""
        super().resizeEvent(event)
        if self._days:
            self._rebuild_scene()

    def _grid_height_for_range(self) -> int:
        total_hours = _time_frac(self._t_end) - _time_frac(self._t_start)
        if total_hours <= 0:
            total_hours = 1.0
        return int(total_hours * self._PX_PER_HOUR)

    def sizeHint(self) -> QtCore.QSize:
        grid_h = self._grid_height_for_range()
        width = self.TIME_COL_W + 7 * 80
        return QtCore.QSize(width, grid_h)

    def minimumSizeHint(self) -> QtCore.QSize:
        return QtCore.QSize(self.TIME_COL_W + 7 * 40, 200)

    def _compute_time_range(self) -> tuple[time, time]:
        hours: list[float] = []
        for s in self._sessions:
            if s.session_type.lower() != "work":
                continue
            if self._range_start <= s.timestamp.date() <= self._range_end:
                hours.append(_time_frac(s.timestamp.time()))
                start_dt = s.timestamp - timedelta(seconds=s.duration_sec)
                if start_dt.date() == s.timestamp.date():
                    hours.append(_time_frac(start_dt.time()))
        for c in self._check_ins:
            if self._range_start <= c.timestamp.date() <= self._range_end:
                hours.append(_time_frac(c.timestamp.time()))
        if not hours:
            return self._DEFAULT_START, self._DEFAULT_END

        start_h = max(0, min(8, int(min(hours)) - 1))
        end_h = max(20, min(24, int(max(hours)) + 2))
        t_end = time(23, 59) if end_h >= 24 else time(end_h, 0)
        return time(start_h, 0), t_end

    def days(self) -> list[date]:
        result, d = [], self._range_start
        while d <= self._range_end:
            result.append(d)
            d += timedelta(days=1)
        return result

    def get_header_info(self) -> tuple[list[date], float]:
        """Return the days and column width for the header to align with grid."""
        return self._days, self._col_w

    def _y_for_hour(self, hour_frac: float, grid_h: float) -> float:
        """Convert fractional hour to scene y-coordinate (float)."""
        total = _time_frac(self._t_end) - _time_frac(self._t_start)
        frac = (hour_frac - _time_frac(self._t_start)) / total
        return frac * grid_h

    def _y_for_time(self, t: time, grid_h: float) -> float:
        """Convert time to scene y-coordinate (float)."""
        return self._y_for_hour(_time_frac(t), grid_h)

    # ── Scene building ────────────────────────────────────────────────────────

    def _rebuild_scene(self) -> None:
        """Rebuild the entire scene from scratch."""
        self._scene.clear()
        self._current_time_line = None
        self._current_time_dot = None

        palette = self.palette()
        fg = palette.color(QtGui.QPalette.ColorRole.WindowText)
        accent = _accent(palette)
        today = date.today()

        day_list = self.days()
        ndays = len(day_list)
        if ndays == 0:
            return

        # Store days for drawForeground
        self._days = day_list

        # Compute grid dimensions from actual viewport width
        vw = self.viewport().width()
        grid_w = max(vw - self.TIME_COL_W, ndays * 60)  # min 60px/col
        grid_h = self._grid_height_for_range()
        self._col_w = grid_w / ndays
        self._day_index = {d: i for i, d in enumerate(day_list)}

        # Set scene rect
        self._scene.setSceneRect(0, 0, self.TIME_COL_W + grid_w, grid_h)

        # Add background tint for today
        self._add_today_tint(accent, today, self._day_index, self._col_w, grid_h)

        # Add hour grid lines and labels
        self._add_hour_grid(fg, grid_h, self._col_w, grid_w)

        # Add column separators
        self._add_column_separators(fg, ndays, self._col_w, grid_h)

        # Add session cards
        self._add_session_cards(fg, accent, day_list, self._day_index, self._col_w, grid_h)

        # Add check-in dots
        self._add_check_in_dots(accent, self._day_index, self._col_w, grid_h)

        # Add current-time line
        self._add_current_time_line(accent, self._day_index, self._col_w, grid_h)

        # Add empty state if needed
        self._add_empty_state(fg, grid_w, grid_h)

    def _add_today_tint(self, accent: QColor, today: date, day_index: dict[date, int], col_w: float, grid_h: int) -> None:
        if today not in day_index:
            return
        tint = QColor(accent)
        tint.setAlpha(18)
        col_i = day_index[today]
        x = self.TIME_COL_W + col_i * col_w
        rect = self._scene.addRect(x, 0, col_w, grid_h, pen=QtGui.QPen(Qt.PenStyle.NoPen), brush=QtGui.QBrush(tint))
        rect.setZValue(-1)

    def _add_hour_grid(self, fg: QColor, grid_h: int, col_w: float, grid_w: float) -> None:
        grid_color = QColor(fg)
        grid_color.setAlpha(18)
        half_color = QColor(fg)
        half_color.setAlpha(8)

        hour_font = QFont(self.font())
        hour_font.setPointSize(max(7, self.font().pointSize() - 2))
        dim_fg = QColor(fg)
        dim_fg.setAlpha(100)

        total_hours = _time_frac(self._t_end) - _time_frac(self._t_start)

        for hour in range(self._t_start.hour, self._t_end.hour + 1):
            y = self._y_for_hour(float(hour), grid_h)

            # Solid hour line
            pen = QtGui.QPen(grid_color, 1)
            self._scene.addLine(self.TIME_COL_W, y, self.TIME_COL_W + grid_w, y, pen)

            if hour < self._t_end.hour:
                # Hour label
                text = self._scene.addText(f"{hour:02d}:00", hour_font)
                text.setPos(5, y + 2)
                text.setDefaultTextColor(dim_fg)
                text.setZValue(1)

                # Half-hour dashed line
                y_half = self._y_for_hour(hour + 0.5, grid_h)
                dash_pen = QtGui.QPen(half_color, 1)
                dash_pen.setStyle(Qt.PenStyle.DashLine)
                self._scene.addLine(self.TIME_COL_W, y_half, self.TIME_COL_W + grid_w, y_half, dash_pen)

    def _add_column_separators(self, fg: QColor, ndays: int, col_w: float, grid_h: int) -> None:
        sep_color = QColor(fg)
        sep_color.setAlpha(14)
        for i in range(ndays + 1):
            x = self.TIME_COL_W + i * col_w
            pen = QtGui.QPen(sep_color, 1)
            self._scene.addLine(x, 0, x, grid_h, pen)

    def _add_session_cards(self, fg: QColor, accent: QColor, days: list[date], day_index: dict[date, int], col_w: float, grid_h: int) -> None:
        for s in self._sessions:
            if s.session_type.lower() != "work":
                continue
            d = s.timestamp.date()
            if d not in day_index:
                continue

            session_end_dt = s.timestamp
            session_start_dt = session_end_dt - timedelta(seconds=s.duration_sec)

            if session_start_dt.date() != d:
                session_start_dt = session_start_dt.replace(
                    year=d.year, month=d.month, day=d.day,
                    hour=self._t_start.hour, minute=self._t_start.minute, second=0,
                )

            t_start = session_start_dt.time()
            t_end = session_end_dt.time()
            vis_start = max(t_start, self._t_start)
            vis_end = min(t_end, self._t_end)
            if vis_start >= vis_end:
                continue

            y1 = self._y_for_time(vis_start, grid_h)
            y2 = self._y_for_time(vis_end, grid_h)
            if y2 - y1 < 4:
                y2 = y1 + 4

            col_i = day_index[d]
            x = self.TIME_COL_W + col_i * col_w + 3
            bw = col_w - 6

            card_color = QColor(accent)
            card_color.setAlpha(210)

            path = QPainterPath()
            path.addRoundedRect(QRectF(x, y1, bw, y2 - y1), 6, 6)

            card = SessionCard(path, s.duration_sec // 60, vis_start, vis_end)
            card.setBrush(QtGui.QBrush(card_color))
            card.setPen(QtGui.QPen(Qt.PenStyle.NoPen))
            card.setZValue(2)
            self._scene.addItem(card)

            # Add text to the card
            card_h = y2 - y1
            if card_h > 10:
                text_color = QColor("white")
                if card_h > 28:
                    label = "Work"
                    mins = s.duration_sec // 60

                    label_item = self._scene.addText(label)
                    label_font = QtGui.QFont(self.font())
                    label_font.setWeight(QtGui.QFont.Weight.Bold)
                    label_item.setFont(label_font)
                    label_item.setDefaultTextColor(text_color)
                    label_item.setPos(x + 5, y1 + 3)
                    label_item.setZValue(3)

                    dur_item = self._scene.addText(f"{mins}m")
                    dur_font = QtGui.QFont(self.font())
                    dur_font.setPointSize(max(6, self.font().pointSize() - 2))
                    dur_item.setFont(dur_font)
                    dim_text = QColor(text_color)
                    dim_text.setAlpha(180)
                    dur_item.setDefaultTextColor(dim_text)
                    dur_item.setPos(x + 5, y1 + 18)
                    dur_item.setZValue(3)
                else:
                    mins = s.duration_sec // 60
                    dur_font = QtGui.QFont(self.font())
                    dur_font.setPointSize(max(6, self.font().pointSize() - 2))

                    text_item = self._scene.addText(f"Work {mins}m")
                    text_item.setFont(dur_font)
                    text_item.setDefaultTextColor(text_color)
                    text_item.setPos(x + 4, y1 + 1)
                    text_item.setZValue(3)

    def _add_check_in_dots(self, accent: QColor, day_index: dict[date, int], col_w: float, grid_h: int) -> None:
        for c in self._check_ins:
            d = c.timestamp.date()
            if d not in day_index:
                continue
            t = c.timestamp.time()
            if not (self._t_start <= t < self._t_end):
                continue
            y = self._y_for_time(t, grid_h)
            col_i = day_index[d]
            dot_x = self.TIME_COL_W + (col_i + 1) * col_w - 10

            dot_color = QColor(accent)
            dot_color.setAlpha(230)

            dot = CheckInDot(t)
            dot.setRect(dot_x - 4, y - 4, 8, 8)
            dot.setBrush(QtGui.QBrush(dot_color))
            dot.setPen(QtGui.QPen(Qt.PenStyle.NoPen))
            dot.setZValue(2)
            self._scene.addItem(dot)

    def _add_current_time_line(self, accent: QColor, day_index: dict[date, int], col_w: float, grid_h: int) -> None:
        now = datetime.now()
        if now.date() not in day_index:
            return
        t = now.time()
        if not (self._t_start <= t < self._t_end):
            return

        y = self._y_for_time(t, grid_h)
        col_i = day_index[now.date()]
        x0 = self.TIME_COL_W + col_i * col_w
        x1 = self.TIME_COL_W + (col_i + 1) * col_w

        now_color = QColor("#eb4034")
        pen = QtGui.QPen(now_color, 2)
        self._current_time_line = self._scene.addLine(x0 + 10, y, x1, y, pen)
        self._current_time_line.setZValue(4)

        self._current_time_dot = self._scene.addEllipse(x0 + 1, y - 5, 10, 10, QtGui.QPen(Qt.PenStyle.NoPen), QtGui.QBrush(now_color))
        self._current_time_dot.setZValue(4)

    def _update_current_time_line_position(self) -> None:
        """Update only the current-time line position, not the entire scene."""
        if self._current_time_line is None or not self._day_index:
            return

        grid_h = self._grid_height_for_range()

        now = datetime.now()
        if now.date() not in self._day_index:
            return
        t = now.time()
        if not (self._t_start <= t < self._t_end):
            return

        y = self._y_for_time(t, grid_h)
        col_i = self._day_index[now.date()]
        x0 = self.TIME_COL_W + col_i * self._col_w
        x1 = self.TIME_COL_W + (col_i + 1) * self._col_w

        self._current_time_line.setLine(x0 + 10, y, x1, y)
        if self._current_time_dot is not None:
            self._current_time_dot.setRect(x0 + 1, y - 5, 10, 10)

    def _add_empty_state(self, fg: QColor, grid_w: float, grid_h: int) -> None:
        has_data = any(
            self._range_start <= s.timestamp.date() <= self._range_end
            and s.session_type.lower() == "work"
            for s in self._sessions
        ) or any(
            self._range_start <= c.timestamp.date() <= self._range_end
            for c in self._check_ins
        )
        if has_data:
            return

        dim = QColor(fg)
        dim.setAlpha(90)
        msg_font = QFont(self.font())
        msg_font.setPointSize(self.font().pointSize() + 1)

        text = self._scene.addText("No sessions recorded this week", msg_font)
        text.setDefaultTextColor(dim)
        text.setPos(self.TIME_COL_W + grid_w / 2 - 100, grid_h / 2 - 20)
        text.setZValue(0)

    def changeEvent(self, event: QtCore.QEvent) -> None:
        if event.type() == QtCore.QEvent.Type.PaletteChange:
            self._rebuild_scene()
        super().changeEvent(event)


# ─── CalendarPage ──────────────────────────────────────────────────────────────

class CalendarPage(QtWidgets.QWidget):
    def __init__(self, settings: AppSettings, parent=None) -> None:
        super().__init__(parent)
        self._reader = MetricsReader(settings.metrics_log_path)
        self._monday = _week_monday(date.today())

        # ── Header bar ────────────────────────────────────────────────────────
        self._btn_prev = QtWidgets.QToolButton()
        self._btn_prev.setText("‹")
        self._btn_prev.setFixedSize(32, 32)

        self._btn_next = QtWidgets.QToolButton()
        self._btn_next.setText("›")
        self._btn_next.setFixedSize(32, 32)

        self._btn_today = QtWidgets.QPushButton("Today")
        self._btn_today.setFixedHeight(32)

        self._range_label = QtWidgets.QLabel()
        self._range_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        self._week_badge = QtWidgets.QLabel()
        self._week_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._week_badge.setFixedHeight(22)
        self._week_badge.setStyleSheet("""
            QLabel {
                background-color: palette(midlight);
                border-radius: 10px;
                padding: 0px 10px;
                font-size: 11px;
                color: palette(windowtext);
            }
        """)

        header = QtWidgets.QHBoxLayout()
        header.setContentsMargins(12, 8, 12, 8)
        header.setSpacing(6)
        header.addWidget(self._btn_prev)
        header.addWidget(self._btn_next)
        header.addWidget(self._btn_today)
        header.addSpacing(8)
        header.addWidget(self._range_label)
        header.addWidget(self._week_badge)
        header.addStretch()

        # Wrap header in a fixed-height widget
        header_widget = QtWidgets.QWidget()
        header_widget.setLayout(header)
        header_widget.setFixedHeight(48)

        # ── Week grid and header ───────────────────────────────────────────────
        self._grid = CalWeekGrid()
        self._week_header = CalWeekHeader()

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(header_widget)
        layout.addWidget(self._week_header)
        layout.addWidget(self._grid, 1)

        self._btn_prev.clicked.connect(self._go_prev)
        self._btn_next.clicked.connect(self._go_next)
        self._btn_today.clicked.connect(self._go_today)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Schedule updates after layout is computed
        QtCore.QTimer.singleShot(0, self._update_view)

    def refresh(self) -> None:
        self._update_view()

    def _sync_header_after_layout(self) -> None:
        """Sync header with grid after layout is complete."""
        days, col_w = self._grid.get_header_info()
        self._week_header.set_days(days, col_w)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        """Update header layout when window is resized."""
        super().resizeEvent(event)
        # Sync header with grid's computed layout after resize
        days, col_w = self._grid.get_header_info()
        self._week_header.set_days(days, col_w)

    def _update_view(self) -> None:
        check_ins, sessions = self._reader.read_all()
        sunday = self._monday + timedelta(days=6)

        self._grid.set_data(self._monday, sunday, check_ins, sessions)

        # Sync header with grid's actual layout
        # Use the column width computed by the grid after it rebuilds
        days, col_w = self._grid.get_header_info()
        self._week_header.set_days(days, col_w)

        if self._monday.month == sunday.month:
            label = f"{self._monday.day} – {sunday.day} {sunday.strftime('%b %Y')}"
        else:
            label = f"{self._monday.strftime('%-d %b')} – {sunday.strftime('%-d %b %Y')}"
        self._range_label.setText(label)

        iso_week = self._monday.isocalendar()[1]
        self._week_badge.setText(f"Week {iso_week}")

    def _go_prev(self) -> None:
        self._monday -= timedelta(weeks=1)
        self._update_view()

    def _go_next(self) -> None:
        self._monday += timedelta(weeks=1)
        self._update_view()

    def _go_today(self) -> None:
        self._monday = _week_monday(date.today())
        self._update_view()

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        key = event.key()
        if key == Qt.Key.Key_Left:
            self._go_prev()
        elif key == Qt.Key.Key_Right:
            self._go_next()
        elif key == Qt.Key.Key_T:
            self._go_today()
        else:
            super().keyPressEvent(event)


def _week_monday(d: date) -> date:
    return d - timedelta(days=d.weekday())
