"""
PixelForge — Stage VU Level Meter & Beat Indicator Widget
Draws multi-segment LED ladder VU meter with peak hold and flashing beat LED.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QSlider, QVBoxLayout, QWidget


class VUMeterWidget(QWidget):
    """MADRIX-style hardware segmented LED VU level meter with peak hold."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumSize(70, 24)
        self.setMaximumHeight(30)

        self._level: float = 0.0
        self._peak: float = 0.0
        self._is_beat: bool = False
        self._beat_brightness: float = 0.0

        # Beat decay timer
        self._decay_timer = QTimer(self)
        self._decay_timer.timeout.connect(self._decay_step)
        self._decay_timer.start(25)  # 40Hz update

    def set_levels(self, level: float, peak: float) -> None:
        self._level = max(0.0, min(1.0, level))
        self._peak = max(self._peak * 0.95, min(1.0, peak))
        self.update()

    def trigger_beat(self, intensity: float = 1.0) -> None:
        self._is_beat = True
        self._beat_brightness = min(1.0, max(0.4, intensity))
        self.update()

    def _decay_step(self) -> None:
        need_update = False
        if self._beat_brightness > 0.0:
            self._beat_brightness = max(0.0, self._beat_brightness - 0.08)
            need_update = True
        if self._peak > 0.0:
            self._peak = max(0.0, self._peak - 0.015)
            need_update = True
        if need_update:
            self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w = self.width()
        h = self.height()

        # Background chassis
        painter.fillRect(0, 0, w, h, QColor("#0d1017"))
        painter.setPen(QPen(QColor("#252c3d"), 1))
        painter.drawRect(0, 0, w - 1, h - 1)

        # Beat LED (Left circle)
        beat_radius = 5.0
        bx = 10.0
        by = h / 2.0
        if self._beat_brightness > 0.05:
            beat_col = QColor(255, 220, 0, int(self._beat_brightness * 255))
            painter.setBrush(QBrush(beat_col))
            painter.setPen(QPen(QColor("#ffe066"), 1))
        else:
            painter.setBrush(QBrush(QColor("#2a2000")))
            painter.setPen(QPen(QColor("#4d3a00"), 1))
        painter.drawEllipse(QPointF(bx, by), beat_radius, beat_radius)

        # Segmented ladder bars
        start_x = 22
        avail_w = w - start_x - 6
        num_segments = 14
        seg_w = max(2, (avail_w - (num_segments - 1) * 2) // num_segments)
        seg_h = h - 8
        sy = 4

        lit_segments = int(self._level * num_segments)
        peak_seg = min(num_segments - 1, int(self._peak * num_segments))

        for i in range(num_segments):
            sx = start_x + i * (seg_w + 2)
            # Segment colors: green (0-8), yellow (9-11), red (12-13)
            if i < 9:
                on_color = QColor("#00e676")
                off_color = QColor("#0a2617")
            elif i < 12:
                on_color = QColor("#ffd600")
                off_color = QColor("#332b00")
            else:
                on_color = QColor("#ff1744")
                off_color = QColor("#380a12")

            is_lit = (i <= lit_segments)
            is_peak = (i == peak_seg and self._peak > 0.05)

            if is_peak:
                painter.fillRect(QRectF(sx, sy, seg_w, seg_h), on_color.lighter(130))
            elif is_lit:
                painter.fillRect(QRectF(sx, sy, seg_w, seg_h), on_color)
            else:
                painter.fillRect(QRectF(sx, sy, seg_w, seg_h), off_color)
