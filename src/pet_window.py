"""src/pet_window.py — transparent, always-on-top desktop pet (PySide6).

The pet is drawn with plain shapes, so no sprite files are needed. Later you can
replace PetWindow.paintEvent with sprite drawing from config.sprite_dir.

Thread safety: other threads must talk to the window ONLY through its signals:
    window.state_changed.emit("thinking")
    window.bubble_requested.emit("some text")
"""
from __future__ import annotations

import math
import pathlib
import time

from PySide6.QtCore import QPoint, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QBrush, QColor, QFont, QImage, QPainter, QPen
from PySide6.QtWidgets import QApplication, QInputDialog, QLabel, QMenu, QWidget

# Animation states emitted by IntentRouter (+ "listening", set by main.py)
STATE_COLORS = {
    "idle": "#7FB8F5",
    "listening": "#8FE0A8",
    "thinking": "#C9A8F0",
    "working": "#F5C96B",
    "celebrate": "#FF9EC4",
    "confused": "#F59A8A",
    "talking": "#FF9EC4",
}
# States that fall back to "idle" by themselves
RESET_AFTER_MS = {"celebrate": 2500, "confused": 2500}

# The supplied 640x1024 sheet is an 8-row grid of 64x128 frames. Four rows
# contain ten frames and the alternating rows contain six (the final four cells
# are blank). The rows are kept separate so each reaction has its own loop.
SPRITE_ROW_FRAME_COUNTS = (10, 6, 10, 6, 10, 6, 10, 6)
SPRITE_STATE_ROWS = {
    "idle": 4,
    "listening": 6,
    "thinking": 0,
    "working": 2,
    "celebrate": 5,
    "confused": 7,
    "talking": 3,
}
SPRITE_FPS = {
    "idle": 8,
    "listening": 10,
    "thinking": 7,
    "working": 12,
    "celebrate": 14,
    "confused": 7,
    "talking": 10,
}


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
        self._state_started = self._t0
        self._sprite_frames = self._load_sprite_frames(config.sprite_dir)
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
        if state != self._state:
            self._state_started = time.monotonic()
        self._state = state
        self._reset_timer.stop()
        if state in RESET_AFTER_MS:
            self._reset_timer.start(RESET_AFTER_MS[state])
        self.update()

    @staticmethod
    def _load_sprite_frames(sprite_dir: str) -> dict[str, list[QImage]]:
        """Load the configured sprite sheet, falling back to vector drawing if absent."""
        folder = pathlib.Path(sprite_dir)
        if not folder.is_absolute():
            folder = pathlib.Path(__file__).resolve().parent.parent / folder
        sheet = QImage(str(folder / "sprite_sheet.png"))
        if sheet.isNull() or sheet.width() % 10 or sheet.height() % 8:
            return {}

        frame_width = sheet.width() // 10
        frame_height = sheet.height() // 8
        rows: dict[int, list[QImage]] = {}
        for row, frame_count in enumerate(SPRITE_ROW_FRAME_COUNTS):
            rows[row] = [
                sheet.copy(QRect(col * frame_width, row * frame_height, frame_width, frame_height))
                for col in range(frame_count)
            ]
        return {state: rows[row] for state, row in SPRITE_STATE_ROWS.items()}

    def _current_sprite_frame(self, now: float | None = None) -> QImage | None:
        """Return the frame for the active state at a monotonic timestamp."""
        frames = self._sprite_frames.get(self._state) or self._sprite_frames.get("idle")
        if not frames:
            return None
        elapsed = max(0.0, (time.monotonic() if now is None else now) - self._state_started)
        frame_index = int(elapsed * SPRITE_FPS.get(self._state, 8)) % len(frames)
        return frames[frame_index]

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
        # A child dialog can be positioned over this small always-on-top window,
        # leaving its input field hidden. Use a top-level dialog and temporarily
        # hide the pet so the user can type and submit without obstruction.
        was_visible = self.isVisible()
        self._bubble.hide()
        if was_visible:
            self.hide()
        try:
            text, ok = QInputDialog.getText(
                None,
                "Desktop Buddy",
                "Say something:",
                flags=Qt.Dialog | Qt.WindowStaysOnTopHint,
            )
        finally:
            if was_visible:
                self.show()
                self.raise_()
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

        sprite = self._current_sprite_frame()
        if sprite is not None:
            bob = math.sin(t * 2.8) * H * 0.012
            if st == "celebrate":
                bob = -abs(math.sin(t * 8.0)) * H * 0.04
            scale = min(W * 0.72 / sprite.width(), H * 0.9 / sprite.height())
            draw_width = sprite.width() * scale
            draw_height = sprite.height() * scale
            target = QRectF(
                (W - draw_width) / 2,
                (H - draw_height) / 2 + bob,
                draw_width,
                draw_height,
            )
            p.setRenderHint(QPainter.SmoothPixmapTransform, False)
            p.drawImage(target, sprite)
            p.end()
            return

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
            f = QFont()
            f.setBold(True)
            f.setPixelSize(max(12, int(s * 0.3)))
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
