"""SCE Checkerboard — Animated geometric checkerboard pattern."""

from __future__ import annotations

from typing import Any
import numpy as np

from pixelforge.effects.base import (
    BaseEffect, EffectCategory, ParamDef, ParamType,
)


class SCECheckerboard(BaseEffect):
    name = "SCE Checkerboard"
    description = "Animated geometric checkerboard grid with scroll, scaling, and rotation"
    category = EffectCategory.SCE
    parameters = [
        ParamDef("speed_x", "Speed X", ParamType.FLOAT, 1.0, -5.0, 5.0, 0.2),
        ParamDef("speed_y", "Speed Y", ParamType.FLOAT, 1.0, -5.0, 5.0, 0.2),
        ParamDef("cell_size", "Grid Size", ParamType.FLOAT, 4.0, 1.0, 16.0, 0.5),
        ParamDef("rotation", "Rotation (deg)", ParamType.FLOAT, 0.0, 0.0, 360.0, 5.0),
        ParamDef("color1", "Color 1", ParamType.COLOR, (255, 255, 255)),
        ParamDef("color2", "Color 2", ParamType.COLOR, (0, 0, 0)),
    ]

    def render(self, width: int, height: int, t: float,
               params: dict[str, Any]) -> np.ndarray:
        sx = params.get("speed_x", 1.0)
        sy = params.get("speed_y", 1.0)
        size = max(params.get("cell_size", 4.0), 0.5)
        rot_deg = params.get("rotation", 0.0)
        c1 = np.array(params.get("color1", (255, 255, 255)), dtype=np.float64)
        c2 = np.array(params.get("color2", (0, 0, 0)), dtype=np.float64)

        yy, xx = np.mgrid[0:height, 0:width]
        cx = width / 2.0
        cy = height / 2.0
        x_centered = xx - cx
        y_centered = yy - cy

        if rot_deg != 0.0:
            rad = np.radians(rot_deg)
            cos_a = np.cos(rad)
            sin_a = np.sin(rad)
            xr = x_centered * cos_a - y_centered * sin_a + cx
            yr = x_centered * sin_a + y_centered * cos_a + cy
        else:
            xr = xx
            yr = yy

        # Apply scroll translation
        shift_x = t * sx * size
        shift_y = t * sy * size

        cell_x = np.floor((xr + shift_x) / size).astype(int)
        cell_y = np.floor((yr + shift_y) / size).astype(int)

        check = ((cell_x + cell_y) % 2 == 0)

        buf = np.zeros((height, width, 3), dtype=np.float64)
        buf[check] = c1
        buf[~check] = c2

        return np.clip(buf, 0, 255).astype(np.uint8)
