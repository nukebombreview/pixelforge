"""SCE Fire — Realistic bottom-up fire simulation using vectorised NumPy."""

from __future__ import annotations
from typing import Any
import numpy as np

from pixelforge.effects.base import BaseEffect, EffectCategory, ParamDef, ParamType


class SCEFire(BaseEffect):
    name = "SCE Fire"
    description = "Realistic fire and flame simulation rising from the bottom"
    category = EffectCategory.SCE
    parameters = [
        ParamDef("cooling", "Cooling", ParamType.FLOAT, 0.04, 0.01, 0.15, 0.005),
        ParamDef("sparking", "Sparking", ParamType.FLOAT, 0.55, 0.1, 1.0, 0.05),
        ParamDef("intensity", "Intensity", ParamType.FLOAT, 1.0, 0.3, 2.0, 0.1),
        ParamDef("palette", "Palette", ParamType.ENUM, "Classic",
                 options=["Classic", "Blue", "Green", "Purple", "White"]),
    ]

    def initialize(self, width: int, height: int) -> None:
        super().initialize(width, height)
        self._heat = np.zeros((height, width), dtype=np.float64)

    def render(self, width: int, height: int, t: float,
               params: dict[str, Any]) -> np.ndarray:
        cooling = params.get("cooling", 0.04)
        sparking = params.get("sparking", 0.55)
        intensity = params.get("intensity", 1.0)
        palette = params.get("palette", "Classic")

        # Ensure heat map matches dimensions
        if not hasattr(self, "_heat") or self._heat.shape != (height, width):
            self._heat = np.zeros((height, width), dtype=np.float64)

        h = self._heat

        # 1. Cool every cell by a random amount
        cool_map = np.random.uniform(0, cooling, (height, width))
        h = np.clip(h - cool_map, 0.0, 1.0)

        # 2. Diffuse heat upward (average with neighbours, shift up)
        padded = np.pad(h, ((0, 2), (1, 1)), mode="edge")
        diffused = (
            padded[0:height, 1:width + 1]          # above
            + padded[1:height + 1, 1:width + 1]    # centre
            + padded[2:height + 2, 1:width + 1]    # below
            + padded[1:height + 1, 0:width]        # left
            + padded[1:height + 1, 2:width + 2]    # right
            + padded[2:height + 2, 0:width]        # below-left
            + padded[2:height + 2, 2:width + 2]    # below-right
        ) / 7.0

        # Shift everything up by one row
        h[:-1, :] = diffused[1:, :]
        h[-1, :] = 0.0

        # 3. Spark the bottom rows
        spark_mask = np.random.random(width) < sparking
        n_sparks = np.sum(spark_mask)
        if n_sparks > 0:
            h[-1, spark_mask] = np.random.uniform(0.75, 1.0, n_sparks) * intensity
            h[-2, spark_mask] = np.random.uniform(0.5, 0.85, n_sparks) * intensity

        h = np.clip(h, 0.0, 1.0)
        self._heat = h

        # 4. Map heat to colour palette
        buf = self._heat_to_colour(h, palette)
        return buf

    @staticmethod
    def _heat_to_colour(heat: np.ndarray, palette: str) -> np.ndarray:
        """Map heat values [0, 1] to an RGB palette."""
        h, w = heat.shape
        buf = np.zeros((h, w, 3), dtype=np.uint8)

        if palette == "Classic":
            # Black → Red → Orange → Yellow → White
            r = np.clip(heat * 3.0, 0, 1)
            g = np.clip(heat * 3.0 - 1.0, 0, 1)
            b = np.clip(heat * 3.0 - 2.0, 0, 1)
        elif palette == "Blue":
            r = np.clip(heat * 3.0 - 2.0, 0, 1)
            g = np.clip(heat * 3.0 - 1.5, 0, 1)
            b = np.clip(heat * 2.5, 0, 1)
        elif palette == "Green":
            r = np.clip(heat * 3.0 - 1.8, 0, 1)
            g = np.clip(heat * 2.5, 0, 1)
            b = np.clip(heat * 3.0 - 2.0, 0, 1)
        elif palette == "Purple":
            r = np.clip(heat * 2.5, 0, 1)
            g = np.clip(heat * 3.0 - 2.0, 0, 1)
            b = np.clip(heat * 2.8 - 0.3, 0, 1)
        else:  # White
            r = np.clip(heat * 2.0, 0, 1)
            g = np.clip(heat * 2.0 - 0.3, 0, 1)
            b = np.clip(heat * 2.0 - 0.5, 0, 1)

        buf[:, :, 0] = (r * 255).astype(np.uint8)
        buf[:, :, 1] = (g * 255).astype(np.uint8)
        buf[:, :, 2] = (b * 255).astype(np.uint8)
        return buf
