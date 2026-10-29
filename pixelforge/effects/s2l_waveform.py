"""
S2L Waveform — Real-time oscilloscope audio waveform visualizer.
"""

from __future__ import annotations

from typing import Any
import numpy as np

from pixelforge.effects.base import (
    BaseEffect, EffectCategory, ParamDef, ParamType,
)


class S2LWaveform(BaseEffect):
    name = "S2L Waveform"
    description = "Real-time audio oscilloscope visualizer tracing raw microphone/music sound waves"
    category = EffectCategory.S2L
    parameters = [
        ParamDef("style", "Style", ParamType.ENUM, "Oscilloscope Line",
                 options=["Oscilloscope Line", "Solid Wave Fill", "Circular Oscilloscope"]),
        ParamDef("line_color", "Wave Color", ParamType.COLOR, (0, 255, 120)),
        ParamDef("bg_color", "Background", ParamType.COLOR, (0, 10, 20)),
        ParamDef("gain", "Vertical Gain", ParamType.FLOAT, 1.5, 0.2, 5.0, 0.1),
        ParamDef("thickness", "Thickness", ParamType.INT, 1, 1, 3, 1),
    ]

    def render(self, width: int, height: int, t: float,
               params: dict[str, Any]) -> np.ndarray:
        style = params.get("style", "Oscilloscope Line")
        line_col = np.array(params.get("line_color", (0, 255, 120)), dtype=np.float64)
        bg_col = np.array(params.get("bg_color", (0, 10, 20)), dtype=np.float64)
        gain = params.get("gain", 1.5)
        thickness = int(params.get("thickness", 1))

        buf = np.zeros((height, width, 3), dtype=np.float64)
        buf[:] = bg_col

        # Retrieve waveform from audio state
        if self.audio_state is not None and hasattr(self.audio_state, "waveform"):
            raw_wave = self.audio_state.waveform
        else:
            raw_wave = np.sin(np.linspace(0, 4 * np.pi, 512) + t * 15.0) * 0.7

        mid_y = height / 2.0

        if style == "Oscilloscope Line":
            # Resample waveform to width
            indices = np.linspace(0, len(raw_wave) - 1, width).astype(int)
            wave_y = np.clip(raw_wave[indices] * gain, -1.0, 1.0)

            for x in range(width):
                py = int(mid_y - wave_y[x] * (mid_y - 1))
                py = max(0, min(height - 1, py))
                y_min = max(0, py - thickness + 1)
                y_max = min(height, py + thickness)
                buf[y_min:y_max, x] = line_col

        elif style == "Solid Wave Fill":
            indices = np.linspace(0, len(raw_wave) - 1, width).astype(int)
            wave_y = np.clip(raw_wave[indices] * gain, -1.0, 1.0)

            for x in range(width):
                py = int(mid_y - wave_y[x] * (mid_y - 1))
                y1 = min(int(mid_y), py)
                y2 = max(int(mid_y), py) + 1
                buf[y1:y2, x] = line_col

        elif style == "Circular Oscilloscope":
            cy, cx = height / 2.0, width / 2.0
            base_r = min(cx, cy) * 0.55
            max_r = min(cx, cy) * 0.95

            n_pts = min(180, len(raw_wave))
            step = len(raw_wave) // n_pts
            sampled = raw_wave[::step][:n_pts]

            angles = np.linspace(0, 2 * np.pi, len(sampled), endpoint=False)
            rads = np.clip(base_r + sampled * gain * (max_r - base_r), 2.0, max_r)

            pxs = (cx + rads * np.cos(angles)).astype(int)
            pys = (cy + rads * np.sin(angles)).astype(int)

            for x, y in zip(pxs, pys):
                if 0 <= x < width and 0 <= y < height:
                    buf[y, x] = line_col

        return np.clip(buf, 0, 255).astype(np.uint8)
