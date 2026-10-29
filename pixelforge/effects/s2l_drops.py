"""
S2L Drops — Beat-triggered explosive particle fountains and audio drops.
"""

from __future__ import annotations

from typing import Any
import numpy as np

from pixelforge.effects.base import (
    BaseEffect, EffectCategory, ParamDef, ParamType, hsv_to_rgb_array,
)


class S2LDrops(BaseEffect):
    name = "S2L Drops"
    description = "Beat-reactive particle fountains and explosions triggered by musical bass transients"
    category = EffectCategory.S2L
    parameters = [
        ParamDef("mode", "Burst Style", ParamType.ENUM, "Radial Burst",
                 options=["Radial Burst", "Fountain Up", "Gravity Shower"]),
        ParamDef("color_mode", "Color Palette", ParamType.ENUM, "Rainbow",
                 options=["Rainbow", "Cyan Ice", "Fire Sparks", "Custom Color"]),
        ParamDef("color", "Custom Color", ParamType.COLOR, (0, 220, 255)),
        ParamDef("count", "Particle Count", ParamType.INT, 180, 40, 500, 20),
        ParamDef("gravity", "Gravity", ParamType.FLOAT, 1.2, 0.0, 4.0, 0.2),
    ]

    _MAX_PARTS = 500

    def initialize(self, width: int, height: int) -> None:
        super().initialize(width, height)
        self._px = np.zeros(self._MAX_PARTS, dtype=np.float64)
        self._py = np.zeros(self._MAX_PARTS, dtype=np.float64)
        self._vx = np.zeros(self._MAX_PARTS, dtype=np.float64)
        self._vy = np.zeros(self._MAX_PARTS, dtype=np.float64)
        self._life = np.zeros(self._MAX_PARTS, dtype=np.float64)
        self._hue = np.random.uniform(0.0, 1.0, self._MAX_PARTS)
        self._last_t = 0.0
        self._was_beat = False

    def render(self, width: int, height: int, t: float,
               params: dict[str, Any]) -> np.ndarray:
        mode = params.get("mode", "Radial Burst")
        col_mode = params.get("color_mode", "Rainbow")
        custom_col = np.array(params.get("color", (0, 220, 255)), dtype=np.float64)
        count = min(int(params.get("count", 180)), self._MAX_PARTS)
        grav = params.get("gravity", 1.2)

        if not hasattr(self, "_px") or len(self._px) < self._MAX_PARTS:
            self.initialize(width, height)

        dt = t - self._last_t
        if dt > 0.2 or dt <= 0:
            dt = 1.0 / 60.0
        self._last_t = t

        # Detect beat
        is_beat = False
        beat_power = 0.5
        if self.audio_state is not None:
            is_beat = self.audio_state.is_beat
            beat_power = max(0.5, self.audio_state.beat_intensity)
        else:
            # Synthetic periodic beat every 0.5s
            is_beat = (int(t * 2.0) != int((t - dt) * 2.0))

        # Spawn burst on beat
        if is_beat and not self._was_beat:
            self._spawn_burst(count, width, height, mode, beat_power)
        self._was_beat = is_beat

        # Physics update
        active = self._life[:count] > 0
        if np.any(active):
            self._px[:count][active] += self._vx[:count][active] * dt * 25.0
            self._py[:count][active] += self._vy[:count][active] * dt * 25.0
            self._vy[:count][active] += grav * dt * 20.0
            self._life[:count][active] -= dt * 1.4

        # Render onto canvas
        buf = np.zeros((height, width, 3), dtype=np.float64)

        for i in range(count):
            if self._life[i] <= 0:
                continue
            ix = int(self._px[i])
            iy = int(self._py[i])
            if 0 <= ix < width and 0 <= iy < height:
                br = np.clip(self._life[i], 0.0, 1.0)
                col = self._get_col(self._hue[i], col_mode, custom_col) * br
                buf[iy, ix] = np.maximum(buf[iy, ix], col)

        return np.clip(buf, 0, 255).astype(np.uint8)

    def _spawn_burst(self, count: int, w: int, h: int, mode: str, power: float) -> None:
        cx, cy = w / 2.0, h / 2.0

        if mode == "Radial Burst":
            angles = np.random.uniform(0, 2 * np.pi, count)
            speeds = np.random.uniform(2.0, 8.0, count) * power
            self._px[:count] = cx
            self._py[:count] = cy
            self._vx[:count] = np.cos(angles) * speeds
            self._vy[:count] = np.sin(angles) * speeds
            self._life[:count] = np.random.uniform(0.6, 1.0, count)

        elif mode == "Fountain Up":
            self._px[:count] = np.random.uniform(cx - w * 0.2, cx + w * 0.2, count)
            self._py[:count] = h - 1
            self._vx[:count] = np.random.uniform(-3.0, 3.0, count)
            self._vy[:count] = np.random.uniform(-10.0, -4.0, count) * power
            self._life[:count] = np.random.uniform(0.8, 1.2, count)

        else:  # Gravity Shower
            self._px[:count] = np.random.uniform(0, w, count)
            self._py[:count] = 0
            self._vx[:count] = np.random.uniform(-1.0, 1.0, count)
            self._vy[:count] = np.random.uniform(1.0, 6.0, count) * power
            self._life[:count] = np.random.uniform(0.7, 1.1, count)

    @staticmethod
    def _get_col(hue: float, mode: str, custom_col: np.ndarray) -> np.ndarray:
        if mode == "Rainbow":
            h6 = (hue % 1.0) * 6.0
            i = int(h6)
            f = h6 - i
            q = 1.0 - f
            t = f
            if i == 0:
                r, g, b = 1.0, t, 0.0
            elif i == 1:
                r, g, b = q, 1.0, 0.0
            elif i == 2:
                r, g, b = 0.0, 1.0, t
            elif i == 3:
                r, g, b = 0.0, q, 1.0
            elif i == 4:
                r, g, b = t, 0.0, 1.0
            else:
                r, g, b = 1.0, 0.0, q
            return np.array([r * 255, g * 255, b * 255], dtype=np.float64)

        elif mode == "Cyan Ice":
            return np.array([20, 200 + hue * 55, 255], dtype=np.float64)

        elif mode == "Fire Sparks":
            return np.array([255, 100 + hue * 155, 10], dtype=np.float64)

        return custom_col
