"""SCE Starfield — 3D perspective starfield flying through space."""

from __future__ import annotations

from typing import Any
import numpy as np

from pixelforge.effects.base import (
    BaseEffect, EffectCategory, ParamDef, ParamType,
)


class SCEStarfield(BaseEffect):
    name = "SCE Starfield"
    description = "3D perspective warp starfield simulation flying through space"
    category = EffectCategory.SCE
    parameters = [
        ParamDef("speed", "Speed", ParamType.FLOAT, 1.5, 0.1, 5.0, 0.1),
        ParamDef("star_count", "Star Count", ParamType.INT, 150, 20, 500, 10),
        ParamDef("color", "Star Color", ParamType.COLOR, (220, 240, 255)),
        ParamDef("warp", "Warp / Streak", ParamType.FLOAT, 0.5, 0.0, 2.0, 0.1),
        ParamDef("direction", "Direction", ParamType.ENUM, "Forward",
                 options=["Forward", "Backward", "Left", "Right"]),
    ]

    _MAX_STARS = 600

    def initialize(self, width: int, height: int) -> None:
        super().initialize(width, height)
        # 3D coordinates: x in [-1, 1], y in [-1, 1], z in [0.01, 1.0]
        self._stars_x = np.random.uniform(-1.0, 1.0, self._MAX_STARS)
        self._stars_y = np.random.uniform(-1.0, 1.0, self._MAX_STARS)
        self._stars_z = np.random.uniform(0.05, 1.0, self._MAX_STARS)
        self._last_t = 0.0

    def render(self, width: int, height: int, t: float,
               params: dict[str, Any]) -> np.ndarray:
        speed = params.get("speed", 1.5)
        count = min(int(params.get("star_count", 150)), self._MAX_STARS)
        color = np.array(params.get("color", (220, 240, 255)), dtype=np.float64)
        warp = params.get("warp", 0.5)
        direction = params.get("direction", "Forward")

        if not hasattr(self, "_stars_x") or len(self._stars_x) < self._MAX_STARS:
            self.initialize(width, height)

        dt = t - self._last_t
        if dt > 0.5 or dt <= 0:
            dt = 1.0 / 60.0
        self._last_t = t

        # Move stars along Z or X
        move = speed * dt * 0.8
        if direction == "Forward":
            self._stars_z[:count] -= move
            # Respawn stars that pass the viewer
            reset = self._stars_z[:count] <= 0.02
            self._stars_z[:count][reset] = np.random.uniform(0.8, 1.0, np.count_nonzero(reset))
            self._stars_x[:count][reset] = np.random.uniform(-1.0, 1.0, np.count_nonzero(reset))
            self._stars_y[:count][reset] = np.random.uniform(-1.0, 1.0, np.count_nonzero(reset))
        elif direction == "Backward":
            self._stars_z[:count] += move
            reset = self._stars_z[:count] >= 1.0
            self._stars_z[:count][reset] = np.random.uniform(0.02, 0.1, np.count_nonzero(reset))
            self._stars_x[:count][reset] = np.random.uniform(-1.0, 1.0, np.count_nonzero(reset))
            self._stars_y[:count][reset] = np.random.uniform(-1.0, 1.0, np.count_nonzero(reset))
        elif direction == "Left":
            self._stars_x[:count] -= move
            reset = self._stars_x[:count] <= -1.0
            self._stars_x[:count][reset] = np.random.uniform(0.9, 1.0, np.count_nonzero(reset))
        else:  # Right
            self._stars_x[:count] += move
            reset = self._stars_x[:count] >= 1.0
            self._stars_x[:count][reset] = np.random.uniform(-1.0, -0.9, np.count_nonzero(reset))

        # Project 3D -> 2D
        cx = width / 2.0
        cy = height / 2.0
        z = np.clip(self._stars_z[:count], 0.02, 1.0)
        sx = cx + (self._stars_x[:count] / z) * cx
        sy = cy + (self._stars_y[:count] / z) * cy

        # Calculate brightness inversely proportional to z (closer = brighter)
        brightness = np.clip((1.0 - z) * 1.4, 0.1, 1.0)

        buf = np.zeros((height, width, 3), dtype=np.float64)

        # Plot star points
        valid = (sx >= 0) & (sx < width) & (sy >= 0) & (sy < height)
        px = sx[valid].astype(int)
        py = sy[valid].astype(int)
        pb = brightness[valid]

        for i in range(len(px)):
            x, y, b = px[i], py[i], pb[i]
            col = color * b
            buf[y, x] = np.maximum(buf[y, x], col)
            # Warp tail
            if warp > 0.05 and b > 0.4:
                tail_len = int(warp * 3.0 * b)
                for step in range(1, tail_len + 1):
                    tx = int(x - (x - cx) * 0.05 * step)
                    ty = int(y - (y - cy) * 0.05 * step)
                    if 0 <= tx < width and 0 <= ty < height:
                        fade = col * (1.0 - step / (tail_len + 1)) * 0.6
                        buf[ty, tx] = np.maximum(buf[ty, tx], fade)

        return np.clip(buf, 0, 255).astype(np.uint8)
