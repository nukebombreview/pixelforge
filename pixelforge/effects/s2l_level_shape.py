"""
S2L Level Shape — Frequency-reactive geometric pulsing shapes.
"""

from __future__ import annotations

from typing import Any
import numpy as np

from pixelforge.effects.base import (
    BaseEffect, EffectCategory, ParamDef, ParamType,
)


class S2LLevelShape(BaseEffect):
    name = "S2L Level Shape"
    description = "Geometric shapes whose scale, border, and rotation pulse directly to audio frequencies"
    category = EffectCategory.S2L
    parameters = [
        ParamDef("shape", "Shape", ParamType.ENUM, "Diamond",
                 options=["Diamond", "Circle", "Square", "Cross", "Hexagon"]),
        ParamDef("band", "Audio Band", ParamType.ENUM, "Bass",
                 options=["Bass", "Mid", "High", "Overall Level"]),
        ParamDef("color", "Shape Color", ParamType.COLOR, (255, 0, 128)),
        ParamDef("fill", "Render Style", ParamType.ENUM, "Concentric Echo",
                 options=["Concentric Echo", "Outline Only", "Solid Fill"]),
        ParamDef("spin", "Spin Speed", ParamType.FLOAT, 1.0, -4.0, 4.0, 0.2),
        ParamDef("scale", "Max Scale", ParamType.FLOAT, 1.3, 0.4, 3.0, 0.1),
    ]

    def render(self, width: int, height: int, t: float,
               params: dict[str, Any]) -> np.ndarray:
        shape_type = params.get("shape", "Diamond")
        band = params.get("band", "Bass")
        color = np.array(params.get("color", (255, 0, 128)), dtype=np.float64)
        fill_mode = params.get("fill", "Concentric Echo")
        spin = params.get("spin", 1.0)
        scale = params.get("scale", 1.3)

        # Determine audio energy
        energy = 0.5
        if self.audio_state is not None:
            if band == "Bass":
                energy = self.audio_state.bass
            elif band == "Mid":
                energy = self.audio_state.mid
            elif band == "High":
                energy = self.audio_state.high
            else:
                energy = self.audio_state.level
        else:
            energy = 0.5 + 0.4 * np.sin(t * 6.0)

        cy, cx = height / 2.0, width / 2.0
        yy, xx = np.mgrid[0:height, 0:width]

        # Rotate coordinates
        angle_rad = t * spin * 2.0
        cos_a = np.cos(angle_rad)
        sin_a = np.sin(angle_rad)

        rx = (xx - cx) * cos_a - (yy - cy) * sin_a
        ry = (xx - cx) * sin_a + (yy - cy) * cos_a

        max_dim = min(cx, cy)
        cur_radius = max(1.5, energy * max_dim * scale)

        buf = np.zeros((height, width, 3), dtype=np.float64)

        # Distance metric per shape
        if shape_type == "Circle":
            dists = np.sqrt(rx ** 2 + ry ** 2)
        elif shape_type == "Square":
            dists = np.maximum(np.abs(rx), np.abs(ry))
        elif shape_type == "Diamond":
            dists = np.abs(rx) + np.abs(ry)
        elif shape_type == "Cross":
            dists = np.minimum(np.abs(rx), np.abs(ry))
        else:  # Hexagon
            dists = np.maximum(np.abs(rx) * 0.866025 + np.abs(ry) * 0.5, np.abs(ry))

        if fill_mode == "Solid Fill":
            inside = dists <= cur_radius
            buf[inside] = color

        elif fill_mode == "Outline Only":
            thickness = max(1.0, cur_radius * 0.2)
            outline = (dists >= cur_radius - thickness) & (dists <= cur_radius)
            buf[outline] = color

        else:  # Concentric Echo
            # Multiple concentric pulsating rings
            period = max(2.0, cur_radius * 0.4)
            wave = 0.5 * (1.0 + np.sin((dists - t * 15.0) / period * 2.0 * np.pi))
            inside = dists <= (cur_radius * 1.5)
            intensity = wave[inside] * np.clip(1.0 - (dists[inside] / (cur_radius * 1.5)), 0, 1)

            for c in range(3):
                buf[:, :, c][inside] = color[c] * intensity

        return np.clip(buf, 0, 255).astype(np.uint8)
