"""
PixelForge — SCE Image Effect
Renders static images (PNG, JPG, BMP, WebP) onto the pixel matrix with
stretching, aspect ratio fitting, tiling, pan/zoom, and rotation.
"""

from __future__ import annotations

import math
import os
from typing import Any, Dict, List, Optional

import numpy as np
from PIL import Image

from pixelforge.effects.base import BaseEffect, EffectCategory, ParamDef, ParamType


class SceImageEffect(BaseEffect):
    """Static image mapping effect with transform controls."""

    name = "SCE Image"
    category = EffectCategory.SCE
    description = "Maps bitmap images to the matrix with scaling, panning, and rotation."

    parameters = [
        ParamDef(
            name="pattern",
            label="Built-in Pattern",
            param_type=ParamType.ENUM,
            default="SMPTE Color Bars",
            options=["SMPTE Color Bars", "PixelForge Logo", "Radial Gradient", "Checker Test", "Custom File"],
        ),
        ParamDef(
            name="file_path",
            label="Custom Image File",
            param_type=ParamType.STRING,
            default="",
        ),
        ParamDef(
            name="fit_mode",
            label="Fit Mode",
            param_type=ParamType.ENUM,
            default="Stretch",
            options=["Stretch", "Fit Aspect", "Fill Aspect", "Tile"],
        ),
        ParamDef(
            name="pan_x",
            label="Pan X",
            param_type=ParamType.FLOAT,
            default=0.0,
            min_val=-1.0,
            max_val=1.0,
            step=0.05,
        ),
        ParamDef(
            name="pan_y",
            label="Pan Y",
            param_type=ParamType.FLOAT,
            default=0.0,
            min_val=-1.0,
            max_val=1.0,
            step=0.05,
        ),
        ParamDef(
            name="rotation",
            label="Rotation",
            param_type=ParamType.FLOAT,
            default=0.0,
            min_val=0.0,
            max_val=360.0,
            step=5.0,
        ),
        ParamDef(
            name="zoom",
            label="Zoom",
            param_type=ParamType.FLOAT,
            default=1.0,
            min_val=0.2,
            max_val=5.0,
            step=0.1,
        ),
    ]

    def __init__(self):
        super().__init__()
        self._loaded_path: Optional[str] = None
        self._cached_image: Optional[Image.Image] = None

    def _generate_pattern_image(self, pattern_name: str, width: int, height: int) -> Image.Image:
        """Generate high-res procedural pattern images if no custom file is loaded."""
        img = Image.new("RGB", (width * 4, height * 4), color="black")
        arr = np.array(img)

        w, h = arr.shape[1], arr.shape[0]

        if pattern_name == "SMPTE Color Bars":
            # 7 standard vertical bars: White, Yellow, Cyan, Green, Magenta, Red, Blue
            colors = [
                (235, 235, 235),  # White
                (235, 235, 16),   # Yellow
                (16, 235, 235),   # Cyan
                (16, 235, 16),    # Green
                (235, 16, 235),   # Magenta
                (235, 16, 16),    # Red
                (16, 16, 235),    # Blue
            ]
            bar_w = w // len(colors)
            for i, col in enumerate(colors):
                x1 = i * bar_w
                x2 = w if i == len(colors) - 1 else (i + 1) * bar_w
                arr[:, x1:x2] = col

        elif pattern_name == "PixelForge Logo":
            # Stylized glowing forge shield
            y_coords, x_coords = np.ogrid[:h, :w]
            center_x, center_y = w / 2, h / 2
            dist = np.sqrt((x_coords - center_x) ** 2 + (y_coords - center_y) ** 2)
            mask = dist < (min(w, h) * 0.42)
            arr[mask] = [0, 210, 255]
            inner_mask = dist < (min(w, h) * 0.28)
            arr[inner_mask] = [255, 45, 117]
            core_mask = dist < (min(w, h) * 0.14)
            arr[core_mask] = [255, 255, 255]

        elif pattern_name == "Radial Gradient":
            y_coords, x_coords = np.ogrid[:h, :w]
            center_x, center_y = w / 2, h / 2
            dist = np.sqrt((x_coords - center_x) ** 2 + (y_coords - center_y) ** 2)
            norm_dist = np.clip(dist / (min(w, h) * 0.5), 0.0, 1.0)
            arr[:, :, 0] = ((1.0 - norm_dist) * 255).astype(np.uint8)
            arr[:, :, 1] = ((norm_dist) * 128).astype(np.uint8)
            arr[:, :, 2] = ((norm_dist) * 255).astype(np.uint8)

        else:  # Checker Test
            block = max(2, w // 8)
            x_blocks = (np.arange(w) // block) % 2
            y_blocks = (np.arange(h) // block) % 2
            grid = (x_blocks[None, :] ^ y_blocks[:, None])
            arr[grid == 1] = [255, 255, 255]
            arr[grid == 0] = [20, 20, 30]

        return Image.fromarray(arr)

    def render(
        self,
        width: int,
        height: int,
        time_seconds: float,
        params: Dict[str, Any],
    ) -> np.ndarray:
        pattern = params.get("pattern", "SMPTE Color Bars")
        custom_path = params.get("file_path", "")
        fit_mode = params.get("fit_mode", "Stretch")
        pan_x = float(params.get("pan_x", 0.0))
        pan_y = float(params.get("pan_y", 0.0))
        rot = float(params.get("rotation", 0.0))
        zoom = max(0.2, float(params.get("zoom", 1.0)))

        # Determine source image
        base_img = None
        if pattern == "Custom File" and custom_path and os.path.exists(custom_path):
            if self._loaded_path != custom_path:
                try:
                    self._cached_image = Image.open(custom_path).convert("RGB")
                    self._loaded_path = custom_path
                except Exception:
                    self._cached_image = None
            base_img = self._cached_image

        if base_img is None:
            base_img = self._generate_pattern_image(pattern, width, height)

        # Apply transforms: Zoom & Rotation
        src_w, src_h = base_img.size
        target_w = int(width * zoom)
        target_h = int(height * zoom)

        if rot != 0.0:
            rotated = base_img.rotate(rot, resample=Image.Resampling.BILINEAR, expand=False)
        else:
            rotated = base_img

        # Fit / Scale
        if fit_mode == "Stretch":
            resized = rotated.resize((width, height), Image.Resampling.BILINEAR)
            result = np.array(resized)

        elif fit_mode == "Fit Aspect":
            ratio = min(width / src_w, height / src_h)
            new_size = (max(1, int(src_w * ratio)), max(1, int(src_h * ratio)))
            scaled = rotated.resize(new_size, Image.Resampling.BILINEAR)
            canvas = Image.new("RGB", (width, height), (0, 0, 0))
            offset_x = (width - new_size[0]) // 2 + int(pan_x * width * 0.5)
            offset_y = (height - new_size[1]) // 2 + int(pan_y * height * 0.5)
            canvas.paste(scaled, (offset_x, offset_y))
            result = np.array(canvas)

        elif fit_mode == "Fill Aspect":
            ratio = max(width / src_w, height / src_h) * zoom
            new_size = (max(1, int(src_w * ratio)), max(1, int(src_h * ratio)))
            scaled = rotated.resize(new_size, Image.Resampling.BILINEAR)
            canvas = Image.new("RGB", (width, height), (0, 0, 0))
            offset_x = (width - new_size[0]) // 2 + int(pan_x * width * 0.5)
            offset_y = (height - new_size[1]) // 2 + int(pan_y * height * 0.5)
            canvas.paste(scaled, (offset_x, offset_y))
            result = np.array(canvas)

        else:  # Tile
            scaled = rotated.resize((max(4, width // 2), max(4, height // 2)), Image.Resampling.NEAREST)
            sw, sh = scaled.size
            canvas = Image.new("RGB", (width * 2, height * 2), (0, 0, 0))
            for y in range(0, height * 2, sh):
                for x in range(0, width * 2, sw):
                    canvas.paste(scaled, (x, y))
            crop_x = int((pan_x + 1.0) * 0.5 * sw) % sw
            crop_y = int((pan_y + 1.0) * 0.5 * sh) % sh
            cropped = canvas.crop((crop_x, crop_y, crop_x + width, crop_y + height))
            result = np.array(cropped)

        # Ensure correct shape and uint8 dtype
        if result.shape != (height, width, 3):
            cropped = Image.fromarray(result).resize((width, height))
            result = np.array(cropped)

        return result.astype(np.uint8)
