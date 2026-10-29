"""
PixelForge — End-to-End Art-Net Transmission Test
Spawns a local UDP Art-Net listener on port 6454 and verifies that PixelForge
transmits valid OpDmx packets over the network.
"""

from __future__ import annotations

import os
import sys
import socket
import struct
import threading
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication
from pixelforge.ui.main_window import MainWindow


def test_live_artnet():
    print("Testing live Art-Net network transmission...")

    # Bind UDP receiver on localhost
    recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    recv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    recv_sock.bind(("127.0.0.1", 6454))
    recv_sock.settimeout(2.0)

    received_packets = []
    stop_event = threading.Event()

    def listen_thread():
        while not stop_event.is_set():
            try:
                data, addr = recv_sock.recvfrom(1024)
                received_packets.append(data)
            except socket.timeout:
                continue
            except Exception:
                break

    t = threading.Thread(target=listen_thread, daemon=True)
    t.start()

    app = QApplication(sys.argv)
    window = MainWindow()

    # Configure Art-Net to send to 127.0.0.1
    window.artnet_ip = "127.0.0.1"
    window.artnet_port = 6454
    window.artnet_universe = 0
    window._toggle_artnet(True)

    def check_packets():
        if len(received_packets) >= 7:  # 32x32 matrix spans 7 universes
            print(f"[PASS] Received {len(received_packets)} Art-Net packets over loopback socket!")
            app.quit()

    timer = QTimer()
    timer.timeout.connect(check_packets)
    timer.start(50)

    # Safety cutoff
    QTimer.singleShot(4000, lambda: app.quit())
    app.exec()

    stop_event.set()
    recv_sock.close()

    assert len(received_packets) > 0, "No Art-Net packets were received!"
    
    # Validate the first packet
    pkt = received_packets[0]
    assert pkt[:8] == b"Art-Net\x00", "Packet header mismatch!"
    opcode = struct.unpack("<H", pkt[8:10])[0]
    assert opcode == 0x5000, f"Expected OpCode 0x5000, got {hex(opcode)}"
    proto_ver = struct.unpack(">H", pkt[10:12])[0]
    assert proto_ver == 14, f"Expected ProtVer 14, got {proto_ver}"
    seq = pkt[12]
    subuni = pkt[14]
    net = pkt[15]
    dmx_len = struct.unpack(">H", pkt[16:18])[0]

    print(f"[PASS] Art-Net OpDmx packet verified: OpCode={hex(opcode)}, ProtVer={proto_ver}, Universe={subuni}, Channels={dmx_len}")
    print("[PASS] End-to-end Art-Net transmission test passed!")


if __name__ == "__main__":
    test_live_artnet()
