"""
PixelForge — Web & REST Remote Control Server
Lightweight threaded HTTP server providing mobile web dashboard and JSON REST API
for remote lighting control over WiFi/Ethernet (MADRIX HTTP Remote Control equivalent).
"""

from __future__ import annotations

import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional

from PyQt6.QtCore import QObject, pyqtSignal


HTML_DASHBOARD = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>PixelForge Web Remote</title>
  <style>
    :root {
      --bg: #0c0e12;
      --panel: #161b22;
      --border: #30363d;
      --deck-a: #00d2ff;
      --deck-b: #ff2d75;
      --master: #ffb703;
      --text: #e6edf3;
      --accent: #238636;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; user-select: none; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 12px;
      min-height: 100vh;
    }
    header {
      width: 100%;
      max-width: 600px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-bottom: 12px;
      border-bottom: 1px solid var(--border);
      margin-bottom: 14px;
    }
    .brand { font-size: 1.25rem; font-weight: 800; letter-spacing: -0.5px; }
    .brand span { color: var(--deck-a); }
    .badge {
      background: #0f2d1e;
      color: #3fb950;
      border: 1px solid #238636;
      border-radius: 12px;
      padding: 3px 10px;
      font-size: 0.75rem;
      font-weight: 700;
    }
    .container {
      width: 100%;
      max-width: 600px;
      display: flex;
      flex-direction: column;
      gap: 14px;
    }
    .card {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 14px;
    }
    .card-title {
      font-size: 0.75rem;
      font-weight: 700;
      color: #8b949e;
      text-transform: uppercase;
      margin-bottom: 10px;
      display: flex;
      justify-content: space-between;
    }
    .slider-box {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    input[type=range] {
      flex: 1;
      height: 24px;
      accent-color: var(--master);
      cursor: pointer;
    }
    .slider-val {
      font-weight: 700;
      font-size: 1rem;
      min-width: 48px;
      text-align: right;
    }
    .grid-buttons {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 8px;
    }
    button {
      background: #21262d;
      color: var(--text);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 12px 8px;
      font-weight: 700;
      font-size: 0.9rem;
      cursor: pointer;
      transition: all 0.15s ease;
    }
    button:active { transform: scale(0.97); }
    .btn-bo { background: #440c14; border-color: #ff1744; color: #ff8090; }
    .btn-frz { background: #0d2744; border-color: #00d2ff; color: #80e5ff; }
    .btn-go { background: #194d27; border-color: #238636; color: #56d364; font-size: 1.1rem; }
    .btn-stop { background: #331518; border-color: #7a1e28; color: #ea6070; }
    .status-text { font-size: 0.85rem; color: #8b949e; }
  </style>
</head>
<body>
  <header>
    <div class="brand">Pixel<span>Forge</span> Web Remote</div>
    <div class="badge" id="fps-badge">60 FPS</div>
  </header>
  <div class="container">
    <!-- Crossfader -->
    <div class="card">
      <div class="card-title">
        <span>Crossfader (Deck A ◄► Deck B)</span>
        <span id="xfade-val" style="color:var(--master)">50%</span>
      </div>
      <div class="slider-box">
        <span style="color:var(--deck-a);font-weight:bold;">A</span>
        <input type="range" id="xfade-slider" min="0" max="100" value="50" oninput="sendXFade(this.value)">
        <span style="color:var(--deck-b);font-weight:bold;">B</span>
      </div>
    </div>

    <!-- Master Dimmer -->
    <div class="card">
      <div class="card-title">
        <span>Master Dimmer</span>
        <span id="dimmer-val" style="color:var(--master)">100%</span>
      </div>
      <div class="slider-box">
        <input type="range" id="dimmer-slider" min="0" max="100" value="100" oninput="sendDimmer(this.value)">
        <span class="slider-val" id="dimmer-text">100%</span>
      </div>
    </div>

    <!-- Quick Overrides -->
    <div class="card">
      <div class="card-title">Master Overrides</div>
      <div class="grid-buttons">
        <button class="btn-bo" onclick="toggleBlackout()">BLACKOUT</button>
        <button class="btn-frz" onclick="toggleFreeze()">FREEZE</button>
        <button onclick="toggleWhiteout()">WHITE-OUT</button>
      </div>
    </div>

    <!-- Cue Automation -->
    <div class="card">
      <div class="card-title">Cue List Automation</div>
      <div style="display:grid; grid-template-columns: 2fr 1fr; gap: 8px;">
        <button class="btn-go" onclick="sendCueGo()">▶ GO (NEXT CUE)</button>
        <button class="btn-stop" onclick="sendCueStop()">⏹ STOP</button>
      </div>
    </div>

    <!-- Info Footer -->
    <div style="text-align:center; padding: 12px;" class="status-text">
      Connected to PixelForge Lighting Server
    </div>
  </div>

  <script>
    async function apiPost(endpoint, data) {
      try {
        await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data)
        });
      } catch (e) { console.error(e); }
    }

    function sendXFade(val) {
      document.getElementById('xfade-val').innerText = val + '%';
      apiPost('/api/crossfader', { position: val / 100.0 });
    }

    function sendDimmer(val) {
      document.getElementById('dimmer-val').innerText = val + '%';
      document.getElementById('dimmer-text').innerText = val + '%';
      apiPost('/api/dimmer', { dimmer: val / 100.0 });
    }

    function toggleBlackout() { apiPost('/api/blackout', {}); }
    function toggleFreeze() { apiPost('/api/freeze', {}); }
    function toggleWhiteout() { apiPost('/api/whiteout', {}); }
    function sendCueGo() { apiPost('/api/cue/go', {}); }
    function sendCueStop() { apiPost('/api/cue/stop', {}); }

    // Poll status every 800ms
    setInterval(async () => {
      try {
        const res = await fetch('/api/status');
        const d = await res.json();
        document.getElementById('fps-badge').innerText = d.fps.toFixed(1) + ' FPS';
      } catch (e) {}
    }, 800);
  </script>
</body>
</html>
"""


class _RemoteHandler(BaseHTTPRequestHandler):
    """Internal HTTP request handler."""

    server_ref: Optional[HttpRemoteServer] = None

    def log_message(self, format, *args):
        # Silence standard console request log flooding
        pass

    def do_GET(self) -> None:
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_DASHBOARD.encode("utf-8"))

        elif self.path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            status_data = self.server_ref.get_status_dict() if self.server_ref else {}
            self.wfile.write(json.dumps(status_data).encode("utf-8"))

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self) -> None:
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else "{}"
        try:
            data = json.loads(body)
        except Exception:
            data = {}

        if self.path == "/api/crossfader":
            if "position" in data and self.server_ref:
                self.server_ref.crossfader_requested.emit(float(data["position"]))
            self._send_ok()

        elif self.path == "/api/dimmer":
            if "dimmer" in data and self.server_ref:
                self.server_ref.dimmer_requested.emit(float(data["dimmer"]))
            self._send_ok()

        elif self.path == "/api/blackout":
            if self.server_ref:
                self.server_ref.blackout_requested.emit()
            self._send_ok()

        elif self.path == "/api/freeze":
            if self.server_ref:
                self.server_ref.freeze_requested.emit()
            self._send_ok()

        elif self.path == "/api/whiteout":
            if self.server_ref:
                self.server_ref.whiteout_requested.emit()
            self._send_ok()

        elif self.path == "/api/cue/go":
            if self.server_ref:
                self.server_ref.cue_go_requested.emit()
            self._send_ok()

        elif self.path == "/api/cue/stop":
            if self.server_ref:
                self.server_ref.cue_stop_requested.emit()
            self._send_ok()

        else:
            self.send_response(404)
            self.end_headers()

    def _send_ok(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')


class HttpRemoteServer(QObject):
    """Background HTTP REST & Web Remote Control server."""

    crossfader_requested = pyqtSignal(float)
    dimmer_requested = pyqtSignal(float)
    blackout_requested = pyqtSignal()
    freeze_requested = pyqtSignal()
    whiteout_requested = pyqtSignal()
    cue_go_requested = pyqtSignal()
    cue_stop_requested = pyqtSignal()

    def __init__(self, port: int = 8080, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.port = port
        self._server: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._is_running: bool = False
        self._engine_ref = None

    def set_engine_reference(self, engine) -> None:
        self._engine_ref = engine

    def get_status_dict(self) -> Dict[str, Any]:
        if not self._engine_ref:
            return {"fps": 60.0, "status": "online"}
        eng = self._engine_ref
        return {
            "fps": float(eng.fps),
            "width": int(eng.width),
            "height": int(eng.height),
            "crossfader": float(eng.crossfader.position),
            "master_dimmer": float(eng.master_dimmer),
            "blackout": bool(eng.blackout),
            "freeze": bool(eng.freeze),
            "white_out": bool(eng.white_out),
        }

    def start(self) -> bool:
        if self._is_running:
            return True
        try:
            _RemoteHandler.server_ref = self
            # Bind to 0.0.0.0 so phones/tablets on LAN can connect
            self._server = ThreadingHTTPServer(("0.0.0.0", self.port), _RemoteHandler)
            self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
            self._thread.start()
            self._is_running = True
            return True
        except Exception:
            self._server = None
            self._thread = None
            self._is_running = False
            return False

    def stop(self) -> None:
        if self._server:
            try:
                self._server.shutdown()
                self._server.server_close()
            except Exception:
                pass
            self._server = None
            self._thread = None
        self._is_running = False

    @property
    def is_running(self) -> bool:
        return self._is_running

