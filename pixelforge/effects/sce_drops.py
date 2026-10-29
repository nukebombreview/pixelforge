"""SCE Drops — Animated falling particle / raindrop visuals."""

from __future__ import annotations
from typing import Any
import numpy as np

from pixelforge.effects.base import BaseEffect, EffectCategory, ParamDef, ParamType


class SCEDrops(BaseEffect):
    name = "SCE Drops"
    description = "Falling particles / raindrops with trails across the matrix"
    category = EffectCategory.SCE
    parameters = [
        ParamDef("speed", "Speed", ParamType.FLOAT, 1.0, 0.1, 5.0, 0.1),
        ParamDef("density", "Density", ParamType.FLOAT, 0.15, 0.02, 0.5, 0.01),
        ParamDef("trail_length", "Trail Length", ParamType.FLOAT, 0.4, 0.05, 1.0, 0.05),
        ParamDef("color", "Color", ParamType.COLOR, (0, 180, 255)),
        ParamDef("direction", "Direction", ParamType.ENUM, "Down",
                 options=["Down", "Up", "Left", "Right"]),
    ]

    _MAX_DROPS = 500

    def initialize(self, width: int, height: int) -> None:
        super().initialize(width, height)
        self._drops_x = np.random.uniform(0, width, self._MAX_DROPS)
        self._drops_y = np.random.uniform(-height, 0, self._MAX_DROPS)
        self._drops_speed = np.random.uniform(0.5, 2.0, self._MAX_DROPS)
        self._drops_brightness = np.random.uniform(0.5, 1.0, self._MAX_DROPS)
        self._last_t = 0.0

    def render(self, width: int, height: int, t: float,
               params: dict[str, Any]) -> np.ndarray:
        speed = params.get("speed", 1.0)
        density = params.get("density", 0.15)
        trail = params.get("trail_length", 0.4)
        color = np.array(params.get("color", (0, 180, 255)), dtype=np.float64)
        direction = params.get("direction", "Down")

        dt = t - self._last_t
        if dt > 1.0:
            dt = 1.0 / 60.0  # cap first frame
        self._last_t = t

        # Ensure arrays match
        if len(self._drops_x) < 1:
            self.initialize(width, height)

        # Determine active count based on density
        active = int(self._MAX_DROPS * density)

        # Advance positions
        movement = self._drops_speed[:active] * speed * dt * height * 0.8

        if direction in ("Down", "Up"):
            if direction == "Down":
                self._drops_y[:active] += movement
            else:
                self._drops_y[:active] -= movement

            # Wrap around
            if direction == "Down":
                overflow = self._drops_y[:active] > height
            else:
                overflow = self._drops_y[:active] < -1
            n_overflow = np.sum(overflow)
            if n_overflow > 0:
                self._drops_x[:active][overflow] = np.random.uniform(0, width, n_overflow)
                if direction == "Down":
                    self._drops_y[:active][overflow] = np.random.uniform(-height * trail, 0, n_overflow)
                else:
                    self._drops_y[:active][overflow] = np.random.uniform(height, height * (1 + trail), n_overflow)
                self._drops_speed[:active][overflow] = np.random.uniform(0.5, 2.0, n_overflow)
                self._drops_brightness[:active][overflow] = np.random.uniform(0.5, 1.0, n_overflow)
        else:
            if direction == "Right":
                self._drops_x[:active] += movement
            else:
                self._drops_x[:active] -= movement

            if direction == "Right":
                overflow = self._drops_x[:active] > width
            else:
                overflow = self._drops_x[:active] < -1
            n_overflow = np.sum(overflow)
            if n_overflow > 0:
                self._drops_y[:active][overflow] = np.random.uniform(0, height, n_overflow)
                if direction == "Right":
                    self._drops_x[:active][overflow] = np.random.uniform(-width * trail, 0, n_overflow)
                else:
                    self._drops_x[:active][overflow] = np.random.uniform(width, width * (1 + trail), n_overflow)

        # Render
        buf = np.zeros((height, width, 3), dtype=np.float64)
        trail_px = max(1, int(height * trail))

        for i in range(active):
            if direction in ("Down", "Up"):
                px = int(self._drops_x[i])
                py = int(self._drops_y[i])
                if 0 <= px < width:
                    bri = self._drops_brightness[i]
                    for tr in range(trail_px):
                        if direction == "Down":
                            ty = py - tr
                        else:
                            ty = py + tr
                        if 0 <= ty < height:
                            fade = 1.0 - (tr / trail_px)
                            val = color * bri * fade / 255.0
                            buf[ty, px] = np.maximum(buf[ty, px], val)
            else:
                px = int(self._drops_x[i])
                py = int(self._drops_y[i])
                if 0 <= py < height:
                    bri = self._drops_brightness[i]
                    for tr in range(trail_px):
                        if direction == "Right":
                            tx = px - tr
                        else:
                            tx = px + tr
                        if 0 <= tx < width:
                            fade = 1.0 - (tr / trail_px)
                            val = color * bri * fade / 255.0
                            buf[py, tx] = np.maximum(buf[py, tx], val)

        return (np.clip(buf, 0, 1) * 255).astype(np.uint8)
