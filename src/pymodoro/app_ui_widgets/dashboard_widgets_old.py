from dataclasses import dataclass
from datetime import date, timedelta

from PySide6 import QtCore, QtGui, QtWidgets

from pymodoro.metrics_reader import MetricsData, WorkSession


class ViewMode:
    DAY = "day"
    THREE_DAYS = "3days"
    WEEK = "week"
    MONTH = "month"


@dataclass(slots=True)
class VisibleRange:
    start: date
    end: date  # inclusive

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1


class DateRangeLabel(QtWidgets.QPushButton):
    """Clickable label that displays the current visible date range."""

    clickedForCalendar = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFlat(True)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.clicked.connect(self.clickedForCalendar.emit)

    def set_range(self, visible_range: VisibleRange) -> None:
        if visible_range.start == visible_range.end:
            text = visible_range.start.strftime("%A, %d %B %Y")
        else:
            start_str = visible_range.start.strftime("%d %b %Y")
            end_str = visible_range.end.strftime("%d %b %Y")
            text = f"{start_str} – {end_str}"
        self.setText(text)


class TorusChartWidget(QtWidgets.QWidget):
    """Simple donut chart for sessions-per-day in the current range."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._values_by_day: list[tuple[date, float]] = []
        self.setMinimumHeight(160)

    def set_values(self, values_by_day: dict[date, float]) -> None:
        items = sorted(values_by_day.items(), key=lambda item: item[0])
        self._values_by_day = [(d, float(v)) for d, v in items if v > 0]
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)

        rect = self.rect().adjusted(16, 16, -16, -16)
        size = min(rect.width(), rect.height())
        if size <= 0:
            return

        cx = rect.center().x()
        cy = rect.center().y()
        radius_outer = size / 2
        radius_inner = radius_outer * 0.55

        total = sum(v for _, v in self._values_by_day)
        if total <= 0:
            # Draw an empty ring as placeholder
            path = QtGui.QPainterPath()
            outer = QtCore.QRectF(
                cx - radius_outer,
                cy - radius_outer,
                2 * radius_outer,
                2 * radius_outer,
            )
            inner = QtCore.QRectF(
                cx - radius_inner,
                cy - radius_inner,
                2 * radius_inner,
                2 * radius_inner,
            )
            path.addEllipse(outer)
            path.addEllipse(inner)
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            color = self.palette().mid().color()
            painter.setBrush(color)
            painter.drawPath(path)
            return

        start_angle = 0.0
        colors = _generate_palette(len(self._values_by_day), self.palette())

        for (day, value), color in zip(self._values_by_day, colors):
            span_angle = 360.0 * (value / total)
            outer = QtCore.QRectF(
                cx - radius_outer,
                cy - radius_outer,
                2 * radius_outer,
                2 * radius_outer,
            )
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawPie(
                outer,
                int(start_angle * 16),
                int(span_angle * 16),
            )
            start_angle += span_angle

        # Cut inner circle to create donut
        painter.setBrush(self.palette().window().color())
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        inner = QtCore.QRectF(
            cx - radius_inner,
            cy - radius_inner,
            2 * radius_inner,
            2 * radius_inner,
        )
        painter.drawEllipse(inner)


def _generate_palette(count: int, palette: QtGui.QPalette) -> list[QtGui.QColor]:
    base = palette.highlight().color()
    colors: list[QtGui.QColor] = []
    for index in range(max(count, 1)):
        factor = 0.5 + 0.5 * (index / max(count - 1, 1))
        color = QtGui.QColor(base)
        color.setHsv(
            color.hue(),
            int(color.saturation() * (0.5 + 0.5 * factor)),
            int(color.value() * (0.7 + 0.3 * factor)),
        )
        colors.append(color)
    return colors


class DayColumnWidget(QtWidgets.QWidget):
    """Column showing work sessions for a single day as a vertical timeline."""

    def __init__(
        self,
        day: date,
        sessions: list[WorkSession],
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        title_label = QtWidgets.QLabel(day.strftime("%a %d %b"))
        title_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter)
        bold_font = title_label.font()
        bold_font.setBold(True)
        title_label.setFont(bold_font)
        layout.addWidget(title_label)

        timeline_widget = QtWidgets.QWidget(self)
        timeline_layout = QtWidgets.QVBoxLayout(timeline_widget)
        timeline_layout.setContentsMargins(4, 4, 4, 4)
        timeline_layout.setSpacing(0)

        if not sessions:
            placeholder = QtWidgets.QLabel("No work sessions")
            placeholder.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            placeholder.setStyleSheet("color: palette(mid);")
            timeline_layout.addStretch(1)
            timeline_layout.addWidget(placeholder)
            timeline_layout.addStretch(1)
        else:
            self._build_timeline(timeline_layout, sessions)

        layout.addWidget(timeline_widget, 1)

        # Daily summary strip
        total_sec = sum(session.duration_sec for session in sessions)
        work_count = len(sessions)
        focus_values: list[int] = []
        for session in sessions:
            if (
                session.check_in is not None
                and session.check_in.focus_rating is not None
            ):
                focus_values.append(session.check_in.focus_rating)
        avg_focus = (sum(focus_values) / len(focus_values)) if focus_values else None
        summary_parts: list[str] = []
        summary_parts.append(f"{work_count} work sessions")
        summary_parts.append(f"{total_sec // 60} min total")
        if avg_focus is not None:
            summary_parts.append(f"avg focus {avg_focus:.1f}")
        summary_label = QtWidgets.QLabel(" · ".join(summary_parts))
        summary_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter)
        summary_label.setStyleSheet("color: palette(mid); font-size: 11px;")
        layout.addWidget(summary_label)

    def _build_timeline(
        self, layout: QtWidgets.QVBoxLayout, sessions: list[WorkSession]
    ) -> None:
        sessions = sorted(sessions, key=lambda s: s.start)
        day_start_time = min(s.start for s in sessions)
        day_end_time = max(s.end for s in sessions)

        # Time range zoom: show only the active span.
        span_minutes = max(
            1,
            int((day_end_time - day_start_time).total_seconds() // 60),
        )
        pixels_per_minute = 1.0  # 1px per minute

        cursor_time = day_start_time
        for session in sessions:
            gap_minutes = int(
                max(
                    0,
                    (session.start - cursor_time).total_seconds() // 60,
                )
            )
            if gap_minutes:
                layout.addSpacing(int(gap_minutes * pixels_per_minute))

            duration_minutes = max(
                1,
                int((session.end - session.start).total_seconds() // 60),
            )
            block_height = int(duration_minutes * pixels_per_minute)
            block = self._make_session_block(session, block_height)
            layout.addWidget(block)
            cursor_time = session.end

        # Fill remaining space
        layout.addStretch(1)

    def _make_session_block(
        self,
        session: WorkSession,
        height: int,
    ) -> QtWidgets.QFrame:
        block = QtWidgets.QFrame(self)
        block.setFrameShape(QtWidgets.QFrame.Shape.Panel)
        block.setFrameShadow(QtWidgets.QFrame.Shadow.Raised)
        block.setMinimumHeight(height)
        block.setStyleSheet("""
            QFrame {
                background-color: #4CAF50;
                border-radius: 4px;
            }
            """)
        layout = QtWidgets.QVBoxLayout(block)
        layout.setContentsMargins(6, 4, 6, 4)

        start_str = session.start.strftime("%H:%M")
        end_str = session.end.strftime("%H:%M")
        title = QtWidgets.QLabel(f"{start_str} – {end_str}")
        title.setStyleSheet("color: white; font-weight: 600;")
        layout.addWidget(title)

        if session.check_in is not None and session.check_in.focus_rating is not None:
            stars = "★" * session.check_in.focus_rating
            focus_label = QtWidgets.QLabel(stars)
            focus_label.setStyleSheet("color: #FFEB3B;")
            layout.addWidget(focus_label)

        # Hover tooltip with full details
        tooltip_lines = [
            f"Start: {start_str}",
            f"End: {end_str}",
            f"Duration: {session.duration_sec // 60} min",
        ]
        if session.check_in is not None:
            ci = session.check_in
            if ci.prompt:
                tooltip_lines.append(f"Prompt: {ci.prompt}")
            if ci.answer:
                tooltip_lines.append(f"Answer: {ci.answer}")
            if ci.focus_rating is not None:
                tooltip_lines.append(f"Focus rating: {ci.focus_rating}")
            if ci.exercise_name:
                reps = ci.exercise_rep_count or 0
                tooltip_lines.append(f"Exercise: {ci.exercise_name} ({reps} reps)")
        block.setToolTip("\n".join(tooltip_lines))
        return block


class CalendarContainer(QtWidgets.QScrollArea):
    """Scrollable container that holds day columns for the current view."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self._content = QtWidgets.QWidget(self)
        self._layout = QtWidgets.QHBoxLayout(self._content)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self._layout.setSpacing(12)
        self._layout.addStretch(1)
        self.setWidget(self._content)

    def set_days(
        self,
        visible_range: VisibleRange,
        data: MetricsData,
    ) -> None:
        # Clear existing columns
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        by_day = data.work_sessions_by_day()
        day = visible_range.start
        while day <= visible_range.end:
            sessions = by_day.get(day, [])
            column = DayColumnWidget(day, sessions, self._content)
            self._layout.addWidget(column)
            day += timedelta(days=1)

        self._layout.addStretch(1)


class FocusTrendWidget(QtWidgets.QWidget):
    """Minimal line chart for average daily focus rating."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._dates: list[date] = []
        self._values: list[float] = []
        self.setMinimumHeight(120)

    def set_data(self, dates: list[date], values: list[float]) -> None:
        if len(dates) != len(values):
            dates = []
            values = []
        self._dates = dates
        self._values = values
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)

        if not self._dates or not self._values:
            return

        rect = self.rect().adjusted(8, 8, -8, -8)
        if rect.width() <= 0 or rect.height() <= 0:
            return

        min_val = min(self._values)
        max_val = max(self._values)
        if min_val == max_val:
            min_val -= 0.5
            max_val += 0.5

        span_x = max(1, len(self._dates) - 1)
        span_y = max_val - min_val

        points: list[QtCore.QPointF] = []
        for index, value in enumerate(self._values):
            x = rect.left() + rect.width() * (index / span_x)
            y_ratio = (value - min_val) / span_y
            y = rect.bottom() - rect.height() * y_ratio
            points.append(QtCore.QPointF(x, y))

        pen = QtGui.QPen(self.palette().highlight().color(), 2)
        painter.setPen(pen)
        for i in range(1, len(points)):
            painter.drawLine(points[i - 1], points[i])

        # Draw points
        painter.setBrush(self.palette().highlight().color())
        for point in points:
            painter.drawEllipse(point, 3, 3)
