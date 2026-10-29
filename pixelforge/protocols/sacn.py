"""
PixelForge — ANSI E1.31 (sACN) Protocol Sender
Broadcasts multi-universe DMX512 over multicast/unicast Streaming ACN (sACN).
"""

from __future__ import annotations

import socket
import struct
import time
import uuid
from typing import Any, Optional

from pixelforge.core.matrix import PixelMatrix


class sACNOutput:
    """ANSI E1.31 (sACN) streaming lighting network protocol transmitter.

    Implements:
    * Full 3-layer E1.31 packet hierarchy (Root, Framing, DMP)
    * Standard E1.31 multicast addressing (239.255.U_hi.U_lo) and unicast
    * Sequence counters per universe
    * Multi-universe packing & patch routing
    """

    DEFAULT_PORT = 5568
    ACN_IDENTIFIER = b"ASC-E1.17\x00\x00\x00"

    # Vectors
    VECTOR_ROOT_DATA = 0x00000004
    VECTOR_FRAMING_DATA = 0x00000002
    VECTOR_DMP_DATA = 0x02

    def __init__(
        self,
        target_ip: Optional[str] = None,  # None = use multicast
        port: int = DEFAULT_PORT,
        start_universe: int = 1,          # sACN universes are 1-based (1 to 63999)
        source_name: str = "PixelForge sACN Controller",
        priority: int = 100,
    ):
        self.target_ip = target_ip
        self.port = port
        self.start_universe = max(1, start_universe)
        self.source_name = source_name[:63]
        self.priority = min(200, max(0, priority))

        self.cid = uuid.uuid4().bytes
        self._sequence: dict[int, int] = {}
        self._socket: Optional[socket.socket] = None
        self._is_open = False

        # Metrics
        self.packets_sent: int = 0
        self.bytes_sent: int = 0
        self.active_universes: int = 0
        self.last_send_time: float = 0.0

    def open(self) -> None:
        if self._is_open:
            return
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        # Enable multicast TTL = 2 (local network span)
        self._socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        # Allow broadcast
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._is_open = True

    def close(self) -> None:
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

    def get_multicast_ip(self, universe: int) -> str:
        """Calculate E1.31 multicast IP for universe: 239.255.(universe>>8).(universe&0xFF)."""
        u_hi = (universe >> 8) & 0xFF
        u_lo = universe & 0xFF
        return f"239.255.{u_hi}.{u_lo}"

    def build_packet(self, universe: int, dmx_data: bytes) -> bytes:
        """Construct full ANSI E1.31 Root + Framing + DMP packet."""
        # Sequence number (0..255)
        seq = (self._sequence.get(universe, 0) + 1) % 256
        self._sequence[universe] = seq

        num_slots = len(dmx_data)
        dmp_length = 10 + 1 + num_slots  # 10 header + 1 start code + slots
        framing_length = 77 + dmp_length
        root_length = 38 + framing_length

        packet = bytearray()

        # ==============================================================
        # 1. Root Layer (38 bytes)
        # ==============================================================
        packet.extend(struct.pack(">H", 0x0010))               # Preamble Size
        packet.extend(struct.pack(">H", 0x0000))               # Post-amble Size
        packet.extend(self.ACN_IDENTIFIER)                    # ACN Packet Identifier (12 bytes)
        packet.extend(struct.pack(">H", 0x7000 | (root_length & 0x0FFF))) # Flags and Length
        packet.extend(struct.pack(">I", self.VECTOR_ROOT_DATA)) # Vector (VECTOR_ROOT_E131_DATA)
        packet.extend(self.cid)                               # Sender CID (16 bytes)

        # ==============================================================
        # 2. Framing Layer (77 bytes)
        # ==============================================================
        packet.extend(struct.pack(">H", 0x7000 | (framing_length & 0x0FFF))) # Flags and Length
        packet.extend(struct.pack(">I", self.VECTOR_FRAMING_DATA)) # Vector (VECTOR_E131_DATA_PACKET)
        # Source Name (64 bytes null-padded)
        src_bytes = self.source_name.encode("utf-8")[:63].ljust(64, b"\x00")
        packet.extend(src_bytes)
        packet.append(self.priority)                          # Priority (0 - 200)
        packet.extend(struct.pack(">H", 0x0000))               # Synchronization Address
        packet.append(seq)                                    # Sequence Number
        packet.append(0x00)                                   # Options Flags
        packet.extend(struct.pack(">H", universe))             # Universe Number

        # ==============================================================
        # 3. DMP Layer (10 bytes + 1 start code + N DMX slots)
        # ==============================================================
        packet.extend(struct.pack(">H", 0x7000 | (dmp_length & 0x0FFF))) # Flags and Length
        packet.append(self.VECTOR_DMP_DATA)                   # Vector (VECTOR_DMP_SET_PROPERTY)
        packet.append(0xA1)                                   # Address Type & Data Type
        packet.extend(struct.pack(">H", 0x0000))               # First Property Address
        packet.extend(struct.pack(">H", 0x0001))               # Address Increment
        packet.extend(struct.pack(">H", 1 + num_slots))        # Property value count
        packet.append(0x00)                                   # DMX Start Code (0x00)
        packet.extend(dmx_data)                               # DMX512 Payload

        return bytes(packet)

    def send_matrix(self, matrix: PixelMatrix, patch: Optional[Any] = None) -> int:
        """Transmit matrix across sACN universes using multicast or unicast."""
        if not self._is_open or self._socket is None:
            return 0

        sent_count = 0

        if patch is not None and getattr(patch, "fixtures", None):
            dmx_map = patch.render_to_dmx(matrix)
            for universe, dmx_data in dmx_map.items():
                # sACN universes are 1-based (shift if 0-based patch)
                sacn_u = max(1, universe if universe > 0 else universe + 1)
                packet = self.build_packet(sacn_u, dmx_data)
                dst_ip = self.target_ip if self.target_ip else self.get_multicast_ip(sacn_u)
                try:
                    self._socket.sendto(packet, (dst_ip, self.port))
                    self.packets_sent += 1
                    self.bytes_sent += len(packet)
                    sent_count += 1
                except Exception:
                    pass

            self.active_universes = sent_count
            self.last_send_time = time.perf_counter()
            return sent_count

        # Default sequential linear packing
        raw_dmx = matrix.to_dmx_bytes("RGB")
        chunk_size = 510
        universe = self.start_universe

        for offset in range(0, len(raw_dmx), chunk_size):
            chunk = raw_dmx[offset : offset + chunk_size]
            packet = self.build_packet(universe, chunk)
            dst_ip = self.target_ip if self.target_ip else self.get_multicast_ip(universe)
            try:
                self._socket.sendto(packet, (dst_ip, self.port))
                self.packets_sent += 1
                self.bytes_sent += len(packet)
                sent_count += 1
            except Exception:
                pass
            universe += 1

        self.active_universes = sent_count
        self.last_send_time = time.perf_counter()
        return sent_count

