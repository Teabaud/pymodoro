from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Sequence

from loguru import logger
from PySide6 import QtCore, QtGui, QtWidgets

from pymodoro.metrics_io import (
    CheckInRecord,
    SessionBlock,
    SessionRecord,
    read_records,
)
from pymodoro.settings import AppSettings

# ---------------------------------------------------------------------------
# Configurable constants (§3.9)
# ---------------------------------------------------------------------------

CALENDAR_CONSTANTS = {
    "CARD_MIN_HEIGHT_PX": 6,
    "CARD_LABEL_FULL_HEIGHT_PX": 40,
    "CARD_LABEL_COMPACT_HEIGHT_PX": 20,
    "CHECKIN_WINDOW_MINUTES": 15,
    "DEFAULT_RANGE_START": time(9, 0),
    "DEFAULT_RANGE_STOP": time(20, 0),
    "MIN_RANGE_START": time(9, 0),
    "MIN_RANGE_STOP": time(20, 0),
    "AUTOFIT_PADDING_MINUTES": 30,
    "CURRENT_TIME_COLOR": "#eb4034",
}

CC = CALENDAR_CONSTANTS  # shorthand

# ---------------------------------------------------------------------------
# Layer 2 — SessionBlockBuilder
# ---------------------------------------------------------------------------


def build_session_blocks(
    records: Sequence[SessionRecord | CheckInRecord],
) -> list[SessionBlock]:
    """Build Work-only SessionBlocks with associated check-ins, sorted by start."""
    sessions: list[SessionRecord] = []
    check_ins: list[CheckInRecord] = []
    for r in records:
        if isinstance(r, SessionRecord):
            sessions.append(r)
        elif isinstance(r, CheckInRecord):
            check_ins.append(r)

    # Build blocks for Work sessions only
    blocks: list[SessionBlock] = []
    for s in sessions:
        if s.session_type != "Work":
            continue
        blocks.append(
            SessionBlock(
                start=s.start_timestamp,
                end=s.end_timestamp,
                session_type=s.session_type,
            )
        )

    blocks.sort(key=lambda b: b.start)

    # Warn on overlapping windows
    for i in range(len(blocks) - 1):
        if blocks[i].end > blocks[i + 1].start:
            logger.warning(
                "Overlapping session blocks detected: {} and {}",
                blocks[i],
                blocks[i + 1],
            )

    # Associate check-ins
    window = timedelta(minutes=CC["CHECKIN_WINDOW_MINUTES"])
    check_ins_sorted = sorted(check_ins, key=lambda c: c.timestamp)
    for ci in check_ins_sorted:
        best_block: SessionBlock | None = None
        best_dist: float | None = None
        for block in blocks:
            if block.start <= ci.timestamp <= block.end + window:
                dist = abs((ci.timestamp - block.end).total_seconds())
                if best_dist is None or dist < best_dist:
                    best_block = block
                    best_dist = dist
        if best_block is not None:
            best_block.check_ins.append(ci)
        else:
            logger.debug("Orphaned check-in at {}", ci.timestamp)

    return blocks


# ---------------------------------------------------------------------------
# Layer 3 — CalendarDataProvider
# ---------------------------------------------------------------------------


@dataclass
class CalendarDataProvider:
    """Provides session blocks for a given week, converting UTC → local time."""

    _blocks: list[SessionBlock]

    def __init__(self, blocks: list[SessionBlock]) -> None:
        self._blocks = blocks

    def get_week(self, week_start: date) -> list[SessionBlock]:
        """Return session blocks for the 7-day window starting at week_start (local)."""
        local_tz = datetime.now().astimezone().tzinfo
        week_end = week_start + timedelta(days=7)

        result: list[SessionBlock] = []
        for b in self._blocks:
            local_start = b.start.astimezone(local_tz)
            local_end = b.end.astimezone(local_tz)
            day = local_start.date()
            if week_start <= day < week_end:
                local_check_ins = [
                    ci.model_copy(
                        update={"timestamp": ci.timestamp.astimezone(local_tz)}
                    )
                    for ci in b.check_ins
                ]
                result.append(
                    SessionBlock(
                        start=local_start,
                        end=local_end,
                        session_type=b.session_type,
                        check_ins=local_check_ins,
                    )
                )
        return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _week_start_for_date(d: date) -> date:
    """Return Monday of the week containing d, respecting locale via Qt."""
    qt_first = QtCore.QLocale().firstDayOfWeek()
    # Qt DayOfWeek: Monday=1 .. Sunday=7; Python isoweekday: Monday=1 .. Sunday=7
    first_iso = qt_first.value
    diff = (d.isoweekday() - first_iso) % 7
    return d - timedelta(days=diff)


def _time_to_minutes(t: time) -> float:
    return t.hour * 60 + t.minute + t.second / 60


def _dt_to_minutes(dt: datetime) -> float:
    return dt.hour * 60 + dt.minute + dt.second / 60


# ---------------------------------------------------------------------------
# QGraphicsScene items
# ---------------------------------------------------------------------------


class SessionCardItem(QtWidgets.QGraphicsRectItem):
    """A session block rendered as a rounded-rect card."""

    def __init__(
        self,
        block: SessionBlock,
        x: float,
        y: float,
        w: float,
        h: float,
        parent: QtWidgets.QGraphicsItem | None = None,
    ) -> None:
        super().__init__(x, y, w, h, parent)
        self.block = block
        palette = QtWidgets.QApplication.palette()
        self._base_color = palette.color(QtGui.QPalette.ColorRole.Highlight)
        self._text_color = palette.color(QtGui.QPalette.ColorRole.HighlightedText)
        self._hover = False
        self.setAcceptHoverEvents(True)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setPen(QtGui.QPen(QtCore.Qt.PenStyle.NoPen))
        self.setBrush(self._base_color)

    def paint(
        self,
        painter: QtGui.QPainter,
        option: QtWidgets.QStyleOptionGraphicsItem,
        widget: QtWidgets.QWidget | None = None,
    ) -> None:
        rect = self.rect()
        color = self._base_color.lighter(115) if self._hover else self._base_color
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawRoundedRect(rect, 4, 4)

        # Check-in dot
        if self.block.check_ins:
            dot_r = 3.5
            dot_x = rect.right() - dot_r - 4
            dot_y = rect.top() + dot_r + 4
            painter.setBrush(self._text_color)
            painter.drawEllipse(QtCore.QPointF(dot_x, dot_y), dot_r, dot_r)

        # Labels
        h = rect.height()
        painter.setPen(self._text_color)
        duration_min = (
            int(self.block.end.timestamp() - self.block.start.timestamp()) // 60
        )
        label = self.block.session_type
        if self.block.check_ins and self.block.check_ins[0].project:
            label = self.block.check_ins[0].project
        if h >= CC["CARD_LABEL_FULL_HEIGHT_PX"]:
            font = painter.font()
            font.setPixelSize(11)
            font.setBold(True)
            painter.setFont(font)
            text_rect = rect.adjusted(5, 3, -14, 0)
            painter.drawText(
                text_rect,
                QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop,
                label,
            )
            font.setBold(False)
            painter.setFont(font)
            painter.drawText(
                text_rect.adjusted(0, 14, 0, 0),
                QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop,
                f"{duration_min}m",
            )
        elif h >= CC["CARD_LABEL_COMPACT_HEIGHT_PX"]:
            font = painter.font()
            font.setPixelSize(10)
            painter.setFont(font)
            painter.drawText(
                rect.adjusted(4, 1, -4, -1),
                QtCore.Qt.AlignmentFlag.AlignLeft
                | QtCore.Qt.AlignmentFlag.AlignVCenter,
                f"{label} {duration_min}m",
            )

    def hoverEnterEvent(self, event: QtWidgets.QGraphicsSceneHoverEvent) -> None:
        self._hover = True
        self.update()

    def hoverLeaveEvent(self, event: QtWidgets.QGraphicsSceneHoverEvent) -> None:
        self._hover = False
        self.update()


class CurrentTimeIndicator(QtWidgets.QGraphicsLineItem):
    """Red horizontal line indicating the current time."""

    def __init__(self, parent: QtWidgets.QGraphicsItem | None = None) -> None:
        super().__init__(parent)
        color = QtGui.QColor(CC["CURRENT_TIME_COLOR"])
        pen = QtGui.QPen(color, 2)
        self.setPen(pen)
        self._dot = QtWidgets.QGraphicsEllipseItem(-3, -3, 6, 6, self)
        self._dot.setBrush(color)
        self._dot.setPen(QtGui.QPen(QtCore.Qt.PenStyle.NoPen))

    def setLine(self, *args: float) -> None:  # type: ignore[override]
        super().setLine(*args)
        line = self.line()
        self._dot.setPos(line.p1().x(), line.p1().y())


# ---------------------------------------------------------------------------
# CalendarGridView — the main graphics-based calendar widget
# ---------------------------------------------------------------------------

# Layout constants
LEFT_MARGIN = 50  # width for hour labels
TOP_HEADER = 50  # height for day headers
HOUR_HEIGHT = 60  # pixels per hour


class _DayHeaderWidget(QtWidgets.QWidget):
    """Fixed header showing day abbreviations and numbers, aligned with grid columns."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._week_start: date = date.today()
        self._day_count = 7
        self._left_margin = LEFT_MARGIN
        self.setFixedHeight(TOP_HEADER)

    def set_week(self, week_start: date) -> None:
        self._week_start = week_start
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        w = self.width()
        col_w = (w - self._left_margin) / self._day_count

        palette = QtWidgets.QApplication.palette()
        text_color = palette.color(QtGui.QPalette.ColorRole.WindowText)
        today = date.today()

        for i in range(self._day_count):
            d = self._week_start + timedelta(days=i)
            x = self._left_margin + i * col_w
            is_today = d == today

            # Day abbreviation
            abbr = d.strftime("%a").upper()
            abbr_font = QtGui.QFont(painter.font())
            abbr_font.setPixelSize(11)
            abbr_font.setBold(is_today)
            painter.setFont(abbr_font)
            abbr_color = (
                palette.color(QtGui.QPalette.ColorRole.Highlight)
                if is_today
                else text_color
            )
            painter.setPen(abbr_color)
            abbr_rect = painter.fontMetrics().boundingRect(abbr)
            abbr_x = x + col_w / 2 - abbr_rect.width() / 2
            painter.drawText(int(abbr_x), 16, abbr)

            # Day number
            day_str = str(d.day)
            day_font = QtGui.QFont(painter.font())
            day_font.setPixelSize(14)
            day_font.setBold(True)
            painter.setFont(day_font)
            fm = painter.fontMetrics()
            day_br = fm.boundingRect(day_str)
            cx = x + col_w / 2
            cy = 34

            if is_today:
                circle_r = max(day_br.width(), day_br.height()) / 2 + 4
                painter.setPen(QtCore.Qt.PenStyle.NoPen)
                painter.setBrush(palette.color(QtGui.QPalette.ColorRole.Highlight))
                painter.drawEllipse(QtCore.QPointF(cx, cy), circle_r, circle_r)
                painter.setPen(QtGui.QColor("white"))
                painter.drawText(
                    int(cx - day_br.width() / 2),
                    int(cy + day_br.height() / 2 - fm.descent()),
                    day_str,
                )
            else:
                is_other_month = d.month != today.month
                c = QtGui.QColor(text_color)
                if is_other_month:
                    c.setAlphaF(0.4)
                painter.setPen(c)
                painter.drawText(
                    int(cx - day_br.width() / 2),
                    int(cy + day_br.height() / 2 - fm.descent()),
                    day_str,
                )

        painter.end()


class CalendarGridView(QtWidgets.QWidget):
    """Weekly calendar grid rendered via QGraphicsScene/QGraphicsView."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._blocks: list[SessionBlock] = []
        self._range_start_min: float = _time_to_minutes(CC["DEFAULT_RANGE_START"])
        self._range_end_min: float = _time_to_minutes(CC["DEFAULT_RANGE_STOP"])
        self._week_start: date = date.today()
        self._day_count = 7
        self._active_tooltip: _SessionTooltip | None = None
        self._col_w: float = 0.0  # Initialized in _rebuild_scene
        self._grid_h: float = 0.0  # Initialized in _rebuild_scene

        self._header = _DayHeaderWidget(self)
        self._scene = QtWidgets.QGraphicsScene(self)
        self._view = QtWidgets.QGraphicsView(self._scene, self)
        self._view.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop
        )
        self._view.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._view.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        self._view.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self._view.setStyleSheet("background: transparent;")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._header)
        layout.addWidget(self._view)

        # Current-time timer
        self._time_indicator: CurrentTimeIndicator | None = None
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._update_time_indicator)
        self._timer.start(60_000)

        # Install event filter to dismiss tooltip on window deactivation
        app = QtWidgets.QApplication.instance()
        if app:
            app.installEventFilter(self)

    # ---- Public API -------------------------------------------------------

    def set_data(self, blocks: list[SessionBlock], week_start: date) -> None:
        self._blocks = blocks
        self._week_start = week_start
        self._header.set_week(week_start)
        self._compute_visible_range()
        self._rebuild_scene()

    # ---- Visible range auto-fit (§3.5) ------------------------------------

    def _compute_visible_range(self) -> None:
        if not self._blocks:
            self._range_start_min = _time_to_minutes(CC["DEFAULT_RANGE_START"])
            self._range_end_min = _time_to_minutes(CC["DEFAULT_RANGE_STOP"])
            return

        earliest = min(_dt_to_minutes(b.start) for b in self._blocks)
        latest = max(_dt_to_minutes(b.end) for b in self._blocks)
        pad = CC["AUTOFIT_PADDING_MINUTES"]

        start = math.floor(earliest / 60) * 60 - pad  # floor to hour then pad
        end = math.ceil(latest / 60) * 60 + pad  # ceil to hour then pad

        min_start = _time_to_minutes(CC["MIN_RANGE_START"])
        min_stop = _time_to_minutes(CC["MIN_RANGE_STOP"])
        start = min(start, min_start)
        end = max(end, min_stop)

        start = max(start, 0)
        end = min(end, 1440)

        self._range_start_min = start
        self._range_end_min = end

    # ---- Scene construction -----------------------------------------------

    def _rebuild_scene(self) -> None:
        self._dismiss_tooltip()
        self._scene.clear()
        self._time_indicator = None

        view_w = self._view.viewport().width()
        if view_w < 100:
            view_w = 800
        col_w = (view_w - LEFT_MARGIN) / self._day_count
        range_hours = (self._range_end_min - self._range_start_min) / 60
        grid_h = range_hours * HOUR_HEIGHT

        self._scene.setSceneRect(0, 0, view_w, grid_h)
        self._col_w = col_w
        self._grid_h = grid_h

        palette = QtWidgets.QApplication.palette()
        text_color = palette.color(QtGui.QPalette.ColorRole.WindowText)
        line_color = palette.color(QtGui.QPalette.ColorRole.Mid)
        today = date.today()

        # --- Grid area ---

        # Today column tint
        for i in range(self._day_count):
            d = self._week_start + timedelta(days=i)
            if d == today:
                x = LEFT_MARGIN + i * col_w
                tint = QtGui.QColor(palette.color(QtGui.QPalette.ColorRole.Highlight))
                tint.setAlphaF(0.06)
                self._scene.addRect(
                    x,
                    0,
                    col_w,
                    grid_h,
                    QtGui.QPen(QtCore.Qt.PenStyle.NoPen),
                    tint,
                )
                break

        # Hour lines and labels
        start_hour = int(self._range_start_min // 60)
        end_hour = int(math.ceil(self._range_end_min / 60))
        for h in range(start_hour, end_hour + 1):
            y = (h * 60 - self._range_start_min) / 60 * HOUR_HEIGHT
            # Hour line
            pen = QtGui.QPen(line_color, 1)
            self._scene.addLine(LEFT_MARGIN, y, view_w, y, pen)
            # Hour label
            label = self._scene.addText(f"{h:02d}:00")
            label_font = label.font()
            label_font.setPixelSize(10)
            label.setFont(label_font)
            label.setDefaultTextColor(text_color)
            label.setPos(4, y - 7)

            # Half-hour dashed line
            if h < end_hour:
                half_y = y + HOUR_HEIGHT / 2
                dash_pen = QtGui.QPen(line_color, 1, QtCore.Qt.PenStyle.DashLine)
                self._scene.addLine(LEFT_MARGIN, half_y, view_w, half_y, dash_pen)

        # Column separators
        for i in range(self._day_count + 1):
            x = LEFT_MARGIN + i * col_w
            sep_pen = QtGui.QPen(line_color, 1)
            sep_pen.setColor(
                QtGui.QColor(
                    line_color.red(), line_color.green(), line_color.blue(), 60
                )
            )
            self._scene.addLine(x, 0, x, grid_h, sep_pen)

        # --- Session cards ---
        if not self._blocks:
            empty_text = self._scene.addText("No sessions recorded this week")
            ef = empty_text.font()
            ef.setPixelSize(14)
            empty_text.setFont(ef)
            empty_text.setDefaultTextColor(text_color)
            tw = empty_text.boundingRect().width()
            empty_text.setPos(
                (view_w - tw) / 2,
                grid_h / 2 - 10,
            )
        else:
            for block in self._blocks:
                day_index = (block.start.date() - self._week_start).days
                if day_index < 0 or day_index >= self._day_count:
                    continue
                x = LEFT_MARGIN + day_index * col_w + 2
                w = col_w - 4

                block_start_min = _dt_to_minutes(block.start)
                block_end_min = _dt_to_minutes(block.end)

                # Clip to visible range
                block_start_min = max(block_start_min, self._range_start_min)
                block_end_min = min(block_end_min, self._range_end_min)

                y = (block_start_min - self._range_start_min) / 60 * HOUR_HEIGHT
                h = max(
                    CC["CARD_MIN_HEIGHT_PX"],
                    (block_end_min - block_start_min) / 60 * HOUR_HEIGHT,
                )

                card = SessionCardItem(block, x, y, w, h)
                card.setZValue(10)
                self._scene.addItem(card)

        # --- Current time indicator ---
        self._add_time_indicator()

    def _add_time_indicator(self) -> None:
        today = date.today()
        day_index = (today - self._week_start).days
        if day_index < 0 or day_index >= self._day_count:
            return
        now_min = _dt_to_minutes(datetime.now())
        if now_min < self._range_start_min or now_min > self._range_end_min:
            return

        x = LEFT_MARGIN + day_index * self._col_w
        y = (now_min - self._range_start_min) / 60 * HOUR_HEIGHT

        indicator = CurrentTimeIndicator()
        indicator.setLine(x, y, x + self._col_w, y)
        indicator.setZValue(20)
        self._scene.addItem(indicator)
        self._time_indicator = indicator

    def _update_time_indicator(self) -> None:
        if self._col_w == 0:  # Scene not yet built
            return

        today = date.today()
        day_index = (today - self._week_start).days
        if day_index < 0 or day_index >= self._day_count:
            if self._time_indicator:
                self._scene.removeItem(self._time_indicator)
                self._time_indicator = None
            return

        now_min = _dt_to_minutes(datetime.now())
        if now_min < self._range_start_min or now_min > self._range_end_min:
            if self._time_indicator:
                self._scene.removeItem(self._time_indicator)
                self._time_indicator = None
            return

        if self._time_indicator is None:
            self._add_time_indicator()
        else:
            x = LEFT_MARGIN + day_index * self._col_w
            y = (now_min - self._range_start_min) / 60 * HOUR_HEIGHT
            self._time_indicator.setLine(x, y, x + self._col_w, y)

    # ---- Tooltip ----------------------------------------------------------

    def _dismiss_tooltip(self) -> None:
        if self._active_tooltip:
            self._active_tooltip.close()
            self._active_tooltip.deleteLater()
            self._active_tooltip = None

    def _show_tooltip_for(self, block: SessionBlock, global_pos: QtCore.QPoint) -> None:
        self._dismiss_tooltip()
        self._active_tooltip = _SessionTooltip(block, self)
        self._active_tooltip.show_at(global_pos)

    # ---- Events -----------------------------------------------------------

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if event.type() == QtCore.QEvent.Type.WindowDeactivate:
            self._dismiss_tooltip()
        return False

    def hideEvent(self, event: QtGui.QHideEvent) -> None:
        self._dismiss_tooltip()
        super().hideEvent(event)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        if self._blocks or self._scene.items():
            self._rebuild_scene()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        scene_pos = self._view.mapToScene(
            self._view.mapFromGlobal(event.globalPosition().toPoint())
        )
        items = self._scene.items(scene_pos)
        card = next((i for i in items if isinstance(i, SessionCardItem)), None)
        if card:
            self._show_tooltip_for(card.block, event.globalPosition().toPoint())
        else:
            self._dismiss_tooltip()
        super().mousePressEvent(event)


# ---------------------------------------------------------------------------
# Session tooltip popup
# ---------------------------------------------------------------------------


class _SessionTooltip(QtWidgets.QFrame):
    def __init__(self, block: SessionBlock, parent: QtWidgets.QWidget) -> None:
        super().__init__(parent, QtCore.Qt.WindowType.ToolTip)
        self.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            "QFrame { border: 1px solid palette(mid); "
            "border-radius: 6px; padding: 8px; }"
            "QLabel { border: none; padding: 0; }"
        )
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(4)

        disabled_text_color = self.palette().color(
            QtGui.QPalette.ColorGroup.Disabled,
            QtGui.QPalette.ColorRole.WindowText,
        )

        duration_min = int((block.end - block.start).total_seconds()) // 60
        start_str = block.start.strftime("%H:%M")
        end_str = block.end.strftime("%H:%M")

        header_parts: list[str] = []
        if block.check_ins:
            ci = block.check_ins[0]
            if ci.project:
                header_parts.append(f"<b>{ci.project}</b>")
            if ci.activity:
                header_parts.append(ci.activity.capitalize())
            if ci.leverage:
                header_parts.append(f"{ci.leverage.capitalize()} leverage")
        if not header_parts:
            header_parts.append(f"<b>{block.session_type}</b>")
        header = QtWidgets.QLabel(f"{' · '.join(header_parts)} — {duration_min} min")
        header.setStyleSheet("font-size: 13px;")
        layout.addWidget(header)

        time_label = QtWidgets.QLabel(f"{start_str} – {end_str}")
        time_label.setStyleSheet(
            f"font-size: 12px; color: {disabled_text_color.name()};"
        )
        layout.addWidget(time_label)

        if block.check_ins:
            for ci in block.check_ins:
                layout.addWidget(self._make_separator())
                prompt_lbl = QtWidgets.QLabel(f"<i>{ci.prompt}</i>")
                prompt_lbl.setWordWrap(True)
                prompt_lbl.setStyleSheet("font-size: 11px;")
                layout.addWidget(prompt_lbl)
                answer_lbl = QtWidgets.QLabel(ci.answer)
                answer_lbl.setWordWrap(True)
                answer_lbl.setStyleSheet("font-size: 11px;")
                layout.addWidget(answer_lbl)
                extras: list[str] = []
                if ci.focus_rating is not None:
                    extras.append(f"Focus: {ci.focus_rating}/5")
                if ci.exercise_name:
                    ex = ci.exercise_name
                    if ci.exercise_rep_count is not None:
                        ex += f" ×{ci.exercise_rep_count}"
                    extras.append(ex)
                if extras:
                    extra_lbl = QtWidgets.QLabel(" · ".join(extras))
                    extra_lbl.setStyleSheet(
                        f"font-size: 10px; color: {disabled_text_color.name()};"
                    )
                    layout.addWidget(extra_lbl)
        else:
            layout.addWidget(self._make_separator())
            no_ci = QtWidgets.QLabel("No check-in recorded.")
            no_ci.setStyleSheet(
                f"font-size: 11px; color: {disabled_text_color.name()};"
            )
            layout.addWidget(no_ci)

        self.adjustSize()

    def _make_separator(self) -> QtWidgets.QFrame:
        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        sep.setStyleSheet(
            "color: palette(mid); border: none; max-height: 1px; background: palette(mid);"
        )
        return sep

    def show_at(self, global_pos: QtCore.QPoint) -> None:
        screen = QtWidgets.QApplication.screenAt(global_pos)
        if screen:
            geo = screen.availableGeometry()
            x = min(global_pos.x() + 8, geo.right() - self.width())
            y = min(global_pos.y() + 8, geo.bottom() - self.height())
            self.move(max(x, geo.left()), max(y, geo.top()))
        else:
            self.move(global_pos)
        self.show()


# ---------------------------------------------------------------------------
# Navigation bar
# ---------------------------------------------------------------------------


class _NavBar(QtWidgets.QWidget):
    weekChanged = QtCore.Signal(date)  # emits the new week_start

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._week_start: date = _week_start_for_date(date.today())

        self._prev_btn = QtWidgets.QPushButton("◀")
        self._next_btn = QtWidgets.QPushButton("▶")
        self._today_btn = QtWidgets.QPushButton("Today")
        self._range_label = QtWidgets.QLabel()
        self._week_label = QtWidgets.QLabel()

        for btn in (self._prev_btn, self._next_btn, self._today_btn):
            btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            btn.setFlat(True)

        self._range_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        self._week_label.setStyleSheet(
            "font-size: 14px; background-color: palette(mid);"
            "border-radius: 6px; padding: 4px 6px;"
        )

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.addWidget(self._prev_btn)
        layout.addWidget(self._range_label)
        layout.addWidget(self._next_btn)
        layout.addWidget(self._week_label)
        layout.addStretch()
        layout.addWidget(self._today_btn)

        self._prev_btn.clicked.connect(lambda: self._navigate(-1))
        self._next_btn.clicked.connect(lambda: self._navigate(1))
        self._today_btn.clicked.connect(self._go_today)

        self._update_labels()

    @property
    def week_start(self) -> date:
        return self._week_start

    def _navigate(self, direction: int) -> None:
        self._week_start += timedelta(weeks=direction)
        self._update_labels()
        self.weekChanged.emit(self._week_start)

    def _go_today(self) -> None:
        self._week_start = _week_start_for_date(date.today())
        self._update_labels()
        self.weekChanged.emit(self._week_start)

    def _update_labels(self) -> None:
        end = self._week_start + timedelta(days=6)
        if self._week_start.month == end.month:
            range_str = f"{self._week_start.day} – {end.day} {end.strftime('%b %Y')}"
        else:
            range_str = (
                f"{self._week_start.day} {self._week_start.strftime('%b')} – "
                f"{end.day} {end.strftime('%b %Y')}"
            )
        self._range_label.setText(range_str)
        iso_week = self._week_start.isocalendar()[1]
        self._week_label.setText(f"Week {iso_week}")


# ---------------------------------------------------------------------------
# CalendarPage — top-level page widget
# ---------------------------------------------------------------------------


class CalendarPage(QtWidgets.QWidget):
    def __init__(
        self,
        settings: AppSettings,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._provider: CalendarDataProvider | None = None

        self._nav = _NavBar(self)
        self._grid = CalendarGridView(self)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.addWidget(self._nav)
        layout.addWidget(self._grid, 1)

        self._nav.weekChanged.connect(self._on_week_changed)

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        super().showEvent(event)
        self._load_data()
        self._refresh_grid()

    def _load_data(self) -> None:
        records = read_records(self._settings.metrics_log_path)
        blocks = build_session_blocks(records)
        self._provider = CalendarDataProvider(blocks)

    def _refresh_grid(self) -> None:
        if self._provider is None:
            return
        week_start = self._nav.week_start
        blocks = self._provider.get_week(week_start)
        self._grid.set_data(blocks, week_start)

    def _on_week_changed(self, week_start: date) -> None:
        self._refresh_grid()
