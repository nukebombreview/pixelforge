"""SCE Strobe — High-intensity strobe, pulse, and flash effect."""

from __future__ import annotations

from typing import Any
import numpy as np

from pixelforge.effects.base import (
    BaseEffect, EffectCategory, ParamDef, ParamType,
)


class SCEStrobe(BaseEffect):
    name = "SCE Strobe"
    description = "High-intensity strobe, pulse, and burst flash with adjustable frequency and duty cycle"
    category = EffectCategory.SCE
    parameters = [
        ParamDef("frequency", "Frequency (Hz)", ParamType.FLOAT, 10.0, 0.5, 30.0, 0.5),
        ParamDef("duty_cycle", "Flash Width (%)", ParamType.FLOAT, 20.0, 5.0, 90.0, 5.0),
        ParamDef("mode", "Mode", ParamType.ENUM, "Strobe",
                 options=["Strobe", "Pulse", "Random Sparkle", "Blinder"]),
        ParamDef("color", "Flash Color", ParamType.COLOR, (255, 255, 255)),
        ParamDef("bg_color", "Background", ParamType.COLOR, (0, 0, 0)),
    ]

    def render(self, width: int, height: int, t: float,
               params: dict[str, Any]) -> np.ndarray:
        freq = max(params.get("frequency", 10.0), 0.1)
        duty = np.clip(params.get("duty_cycle", 20.0) / 100.0, 0.01, 0.99)
        mode = params.get("mode", "Strobe")
        color = np.array(params.get("color", (255, 255, 255)), dtype=np.float64)
        bg = np.array(params.get("bg_color", (0, 0, 0)), dtype=np.float64)

        buf = np.zeros((height, width, 3), dtype=np.float64)

        if mode == "Blinder":
            buf[:] = color
            return np.clip(buf, 0, 255).astype(np.uint8)

        # Time phase in [0, 1]
        cycle_pos = (t * freq) % 1.0

        if mode == "Strobe":
            is_flash = cycle_pos < duty
            buf[:] = color if is_flash else bg

        elif mode == "Pulse":
            # Smooth sine pulse
            intensity = 0.5 * (1.0 + np.sin(2.0 * np.pi * t * freq))
            for ch in range(3):
                buf[:, :, ch] = bg[ch] + (color[ch] - bg[ch]) * intensity

        elif mode == "Random Sparkle":
            # Deterministic noise based on integer time frame
            frame_id = int(t * freq)
            rng = np.random.default_rng(frame_id)
            mask = rng.random((height, width)) < duty
            buf[:] = bg
            buf[mask] = color

        return np.clip(buf, 0, 255).astype(np.uint8)
