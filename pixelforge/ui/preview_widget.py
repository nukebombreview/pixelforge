"""
PixelForge — LED Matrix Preview Widget
High-performance QPainter widget simulating physical LED fixtures with grid and dot modes.
"""

from __future__ import annotations

import math
from typing import Optional

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QMouseEvent, QPainter, QPen, QRadialGradient
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from pixelforge.core.matrix import PixelMatrix


class MatrixPreviewWidget(QWidget):
    """Visualizer widget that renders a PixelMatrix as an LED grid display or 3D voxel stage.

    Features:
    * 2D LED Dot Mode (round fixtures with soft edge falloff) vs Square Tile Mode
    * 3D Voxel Mode (interactive 3D orbital perspective projection with depth sorting)
    * Mouse orbital controls (click and drag to rotate in 3D, double-click to toggle 2D/3D)
    * Subtle grid lines simulating fixture gaps
    * Deck badge and resolution label overlay
    * Clean border with accent color (Deck A Cyan, Deck B Magenta, Master Amber)
    """

    def __init__(
        self,
        title: str = "PREVIEW",
        accent_color: str = "#00d2ff",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.title = title
        self.accent_color = QColor(accent_color)
        self.dot_mode: bool = True  # True = round LEDs, False = square pixels
        self.show_grid: bool = True
        self.voxel_3d_mode: bool = False  # 3D Voxel View mode

        # 3D orbital angles (degrees)
        self.yaw: float = 35.0
        self.pitch: float = 30.0
        self._last_mouse_pos = None

        self._matrix: Optional[PixelMatrix] = None

        # Minimum display size
        self.setMinimumSize(180, 180)
        self.setToolTip("Double-click to toggle between 2D Matrix and 3D Voxel modes. Drag to orbit in 3D.")

    def set_matrix(self, matrix: PixelMatrix) -> None:
        """Update the displayed matrix and trigger redraw."""
        self._matrix = matrix
        self.update()

    def set_dot_mode(self, enabled: bool) -> None:
        self.dot_mode = enabled
        self.update()

    def set_show_grid(self, enabled: bool) -> None:
        self.show_grid = enabled
        self.update()

    @property
    def is_3d_mode(self) -> bool:
        return self.voxel_3d_mode

    def toggle_3d_mode(self, enabled: Optional[bool] = None) -> None:
        if enabled is None:
            self.voxel_3d_mode = not self.voxel_3d_mode
        else:
            self.voxel_3d_mode = enabled
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._last_mouse_pos = event.position()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._last_mouse_pos is not None and self.voxel_3d_mode:
            pos = event.position()
            dx = pos.x() - self._last_mouse_pos.x()
            dy = pos.y() - self._last_mouse_pos.y()
            self.yaw = (self.yaw + dx * 0.7) % 360.0
            self.pitch = max(-85.0, min(85.0, self.pitch + dy * 0.7))
            self._last_mouse_pos = pos
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._last_mouse_pos = None

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        self.toggle_3d_mode()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w = self.width()
        h = self.height()

        # Background fill
        painter.fillRect(0, 0, w, h, QColor("#08090c"))

        # Outer border
        pen = QPen(self.accent_color.darker(180), 1)
        painter.setPen(pen)
        painter.drawRect(0, 0, w - 1, h - 1)

        # Header title badge
        mode_badge = " [3D VOXEL]" if self.voxel_3d_mode else ""
        badge_text = f"{self.title}{mode_badge}"
        badge_w = 110 if self.voxel_3d_mode else 85

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(18, 22, 30, 220)))
        painter.drawRoundedRect(6, 6, badge_w, 20, 3, 3)

        painter.setPen(QPen(self.accent_color))
        font = QFont("Segoe UI", 9, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(12, 20, badge_text)

        if self._matrix is None:
            painter.setPen(QPen(QColor("#40485a")))
            painter.setFont(QFont("Segoe UI", 10))
            painter.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, "NO SIGNAL")
            return

        mat_w = self._matrix.width
        mat_h = self._matrix.height
        buf = self._matrix.buffer

        # Resolution indicator (top right)
        res_str = f"{mat_w}×{mat_h}"
        painter.setPen(QPen(QColor("#808a9d")))
        painter.setFont(QFont("Segoe UI", 8))
        painter.drawText(w - 55, 20, res_str)

        # --------------------------------------------------------------
        # 3D Voxel Mode
        # --------------------------------------------------------------
        if self.voxel_3d_mode:
            self._paint_3d_voxels(painter, w, h, mat_w, mat_h, buf)
            return

        # --------------------------------------------------------------
        # 2D Matrix Mode
        # --------------------------------------------------------------
        margin_top = 28
        margin = 8
        avail_w = max(10, w - margin * 2)
        avail_h = max(10, h - margin_top - margin)

        aspect = mat_w / max(mat_h, 1)
        if avail_w / avail_h > aspect:
            draw_h = avail_h
            draw_w = draw_h * aspect
        else:
            draw_w = avail_w
            draw_h = draw_w / aspect

        ox = margin + (avail_w - draw_w) / 2.0
        oy = margin_top + (avail_h - draw_h) / 2.0

        cell_w = draw_w / mat_w
        cell_h = draw_h / mat_h

        painter.fillRect(QRectF(ox, oy, draw_w, draw_h), QColor("#0e1117"))

        if self.dot_mode:
            radius = min(cell_w, cell_h) * 0.42
            painter.setPen(Qt.PenStyle.NoPen)
            for y in range(mat_h):
                py = oy + (y + 0.5) * cell_h
                for x in range(mat_w):
                    px = ox + (x + 0.5) * cell_w
                    r, g, b = int(buf[y, x, 0]), int(buf[y, x, 1]), int(buf[y, x, 2])
                    if r > 0 or g > 0 or b > 0:
                        painter.setBrush(QBrush(QColor(r, g, b)))
                        painter.drawEllipse(QPointF(px, py), radius, radius)
                    else:
                        painter.setBrush(QBrush(QColor(18, 22, 28)))
                        painter.drawEllipse(QPointF(px, py), radius * 0.8, radius * 0.8)
        else:
            for y in range(mat_h):
                ry = oy + y * cell_h
                for x in range(mat_w):
                    rx = ox + x * cell_w
                    r, g, b = int(buf[y, x, 0]), int(buf[y, x, 1]), int(buf[y, x, 2])
                    painter.fillRect(QRectF(rx, ry, cell_w, cell_h), QColor(r, g, b))

        if self.show_grid and min(cell_w, cell_h) >= 4.0:
            grid_pen = QPen(QColor(30, 36, 48, 120), 0.5)
            painter.setPen(grid_pen)
            for x in range(mat_w + 1):
                gx = ox + x * cell_w
                painter.drawLine(QPointF(gx, oy), QPointF(gx, oy + draw_h))
            for y in range(mat_h + 1):
                gy = oy + y * cell_h
                painter.drawLine(QPointF(ox, gy), QPointF(ox + draw_w, gy))

    def _paint_3d_voxels(self, painter: QPainter, w: int, h: int, mat_w: int, mat_h: int, buf) -> None:
        """Render isometric / perspective 3D voxel matrix with depth sorting."""
        center_x = w / 2.0
        center_y = h / 2.0 + 10.0

        rad_yaw = math.radians(self.yaw)
        rad_pitch = math.radians(self.pitch)
        cos_y, sin_y = math.cos(rad_yaw), math.sin(rad_yaw)
        cos_p, sin_p = math.cos(rad_pitch), math.sin(rad_pitch)

        # Scale spacing to fit viewport
        span = max(mat_w, mat_h)
        spacing = min(w, h) * 0.65 / max(1.0, float(span))
        node_radius = max(2.0, min(8.0, spacing * 0.45))

        # 1. Draw 3D Ground Grid
        painter.setPen(QPen(QColor(30, 38, 54, 130), 1))
        ground_step = max(1, span // 6)
        ground_y = 10.0

        for gx in range(-span // 2, span // 2 + 1, ground_step):
            p1_x = gx * spacing
            p1_z = (-span / 2) * spacing
            p2_x = gx * spacing
            p2_z = (span / 2) * spacing

            rx1 = p1_x * cos_y + p1_z * sin_y
            rz1 = -p1_x * sin_y + p1_z * cos_y
            ry1 = ground_y * cos_p - rz1 * sin_p

            rx2 = p2_x * cos_y + p2_z * sin_y
            rz2 = -p2_x * sin_y + p2_z * cos_y
            ry2 = ground_y * cos_p - rz2 * sin_p

            painter.drawLine(
                QPointF(center_x + rx1, center_y + ry1),
                QPointF(center_x + rx2, center_y + ry2),
            )

        # 2. Collect and project 3D voxels
        voxels = []
        for y in range(mat_h):
            for x in range(mat_w):
                r = int(buf[y, x, 0])
                g = int(buf[y, x, 1])
                b = int(buf[y, x, 2])

                # Centered 3D coordinates
                x3 = (x - mat_w / 2.0 + 0.5) * spacing
                z3 = (y - mat_h / 2.0 + 0.5) * spacing
                # Elevation based on brightness
                lum = 0.299 * r + 0.587 * g + 0.114 * b
                y3 = -(lum / 255.0) * (spacing * 2.5)

                # Rotate around Y then X
                x_rot = x3 * cos_y + z3 * sin_y
                z_rot = -x3 * sin_y + z3 * cos_y
                y_rot = y3 * cos_p - z_rot * sin_p
                depth = y3 * sin_p + z_rot * cos_p  # Higher depth = farther away

                screen_x = center_x + x_rot
                screen_y = center_y + y_rot
                voxels.append((depth, screen_x, screen_y, r, g, b, lum))

        # 3. Sort back-to-front (Painters algorithm)
        voxels.sort(key=lambda v: v[0], reverse=True)

        # 4. Render Voxels
        painter.setPen(Qt.PenStyle.NoPen)
        for depth, sx, sy, r, g, b, lum in voxels:
            # Depth attenuation
            if r > 0 or g > 0 or b > 0:
                color = QColor(r, g, b)
                # Outer glow for bright voxels
                if lum > 160:
                    painter.setBrush(QBrush(QColor(r, g, b, 60)))
                    painter.drawEllipse(QPointF(sx, sy), node_radius * 1.8, node_radius * 1.8)

                painter.setBrush(QBrush(color))
                painter.drawEllipse(QPointF(sx, sy), node_radius, node_radius)
            else:
                # Dim inactive voxel wire
                painter.setBrush(QBrush(QColor(16, 20, 28, 140)))
                painter.drawEllipse(QPointF(sx, sy), node_radius * 0.6, node_radius * 0.6)

