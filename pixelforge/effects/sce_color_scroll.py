"""SCE Color Scroll — Animated scrolling colour gradient."""

from __future__ import annotations
from typing import Any
import numpy as np

from pixelforge.effects.base import (
    BaseEffect, EffectCategory, ParamDef, ParamType, hsv_to_rgb_array,
)


class SCEColorScroll(BaseEffect):
    name = "SCE Color Scroll"
    description = "Scrolling colour gradient with adjustable speed and direction"
    category = EffectCategory.SCE
    parameters = [
        ParamDef("speed", "Speed", ParamType.FLOAT, 1.0, 0.1, 10.0, 0.1),
        ParamDef("bands", "Bands", ParamType.INT, 3, 1, 16, 1),
        ParamDef("saturation", "Saturation", ParamType.FLOAT, 1.0, 0.0, 1.0, 0.05),
        ParamDef("direction", "Direction", ParamType.ENUM, "Right",
                 options=["Right", "Left", "Down", "Up", "Diagonal"]),
    ]

    def render(self, width: int, height: int, t: float,
               params: dict[str, Any]) -> np.ndarray:
        speed = params.get("speed", 1.0)
        bands = params.get("bands", 3)
        sat = params.get("saturation", 1.0)
        direction = params.get("direction", "Right")

        yy, xx = np.mgrid[0:height, 0:width]
        xn = xx / max(width - 1, 1)
        yn = yy / max(height - 1, 1)

        if direction == "Right":
            coord = xn
        elif direction == "Left":
            coord = 1.0 - xn
        elif direction == "Down":
            coord = yn
        elif direction == "Up":
            coord = 1.0 - yn
        else:  # Diagonal
            coord = (xn + yn) / 2.0

        hue = (coord * bands + t * speed * 0.5) % 1.0
        s = np.full_like(hue, sat)
        v = np.ones_like(hue)

        rgb = hsv_to_rgb_array(hue, s, v)
        return (rgb * 255).astype(np.uint8)
