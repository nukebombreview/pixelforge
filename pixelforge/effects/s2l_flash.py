"""
S2L Flash — Audio transient strobe and stage blinder effect.
"""

from __future__ import annotations

from typing import Any
import numpy as np

from pixelforge.effects.base import (
    BaseEffect, EffectCategory, ParamDef, ParamType,
)


class S2LFlash(BaseEffect):
    name = "S2L Flash"
    description = "Stage blinder and transient flash effect triggered by strong bass kicks or snare hits"
    category = EffectCategory.S2L
    parameters = [
        ParamDef("trigger", "Trigger Source", ParamType.ENUM, "Bass / Kick Drum",
                 options=["Bass / Kick Drum", "Snare / High-Mid", "Beat Transient"]),
        ParamDef("flash_color", "Flash Color", ParamType.COLOR, (255, 255, 255)),
        ParamDef("bg_color", "Idle Color", ParamType.COLOR, (0, 0, 0)),
        ParamDef("decay", "Decay Time (s)", ParamType.FLOAT, 0.25, 0.05, 1.5, 0.05),
        ParamDef("threshold", "Threshold", ParamType.FLOAT, 0.55, 0.1, 0.9, 0.05),
    ]

    def initialize(self, width: int, height: int) -> None:
        super().initialize(width, height)
        self._intensity = 0.0
        self._last_t = 0.0

    def render(self, width: int, height: int, t: float,
               params: dict[str, Any]) -> np.ndarray:
        trigger = params.get("trigger", "Bass / Kick Drum")
        flash_col = np.array(params.get("flash_color", (255, 255, 255)), dtype=np.float64)
        bg_col = np.array(params.get("bg_color", (0, 0, 0)), dtype=np.float64)
        decay = max(0.02, params.get("decay", 0.25))
        thresh = params.get("threshold", 0.55)

        dt = t - self._last_t
        if dt > 0.2 or dt <= 0:
            dt = 1.0 / 60.0
        self._last_t = t

        # Check audio trigger
        triggered = False
        power = 1.0

        if self.audio_state is not None:
            if trigger == "Bass / Kick Drum":
                triggered = self.audio_state.bass > thresh
                power = self.audio_state.bass
            elif trigger == "Snare / High-Mid":
                triggered = self.audio_state.high_mid > thresh
                power = self.audio_state.high_mid
            else:
                triggered = self.audio_state.is_beat
                power = self.audio_state.beat_intensity
        else:
            # Synthetic flash every 0.6 seconds
            triggered = (int(t * 1.66) != int((t - dt) * 1.66))

        if triggered:
            self._intensity = max(self._intensity, min(1.0, power * 1.2))
        else:
            # Exponential decay
            decay_rate = 1.0 / decay
            self._intensity = max(0.0, self._intensity - dt * decay_rate)

        buf = np.zeros((height, width, 3), dtype=np.float64)
        for c in range(3):
            buf[:, :, c] = bg_col[c] + (flash_col[c] - bg_col[c]) * self._intensity

        return np.clip(buf, 0, 255).astype(np.uint8)
