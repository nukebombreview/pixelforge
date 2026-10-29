"""SCE Wave — Concentric sine/cosine ripple waves."""

from __future__ import annotations
from typing import Any
import numpy as np

from pixelforge.effects.base import (
    BaseEffect, EffectCategory, ParamDef, ParamType, hsv_to_rgb_array,
)


class SCEWave(BaseEffect):
    name = "SCE Wave"
    description = "Mathematical sine/cosine ripple waves with adjustable frequency and speed"
    category = EffectCategory.SCE
    parameters = [
        ParamDef("speed", "Speed", ParamType.FLOAT, 2.0, 0.1, 10.0, 0.1),
        ParamDef("frequency", "Frequency", ParamType.FLOAT, 6.0, 1.0, 30.0, 0.5),
        ParamDef("amplitude", "Amplitude", ParamType.FLOAT, 1.0, 0.1, 2.0, 0.1),
        ParamDef("color1", "Color 1", ParamType.COLOR, (0, 200, 255)),
        ParamDef("color2", "Color 2", ParamType.COLOR, (0, 0, 40)),
        ParamDef("wave_type", "Type", ParamType.ENUM, "Concentric",
                 options=["Concentric", "Horizontal", "Vertical", "Cross"]),
    ]

    def render(self, width: int, height: int, t: float,
               params: dict[str, Any]) -> np.ndarray:
        speed = params.get("speed", 2.0)
        freq = params.get("frequency", 6.0)
        amp = params.get("amplitude", 1.0)
        c1 = np.array(params.get("color1", (0, 200, 255)), dtype=np.float64)
        c2 = np.array(params.get("color2", (0, 0, 40)), dtype=np.float64)
        wave_type = params.get("wave_type", "Concentric")

        yy, xx = np.mgrid[0:height, 0:width]
        xn = (xx / max(width - 1, 1) - 0.5) * 2.0  # [-1, 1]
        yn = (yy / max(height - 1, 1) - 0.5) * 2.0

        if wave_type == "Concentric":
            dist = np.sqrt(xn ** 2 + yn ** 2)
            v = np.sin(dist * freq - t * speed) * amp
        elif wave_type == "Horizontal":
            v = np.sin(xn * freq - t * speed) * amp
        elif wave_type == "Vertical":
            v = np.sin(yn * freq - t * speed) * amp
        else:  # Cross
            v = (np.sin(xn * freq - t * speed) + np.sin(yn * freq - t * speed * 0.8)) * 0.5 * amp

        # Normalise to [0, 1]
        v = (v + amp) / (2.0 * amp)
        v = np.clip(v, 0, 1)

        # Map to colour
        buf = np.zeros((height, width, 3), dtype=np.float64)
        for ch in range(3):
            buf[:, :, ch] = c2[ch] + (c1[ch] - c2[ch]) * v

        return np.clip(buf, 0, 255).astype(np.uint8)
