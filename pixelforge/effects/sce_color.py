"""SCE Color — Solid colour fill or smooth two-colour gradient."""

from __future__ import annotations
from typing import Any
import numpy as np

from pixelforge.effects.base import (
    BaseEffect, EffectCategory, ParamDef, ParamType,
)


class SCEColor(BaseEffect):
    name = "SCE Color"
    description = "Solid colour fill or smooth gradient between two colours"
    category = EffectCategory.SCE
    parameters = [
        ParamDef("color1", "Color 1", ParamType.COLOR, (0, 120, 255)),
        ParamDef("color2", "Color 2", ParamType.COLOR, (255, 0, 180)),
        ParamDef("mode", "Mode", ParamType.ENUM, "Solid",
                 options=["Solid", "Gradient H", "Gradient V", "Gradient Radial"]),
    ]

    def render(self, width: int, height: int, t: float,
               params: dict[str, Any]) -> np.ndarray:
        c1 = np.array(params.get("color1", (0, 120, 255)), dtype=np.float64)
        c2 = np.array(params.get("color2", (255, 0, 180)), dtype=np.float64)
        mode = params.get("mode", "Solid")

        buf = np.zeros((height, width, 3), dtype=np.float64)

        if mode == "Solid":
            buf[:] = c1

        elif mode == "Gradient H":
            for x in range(width):
                frac = x / max(width - 1, 1)
                buf[:, x] = c1 * (1 - frac) + c2 * frac

        elif mode == "Gradient V":
            for y in range(height):
                frac = y / max(height - 1, 1)
                buf[y, :] = c1 * (1 - frac) + c2 * frac

        elif mode == "Gradient Radial":
            cy, cx = height / 2, width / 2
            max_dist = np.sqrt(cx ** 2 + cy ** 2)
            yy, xx = np.mgrid[0:height, 0:width]
            dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / max_dist
            dist = np.clip(dist, 0, 1)
            for ch in range(3):
                buf[:, :, ch] = c1[ch] * (1 - dist) + c2[ch] * dist

        return np.clip(buf, 0, 255).astype(np.uint8)
