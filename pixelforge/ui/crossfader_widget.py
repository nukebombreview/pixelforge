"""
PixelForge — Crossfader Widget
Controls Deck A/B blending, blend modes, snap buttons, and automated timed crossfading.
"""

from __future__ import annotations

import time
from typing import Optional

from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from pixelforge.core.crossfader import BlendMode, Crossfader


class CrossfaderWidget(QFrame):
    """MADRIX-style DJ/VJ crossfader control panel.

    Signals
    -------
    position_changed(float)
        Emitted when crossfader position updates (0.0 = A, 1.0 = B).
    blend_mode_changed(BlendMode)
        Emitted when the blend mode changes.
    """

    position_changed = pyqtSignal(float)
    blend_mode_changed = pyqtSignal(object)

    def __init__(self, crossfader: Crossfader, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.crossfader = crossfader
        self._auto_fade_timer = QTimer(self)
        self._auto_fade_timer.timeout.connect(self._auto_fade_step)
        self._fade_start_pos: float = 0.0
        self._fade_target_pos: float = 0.0
        self._fade_start_time: float = 0.0
        self._fade_duration: float = 2.0

        self._init_ui()

    def _init_ui(self) -> None:
        self.setStyleSheet(
            "QFrame { background-color: #161a22; border: 1px solid #2a3142; border-radius: 6px; padding: 6px; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # --- Top row: Mode selector and auto-fade duration ---
        top_row = QHBoxLayout()
        top_row.setSpacing(6)

        lbl_mode = QLabel("BLEND MODE:")
        lbl_mode.setStyleSheet("color: #8b949e; font-size: 10px; font-weight: bold;")
        top_row.addWidget(lbl_mode)

        self.combo_mode = QComboBox()
        for mode in BlendMode:
            self.combo_mode.addItem(mode.value.replace("_", " ").title(), mode)
        self.combo_mode.currentIndexChanged.connect(self._on_mode_selected)
        top_row.addWidget(self.combo_mode, stretch=1)

        lbl_time = QLabel("TIME:")
        lbl_time.setStyleSheet("color: #8b949e; font-size: 10px; font-weight: bold;")
        top_row.addWidget(lbl_time)

        self.spin_fade_time = QDoubleSpinBox()
        self.spin_fade_time.setRange(0.2, 30.0)
        self.spin_fade_time.setSingleStep(0.5)
        self.spin_fade_time.setValue(2.0)
        self.spin_fade_time.setSuffix(" s")
        self.spin_fade_time.setFixedWidth(70)
        top_row.addWidget(self.spin_fade_time)

        layout.addLayout(top_row)

        # --- Middle row: Auto-fade buttons + Snap buttons + Crossfader ---
        mid_row = QHBoxLayout()
        mid_row.setSpacing(8)

        # Auto Fade to Deck A
        self.btn_auto_a = QPushButton("◀ FADE A")
        self.btn_auto_a.setStyleSheet(
            "QPushButton { background-color: #0d2838; color: #00d2ff; border: 1px solid #0099cc; font-weight: bold; padding: 6px 10px; }"
            "QPushButton:hover { background-color: #123d57; }"
        )
        self.btn_auto_a.clicked.connect(lambda: self.start_auto_fade(0.0))
        mid_row.addWidget(self.btn_auto_a)

        # Snap to Deck A
        self.btn_snap_a = QPushButton("A")
        self.btn_snap_a.setFixedWidth(28)
        self.btn_snap_a.setStyleSheet("font-weight: bold; color: #00d2ff;")
        self.btn_snap_a.clicked.connect(lambda: self.set_position(0.0))
        mid_row.addWidget(self.btn_snap_a)

        # Main Crossfader Slider
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setObjectName("crossfader")
        self.slider.setRange(0, 1000)
        self.slider.setValue(0)
        self.slider.setTracking(True)
        self.slider.valueChanged.connect(self._on_slider_moved)
        mid_row.addWidget(self.slider, stretch=1)

        # Snap to Deck B
        self.btn_snap_b = QPushButton("B")
        self.btn_snap_b.setFixedWidth(28)
        self.btn_snap_b.setStyleSheet("font-weight: bold; color: #ff2d75;")
        self.btn_snap_b.clicked.connect(lambda: self.set_position(1.0))
        mid_row.addWidget(self.btn_snap_b)

        # Auto Fade to Deck B
        self.btn_auto_b = QPushButton("FADE B ▶")
        self.btn_auto_b.setStyleSheet(
            "QPushButton { background-color: #380d22; color: #ff2d75; border: 1px solid #cc0055; font-weight: bold; padding: 6px 10px; }"
            "QPushButton:hover { background-color: #571235; }"
        )
        self.btn_auto_b.clicked.connect(lambda: self.start_auto_fade(1.0))
        mid_row.addWidget(self.btn_auto_b)

        layout.addLayout(mid_row)

        # --- Bottom row: Percentage feedback and center snap button ---
        bot_row = QHBoxLayout()

        self.lbl_pos_a = QLabel("100% DECK A")
        self.lbl_pos_a.setStyleSheet("color: #00d2ff; font-weight: bold; font-size: 11px;")
        bot_row.addWidget(self.lbl_pos_a)

        bot_row.addStretch(1)

        self.btn_center = QPushButton("CENTER (50/50)")
        self.btn_center.setFixedHeight(20)
        self.btn_center.setStyleSheet("font-size: 10px; padding: 2px 8px;")
        self.btn_center.clicked.connect(lambda: self.set_position(0.5))
        bot_row.addWidget(self.btn_center)

        bot_row.addStretch(1)

        self.lbl_pos_b = QLabel("0% DECK B")
        self.lbl_pos_b.setStyleSheet("color: #ff2d75; font-weight: bold; font-size: 11px;")
        bot_row.addWidget(self.lbl_pos_b)

        layout.addLayout(bot_row)

    def set_position(self, pos: float) -> None:
        """Set crossfader position programmatically (0.0 to 1.0)."""
        clamped = max(0.0, min(1.0, pos))
        self.slider.blockSignals(True)
        self.slider.setValue(int(clamped * 1000))
        self.slider.blockSignals(False)
        self._update_state(clamped)

    def _on_slider_moved(self, int_val: int) -> None:
        pos = int_val / 1000.0
        self._update_state(pos)

    def _update_state(self, pos: float) -> None:
        self.crossfader.position = pos

        pct_a = int((1.0 - pos) * 100)
        pct_b = int(pos * 100)
        self.lbl_pos_a.setText(f"{pct_a}% DECK A")
        self.lbl_pos_b.setText(f"{pct_b}% DECK B")

        self.position_changed.emit(pos)

    def _on_mode_selected(self, index: int) -> None:
        mode = self.combo_mode.currentData()
        if mode:
            self.crossfader.blend_mode = mode
            self.blend_mode_changed.emit(mode)

    # ------------------------------------------------------------------
    # Automated timed crossfading
    # ------------------------------------------------------------------

    def start_auto_fade(self, target_pos: float) -> None:
        """Smoothly crossfade to target position over specified duration."""
        self._fade_start_pos = self.crossfader.position
        self._fade_target_pos = target_pos
        self._fade_duration = max(0.1, self.spin_fade_time.value())
        self._fade_start_time = time.perf_counter()
        self._auto_fade_timer.start(16)  # ~60 fps animation

    def _auto_fade_step(self) -> None:
        elapsed = time.perf_counter() - self._fade_start_time
        progress = elapsed / self._fade_duration

        if progress >= 1.0:
            self._auto_fade_timer.stop()
            self.set_position(self._fade_target_pos)
            return

        # Smooth cosine interpolation (ease-in-out)
        smooth_progress = 0.5 * (1.0 - np_cos(progress * 3.14159265))
        new_pos = self._fade_start_pos + (self._fade_target_pos - self._fade_start_pos) * smooth_progress
        self.set_position(new_pos)


def np_cos(val: float) -> float:
    import math
    return math.cos(val)
