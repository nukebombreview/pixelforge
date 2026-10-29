"""
PixelForge — Rendering Engine
60 fps render loop that drives decks, crossfader, master controls, and protocol output.
"""

from __future__ import annotations

import time
from typing import Optional

from PyQt6.QtCore import QObject, QTimer, Qt, pyqtSignal

from pixelforge.core.crossfader import Crossfader
from pixelforge.core.deck import Deck
from pixelforge.core.matrix import PixelMatrix
from pixelforge.core.patch import Patch
from pixelforge.protocols.artnet import ArtNetOutput
from pixelforge.protocols.manager import ProtocolManager
from pixelforge.audio.analyzer import AudioAnalyzer


class RenderEngine(QObject):
    """Central rendering engine driving the entire PixelForge pipeline.

    Signals
    -------
    frame_rendered(deck_a_matrix, deck_b_matrix, output_matrix)
        Emitted every frame with the three matrices for UI preview updates.
    fps_updated(float)
        Emitted periodically with the measured frames-per-second.
    """

    frame_rendered = pyqtSignal(object, object, object)  # PixelMatrix × 3
    fps_updated = pyqtSignal(float)

    TARGET_FPS = 60

    def __init__(
        self,
        width: int = 32,
        height: int = 32,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)

        self.width = width
        self.height = height

        # --- Dual decks ---
        self.deck_a = Deck("A", width, height)
        self.deck_b = Deck("B", width, height)

        # --- Crossfader ---
        self.crossfader = Crossfader()

        # --- Master controls ---
        self.master_dimmer: float = 1.0  # 0.0 – 1.0
        self.blackout: bool = False
        self.freeze: bool = False
        self.white_out: bool = False

        # --- Output matrix (what goes to the LEDs) ---
        self.output_matrix = PixelMatrix(width, height)

        # --- Protocol manager & Patch ---
        self.protocols = ProtocolManager(self)
        self.patch = Patch(width, height)

        # --- Timing ---
        self._start_time: float = time.perf_counter()
        self._frame_count: int = 0
        self._last_fps_time: float = self._start_time
        self._last_fps: float = 0.0

        # --- Audio analyzer & S2L engine ---
        self.audio = AudioAnalyzer(self)

        # --- Frozen frame ---
        self._frozen_frame: Optional[PixelMatrix] = None

        # --- Render timer ---
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._tick)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the render loop and audio analyzer."""
        self._start_time = time.perf_counter()
        self._last_fps_time = self._start_time
        self._frame_count = 0
        self.audio.start()
        interval_ms = max(1, int(1000 / self.TARGET_FPS))
        self._timer.start(interval_ms)

    def stop(self) -> None:
        """Stop the render loop, audio analyzer, and protocol outputs."""
        self._timer.stop()
        self.audio.stop()
        self.protocols.shutdown_all()

    @property
    def is_running(self) -> bool:
        return self._timer.isActive()

    # ------------------------------------------------------------------
    # Art-Net / Protocol backward-compatible helpers
    # ------------------------------------------------------------------

    @property
    def artnet(self) -> Optional[ArtNetOutput]:
        return self.protocols.artnet

    @artnet.setter
    def artnet(self, val: Optional[ArtNetOutput]) -> None:
        self.protocols.artnet = val

    def enable_artnet(
        self,
        target_ip: str = "255.255.255.255",
        port: int = 6454,
        start_universe: int = 0,
    ) -> None:
        """Enable Art-Net output."""
        self.protocols.enable_artnet(target_ip, port, start_universe)

    def disable_artnet(self) -> None:
        self.protocols.disable_artnet()

    # ------------------------------------------------------------------
    # Resize
    # ------------------------------------------------------------------

    def resize_matrix(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.deck_a.resize(width, height)
        self.deck_b.resize(width, height)
        self.output_matrix.resize(width, height)
        self._frozen_frame = None

    # ------------------------------------------------------------------
    # Core render tick
    # ------------------------------------------------------------------

    def _tick(self) -> None:
        """Called every frame by the QTimer."""
        now = time.perf_counter()
        elapsed = now - self._start_time

        # --- FPS measurement ---
        self._frame_count += 1
        fps_delta = now - self._last_fps_time
        if fps_delta >= 1.0:
            self._last_fps = self._frame_count / fps_delta
            self._frame_count = 0
            self._last_fps_time = now
            self.fps_updated.emit(self._last_fps)

        # --- Freeze: skip rendering, reuse last frame ---
        if self.freeze and self._frozen_frame is not None:
            self.frame_rendered.emit(
                self.deck_a.matrix,
                self.deck_b.matrix,
                self._frozen_frame,
            )
            self.protocols.broadcast_frame(self._frozen_frame, self.patch)
            return

        # --- Audio State ---
        audio_state = self.audio.get_state()

        # --- Render both decks ---
        mat_a = self.deck_a.render(elapsed, audio_state)
        mat_b = self.deck_b.render(elapsed, audio_state)

        # --- Crossfade ---
        output = self.crossfader.mix(mat_a, mat_b)

        # --- Master dimmer ---
        if self.master_dimmer < 1.0:
            output = output.apply_master_dimmer(self.master_dimmer)

        # --- Blackout override ---
        if self.blackout:
            output.clear()

        # --- White-out override ---
        if self.white_out:
            output.fill(255, 255, 255)

        self.output_matrix = output

        # --- Store for freeze ---
        self._frozen_frame = output.copy()

        # --- Protocol output ---
        self.protocols.broadcast_frame(output, self.patch)

        # --- Emit to UI ---
        self.frame_rendered.emit(mat_a, mat_b, output)

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @property
    def elapsed_time(self) -> float:
        return time.perf_counter() - self._start_time

    @property
    def fps(self) -> float:
        return self._last_fps

    def __repr__(self) -> str:
        running = "running" if self.is_running else "stopped"
        return f"RenderEngine({self.width}×{self.height}, {running}, {self.fps:.0f} fps)"
