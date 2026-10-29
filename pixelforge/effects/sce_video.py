"""
PixelForge — SCE Video Effect
Animated GIF playback, video frame sequencing, and procedural looping video generators.
"""

from __future__ import annotations

import math
import os
from typing import Any, Dict, List, Optional

import numpy as np
from PIL import Image, ImageSequence

from pixelforge.effects.base import BaseEffect, EffectCategory, ParamDef, ParamType


class SceVideoEffect(BaseEffect):
    """Video clip and animated GIF playback engine."""

    name = "SCE Video"
    category = EffectCategory.SCE
    description = "Plays animated GIF loops and video frame sequences on the matrix."

    parameters = [
        ParamDef(
            name="source",
            label="Video Loop",
            param_type=ParamType.ENUM,
            default="Techno Tunnel",
            options=["Techno Tunnel", "Radar Sweep", "Retro Grid", "Custom GIF"],
        ),
        ParamDef(
            name="file_path",
            label="Custom GIF File",
            param_type=ParamType.STRING,
            default="",
        ),
        ParamDef(
            name="speed",
            label="Playback Speed",
            param_type=ParamType.FLOAT,
            default=1.0,
            min_val=0.1,
            max_val=4.0,
            step=0.1,
        ),
        ParamDef(
            name="reverse",
            label="Reverse Playback",
            param_type=ParamType.BOOL,
            default=False,
        ),
    ]

    def __init__(self):
        super().__init__()
        self._loaded_path: Optional[str] = None
        self._frames: List[np.ndarray] = []
        self._frame_durations: List[float] = []

    def _load_gif(self, path: str, target_w: int, target_h: int) -> bool:
        """Load animated GIF frames into memory."""
        try:
            im = Image.open(path)
            frames = []
            durations = []
            for frame in ImageSequence.Iterator(im):
                f_rgb = frame.convert("RGB").resize((target_w, target_h), Image.Resampling.BILINEAR)
                frames.append(np.array(f_rgb, dtype=np.uint8))
                duration = frame.info.get("duration", 100) / 1000.0  # seconds
                durations.append(max(0.02, duration))

            self._frames = frames
            self._frame_durations = durations
            self._loaded_path = path
            return len(frames) > 0
        except Exception:
            self._frames = []
            return False

    def render(
        self,
        width: int,
        height: int,
        time_seconds: float,
        params: Dict[str, Any],
    ) -> np.ndarray:
        source = params.get("source", "Techno Tunnel")
        custom_path = params.get("file_path", "")
        speed = max(0.1, float(params.get("speed", 1.0)))
        reverse = bool(params.get("reverse", False))

        t = time_seconds * speed
        if reverse:
            t = -t

        # 1. Custom GIF mode
        if source == "Custom GIF" and custom_path and os.path.exists(custom_path):
            if self._loaded_path != custom_path:
                self._load_gif(custom_path, width, height)

            if self._frames:
                total_duration = sum(self._frame_durations)
                loop_t = (t % total_duration) if total_duration > 0 else 0.0
                accum = 0.0
                frame_idx = 0
                for i, d in enumerate(self._frame_durations):
                    accum += d
                    if accum >= loop_t:
                        frame_idx = i
                        break
                return self._frames[frame_idx]

        # 2. Built-in Procedural Video Loops
        arr = np.zeros((height, width, 3), dtype=np.uint8)
        y, x = np.ogrid[:height, :width]
        cx, cy = width / 2.0, height / 2.0

        if source == "Techno Tunnel":
            # Hypnotic zooming square techno tunnel
            dx = np.abs(x - cx)
            dy = np.abs(y - cy)
            max_d = np.maximum(dx, dy)
            rings = (max_d * 0.8 - t * 12.0) % 10.0
            mask = rings < 4.0

            hue_shift = (t * 0.5 + max_d * 0.05) % 1.0
            r = (np.sin(hue_shift * 2 * math.pi) * 127 + 128).astype(np.uint8)
            g = (np.sin((hue_shift + 0.33) * 2 * math.pi) * 127 + 128).astype(np.uint8)
            b = (np.sin((hue_shift + 0.66) * 2 * math.pi) * 127 + 128).astype(np.uint8)

            arr[mask, 0] = r[mask]
            arr[mask, 1] = g[mask]
            arr[mask, 2] = b[mask]

        elif source == "Radar Sweep":
            # 360 degree military radar sweep with phosphor fade
            angle = np.arctan2(y - cy, x - cx)
            sweep_angle = (t * 3.0) % (2 * math.pi) - math.pi
            diff = (angle - sweep_angle + math.pi) % (2 * math.pi)
            trail = np.clip(1.0 - diff / (math.pi * 0.8), 0.0, 1.0) ** 3.0

            dist = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
            circles = np.abs((dist % (width / 4.0)) - 1.0) < 0.6

            arr[:, :, 1] = np.clip(trail * 255 + circles * 80, 0, 255).astype(np.uint8)
            arr[:, :, 0] = (circles * 30).astype(np.uint8)
            arr[:, :, 2] = (circles * 30).astype(np.uint8)

        else:  # Retro Grid
            # Synthwave horizon perspective grid
            horiz = int(height * 0.35)
            # Sky
            sky_y = y[:horiz, :]
            arr[:horiz, :, 0] = (sky_y * 120 / horiz).astype(np.uint8)
            arr[:horiz, :, 2] = 80

            # Ground perspective
            ground_h = height - horiz
            if ground_h > 0:
                gy = y[horiz:, :] - horiz
                persp = (gy + 1.0) / float(ground_h)
                grid_y = np.abs(((gy * 4.0 / persp) - t * 40.0) % 20.0) < 1.8
                grid_x = np.abs(((x - cx) / persp) % 15.0) < 1.2
                mask = grid_y | grid_x
                arr[horiz:, :, :][mask] = [0, 230, 255]

        return arr
