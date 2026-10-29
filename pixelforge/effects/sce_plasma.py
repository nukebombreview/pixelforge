"""SCE Plasma — Classic demoscene plasma using overlapping sinusoidal functions."""

from __future__ import annotations
from typing import Any
import numpy as np

from pixelforge.effects.base import (
    BaseEffect, EffectCategory, ParamDef, ParamType, hsv_to_rgb_array,
)


class SCEPlasma(BaseEffect):
    name = "SCE Plasma"
    description = "Fluid organic plasma colour patterns (classic demoscene aesthetic)"
    category = EffectCategory.SCE
    parameters = [
        ParamDef("speed", "Speed", ParamType.FLOAT, 1.0, 0.1, 5.0, 0.1),
        ParamDef("scale", "Scale", ParamType.FLOAT, 4.0, 1.0, 20.0, 0.5),
        ParamDef("complexity", "Complexity", ParamType.FLOAT, 1.0, 0.2, 3.0, 0.1),
        ParamDef("palette_speed", "Palette Speed", ParamType.FLOAT, 0.3, 0.0, 2.0, 0.05),
        ParamDef("saturation", "Saturation", ParamType.FLOAT, 0.9, 0.0, 1.0, 0.05),
    ]

    def render(self, width: int, height: int, t: float,
               params: dict[str, Any]) -> np.ndarray:
        speed = params.get("speed", 1.0)
        scale = params.get("scale", 4.0)
        complexity = params.get("complexity", 1.0)
        pal_speed = params.get("palette_speed", 0.3)
        sat = params.get("saturation", 0.9)

        ts = t * speed

        yy, xx = np.mgrid[0:height, 0:width]
        xn = xx / max(width, 1) * scale
        yn = yy / max(height, 1) * scale

        # Centre coordinates for radial component
        cx = scale / 2.0
        cy = scale / 2.0

        # Four overlapping sinusoidal layers
        v1 = np.sin(xn * 2.5 * complexity + ts * 1.1)
        v2 = np.sin(yn * 3.0 * complexity + ts * 0.8)
        v3 = np.sin((xn + yn) * 1.8 * complexity + ts * 1.5)
        dist = np.sqrt((xn - cx) ** 2 + (yn - cy) ** 2)
        v4 = np.sin(dist * 3.5 * complexity - ts * 2.0)

        # Combine and normalise to [0, 1]
        v = (v1 + v2 + v3 + v4) / 4.0  # range [-1, 1]
        v = (v + 1.0) / 2.0             # range [ 0, 1]

        # Map through HSV palette
        hue = (v + ts * pal_speed) % 1.0
        s = np.full_like(hue, sat)
        val = np.clip(0.6 + v * 0.4, 0, 1)

        rgb = hsv_to_rgb_array(hue, s, val)
        return (rgb * 255).astype(np.uint8)
