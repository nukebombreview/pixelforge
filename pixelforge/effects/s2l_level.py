"""
S2L Level — Sound amplitude and volume level meter effect.
"""

from __future__ import annotations

from typing import Any
import numpy as np

from pixelforge.effects.base import (
    BaseEffect, EffectCategory, ParamDef, ParamType,
)


class S2LLevel(BaseEffect):
    name = "S2L Level"
    description = "Audio volume level meter and expanding energy rings mapped to RMS amplitude"
    category = EffectCategory.S2L
    parameters = [
        ParamDef("mode", "Mode", ParamType.ENUM, "Expanding Circle",
                 options=["Expanding Circle", "Vertical Meter", "Horizontal Meter", "Matrix Pump"]),
        ParamDef("target_band", "Target Band", ParamType.ENUM, "Overall Volume",
                 options=["Overall Volume", "Bass Only", "Mid Only", "High Only"]),
        ParamDef("color_scheme", "Color Scheme", ParamType.ENUM, "Green-Yellow-Red",
                 options=["Green-Yellow-Red", "Neon Cyan-Magenta", "Gold Glow", "Electric Purple"]),
        ParamDef("gain", "Sensitivity", ParamType.FLOAT, 1.4, 0.5, 5.0, 0.1),
    ]

    def render(self, width: int, height: int, t: float,
               params: dict[str, Any]) -> np.ndarray:
        mode = params.get("mode", "Expanding Circle")
        band = params.get("target_band", "Overall Volume")
        scheme = params.get("color_scheme", "Green-Yellow-Red")
        gain = params.get("gain", 1.4)

        # Extract target energy
        val = 0.5
        if self.audio_state is not None:
            if band == "Bass Only":
                val = self.audio_state.bass
            elif band == "Mid Only":
                val = self.audio_state.mid
            elif band == "High Only":
                val = self.audio_state.high
            else:
                val = self.audio_state.level
        else:
            val = 0.5 + 0.4 * np.sin(t * 5.0)

        level = np.clip(val * gain, 0.0, 1.0)
        buf = np.zeros((height, width, 3), dtype=np.float64)

        if mode == "Vertical Meter":
            bar_h = int(level * height)
            for y in range(height - bar_h, height):
                frac = (height - y) / max(height, 1)
                col = self._get_level_color(frac, scheme)
                buf[y, :] = col

        elif mode == "Horizontal Meter":
            bar_w = int(level * width)
            for x in range(bar_w):
                frac = x / max(width, 1)
                col = self._get_level_color(frac, scheme)
                buf[:, x] = col

        elif mode == "Expanding Circle":
            cy, cx = height / 2.0, width / 2.0
            max_r = np.sqrt(cx ** 2 + cy ** 2)
            cur_r = level * max_r

            yy, xx = np.mgrid[0:height, 0:width]
            dists = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)

            inside = dists <= cur_r
            fracs = dists[inside] / max(cur_r, 1.0)

            for i, (y, x) in enumerate(zip(*np.where(inside))):
                frac = dists[y, x] / max(cur_r, 1.0)
                buf[y, x] = self._get_level_color(frac, scheme)

        elif mode == "Matrix Pump":
            col = self._get_level_color(level, scheme)
            buf[:] = col * level

        return np.clip(buf, 0, 255).astype(np.uint8)

    @staticmethod
    def _get_level_color(frac: float, scheme: str) -> np.ndarray:
        f = np.clip(frac, 0.0, 1.0)
        if scheme == "Green-Yellow-Red":
            if f < 0.6:
                r = (f / 0.6) * 255.0
                g = 255.0
                b = 0.0
            else:
                r = 255.0
                g = ((1.0 - f) / 0.4) * 255.0
                b = 0.0
            return np.array([r, g, b], dtype=np.float64)

        elif scheme == "Neon Cyan-Magenta":
            r = f * 255.0
            g = (1.0 - f) * 220.0
            b = 255.0
            return np.array([r, g, b], dtype=np.float64)

        elif scheme == "Gold Glow":
            r = 255.0
            g = 180.0 + f * 70.0
            b = f * 100.0
            return np.array([r, g, b], dtype=np.float64)

        else:  # Electric Purple
            r = 160.0 + f * 95.0
            g = 20.0 + f * 50.0
            b = 240.0
            return np.array([r, g, b], dtype=np.float64)
