"""
PixelForge — Deck
Manages one side of the dual-deck VJ engine (Deck A or Deck B).
"""

from __future__ import annotations

from typing import Any

from pixelforge.core.matrix import PixelMatrix


class Deck:
    """One half of the dual-deck architecture.

    A deck holds:
    * The currently active *effect* instance.
    * The current parameter values for that effect.
    * A dedicated :class:`PixelMatrix` render target.
    * Speed multiplier and solo/mute state.
    """

    def __init__(self, name: str, width: int = 32, height: int = 32):
        self.name = name  # "A" or "B"
        self.matrix = PixelMatrix(width, height)

        # Effect state
        self._effect = None  # BaseEffect instance
        self._effect_name: str = ""
        self._params: dict[str, Any] = {}

        # Playback modifiers
        self.speed: float = 1.0
        self.muted: bool = False

    # ------------------------------------------------------------------
    # Effect management
    # ------------------------------------------------------------------

    @property
    def effect(self):
        return self._effect

    @effect.setter
    def effect(self, eff) -> None:
        """Assign a new effect.  Resets parameters to defaults."""
        self._effect = eff
        if eff is not None:
            self._effect_name = eff.name
            self._params = {p.name: p.default for p in eff.parameters}
            eff.initialize(self.matrix.width, self.matrix.height)
        else:
            self._effect_name = ""
            self._params = {}

    @property
    def effect_name(self) -> str:
        return self._effect_name

    @property
    def params(self) -> dict[str, Any]:
        return self._params

    def set_param(self, key: str, value: Any) -> None:
        self._params[key] = value

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(self, time_sec: float, audio: Optional[Any] = None) -> PixelMatrix:
        """Render the current effect into this deck's matrix and return it."""
        if self._effect is None or self.muted:
            self.matrix.clear()
            return self.matrix

        adjusted_time = time_sec * self.speed
        if hasattr(self._effect, "audio_state"):
            self._effect.audio_state = audio

        buf = self._effect.render(
            self.matrix.width,
            self.matrix.height,
            adjusted_time,
            self._params,
        )
        self.matrix.buffer = buf
        return self.matrix

    # ------------------------------------------------------------------
    # Resize
    # ------------------------------------------------------------------

    def resize(self, width: int, height: int) -> None:
        self.matrix.resize(width, height)
        if self._effect is not None:
            self._effect.initialize(width, height)

    def __repr__(self) -> str:
        return f"Deck({self.name}, effect={self._effect_name!r})"
