"""
Widgets for the Roohvi dashboard look (calm dusk palette, sage accent).

Everything here is plain Qt painting (no images, no external assets): translucent
navy cards with a blue edge, vector icons, ring gauges, a procedural landscape for
the quote cards, and a large mic button. ui.py wires them to the assistant.

    zehan_ui.init(C, qf)   must be called once, with ui.py's palette class and font
                           factory, before any widget is created.
"""
from __future__ import annotations

import math
import time

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (QBrush, QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPainterPath,
                         QPen, QPolygonF, QRadialGradient)
from PyQt6.QtWidgets import QAbstractButton, QLabel, QLineEdit, QWidget

C = None            # palette (ui.C)
qf = None           # font factory (ui._qf)


def init(palette, font_factory) -> None:
    global C, qf
    C, qf = palette, font_factory


def col(hexstr: str, a: int = 255) -> QColor:
    c = QColor(hexstr)
    c.setAlpha(a)
    return c


# ── vector icons (24 x 24 grid, drawn as strokes) ────────────────────────────
def _pts(*xy):
    return QPolygonF([QPointF(x, y) for x, y in zip(xy[0::2], xy[1::2])])


def draw_icon(p: QPainter, name: str, r: QRectF, color, width: float = 1.7, fill=None) -> None:
    """Draw icon `name` centred in rect r."""
    p.save()
    p.translate(r.center())
    s = min(r.width(), r.height()) / 24.0
    p.scale(s, s)
    p.translate(-12, -12)
    pen = QPen(QColor(color), width / 1.0)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    R = QRectF
    if name == "home":
        p.drawPolyline(_pts(3, 11, 12, 3, 21, 11))
        p.drawPolyline(_pts(5.5, 9.5, 5.5, 20, 18.5, 20, 18.5, 9.5))
        p.drawPolyline(_pts(10, 20, 10, 14, 14, 14, 14, 20))
    elif name == "chat":
        p.drawRoundedRect(R(3.5, 4, 17, 12.5), 3.5, 3.5)
        p.drawPolyline(_pts(8, 16.5, 8, 20.5, 12, 16.5))
    elif name == "mic":
        p.drawRoundedRect(R(9, 3, 6, 11), 3, 3)
        p.drawArc(R(5.5, 6.5, 13, 10), 180 * 16, 180 * 16)
        p.drawLine(QPointF(12, 16.5), QPointF(12, 20.5))
        p.drawLine(QPointF(8.5, 20.5), QPointF(15.5, 20.5))
    elif name == "grid":
        for x, y in ((4, 4), (14, 4), (4, 14), (14, 14)):
            p.drawRoundedRect(R(x, y, 6, 6), 1.6, 1.6)
    elif name == "cube":
        p.drawPolygon(_pts(12, 3, 20, 7.5, 20, 16.5, 12, 21, 4, 16.5, 4, 7.5))
        p.drawPolyline(_pts(4, 7.5, 12, 12, 20, 7.5))
        p.drawLine(QPointF(12, 12), QPointF(12, 21))
    elif name == "folder":
        path = QPainterPath()
        path.moveTo(3.5, 7); path.lineTo(9, 7); path.lineTo(11, 9.2); path.lineTo(20.5, 9.2)
        path.lineTo(20.5, 19); path.lineTo(3.5, 19); path.closeSubpath()
        p.drawPath(path)
    elif name == "book":
        p.drawRoundedRect(R(3.5, 4, 17, 16), 2, 2)
        p.drawLine(QPointF(12, 4), QPointF(12, 20))
        p.drawLine(QPointF(6.5, 9), QPointF(9.5, 9)); p.drawLine(QPointF(6.5, 12), QPointF(9.5, 12))
        p.drawLine(QPointF(14.5, 9), QPointF(17.5, 9)); p.drawLine(QPointF(14.5, 12), QPointF(17.5, 12))
    elif name == "gear":
        p.drawEllipse(QPointF(12, 12), 3.2, 3.2)
        p.drawEllipse(QPointF(12, 12), 7.2, 7.2)
        for k in range(8):
            a = k * math.pi / 4
            p.drawLine(QPointF(12 + 7.2 * math.cos(a), 12 + 7.2 * math.sin(a)),
                       QPointF(12 + 9.6 * math.cos(a), 12 + 9.6 * math.sin(a)))
    elif name == "globe":
        p.drawEllipse(QPointF(12, 12), 8.5, 8.5)
        p.drawEllipse(QPointF(12, 12), 3.8, 8.5)
        p.drawLine(QPointF(3.5, 12), QPointF(20.5, 12))
        p.drawArc(R(5, 5.5, 14, 6), 0, 180 * 16); p.drawArc(R(5, 12.5, 14, 6), 180 * 16, 180 * 16)
    elif name == "notepad":
        p.drawRoundedRect(R(5, 3.5, 14, 17), 2, 2)
        for y in (9, 12.5, 16):
            p.drawLine(QPointF(8, y), QPointF(16, y))
    elif name == "calc":
        p.drawRoundedRect(R(5, 3.5, 14, 17), 2.2, 2.2)
        p.drawRect(R(8, 6.5, 8, 3))
        for x, y in ((8.6, 13), (12, 13), (15.4, 13), (8.6, 16.6), (12, 16.6), (15.4, 16.6)):
            p.drawPoint(QPointF(x, y))
    elif name == "calendar":
        p.drawRoundedRect(R(4, 5.5, 16, 14.5), 2.2, 2.2)
        p.drawLine(QPointF(4, 10), QPointF(20, 10))
        p.drawLine(QPointF(8.5, 3.5), QPointF(8.5, 7.5)); p.drawLine(QPointF(15.5, 3.5), QPointF(15.5, 7.5))
    elif name == "cloudsun":
        p.drawEllipse(QPointF(8.5, 8.5), 3, 3)
        p.drawLine(QPointF(8.5, 2.6), QPointF(8.5, 3.6)); p.drawLine(QPointF(2.8, 8.5), QPointF(3.8, 8.5))
        path = QPainterPath()
        path.moveTo(8, 19.5); path.cubicTo(3.5, 19.5, 3.5, 13.5, 8.5, 13.5)
        path.cubicTo(9, 10.5, 15.5, 10.5, 16, 14); path.cubicTo(20.5, 13.5, 21.5, 19.5, 17, 19.5); path.closeSubpath()
        p.drawPath(path)
    elif name == "play":
        p.drawRoundedRect(R(3, 5.5, 18, 13, ), 3.4, 3.4)
        p.setBrush(QBrush(QColor(color)))
        p.drawPolygon(_pts(10, 9.2, 15.4, 12, 10, 14.8))
    elif name == "wave":
        for i, (x, h) in enumerate(((4, 5), (8, 11), (12, 17), (16, 11), (20, 5))):
            p.drawLine(QPointF(x, 12 - h / 2), QPointF(x, 12 + h / 2))
    elif name == "user":
        p.drawEllipse(QPointF(12, 8.5), 3.8, 3.8)
        p.drawArc(R(4.5, 13.5, 15, 13), 0, 180 * 16)
    elif name == "send":
        p.setBrush(QBrush(QColor(color)))
        p.drawPolygon(_pts(3.5, 11.5, 20.5, 4, 14, 20.5, 11.5, 13.5))
    elif name == "attach":
        path = QPainterPath()
        path.moveTo(8, 12.5); path.lineTo(13.5, 7); path.cubicTo(15.5, 5, 18.5, 8, 16.5, 10)
        path.lineTo(9.5, 17); path.cubicTo(7, 19.5, 3.5, 16, 6, 13.5); path.lineTo(12.5, 7)
        p.drawPath(path)
    elif name == "chevron":
        p.drawPolyline(_pts(9, 5.5, 15.5, 12, 9, 18.5))
    elif name == "more":
        p.setBrush(QBrush(QColor(color)))
        for x in (5.5, 12, 18.5):
            p.drawEllipse(QPointF(x, 12), 1.6, 1.6)
    elif name == "code":
        p.drawPolyline(_pts(8.5, 7, 3.5, 12, 8.5, 17))
        p.drawPolyline(_pts(15.5, 7, 20.5, 12, 15.5, 17))
        p.drawLine(QPointF(13.5, 5.5), QPointF(10.5, 18.5))
    elif name == "stop":
        p.setBrush(QBrush(QColor(color)))
        p.drawRoundedRect(R(6.5, 6.5, 11, 11), 2, 2)
    elif name == "arrow":
        p.drawPolyline(_pts(4.5, 12, 19, 12)); p.drawPolyline(_pts(13.5, 6.5, 19, 12, 13.5, 17.5))
    p.restore()


# ── base card ────────────────────────────────────────────────────────────────
class Card(QWidget):
    """Soft dusk-coloured panel with a gentle sage edge."""

    def __init__(self, parent=None, radius: int = 20, alpha: int = 205):
        super().__init__(parent)
        self._radius = radius
        self._alpha = alpha
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def paint_frame(self, p: QPainter) -> QRectF:
        r = QRectF(self.rect()).adjusted(0.75, 0.75, -0.75, -0.75)
        g = QLinearGradient(r.topLeft(), r.bottomLeft())
        g.setColorAt(0.0, col("#222a3d", self._alpha))
        g.setColorAt(1.0, col("#161b29", self._alpha))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(g))
        p.drawRoundedRect(r, self._radius, self._radius)
        edge = QLinearGradient(r.topLeft(), r.bottomRight())
        edge.setColorAt(0.0, col("#5fc4ae", 150))
        edge.setColorAt(0.5, col("#3f8f82", 90))
        edge.setColorAt(1.0, col("#5fc4ae", 130))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QBrush(edge), 1.1))
        p.drawRoundedRect(r, self._radius, self._radius)
        return r

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.paint_frame(p)
        p.end()


def _elide(p: QPainter, text: str, width: float) -> str:
    return QFontMetrics(p.font()).elidedText(text, Qt.TextElideMode.ElideRight, int(max(10, width)))


def _title(p: QPainter, text: str, x: float, y: float, size: int = 12) -> None:
    p.setFont(qf(size, QFont.Weight.Bold))
    p.setPen(col(C.WHITE))
    p.drawText(QPointF(x, y), text)


# ── nav ──────────────────────────────────────────────────────────────────────
class NavButton(QAbstractButton):
    def __init__(self, icon: str, label: str, parent=None):
        super().__init__(parent)
        self._icon, self._label = icon, label
        self._collapsed = False
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hover = False
        self.setMouseTracking(True)

    def set_collapsed(self, on: bool) -> None:
        self._collapsed = on
        self.update()

    def enterEvent(self, e):                         # noqa: N802
        self._hover = True; self.update()

    def leaveEvent(self, e):                         # noqa: N802
        self._hover = False; self.update()

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        if self.isChecked():
            g = QLinearGradient(r.topLeft(), r.topRight())
            g.setColorAt(0, col("#5fc4ae")); g.setColorAt(1, col("#5fc4ae", 200))
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(g)); p.drawRoundedRect(r, 12, 12)
        elif self._hover:
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(col("#5fc4ae", 40)); p.drawRoundedRect(r, 12, 12)
        color = C.WHITE if (self.isChecked() or self._hover) else C.TEXT_MED
        icon_r = QRectF(r.left() + (r.width() - 24) / 2 if self._collapsed else r.left() + 16, r.center().y() - 12, 24, 24)
        draw_icon(p, self._icon, icon_r, color, 1.7)
        if not self._collapsed:
            p.setFont(qf(11, QFont.Weight.DemiBold if self.isChecked() else QFont.Weight.Normal))
            p.setPen(col(color))
            p.drawText(QRectF(r.left() + 52, r.top(), r.width() - 56, r.height()),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self._label)
        p.end()


# ── round / icon buttons ─────────────────────────────────────────────────────
class IconButton(QAbstractButton):
    def __init__(self, icon: str, size: int = 40, ring: bool = True, parent=None):
        super().__init__(parent)
        self._icon, self._ring = icon, ring
        self.setFixedSize(size, size)
        self.setCheckable(False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hover = False

    def enterEvent(self, e):                         # noqa: N802
        self._hover = True; self.update()

    def leaveEvent(self, e):                         # noqa: N802
        self._hover = False; self.update()

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        if self._ring:
            p.setPen(QPen(col("#5fc4ae", 150 if not self._hover else 230), 1.2))
            p.setBrush(col("#222a3d", 170) if not self.isChecked() else col("#5fc4ae", 200))
            p.drawEllipse(r)
        draw_icon(p, self._icon, r.adjusted(9, 9, -9, -9), C.WHITE if (self._hover or self.isChecked()) else C.TEXT_MED, 1.7)
        p.end()


class MicButton(QAbstractButton):
    """The big round microphone: glows while listening, turns rose when muted."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(66, 66)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.muted = False
        self.active = False          # speaking / thinking pulse
        self._t0 = time.monotonic()

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = QRectF(self.rect()).center()
        pulse = 0.5 + 0.5 * math.sin((time.monotonic() - self._t0) * 3.0)
        base = "#ff5d7e" if self.muted else "#5fc4ae"
        halo = QRadialGradient(c, 33)
        halo.setColorAt(0.55, col(base, int(70 + 60 * pulse) if not self.muted else 40))
        halo.setColorAt(1.0, col(base, 0))
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(halo)); p.drawEllipse(c, 33, 33)
        g = QRadialGradient(c - QPointF(6, 8), 40)
        g.setColorAt(0, col("#5fc4ae" if not self.muted else "#ff8aa2")); g.setColorAt(1, col("#3f8f82" if not self.muted else "#b8324f"))
        p.setPen(QPen(col("#9be3d0" if not self.muted else "#ffb0c0", 200), 1.4)); p.setBrush(QBrush(g))
        p.drawEllipse(c, 25, 25)
        draw_icon(p, "mic", QRectF(c.x() - 13, c.y() - 13, 26, 26), "#ffffff", 1.8)
        if self.muted:
            p.setPen(QPen(col("#ffffff", 230), 2.2)); p.drawLine(QPointF(c.x() - 12, c.y() + 12), QPointF(c.x() + 12, c.y() - 12))
        p.end()


class SendButton(QAbstractButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(46, 46)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        g = QLinearGradient(r.topLeft(), r.bottomRight())
        g.setColorAt(0, col("#5fc4ae")); g.setColorAt(1, col("#5fc4ae"))
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(g)); p.drawEllipse(r)
        draw_icon(p, "send", r.adjusted(11, 11, -11, -11), "#ffffff", 1.4)
        p.end()


# ── greeting ─────────────────────────────────────────────────────────────────
class GreetingCard(Card):
    def __init__(self, parent=None):
        super().__init__(parent, 20, 205)
        self.user = ""
        self.name = ""
        self.level = 0.0
        self._t0 = time.monotonic()

    def set_names(self, user: str, assistant: str) -> None:
        self.user, self.name = user, assistant
        self.update()

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.paint_frame(p)
        # waveform badge
        c = QPointF(r.left() + 52, r.center().y())
        g = QRadialGradient(c, 34)
        g.setColorAt(0, col("#5fc4ae", 90)); g.setColorAt(1, col("#5fc4ae", 20))
        p.setPen(QPen(col("#5fc4ae", 170), 1.2)); p.setBrush(QBrush(g)); p.drawEllipse(c, 31, 31)
        t = time.monotonic() - self._t0
        p.setPen(QPen(col("#9be3d0"), 3.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        for i, k in enumerate((-2, -1, 0, 1, 2)):
            amp = 0.35 + 0.65 * abs(math.sin(t * 2.4 + i * 0.9)) * (0.3 + self.level)
            h = (8 + 22 * (1 - abs(k) * 0.28)) * (0.55 + 0.45 * amp)
            p.drawLine(QPointF(c.x() + k * 8, c.y() - h / 2), QPointF(c.x() + k * 8, c.y() + h / 2))
        x = r.left() + 100
        p.setFont(qf(11)); p.setPen(col(C.TEXT_MED))
        p.drawText(QPointF(x, r.top() + 36), "Welcome,")
        p.setFont(qf(20, QFont.Weight.Bold)); p.setPen(col(C.WHITE))
        p.drawText(QPointF(x, r.top() + 66), _elide(p, (self.user or "friend"), r.width() - 110))
        p.setFont(qf(10)); p.setPen(col(C.TEXT_MED))
        p.drawText(QRectF(x, r.top() + 74, r.width() - 112, r.height() - 80),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
                   f"I'm {self.name or 'Roohvi'}, an AI companion. How are you today?")
        p.end()


# ── system status ────────────────────────────────────────────────────────────
class SystemCard(Card):
    """This week's self-reported check-ins. Plain averages, neutral colours, no
    'health score': the numbers are the user's own words, not a measurement."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.av = None          # {"mood":3.2,"energy":2.8,"stress":4.0} or None
        self.tracking = False

    def set_values(self, av, tracking: bool = False) -> None:
        self.av, self.tracking = av, bool(tracking)
        self.update()

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.paint_frame(p)
        _title(p, "This Week", r.left() + 18, r.top() + 30)
        top = r.top() + 44
        rowh = (r.bottom() - top - 26) / 3.0
        p.setPen(QPen(col("#3f8f82", 80), 1)); p.drawLine(QPointF(r.left() + 16, top - 4), QPointF(r.right() - 16, top - 4))
        rows = (("mood", "Mood"), ("energy", "Energy"), ("stress", "Stress"))
        for i, (key, label) in enumerate(rows):
            cy = top + rowh * i + rowh / 2
            d = min(rowh - 8, 46)
            ring = QRectF(r.left() + 18, cy - d / 2, d, d)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(col("#2a3348"), 4.2)); p.drawEllipse(ring.adjusted(2, 2, -2, -2))
            val = (self.av or {}).get(key)
            if val:
                grad = QLinearGradient(ring.topLeft(), ring.bottomRight())
                grad.setColorAt(0, col("#9be3d0")); grad.setColorAt(1, col("#5fc4ae"))
                pen = QPen(QBrush(grad), 4.2); pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                p.setPen(pen)
                p.drawArc(ring.adjusted(2, 2, -2, -2), 90 * 16, int(-(val / 5.0) * 360 * 16))
            p.setFont(qf(9, QFont.Weight.Bold)); p.setPen(col(C.WHITE))
            p.drawText(ring, Qt.AlignmentFlag.AlignCenter, f"{val:.1f}" if val else "-")
            x = ring.right() + 14
            p.setFont(qf(11, QFont.Weight.DemiBold)); p.setPen(col(C.WHITE))
            p.drawText(QPointF(x, cy - 3), label)
            p.setFont(qf(9)); p.setPen(col(C.TEXT_MED))
            note = ("avg of 5" if val else ("not enough yet" if self.tracking else "tracking is off"))
            p.drawText(QPointF(x, cy + 14), note)
            if i < 2:
                p.setPen(QPen(col("#3f8f82", 50), 1)); p.drawLine(QPointF(r.left() + 16, cy + rowh / 2), QPointF(r.right() - 16, cy + rowh / 2))
        p.setFont(qf(7)); p.setPen(col(C.TEXT_MED))
        p.drawText(QRectF(r.left() + 16, r.bottom() - 22, r.width() - 32, 16), Qt.AlignmentFlag.AlignLeft,
                   "Your own ratings, not medical")
        p.end()


# ── list-style cards (quick actions / try saying) ─────────────────────────────
class _RowCard(Card):
    picked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: list[tuple[str, str, str]] = []      # key, label, icon
        self._hover = -1
        self._rects: list[QRectF] = []
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseMoveEvent(self, e):                       # noqa: N802
        h = next((i for i, r in enumerate(self._rects) if r.contains(e.position())), -1)
        if h != self._hover:
            self._hover = h; self.update()

    def leaveEvent(self, e):                           # noqa: N802
        self._hover = -1; self.update()

    def mouseReleaseEvent(self, e):                    # noqa: N802
        for i, r in enumerate(self._rects):
            if r.contains(e.position()) and i < len(self._items):
                self.picked.emit(self._items[i][0])
                return


class QuickActionsCard(_RowCard):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = [("checkin", "Mood check-in", "calendar"), ("breathing", "Breathing", "wave"),
                       ("grounding", "Grounding", "cloudsun"), ("journal", "Journal prompt", "notepad"),
                       ("resources", "Get support", "book")]

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.paint_frame(p)
        _title(p, "Quick Actions", r.left() + 18, r.top() + 30)
        top = r.top() + 44
        n = len(self._items)
        rowh = (r.bottom() - top - 12) / n
        self._rects = []
        for i, (_k, label, icon) in enumerate(self._items):
            row = QRectF(r.left() + 12, top + rowh * i + 2, r.width() - 24, rowh - 6)
            self._rects.append(row)
            p.setPen(QPen(col("#3f8f82", 130 if i != self._hover else 230), 1.1))
            p.setBrush(col("#232b40", 200 if i != self._hover else 235))
            p.drawRoundedRect(row, 10, 10)
            draw_icon(p, icon, QRectF(row.left() + 10, row.center().y() - 11, 22, 22), C.WHITE, 1.6)
            p.setFont(qf(10)); p.setPen(col(C.WHITE))
            p.drawText(QRectF(row.left() + 44, row.top(), row.width() - 70, row.height()),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, label)
            draw_icon(p, "chevron", QRectF(row.right() - 28, row.center().y() - 8, 16, 16), C.TEXT_MED, 1.6)
        p.end()


class TrySayingCard(_RowCard):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.assistant = "Roohvi"
        self._rebuild()

    def _rebuild(self) -> None:
        a = self.assistant
        self._items = [(f"{a}, I'm feeling stressed", f"\u201cI'm feeling stressed\u201d", "chat"),
                       (f"{a}, let's do a breathing exercise", f"\u201cLet's do a breathing exercise\u201d", "wave"),
                       (f"{a}, I'd like a mood check-in", f"\u201cI'd like a mood check-in\u201d", "calendar"),
                       (f"{a}, I can't switch my thoughts off", f"\u201cI can't switch my thoughts off\u201d", "cloudsun"),
                       (f"{a}, where can I find a counsellor?", f"\u201cWhere can I find a counsellor?\u201d", "book")]
        self.update()

    def set_assistant(self, name: str) -> None:
        self.assistant = name or "Assistant"
        self._rebuild()

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.paint_frame(p)
        draw_icon(p, "wave", QRectF(r.left() + 14, r.top() + 12, 30, 30), "#9be3d0", 1.8)
        _title(p, "Try saying...", r.left() + 54, r.top() + 34, 11)
        top = r.top() + 52
        n = len(self._items)
        rowh = (r.bottom() - top - 12) / n
        self._rects = []
        for i, (_k, label, icon) in enumerate(self._items):
            row = QRectF(r.left() + 10, top + rowh * i, r.width() - 20, rowh)
            self._rects.append(row)
            if i == self._hover:
                p.setPen(Qt.PenStyle.NoPen); p.setBrush(col("#5fc4ae", 45)); p.drawRoundedRect(row, 10, 10)
            draw_icon(p, icon, QRectF(row.left() + 6, row.center().y() - 12, 24, 24), "#9be3d0", 1.6)
            p.setFont(qf(9)); p.setPen(col(C.WHITE))
            p.drawText(QRectF(row.left() + 42, row.top(), row.width() - 46, row.height()),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, label)
        p.end()


# ── recent activity ──────────────────────────────────────────────────────────
class ActivityCard(Card):
    view_all = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.items: list[dict] = []         # {you, ai, time, icon}
        self.assistant = "Roohvi"
        self._va = QRectF()
        self.setMouseTracking(True)

    def set_items(self, items: list, assistant: str) -> None:
        self.items, self.assistant = items, assistant
        self.update()

    def mouseReleaseEvent(self, e):                     # noqa: N802
        if self._va.contains(e.position()):
            self.view_all.emit()

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.paint_frame(p)
        _title(p, "Recent Activity", r.left() + 18, r.top() + 32, 12)
        p.setFont(qf(9)); p.setPen(col("#9be3d0"))
        p.drawText(QPointF(r.right() - 78, r.top() + 31), "View All \u2192")
        self._va = QRectF(r.right() - 86, r.top() + 14, 74, 24)
        top = r.top() + 46
        avail = r.bottom() - top - 6
        n = 5
        rowh = avail / n
        if not self.items:
            p.setFont(qf(10)); p.setPen(col(C.TEXT_DIM))
            p.drawText(QRectF(r.left() + 18, top, r.width() - 36, avail), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                       "Nothing here yet \u2014 say hello when you are ready.")
        for i, it in enumerate(self.items[:n]):
            y = top + rowh * i
            p.setPen(QPen(col("#3f8f82", 55), 1)); p.drawLine(QPointF(r.left() + 16, y), QPointF(r.right() - 16, y)) if i else None
            d = min(38, rowh - 14)
            ic = QRectF(r.left() + 16, y + (rowh - d) / 2, d, d)
            icon = it.get("icon", "chat")
            tint = {"play": "#ff4d4d", "calendar": "#5fc4ae", "cloudsun": "#5fc4ae", "book": "#5fc4ae"}.get(icon, "#5fc4ae")
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(col(tint, 230)); p.drawEllipse(ic)
            draw_icon(p, icon, ic.adjusted(d * .26, d * .26, -d * .26, -d * .26), "#ffffff", 1.6)
            tx = ic.right() + 12
            tw = r.right() - tx - 68
            p.setFont(qf(9)); p.setPen(col(C.WHITE))
            p.drawText(QPointF(tx, y + rowh / 2 - 3), _elide(p, "You: " + it.get("you", ""), tw))
            p.setPen(col("#5fc4ae"))
            p.drawText(QPointF(tx, y + rowh / 2 + 13), _elide(p, f"{self.assistant}: " + it.get("ai", ""), tw))
            p.setFont(qf(8)); p.setPen(col(C.TEXT_DIM))
            p.drawText(QRectF(r.right() - 66, y + rowh / 2 - 22, 52, 16), Qt.AlignmentFlag.AlignRight, it.get("time", ""))
        p.end()


# ── apps grid ────────────────────────────────────────────────────────────────
APPS = [("breathing", "Breathing", "wave", "#6fcfb7", "#3f8f82"),
        ("grounding", "Grounding", "cloudsun", "#7fb8e0", "#4a82a8"),
        ("mindfulness", "Mindful", "cube", "#b4a7f5", "#7d6fc9"),
        ("journaling", "Journal", "notepad", "#f2b27a", "#c98348"),
        ("sleep", "Sleep", "calendar", "#8a96d6", "#5b66a8"),
        ("study_work", "Study/Work", "book", "#e6c98a", "#b89a55"),
        ("social", "Connect", "chat", "#f09aa8", "#c26a7a"),
        ("more", "More", "more", "#5b6480", "#3e465e")]


class AppsCard(Card):
    picked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rects: list[QRectF] = []
        self._hover = -1
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._see = QRectF()

    def mouseMoveEvent(self, e):                       # noqa: N802
        h = next((i for i, r in enumerate(self._rects) if r.contains(e.position())), -1)
        if h != self._hover:
            self._hover = h; self.update()

    def leaveEvent(self, e):                           # noqa: N802
        self._hover = -1; self.update()

    def mouseReleaseEvent(self, e):                    # noqa: N802
        if self._see.contains(e.position()):
            self.picked.emit("more"); return
        for i, r in enumerate(self._rects):
            if r.contains(e.position()):
                self.picked.emit(APPS[i][0]); return

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.paint_frame(p)
        _title(p, "Calming Activities", r.left() + 18, r.top() + 32, 12)
        p.setFont(qf(9)); p.setPen(col("#9be3d0"))
        p.drawText(QPointF(r.right() - 72, r.top() + 31), "Ask \u2192")
        self._see = QRectF(r.right() - 82, r.top() + 14, 72, 24)
        top = r.top() + 46
        cols, rows = 4, 2
        cw = (r.width() - 24) / cols
        rh = (r.bottom() - top - 8) / rows
        self._rects = []
        for i, (key, label, icon, c1, c2) in enumerate(APPS):
            cx = r.left() + 12 + (i % cols) * cw + cw / 2
            row = i // cols
            ts = min(52, rh - 24, cw - 14)
            tile = QRectF(cx - ts / 2, top + row * rh + 2, ts, ts)
            self._rects.append(QRectF(cx - cw / 2, top + row * rh, cw, rh))
            g = QLinearGradient(tile.topLeft(), tile.bottomRight())
            g.setColorAt(0, col(c1)); g.setColorAt(1, col(c2))
            p.setPen(QPen(col("#9be3d0", 120 if i != self._hover else 255), 1.2)); p.setBrush(QBrush(g))
            p.drawRoundedRect(tile, ts * 0.26, ts * 0.26)
            if len(icon) <= 2 and icon not in ("more",):
                p.setFont(qf(int(ts * 0.36), QFont.Weight.Bold))
                p.setPen(col("#ffffff" if key not in ("notion",) else "#111111"))
                p.drawText(tile, Qt.AlignmentFlag.AlignCenter, icon)
            else:
                draw_icon(p, icon, tile.adjusted(ts * .22, ts * .22, -ts * .22, -ts * .22), "#ffffff", 1.8)
            p.setFont(qf(8)); p.setPen(col(C.WHITE))
            p.drawText(QRectF(cx - cw / 2, tile.bottom() + 3, cw, 16), Qt.AlignmentFlag.AlignCenter, label)
        p.end()


# ── credits ──────────────────────────────────────────────────────────────────
TEAM_LEAD = ("Muhammad Younas", "Team Lead")
TEAM_MEMBERS = (("Saifullah", "Coping"),
                ("Bibi Hani", "Education"),
                ("Zuhaib Ahmed", "Safety"),
                ("Amir Khan", "Pro help"),
                ("Maria", "Language"))


class TeamCard(Card):
    """Who designed Roohvi. Names only, nothing clickable. Roomy layout when the window is
    tall, a one-line-per-person layout when it is short, so the credit is never dropped."""

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.paint_frame(p)
        compact = r.height() < 238
        _title(p, "Designed by", r.left() + 18, r.top() + 30)
        y = r.top() + 44
        p.setPen(QPen(col("#3f8f82", 80), 1)); p.drawLine(QPointF(r.left() + 16, y), QPointF(r.right() - 16, y))
        x, wmax = r.left() + 18, r.width() - 30

        def fit(text, size, weight):
            while size > 8:
                p.setFont(qf(size, weight))
                if QFontMetrics(p.font()).horizontalAdvance(text) <= wmax:
                    return
                size -= 1
            p.setFont(qf(8, weight))

        if compact:
            y += 16
            p.setFont(qf(7)); p.setPen(col("#9be3d0"))
            p.drawText(QPointF(x, y), TEAM_LEAD[1].upper())
            y += 15
            fit(TEAM_LEAD[0], 10, QFont.Weight.Bold); p.setPen(col(C.WHITE))
            p.drawText(QPointF(x, y), TEAM_LEAD[0])
            y += 8
            p.setPen(QPen(col("#3f8f82", 50), 1)); p.drawLine(QPointF(r.left() + 16, y), QPointF(r.right() - 16, y))
            y += 4
            rowh = max(15.0, (r.bottom() - y - 4) / len(TEAM_MEMBERS))
            for name, role in TEAM_MEMBERS:
                txt = f"{name} \u00b7 {role}"
                fit(txt, 9, QFont.Weight.Normal); p.setPen(col(C.WHITE))
                p.drawText(QPointF(x, y + rowh * 0.74), txt)
                y += rowh
            p.end()
            return

        y += 20
        p.setFont(qf(8)); p.setPen(col("#9be3d0"))
        p.drawText(QPointF(x, y), TEAM_LEAD[1].upper())
        y += 18
        fit(TEAM_LEAD[0], 11, QFont.Weight.Bold); p.setPen(col(C.WHITE))
        p.drawText(QPointF(x, y), TEAM_LEAD[0])
        y += 12
        p.setPen(QPen(col("#3f8f82", 50), 1)); p.drawLine(QPointF(r.left() + 16, y), QPointF(r.right() - 16, y))
        y += 8
        rowh = min(38.0, max(26.0, (r.bottom() - y - 8) / len(TEAM_MEMBERS)))
        for name, role in TEAM_MEMBERS:
            p.setFont(qf(9, QFont.Weight.DemiBold)); p.setPen(col(C.WHITE))
            p.drawText(QPointF(x, y + 15), _elide(p, name, wmax))
            p.setFont(qf(8)); p.setPen(col(C.TEXT_MED))
            p.drawText(QPointF(x, y + 29), role)
            y += rowh
        p.end()


class InputBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 8, -1, -8)
        glow = QLinearGradient(r.topLeft(), r.topRight())
        glow.setColorAt(0, col("#5fc4ae", 0)); glow.setColorAt(0.5, col("#5fc4ae", 60)); glow.setColorAt(1, col("#5fc4ae", 0))
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(glow)); p.drawRoundedRect(r.adjusted(-6, -6, 6, 8), 34, 34)
        g = QLinearGradient(r.topLeft(), r.bottomLeft())
        g.setColorAt(0, col("#222a3d", 235)); g.setColorAt(1, col("#161b29", 235))
        p.setPen(QPen(col("#5fc4ae", 190), 1.3)); p.setBrush(QBrush(g)); p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        p.end()


# ── header ───────────────────────────────────────────────────────────────────
class HeaderCard(Card):
    """Logo + title + tagline and a live clock / date."""

    def __init__(self, parent=None):
        super().__init__(parent, 18, 190)
        self.title = "Roohvi"
        self.tagline = "Your AI Wellness Companion"
        self.clock_text = "--:--"
        self.date_text = ""

    def set_title(self, title: str, tagline: str = "") -> None:
        self.title = title or "Roohvi"
        if tagline:
            self.tagline = tagline
        self.update()

    def set_clock(self, clock_text: str, date_text: str) -> None:
        self.clock_text, self.date_text = clock_text, date_text
        self.update()

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.paint_frame(p)
        logo = QRectF(r.left() + 16, r.center().y() - 18, 36, 36)
        LogoMark_paint(p, logo)
        tx = logo.right() + 12
        p.setFont(qf(15, QFont.Weight.Bold)); p.setPen(col(C.WHITE))
        p.drawText(QPointF(tx, r.center().y() - 2), self.title.upper())
        p.setFont(qf(8)); p.setPen(col(C.TEXT_DIM))
        p.drawText(QPointF(tx, r.center().y() + 14), self.tagline)

        p.setFont(qf(13, QFont.Weight.Bold)); p.setPen(col(C.WHITE))
        clock_w = QFontMetrics(p.font()).horizontalAdvance(self.clock_text)
        rx = r.right() - 410
        p.drawText(QPointF(rx, r.center().y() - 2), self.clock_text)
        p.setFont(qf(8)); p.setPen(col(C.TEXT_DIM))
        p.drawText(QPointF(rx, r.center().y() + 14), self.date_text)
        p.end()


def LogoMark_paint(p: QPainter, r: QRectF) -> None:
    g = QLinearGradient(r.topLeft(), r.bottomRight())
    g.setColorAt(0, col("#9be3d0")); g.setColorAt(1, col("#3f8f82"))
    path = QPainterPath()
    w, h = r.width(), r.height()
    path.moveTo(r.left() + w * .18, r.top()); path.lineTo(r.right(), r.top()); path.lineTo(r.right() - w * .16, r.top() + h * .30)
    path.lineTo(r.left() + w * .44, r.top() + h * .30); path.lineTo(r.right() - w * .02, r.bottom() - h * .30)
    path.lineTo(r.left() + w * .02, r.bottom() - h * .30); path.lineTo(r.left() + w * .18, r.top())
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(g)); p.drawPath(path)
    path2 = QPainterPath()
    path2.moveTo(r.left(), r.bottom()); path2.lineTo(r.right() - w * .30, r.bottom() - h * .30); path2.lineTo(r.right(), r.bottom() - h * .30)
    path2.lineTo(r.right() - w * .16, r.bottom()); path2.closeSubpath()
    p.drawPath(path2)


# ── nav column ───────────────────────────────────────────────────────────────
class NavCard(Card):
    """Background for the sidebar nav; the NavButtons are its children."""
    pass


# ── small utilities ──────────────────────────────────────────────────────────
class StatusBadge(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.state = "Online"
        self.detail = "Always here for you"
        self.color = "#2ee6a6"

    def set_state(self, state: str, detail: str, color: str) -> None:
        if (state, detail, color) != (self.state, self.detail, self.color):
            self.state, self.detail, self.color = state, detail, color
            self.update()

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect())
        c = QPointF(r.left() + 14, r.center().y() - 6)
        halo = QRadialGradient(c, 10); halo.setColorAt(0, col(self.color, 120)); halo.setColorAt(1, col(self.color, 0))
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(halo)); p.drawEllipse(c, 10, 10)
        p.setBrush(col(self.color)); p.drawEllipse(c, 5, 5)
        p.setFont(qf(11, QFont.Weight.DemiBold)); p.setPen(col(C.WHITE))
        p.drawText(QPointF(r.left() + 32, r.center().y() - 2), self.state)
        p.setFont(qf(8)); p.setPen(col(C.TEXT_DIM))
        p.drawText(QPointF(r.left() + 32, r.center().y() + 14), self.detail)
        p.end()


class LogoMark(QWidget):
    """A stylised Z monogram."""

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        LogoMark_paint(p, QRectF(self.rect()).adjusted(2, 2, -2, -2))
        p.end()


class Toast(QLabel):
    """A brief floating message (errors, confirmations)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setWordWrap(True)
        self.hide()
        from PyQt6.QtCore import QTimer
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def show_text(self, text: str, kind: str = "info", ms: int = 6000, max_w: int = 560) -> None:
        colr = {"error": "#ff6b7a", "ok": "#2ee6a6"}.get(kind, "#9be3d0")
        self.setStyleSheet(f"QLabel {{ background: rgba(8,20,44,235); color: {C.WHITE}; border: 1px solid {colr}; "
                           f"border-radius: 14px; padding: 10px 18px; }}")
        self.setFont(qf(9))
        self.setText(text)
        w = min(max_w, max(240, QFontMetrics(self.font()).horizontalAdvance(text) + 60))
        self.setFixedWidth(w)
        self.setMinimumHeight(0); self.setMaximumHeight(16777215)
        h = max(self.sizeHint().height(), self.heightForWidth(w) if self.hasHeightForWidth() else 0)
        self.setFixedHeight(h + 6)
        self.show()
        self.raise_()
        self._timer.start(ms)



# -- mood chips: one tap says how you feel ------------------------------------
class MoodChips(QWidget):
    """A row of small chips under the face: 'how are you feeling?' in one tap."""
    picked = pyqtSignal(str)
    ITEMS = (("Good", "I'm feeling good today."),
             ("Okay", "I'm feeling okay, nothing special."),
             ("Low", "I'm feeling low today."),
             ("Stressed", "I'm feeling stressed."),
             ("Anxious", "I'm feeling anxious."))

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hover = -1
        self._rects: list[QRectF] = []

    def _font_size(self) -> int:
        for size in (10, 9, 8):
            fm = QFontMetrics(qf(size, QFont.Weight.DemiBold))
            total = sum(fm.horizontalAdvance(t) + 2 * 14 for t, _ in self.ITEMS) + 6 * (len(self.ITEMS) - 1)
            if total <= self.width():
                return size
        return 8

    def _layout(self) -> list[QRectF]:
        fm = QFontMetrics(qf(self._font_size(), QFont.Weight.DemiBold))
        ws = [fm.horizontalAdvance(t) + 28 for t, _ in self.ITEMS]
        total = sum(ws) + 6 * (len(ws) - 1)
        x = max(0.0, (self.width() - total) / 2.0)
        out = []
        for w in ws:
            out.append(QRectF(x, 1, w, self.height() - 2))
            x += w + 6
        return out

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._rects = self._layout()
        p.setFont(qf(self._font_size(), QFont.Weight.DemiBold))
        for i, ((text, _msg), r) in enumerate(zip(self.ITEMS, self._rects)):
            hot = i == self._hover
            p.setPen(QPen(col("#6fcfb7", 200 if hot else 95), 1.1))
            p.setBrush(QBrush(col("#6fcfb7", 52) if hot else col("#222a3d", 215)))
            p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
            p.setPen(col(C.WHITE if hot else C.TEXT_MED))
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, text)
        p.end()

    def _at(self, pos) -> int:
        pt = QPointF(pos)
        for i, r in enumerate(self._rects):
            if r.contains(pt):
                return i
        return -1

    def mouseMoveEvent(self, ev):
        i = self._at(ev.position())
        if i != self._hover:
            self._hover = i
            self.update()

    def leaveEvent(self, _ev):
        self._hover = -1
        self.update()

    def mouseReleaseEvent(self, ev):
        i = self._at(ev.position())
        if i >= 0:
            self.picked.emit(self.ITEMS[i][1])


# -- breathing circle: works instantly, even offline --------------------------
class BreathingOrb(QWidget):
    """A slow circle: in for 4, hold 1, out for 6, six breaths. Tap anywhere to stop."""
    closed = pyqtSignal()
    IN, HOLD, OUT, CYCLES = 4.0, 1.0, 6.0, 6

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._t0 = 0.0
        self._done_at = None
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def start(self) -> None:
        self._t0, self._done_at = time.monotonic(), None
        self._timer.start(33)
        self.show()
        self.raise_()

    def stop(self) -> None:
        self._timer.stop()
        self.hide()
        self.closed.emit()

    def _tick(self) -> None:
        if self._done_at and time.monotonic() - self._done_at > 2.6:
            self.stop()
            return
        self.update()

    def mousePressEvent(self, _ev):
        self.stop()

    def _phase(self, t: float):
        cyc = self.IN + self.HOLD + self.OUT
        n, u = int(t // cyc), t % cyc
        if u < self.IN:
            x, label = u / self.IN, "Breathe in"
        elif u < self.IN + self.HOLD:
            x, label = 1.0, "Hold gently"
        else:
            x, label = 1.0 - (u - self.IN - self.HOLD) / self.OUT, "Breathe out"
        return n, label, 0.5 - 0.5 * math.cos(math.pi * x)

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(col("#0e1220", 248)))
        p.drawRoundedRect(r, 24, 24)
        t = time.monotonic() - self._t0
        n, label, k = self._phase(t)
        if n >= self.CYCLES:
            if not self._done_at:
                self._done_at = time.monotonic()
            n, label, k = self.CYCLES - 1, "Well done", 0.0
        c = r.center() + QPointF(0, -10)
        base = min(r.width(), r.height()) * 0.30
        rad = base * (0.52 + 0.48 * k)
        g = QRadialGradient(c, rad * 1.7)
        g.setColorAt(0.0, col("#6fcfb7", 120)); g.setColorAt(0.55, col("#6fcfb7", 40)); g.setColorAt(1.0, col("#6fcfb7", 0))
        p.setBrush(QBrush(g)); p.drawEllipse(c, rad * 1.7, rad * 1.7)
        g2 = QRadialGradient(c, rad)
        g2.setColorAt(0.0, col("#bff0e2", 235)); g2.setColorAt(1.0, col("#5fc4ae", 215))
        p.setBrush(QBrush(g2)); p.drawEllipse(c, rad, rad)
        p.setPen(col(C.WHITE)); p.setFont(qf(17, QFont.Weight.DemiBold))
        p.drawText(QRectF(r.left(), c.y() + base * 1.08, r.width(), 34), Qt.AlignmentFlag.AlignCenter, label)
        p.setPen(col(C.TEXT_MED)); p.setFont(qf(10))
        sub = "Breath %d of %d" % (min(n + 1, self.CYCLES), self.CYCLES) if label != "Well done" else "Notice how you feel right now."
        p.drawText(QRectF(r.left(), c.y() + base * 1.08 + 34, r.width(), 24), Qt.AlignmentFlag.AlignCenter, sub)
        p.setPen(col(C.TEXT_DIM)); p.setFont(qf(9))
        p.drawText(QRectF(r.left(), r.bottom() - 30, r.width(), 22), Qt.AlignmentFlag.AlignCenter,
                   "Tap anywhere to stop. You can stop any time.")
        p.end()
