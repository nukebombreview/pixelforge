"""SCE Rainbow — Dynamic rotating rainbow sweep effect."""

from __future__ import annotations

from typing import Any
import numpy as np

from pixelforge.effects.base import (
    BaseEffect, EffectCategory, ParamDef, ParamType, hsv_to_rgb_array,
)


class SCERainbow(BaseEffect):
    name = "SCE Rainbow"
    description = "Dynamic rotating multi-color rainbow sweep with wave cycles and angle rotation"
    category = EffectCategory.SCE
    parameters = [
        ParamDef("speed", "Speed", ParamType.FLOAT, 1.0, 0.1, 8.0, 0.1),
        ParamDef("frequency", "Cycles", ParamType.FLOAT, 1.0, 0.2, 5.0, 0.1),
        ParamDef("angle", "Angle (deg)", ParamType.FLOAT, 45.0, 0.0, 360.0, 5.0),
        ParamDef("rotation_speed", "Spin Speed", ParamType.FLOAT, 0.2, -3.0, 3.0, 0.1),
        ParamDef("saturation", "Saturation", ParamType.FLOAT, 1.0, 0.0, 1.0, 0.05),
        ParamDef("brightness", "Brightness", ParamType.FLOAT, 1.0, 0.0, 1.0, 0.05),
    ]

    def render(self, width: int, height: int, t: float,
               params: dict[str, Any]) -> np.ndarray:
        speed = params.get("speed", 1.0)
        freq = params.get("frequency", 1.0)
        base_angle_deg = params.get("angle", 45.0)
        rot_speed = params.get("rotation_speed", 0.2)
        sat = params.get("saturation", 1.0)
        val = params.get("brightness", 1.0)

        # Dynamic angle in radians
        angle_rad = np.radians(base_angle_deg + t * rot_speed * 60.0)
        cos_a = np.cos(angle_rad)
        sin_a = np.sin(angle_rad)

        # Normalized coordinates centered at origin [-0.5, 0.5]
        yy, xx = np.mgrid[0:height, 0:width]
        norm_x = (xx / max(width - 1, 1)) - 0.5
        norm_y = (yy / max(height - 1, 1)) - 0.5

        # Projected position along rotation axis
        projected = norm_x * cos_a + norm_y * sin_a

        # Calculate Hue [0, 1]
        hue = (projected * freq - t * speed * 0.5) % 1.0
        s = np.full((height, width), sat, dtype=np.float64)
        v = np.full((height, width), val, dtype=np.float64)

        rgb = hsv_to_rgb_array(hue, s, v) * 255.0
        return np.clip(rgb, 0, 255).astype(np.uint8)
