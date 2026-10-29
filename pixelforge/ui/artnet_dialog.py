"""
PixelForge — Art-Net Configuration Dialog
Configures broadcast/unicast IP, UDP port, start universe, and channel layout.
"""

from __future__ import annotations

import socket
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class ArtNetDialog(QDialog):
    """Modal dialog for configuring Art-Net IV protocol transmission."""

    def __init__(
        self,
        current_ip: str = "255.255.255.255",
        current_port: int = 6454,
        start_universe: int = 0,
        channel_order: str = "RGB",
        matrix_width: int = 32,
        matrix_height: int = 32,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Art-Net IV Output Configuration")
        self.setFixedWidth(420)
        self.setModal(True)

        self.current_ip = current_ip
        self.current_port = current_port
        self.start_universe = start_universe
        self.channel_order = channel_order
        self.matrix_width = matrix_width
        self.matrix_height = matrix_height

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Form group
        grp = QGroupBox("Network & DMX Parameters")
        form = QFormLayout(grp)
        form.setSpacing(10)

        # Target IP
        self.edit_ip = QLineEdit(self.current_ip)
        self.edit_ip.setPlaceholderText("255.255.255.255 or 127.0.0.1 or device IP")
        form.addRow("Target IP Address:", self.edit_ip)

        # Port
        self.spin_port = QSpinBox()
        self.spin_port.setRange(1, 65535)
        self.spin_port.setValue(self.current_port)
        form.addRow("UDP Port (Default 6454):", self.spin_port)

        # Start Universe
        self.spin_universe = QSpinBox()
        self.spin_universe.setRange(0, 32767)
        self.spin_universe.setValue(self.start_universe)
        self.spin_universe.valueChanged.connect(self._update_calc)
        form.addRow("Start Sub-Net / Universe:", self.spin_universe)

        # Channel Order
        self.combo_order = QComboBox()
        for ord_str in ["RGB", "GRB", "BGR", "BRG", "RBG", "GBR"]:
            self.combo_order.addItem(ord_str)
        idx = self.combo_order.findText(self.channel_order)
        if idx >= 0:
            self.combo_order.setCurrentIndex(idx)
        form.addRow("LED Channel Order:", self.combo_order)

        layout.addWidget(grp)

        # Info Box (Calculated requirements)
        self.lbl_calc = QLabel()
        self.lbl_calc.setStyleSheet(
            "background-color: #161b22; border: 1px solid #30363d; border-radius: 4px; padding: 8px; color: #58a6ff; font-family: monospace;"
        )
        self._update_calc()
        layout.addWidget(self.lbl_calc)

        # Buttons
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _update_calc(self) -> None:
        total_pixels = self.matrix_width * self.matrix_height
        total_channels = total_pixels * 3
        pixels_per_uni = 170  # 510 channels
        universes_needed = max(1, (total_pixels + pixels_per_uni - 1) // pixels_per_uni)
        start_u = self.spin_universe.value()
        end_u = start_u + universes_needed - 1

        self.lbl_calc.setText(
            f"Matrix: {self.matrix_width}×{self.matrix_height} ({total_pixels} pixels)\n"
            f"DMX Channels: {total_channels} (RGB)\n"
            f"Universes Required: {universes_needed} (Univ {start_u} – {end_u})\n"
            f"Bandwidth @ 60fps: ~{(universes_needed * 530 * 60 * 8) / 1_000_000:.2f} Mbps"
        )

    def get_settings(self) -> dict:
        return {
            "target_ip": self.edit_ip.text().strip(),
            "port": self.spin_port.value(),
            "start_universe": self.spin_universe.value(),
            "channel_order": self.combo_order.currentText(),
        }
