"""
PixelForge — Art-Net IV Protocol Sender
Transmits LED matrix pixel data over standard UDP Art-Net DMX packets.
"""

from __future__ import annotations

import socket
import struct
import time
from typing import Optional

import numpy as np

from pixelforge.core.matrix import PixelMatrix


class ArtNetOutput:
    """Sends real-time pixel data across one or more Art-Net DMX universes.

    Supports:
    * Art-Net DMX (OpOutput / OpDmx = 0x5000)
    * Multi-universe packing (up to 170 RGB pixels / 510 channels per universe)
    * Broadcast and Unicast addressing
    * Custom start universe and channel ordering (RGB, GRB, BGR)
    * Transmission metrics (packets sent, data rate, error rate)
    """

    ARTNET_PORT = 6454
    ARTNET_HEADER = b"Art-Net\x00"
    OP_DMX = 0x5000
    PROTOCOL_VERSION = 14
    MAX_CHANNELS_PER_UNIVERSE = 512
    PIXELS_PER_UNIVERSE = 170  # 170 * 3 = 510 channels

    def __init__(
        self,
        target_ip: str = "255.255.255.255",
        port: int = 6454,
        start_universe: int = 0,
        channel_order: str = "RGB",
    ):
        self.target_ip = target_ip
        self.port = port
        self.start_universe = start_universe
        self.channel_order = channel_order.upper()

        self._socket: Optional[socket.socket] = None
        self._is_open = False
        self._sequence: dict[int, int] = {}  # universe -> seq (0-255)

        # Metrics
        self.packets_sent: int = 0
        self.bytes_sent: int = 0
        self.last_send_time: float = 0.0
        self.error_count: int = 0
        self.active_universes: int = 0

    def open(self) -> None:
        """Create and configure the UDP socket."""
        if self._is_open:
            return

        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Enable broadcast
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        # Enable address reuse
        try:
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except (AttributeError, OSError):
            pass

        self._is_open = True

    def close(self) -> None:
        """Close the socket and reset state."""
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None
        self._is_open = False

    @property
    def is_open(self) -> bool:
        return self._is_open

    def build_packet(self, universe: int, dmx_data: bytes) -> bytes:
        """Construct a standard ArtDmx packet (OpDmx = 0x5000).

        ArtDmx packet structure (RFC / Art-Net 4 specification):
        Byte 0-7:   "Art-Net\0"
        Byte 8-9:   OpCode (0x5000 in little-endian = 0x00, 0x50)
        Byte 10-11: ProtVer (14 in big-endian = 0x00, 0x0e)
        Byte 12:    Sequence (0x00 to disable, or 1-255)
        Byte 13:    Physical input port (0x00)
        Byte 14:    SubUni (Universe low byte & 0xFF)
        Byte 15:    Net (Universe high byte & 0x7F)
        Byte 16-17: Length of DMX data in bytes (big-endian, must be even, 2 to 512)
        Byte 18+:   DMX512 payload data
        """
        # Increment sequence counter for this universe (1..255)
        seq = (self._sequence.get(universe, 0) % 255) + 1
        self._sequence[universe] = seq

        length = len(dmx_data)
        # DMX data length must be even according to Art-Net spec
        if length % 2 != 0:
            dmx_data += b"\x00"
            length += 1

        packet = bytearray()
        packet.extend(self.ARTNET_HEADER)
        packet.extend(struct.pack("<H", self.OP_DMX))
        packet.extend(struct.pack(">H", self.PROTOCOL_VERSION))
        packet.append(seq)
        packet.append(0)  # Physical
        packet.append(universe & 0xFF)
        packet.append((universe >> 8) & 0x7F)
        packet.extend(struct.pack(">H", length))
        packet.extend(dmx_data)
        return bytes(packet)

    def send_matrix(self, matrix: PixelMatrix, patch: Optional[Any] = None) -> int:
        """Convert matrix pixel data into DMX channels and broadcast over Art-Net.

        If a Patch layout is provided, pixels are routed according to fixture addresses.
        Otherwise, automatically splits matrix pixels into chunks of 170 pixels per universe.

        Returns number of universe packets sent.
        """
        if not self._is_open or self._socket is None:
            return 0

        sent_count = 0

        # If a visual patch is defined, use patch routing
        if patch is not None and getattr(patch, "fixtures", None):
            dmx_map = patch.render_to_dmx(matrix)
            for universe, dmx_data in dmx_map.items():
                packet = self.build_packet(universe, dmx_data)
                try:
                    self._socket.sendto(packet, (self.target_ip, self.port))
                    self.packets_sent += 1
                    self.bytes_sent += len(packet)
                    sent_count += 1
                except Exception:
                    self.error_count += 1

            self.active_universes = sent_count
            self.last_send_time = time.perf_counter()
            return sent_count

        # Default linear fallback
        raw_dmx = matrix.to_dmx_bytes(self.channel_order)
        channels_per_chunk = self.PIXELS_PER_UNIVERSE * 3  # 510 bytes

        universe = self.start_universe
        for offset in range(0, len(raw_dmx), channels_per_chunk):
            chunk = raw_dmx[offset : offset + channels_per_chunk]
            packet = self.build_packet(universe, chunk)
            try:
                self._socket.sendto(packet, (self.target_ip, self.port))
                self.packets_sent += 1
                self.bytes_sent += len(packet)
                sent_count += 1
            except Exception:
                self.error_count += 1

            universe += 1

        self.active_universes = sent_count
        self.last_send_time = time.perf_counter()
        return sent_count
