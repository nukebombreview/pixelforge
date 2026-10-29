"""
PixelForge — Protocol Manager Configuration Center
Tabbed control dialog for Art-Net IV, ANSI E1.31 sACN, USB DMX512, and DVI Output.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from pixelforge.protocols.manager import ProtocolManager
from pixelforge.protocols.usb_dmx import UsbDmxOutput


class ProtocolConfigDialog(QDialog):
    """Unified configuration dialog for all network and hardware protocols."""

    def __init__(self, manager: ProtocolManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Protocol & Device Manager")
        self.setFixedWidth(480)
        self.manager = manager

        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        tabs = QTabWidget()

        # Tabs
        tabs.addTab(self._build_artnet_tab(), "📡 Art-Net IV")
        tabs.addTab(self._build_sacn_tab(), "🌐 sACN (E1.31)")
        tabs.addTab(self._build_usb_dmx_tab(), "🔌 USB DMX512")
        tabs.addTab(self._build_dvi_tab(), "🖥 DVI / Video Wall")

        main_layout.addWidget(tabs)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._apply_and_close)
        btns.rejected.connect(self.reject)
        main_layout.addWidget(btns)

    def _build_artnet_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(10)

        self.chk_artnet = QCheckBox("Enable Art-Net IV Output")
        self.chk_artnet.setChecked(self.manager.artnet is not None and self.manager.artnet.is_open)
        form.addRow(self.chk_artnet)

        self.edit_artnet_ip = QLineEdit("255.255.255.255")
        if self.manager.artnet:
            self.edit_artnet_ip.setText(self.manager.artnet.target_ip)
        form.addRow("Target IP:", self.edit_artnet_ip)

        self.spin_artnet_port = QSpinBox()
        self.spin_artnet_port.setRange(1, 65535)
        self.spin_artnet_port.setValue(6454)
        form.addRow("UDP Port:", self.spin_artnet_port)

        self.spin_artnet_uni = QSpinBox()
        self.spin_artnet_uni.setRange(0, 32767)
        self.spin_artnet_uni.setValue(0)
        form.addRow("Start Universe:", self.spin_artnet_uni)

        return w

    def _build_sacn_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(10)

        self.chk_sacn = QCheckBox("Enable ANSI E1.31 (sACN) Output")
        self.chk_sacn.setChecked(self.manager.sacn is not None and self.manager.sacn.is_open)
        form.addRow(self.chk_sacn)

        self.combo_sacn_mode = QComboBox()
        self.combo_sacn_mode.addItem("Multicast (239.255.x.x)", None)
        self.combo_sacn_mode.addItem("Unicast", "unicast")
        form.addRow("Transmission Mode:", self.combo_sacn_mode)

        self.edit_sacn_ip = QLineEdit("127.0.0.1")
        form.addRow("Unicast Target IP:", self.edit_sacn_ip)

        self.spin_sacn_port = QSpinBox()
        self.spin_sacn_port.setRange(1, 65535)
        self.spin_sacn_port.setValue(5568)
        form.addRow("sACN Port:", self.spin_sacn_port)

        self.spin_sacn_uni = QSpinBox()
        self.spin_sacn_uni.setRange(1, 63999)
        self.spin_sacn_uni.setValue(1)
        form.addRow("Start Universe (1-63999):", self.spin_sacn_uni)

        self.spin_sacn_prio = QSpinBox()
        self.spin_sacn_prio.setRange(0, 200)
        self.spin_sacn_prio.setValue(100)
        form.addRow("E1.31 Priority (0-200):", self.spin_sacn_prio)

        return w

    def _build_usb_dmx_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(10)

        self.chk_usb = QCheckBox("Enable USB DMX512 (ENTTEC Pro / FTDI)")
        self.chk_usb.setChecked(self.manager.usb_dmx is not None and self.manager.usb_dmx.is_open)
        form.addRow(self.chk_usb)

        self.combo_ports = QComboBox()
        detected = UsbDmxOutput.list_available_ports()
        if detected:
            for p in detected:
                self.combo_ports.addItem(f"{p['device']} - {p['description']}", p["device"])
        else:
            self.combo_ports.addItem("No COM ports detected", "COM1")
        form.addRow("Serial COM Port:", self.combo_ports)

        self.spin_usb_uni = QSpinBox()
        self.spin_usb_uni.setRange(0, 32767)
        self.spin_usb_uni.setValue(0)
        form.addRow("Mapped Patch Universe:", self.spin_usb_uni)

        return w

    def _build_dvi_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(10)

        lbl = QLabel(
            "DVI Output opens a frameless/fullscreen window designed for LED processors\n"
            "(NovaStar, Brompton, Colorlight) and external video walls."
        )
        lbl.setStyleSheet("color: #8b949e;")
        layout.addWidget(lbl)

        btn_launch = QPushButton("🖥 Launch DVI Display Output")
        btn_launch.setStyleSheet("font-weight: bold; background-color: #1a2333; color: #58a6ff; padding: 8px;")
        btn_launch.clicked.connect(self._launch_dvi)
        layout.addWidget(btn_launch)

        self.chk_dvi_grid = QCheckBox("Show LED Tile Alignment Grid")
        self.chk_dvi_grid.toggled.connect(self._toggle_dvi_grid)
        layout.addWidget(self.chk_dvi_grid)

        layout.addStretch(1)
        return w

    def _launch_dvi(self) -> None:
        win = self.manager.show_dvi_window()
        win.show_grid = self.chk_dvi_grid.isChecked()

    def _toggle_dvi_grid(self, checked: bool) -> None:
        if self.manager.dvi_window:
            self.manager.dvi_window.show_grid = checked
            self.manager.dvi_window.update()

    def _apply_and_close(self) -> None:
        # Apply Art-Net
        if self.chk_artnet.isChecked():
            self.manager.enable_artnet(
                target_ip=self.edit_artnet_ip.text().strip(),
                port=self.spin_artnet_port.value(),
                start_universe=self.spin_artnet_uni.value(),
            )
        else:
            self.manager.disable_artnet()

        # Apply sACN
        if self.chk_sacn.isChecked():
            target_ip = None
            if self.combo_sacn_mode.currentData() == "unicast":
                target_ip = self.edit_sacn_ip.text().strip()
            self.manager.enable_sacn(
                target_ip=target_ip,
                port=self.spin_sacn_port.value(),
                start_universe=self.spin_sacn_uni.value(),
                priority=self.spin_sacn_prio.value(),
            )
        else:
            self.manager.disable_sacn()

        # Apply USB DMX
        if self.chk_usb.isChecked():
            port = self.combo_ports.currentData() or "COM1"
            self.manager.enable_usb_dmx(port)
            if self.manager.usb_dmx:
                self.manager.usb_dmx.universe = self.spin_usb_uni.value()
        else:
            self.manager.disable_usb_dmx()

        self.accept()

