"""
PixelForge — USB DMX512 Hardware Protocol Sender
Drives physical ENTTEC DMX USB Pro & FTDI USB-to-DMX512 hardware adapters via serial.
"""

from __future__ import annotations

import struct
import time
from typing import Any, Optional

from pixelforge.core.matrix import PixelMatrix


class UsbDmxOutput:
    """USB-DMX512 hardware transmitter supporting ENTTEC DMX USB Pro protocol."""

    ENTTEC_PRO_START = 0x7E
    ENTTEC_PRO_END = 0xE7
    LABEL_OUTPUT_DMX = 6

    def __init__(self, port_name: str = "COM1", baudrate: int = 57600):
        self.port_name = port_name
        self.baudrate = baudrate
        self.universe: int = 0  # Universe to map to physical DMX512 port

        self._serial = None
        self._is_open = False

        # Metrics
        self.frames_sent: int = 0
        self.bytes_sent: int = 0
        self.last_send_time: float = 0.0

    @staticmethod
    def list_available_ports() -> list[dict[str, str]]:
        """List all detected physical and virtual USB/serial COM ports."""
        try:
            import serial.tools.list_ports
            ports = serial.tools.list_ports.comports()
            return [
                {
                    "device": p.device,
                    "description": p.description,
                    "hwid": p.hwid,
                }
                for p in ports
            ]
        except Exception:
            return []

    def open(self, port_name: Optional[str] = None) -> bool:
        if port_name:
            self.port_name = port_name

        if self._is_open:
            self.close()

        try:
            import serial
            self._serial = serial.Serial(
                port=self.port_name,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.1,
            )
            self._is_open = True
            return True
        except Exception:
            self._serial = None
            self._is_open = False
            return False

    def close(self) -> None:
        if self._serial:
            try:
                self._serial.close()
            except Exception:
                pass
            self._serial = None
        self._is_open = False

    @property
    def is_open(self) -> bool:
        return self._is_open

    def build_enttec_packet(self, dmx_channels: bytes) -> bytes:
        """Encapsulate DMX512 data into ENTTEC DMX USB Pro packet."""
        # Pad or truncate payload to 512 channels
        data = dmx_channels[:512].ljust(512, b"\x00")
        length = len(data) + 1  # 1 start code + 512 channels = 513

        pkt = bytearray()
        pkt.append(self.ENTTEC_PRO_START)
        pkt.append(self.LABEL_OUTPUT_DMX)
        pkt.extend(struct.pack("<H", length))  # Little-endian length
        pkt.append(0x00)                       # DMX Start Code
        pkt.extend(data)
        pkt.append(self.ENTTEC_PRO_END)
        return bytes(pkt)

    def send_dmx(self, dmx_channels: bytes) -> bool:
        """Transmit a single universe of 512 DMX channels to USB."""
        if not self._is_open or self._serial is None:
            return False

        packet = self.build_enttec_packet(dmx_channels)
        try:
            self._serial.write(packet)
            self.frames_sent += 1
            self.bytes_sent += len(packet)
            self.last_send_time = time.perf_counter()
            return True
        except Exception:
            return False

    def send_matrix(self, matrix: PixelMatrix, patch: Optional[Any] = None) -> int:
        """Extract universe data from matrix/patch and stream to USB DMX adapter."""
        if not self._is_open:
            return 0

        dmx_data = None
        if patch is not None and getattr(patch, "fixtures", None):
            dmx_map = patch.render_to_dmx(matrix)
            dmx_data = dmx_map.get(self.universe, None)
            if dmx_data is None and dmx_map:
                # Default to first available universe
                dmx_data = next(iter(dmx_map.values()))
        else:
            raw = matrix.to_dmx_bytes("RGB")
            dmx_data = raw[:512]

        if dmx_data is not None and self.send_dmx(dmx_data):
            return 1
        return 0

