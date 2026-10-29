"""
PixelForge — Unified Multi-Protocol Network & Hardware Manager
Orchestrates simultaneous transmission across Art-Net IV, sACN E1.31, USB DMX512, and DVI.
"""

from __future__ import annotations

from typing import Any, Optional

from PyQt6.QtCore import QObject, pyqtSignal

from pixelforge.core.matrix import PixelMatrix
from pixelforge.protocols.artnet import ArtNetOutput
from pixelforge.protocols.sacn import sACNOutput
from pixelforge.protocols.usb_dmx import UsbDmxOutput
from pixelforge.protocols.dvi_output import DviOutputWindow


class ProtocolManager(QObject):
    """Central transmission controller managing all output pipelines."""

    stats_updated = pyqtSignal(dict)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)

        # Output pipelines
        self.artnet: Optional[ArtNetOutput] = None
        self.sacn: Optional[sACNOutput] = None
        self.usb_dmx: Optional[UsbDmxOutput] = None
        self.dvi_window: Optional[DviOutputWindow] = None

    # ------------------------------------------------------------------
    # Art-Net IV
    # ------------------------------------------------------------------

    def enable_artnet(
        self,
        target_ip: str = "255.255.255.255",
        port: int = 6454,
        start_universe: int = 0,
        channel_order: str = "RGB",
    ) -> None:
        self.artnet = ArtNetOutput(target_ip, port, start_universe, channel_order)
        self.artnet.open()

    def disable_artnet(self) -> None:
        if self.artnet:
            self.artnet.close()
            self.artnet = None

    # ------------------------------------------------------------------
    # sACN (ANSI E1.31)
    # ------------------------------------------------------------------

    def enable_sacn(
        self,
        target_ip: Optional[str] = None,
        port: int = 5568,
        start_universe: int = 1,
        priority: int = 100,
    ) -> None:
        self.sacn = sACNOutput(
            target_ip=target_ip,
            port=port,
            start_universe=start_universe,
            priority=priority,
        )
        self.sacn.open()

    def disable_sacn(self) -> None:
        if self.sacn:
            self.sacn.close()
            self.sacn = None

    # ------------------------------------------------------------------
    # USB DMX512 (ENTTEC / FTDI)
    # ------------------------------------------------------------------

    def enable_usb_dmx(self, port_name: str, baudrate: int = 57600) -> bool:
        self.usb_dmx = UsbDmxOutput(port_name, baudrate)
        return self.usb_dmx.open()

    def disable_usb_dmx(self) -> None:
        if self.usb_dmx:
            self.usb_dmx.close()
            self.usb_dmx = None

    # ------------------------------------------------------------------
    # DVI / External Display Window
    # ------------------------------------------------------------------

    def show_dvi_window(self) -> DviOutputWindow:
        if self.dvi_window is None:
            self.dvi_window = DviOutputWindow()
        self.dvi_window.show()
        return self.dvi_window

    def close_dvi_window(self) -> None:
        if self.dvi_window:
            self.dvi_window.close()
            self.dvi_window = None

    # ------------------------------------------------------------------
    # Broadcast Loop
    # ------------------------------------------------------------------

    def broadcast_frame(self, matrix: PixelMatrix, patch: Optional[Any] = None) -> None:
        """Transmit current rendered frame to all active protocols."""
        if self.artnet and self.artnet.is_open:
            self.artnet.send_matrix(matrix, patch)

        if self.sacn and self.sacn.is_open:
            self.sacn.send_matrix(matrix, patch)

        if self.usb_dmx and self.usb_dmx.is_open:
            self.usb_dmx.send_matrix(matrix, patch)

        if self.dvi_window and self.dvi_window.isVisible():
            self.dvi_window.set_matrix(matrix)

    def shutdown_all(self) -> None:
        """Gracefully terminate all open network sockets and serial ports."""
        self.disable_artnet()
        self.disable_sacn()
        self.disable_usb_dmx()
        self.close_dvi_window()

