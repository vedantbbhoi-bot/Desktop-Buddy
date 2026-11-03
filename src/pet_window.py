"""src/pet_window.py — transparent, always-on-top desktop pet (PySide6).

The pet is drawn with plain shapes, so no sprite files are needed. Later you can
replace PetWindow.paintEvent with sprite drawing from config.sprite_dir.

Thread safety: other threads must talk to the window ONLY through its signals:
    window.state_changed.emit("thinking")
    window.bubble_requested.emit("some text")
"""
from __future__ import annotations

import math
import time

from PySide6.QtCore import QPoint, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QApplication, QInputDialog, QLabel, QMenu, QWidget

# Animation states emitted by IntentRouter (+ "listening", set by main.py)
STATE_COLORS = {
    "idle": "#7FB8F5",
    "listening": "#8FE0A8",
    "thinking": "#C9A8F0",
    "working": "#F5C96B",
    "celebrate": "#FF9EC4",
    "confused": "#F59A8A",
}
# States that fall back to "idle" by themselves
RESET_AFTER_MS = {"celebrate": 2500, "confused": 2500}


class Bubble(QLabel):
    """Small speech bubble shown above the pet; click-through and non-focusing."""

    def __init__(self, always_on_top: bool) -> None:
        flags = Qt.Tool | Qt.FramelessWindowHint | Qt.WindowTransparentForInput
        if always_on_top:
            flags |= Qt.WindowStaysOnTopHint
        super().__init__(None, flags)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setWordWrap(True)
        self.setMaximumWidth(280)
        self.setStyleSheet(
            "background:#FFFFFF; color:#222; border:2px solid #555;"
            "border-radius:12px; padding:8px 10px; font-size:13px;"
        )
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    def show_text(self, text: str, anchor) -> None:
        """anchor: the pet's global QRect. Places the bubble above it (or below if no room)."""
        self.setText(text)
        self.adjustSize()
        screen = QApplication.screenAt(anchor.center()) or QApplication.primaryScreen()
        area = screen.availableGeometry()
        x = anchor.center().x() - self.width() // 2
        y = anchor.top() - self.height() - 6
        if y < area.top():
            y = anchor.bottom() + 6
        x = max(area.left(), min(x, area.right() - self.width()))
        self.move(x, y)
        self.show()
        self.raise_()
        self._hide_timer.start(max(3000, min(15000, 2500 + 60 * len(text))))


class PetWindow(QWidget):
    user_text = Signal(str)         # user typed a message
    talk_requested = Signal()       # user clicked the pet (push-to-talk)
    quit_requested = Signal()
    state_changed = Signal(str)     # thread-safe: set animation state
    bubble_requested = Signal(str)  # thread-safe: show speech bubble

    def __init__(self, config) -> None:
        flags = Qt.FramelessWindowHint | Qt.Tool
        if config.always_on_top:
            flags |= Qt.WindowStaysOnTopHint
        super().__init__(None, flags)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle("Desktop Buddy")
        w = max(80, int(config.window.width * config.scale))
        h = max(80, int(config.window.height * config.scale))
        self.resize(w, h)
        self.move(config.window.x, config.window.y)

        self._state = "idle"
        self._t0 = time.monotonic()
        self._press_offset = QPoint()
        self._moved = False

        self._bubble = Bubble(config.always_on_top)
        self._reset_timer = QTimer(self)
        self._reset_timer.setSingleShot(True)
        self._reset_timer.timeout.connect(lambda: self.set_state("idle"))
        self._frame_timer = QTimer(self)
        self._frame_timer.timeout.connect(self.update)
        self._frame_timer.start(33)  # ~30 fps

        self.state_changed.connect(self.set_state)
        self.bubble_requested.connect(self.show_bubble)

    # ── Public API ─────────────────────────────────────────────────────────

    @property
    def state(self) -> str:
        return self._state

    def set_state(self, state: str) -> None:
        if state not in STATE_COLORS:
            state = "idle"
        self._state = state
        self._reset_timer.stop()
        if state in RESET_AFTER_MS:
            self._reset_timer.start(RESET_AFTER_MS[state])
        self.update()

    def show_bubble(self, text: str) -> None:
        if text:
            self._bubble.show_text(text, self.frameGeometry())

    # ── Mouse: drag to move, click to talk, right-click for menu ───────────

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.LeftButton:
            self._press_offset = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._moved = False

    def mouseMoveEvent(self, e) -> None:
        if e.buttons() & Qt.LeftButton:
            target = e.globalPosition().toPoint() - self._press_offset
            if (target - self.frameGeometry().topLeft()).manhattanLength() > 4:
                self._moved = True
            if self._moved:
                self.move(target)
                if self._bubble.isVisible():
                    self._bubble.hide()

    def mouseReleaseEvent(self, e) -> None:
        if e.button() == Qt.LeftButton and not self._moved:
            self.talk_requested.emit()

    def contextMenuEvent(self, e) -> None:
        menu = QMenu(self)
        talk = QAction("Talk (voice)", menu)
        talk.triggered.connect(self.talk_requested.emit)
        typed = QAction("Type a message…", menu)
        typed.triggered.connect(self._ask_text)
        quit_ = QAction("Quit", menu)
        quit_.triggered.connect(self.quit_requested.emit)
        menu.addAction(talk)
        menu.addAction(typed)
        menu.addSeparator()
        menu.addAction(quit_)
        menu.exec(e.globalPos())

    def _ask_text(self) -> None:
        text, ok = QInputDialog.getText(self, "Desktop Buddy", "Say something:")
        if ok and text.strip():
            self.user_text.emit(text.strip())

    def closeEvent(self, e) -> None:
        self._bubble.hide()
        super().closeEvent(e)

    # ── Drawing ────────────────────────────────────────────────────────────

    def paintEvent(self, _e) -> None:
        t = time.monotonic() - self._t0
        st = self._state
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        W, H = self.width(), self.height()
        s = min(W, H) * 0.72

        bob = math.sin(t * 2.0) * H * 0.02
        if st == "celebrate":
            bob = -abs(math.sin(t * 8.0)) * H * 0.08
        elif st == "thinking":
            bob = math.sin(t * 3.0) * H * 0.01
        cx, cy = W / 2, H * 0.58 + bob

        if st == "listening":  # pulsing ring
            r = s * (0.58 + 0.05 * math.sin(t * 6.0))
            ring = QColor(STATE_COLORS["listening"])
            ring.setAlpha(150)
            p.setPen(QPen(ring, max(2, s * 0.03)))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QRectF(cx - r, cy - r, 2 * r, 2 * r))

        outline = QPen(QColor("#2B2B3A"), max(2, s * 0.035))
        p.setPen(outline)
        p.setBrush(QBrush(QColor(STATE_COLORS[st])))
        p.drawEllipse(QRectF(cx - s / 2, cy - s * 0.45, s, s * 0.9))

        ink = QPen(QColor("#2B2B3A"), max(2, s * 0.04), Qt.SolidLine, Qt.RoundCap)
        p.setPen(ink)
        p.setBrush(QBrush(QColor("#2B2B3A")))
        ey, dx, er = cy - s * 0.08, s * 0.18, s * 0.05

        if st == "celebrate":      # ^ ^ eyes, big smile
            p.setBrush(Qt.NoBrush)
            for sx in (-dx, dx):
                p.drawArc(QRectF(cx + sx - er * 1.4, ey - er, er * 2.8, er * 2), 20 * 16, 140 * 16)
            p.drawArc(QRectF(cx - s * 0.16, cy + s * 0.02, s * 0.32, s * 0.22), 200 * 16, 140 * 16)
        elif st == "working":      # squinting eyes, flat mouth, "typing" dots
            for sx in (-dx, dx):
                p.drawLine(int(cx + sx - er), int(ey), int(cx + sx + er), int(ey))
            p.drawLine(int(cx - s * 0.08), int(cy + s * 0.14), int(cx + s * 0.08), int(cy + s * 0.14))
            n = int(t * 4) % 4
            p.setBrush(QBrush(QColor("#2B2B3A")))
            for i in range(n):
                p.drawEllipse(QRectF(cx - s * 0.12 + i * s * 0.08, cy + s * 0.27, s * 0.04, s * 0.04))
        elif st == "confused":     # unequal eyes, wavy mouth, "?"
            p.drawEllipse(QRectF(cx - dx - er, ey - er, er * 2, er * 2))
            p.drawEllipse(QRectF(cx + dx - er * 1.6, ey - er * 1.6, er * 3.2, er * 3.2))
            p.drawLine(int(cx - s * 0.1), int(cy + s * 0.16), int(cx + s * 0.1), int(cy + s * 0.11))
            f = QFont(); f.setBold(True); f.setPixelSize(max(12, int(s * 0.3)))
            p.setFont(f)
            p.drawText(QRectF(cx - s * 0.1, cy - s * 0.78, s * 0.2, s * 0.3), Qt.AlignCenter, "?")
        else:                      # idle / listening / thinking: round eyes
            look_x, look_y = (er * 0.8, -er * 0.9) if st == "thinking" else (0.0, 0.0)
            big = er * 1.4 if st == "listening" else er
            blink = st == "idle" and (t % 4.0) < 0.15
            for sx in (-dx, dx):
                if blink:
                    p.drawLine(int(cx + sx - er), int(ey), int(cx + sx + er), int(ey))
                else:
                    p.drawEllipse(QRectF(cx + sx - big + look_x, ey - big + look_y, big * 2, big * 2))
            p.setBrush(Qt.NoBrush)
            if st == "thinking":
                p.drawEllipse(QRectF(cx - s * 0.03, cy + s * 0.1, s * 0.06, s * 0.06))
                n = int(t * 2) % 3 + 1
                p.setBrush(QBrush(QColor("#2B2B3A")))
                for i in range(n):
                    p.drawEllipse(QRectF(cx + s * 0.2 + i * s * 0.09, cy - s * 0.62 - i * s * 0.05,
                                         s * 0.05, s * 0.05))
            else:
                p.drawArc(QRectF(cx - s * 0.1, cy + s * 0.04, s * 0.2, s * 0.14), 200 * 16, 140 * 16)
        p.end()
