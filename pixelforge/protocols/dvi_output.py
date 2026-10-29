"""
PixelForge — DVI / External Display Video Wall Output
Streams virtual matrix rendering to full-screen secondary monitors, LED wall processors
(NovaStar, Brompton, Colorlight), and external projectors.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPen
from PyQt6.QtWidgets import QLabel, QMainWindow, QVBoxLayout, QWidget

from pixelforge.core.matrix import PixelMatrix


class DviOutputWindow(QWidget):
    """Full-screen / windowed video output for LED wall processor mapping."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("PixelForge — DVI External Display Output")
        self.resize(640, 480)

        self._matrix: Optional[PixelMatrix] = None
        self.show_grid: bool = False
        self.smooth_scaling: bool = False  # False = Crisp pixel-art/LED style

        # Dark theme background
        self.setStyleSheet("background-color: #000000;")

    def set_matrix(self, matrix: PixelMatrix) -> None:
        self._matrix = matrix
        self.update()

    def set_screen_fullscreen(self, screen_index: int = 1) -> None:
        """Move output to specified display and engage fullscreen."""
        screens = QGuiApplication.screens()
        if 0 <= screen_index < len(screens):
            target_screen = screens[screen_index]
            self.setScreen(target_screen)
            self.setGeometry(target_screen.geometry())
            self.showFullScreen()
        else:
            self.show()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        w = self.width()
        h = self.height()

        # Pure black stage fill
        painter.fillRect(0, 0, w, h, QColor("#000000"))

        if self._matrix is None:
            painter.setPen(QPen(QColor("#333333")))
            painter.setFont(QFont("Segoe UI", 14))
            painter.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, "PIXELFORGE DVI OUTPUT — NO SIGNAL")
            return

        mat_w = self._matrix.width
        mat_h = self._matrix.height

        # Fit with aspect ratio
        aspect = mat_w / max(mat_h, 1)
        if w / max(h, 1) > aspect:
            draw_h = h
            draw_w = draw_h * aspect
        else:
            draw_w = w
            draw_h = draw_w / aspect

        ox = (w - draw_w) / 2.0
        oy = (h - draw_h) / 2.0

        cell_w = draw_w / mat_w
        cell_h = draw_h / mat_h
        buf = self._matrix.buffer

        # Draw matrix pixels
        for y in range(mat_h):
            ry = oy + y * cell_h
            for x in range(mat_w):
                rx = ox + x * cell_w
                r, g, b = int(buf[y, x, 0]), int(buf[y, x, 1]), int(buf[y, x, 2])
                painter.fillRect(QRectF(rx, ry, cell_w, cell_h), QColor(r, g, b))

        # Optional alignment grid
        if self.show_grid and min(cell_w, cell_h) >= 6:
            painter.setPen(QPen(QColor(60, 60, 60, 150), 1))
            for x in range(mat_w + 1):
                painter.drawLine(int(ox + x * cell_w), int(oy), int(ox + x * cell_w), int(oy + draw_h))
            for y in range(mat_h + 1):
                painter.drawLine(int(ox), int(oy + y * cell_h), int(ox + draw_w), int(oy + y * cell_h))

    def keyPressEvent(self, event) -> None:
        # ESC or F11 toggles fullscreen / closes
        if event.key() == Qt.Key.Key_Escape or event.key() == Qt.Key.Key_F11:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.close()
        super().keyPressEvent(event)

