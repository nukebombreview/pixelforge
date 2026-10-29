"""
PixelForge — Crossfader
Blends Deck A and Deck B output into a single master output using rich VJ blend & wipe modes.
"""

from __future__ import annotations

import math
from enum import Enum
import numpy as np

from pixelforge.core.matrix import PixelMatrix


class BlendMode(Enum):
    """Supported crossfade and visual transition modes."""
    FADE = "fade"
    EQUAL_POWER = "equal_power"
    HARD_CUT = "hard_cut"
    WIPE_LEFT = "wipe_left"
    WIPE_RIGHT = "wipe_right"
    WIPE_UP = "wipe_up"
    WIPE_DOWN = "wipe_down"
    ADD = "add"
    MULTIPLY = "multiply"
    MAXIMUM = "maximum"
    MINIMUM = "minimum"
    OVERLAY = "overlay"
    DIFFERENCE = "difference"


# Backward compatibility alias
CrossfadeMode = BlendMode


class Crossfader:
    """Mixes two :class:`PixelMatrix` buffers according to a position value.

    ``position = 0.0`` → full Deck A
    ``position = 1.0`` → full Deck B
    """

    def __init__(self):
        self._position: float = 0.0  # 0 = A, 1 = B
        self.blend_mode: BlendMode = BlendMode.FADE

    @property
    def mode(self) -> BlendMode:
        return self.blend_mode

    @mode.setter
    def mode(self, m: BlendMode) -> None:
        self.blend_mode = m

    @property
    def position(self) -> float:
        return self._position

    @position.setter
    def position(self, value: float) -> None:
        self._position = max(0.0, min(1.0, float(value)))

    def mix(self, deck_a: PixelMatrix, deck_b: PixelMatrix) -> PixelMatrix:
        """Return a new matrix blending *deck_a* and *deck_b*."""
        p = self._position
        w = deck_a.width
        h = deck_a.height

        result = PixelMatrix(w, h)

        buf_a = deck_a.buffer.astype(np.float64)
        buf_b = deck_b.buffer.astype(np.float64)

        if self.blend_mode == BlendMode.HARD_CUT:
            result.buffer = deck_a.buffer if p < 0.5 else deck_b.buffer
            return result

        elif self.blend_mode == BlendMode.EQUAL_POWER:
            fa = math.cos(p * math.pi / 2.0)
            fb = math.sin(p * math.pi / 2.0)
            out = fa * buf_a + fb * buf_b

        elif self.blend_mode == BlendMode.WIPE_LEFT:
            split_x = int(p * w)
            out = buf_a.copy()
            if split_x > 0:
                out[:, :split_x] = buf_b[:, :split_x]

        elif self.blend_mode == BlendMode.WIPE_RIGHT:
            split_x = int((1.0 - p) * w)
            out = buf_a.copy()
            if split_x < w:
                out[:, split_x:] = buf_b[:, split_x:]

        elif self.blend_mode == BlendMode.WIPE_UP:
            split_y = int((1.0 - p) * h)
            out = buf_a.copy()
            if split_y < h:
                out[split_y:, :] = buf_b[split_y:, :]

        elif self.blend_mode == BlendMode.WIPE_DOWN:
            split_y = int(p * h)
            out = buf_a.copy()
            if split_y > 0:
                out[:split_y, :] = buf_b[:split_y, :]

        elif self.blend_mode == BlendMode.ADD:
            mixed = np.clip(buf_a + buf_b, 0, 255)
            out = (1.0 - p) * buf_a + p * mixed

        elif self.blend_mode == BlendMode.MULTIPLY:
            mult = (buf_a / 255.0) * (buf_b / 255.0) * 255.0
            out = (1.0 - p) * buf_a + p * mult

        elif self.blend_mode == BlendMode.MAXIMUM:
            out = np.maximum(buf_a * (1.0 - p * 0.5), buf_b * (p * 1.5))
            out = np.clip(out, 0, 255)

        elif self.blend_mode == BlendMode.MINIMUM:
            blended = (1.0 - p) * buf_a + p * buf_b
            out = np.minimum(buf_a, buf_b) * (1.0 - abs(p - 0.5) * 2) + blended * (abs(p - 0.5) * 2)

        elif self.blend_mode == BlendMode.OVERLAY:
            norm_a = buf_a / 255.0
            norm_b = buf_b / 255.0
            overlay = np.where(
                norm_a < 0.5,
                2.0 * norm_a * norm_b,
                1.0 - 2.0 * (1.0 - norm_a) * (1.0 - norm_b),
            ) * 255.0
            out = (1.0 - p) * buf_a + p * overlay

        elif self.blend_mode == BlendMode.DIFFERENCE:
            diff = np.abs(buf_a - buf_b)
            out = (1.0 - p) * buf_a + p * diff

        else:  # BlendMode.FADE (Linear)
            out = (1.0 - p) * buf_a + p * buf_b

        result.buffer = np.clip(out, 0, 255).astype(np.uint8)
        return result

    def __repr__(self) -> str:
        pct_a = int((1.0 - self._position) * 100)
        pct_b = int(self._position * 100)
        return f"Crossfader(A={pct_a}% B={pct_b}% mode={self.blend_mode.value})"
