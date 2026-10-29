"""
PixelForge — SCE Ticker Effect
Scrolling marquee text ticker for messaging, stage announcements, and branding.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from pixelforge.effects.base import BaseEffect, EffectCategory, ParamDef, ParamType


class SceTickerEffect(BaseEffect):
    """Scrolling text banner ticker effect."""

    name = "SCE Ticker"
    category = EffectCategory.SCE
    description = "Scrolls animated marquee text across the LED matrix."

    parameters = [
        ParamDef(
            name="text",
            label="Message Text",
            param_type=ParamType.STRING,
            default="PIXELFORGE LIVE",
        ),
        ParamDef(
            name="direction",
            label="Scroll Direction",
            param_type=ParamType.ENUM,
            default="Left",
            options=["Left", "Right", "Up", "Down", "Static"],
        ),
        ParamDef(
            name="speed",
            label="Scroll Speed",
            param_type=ParamType.FLOAT,
            default=1.5,
            min_val=0.1,
            max_val=8.0,
            step=0.2,
        ),
        ParamDef(
            name="text_color",
            label="Text Color",
            param_type=ParamType.COLOR,
            default=(255, 230, 0),  # Yellow
        ),
        ParamDef(
            name="bg_color",
            label="Background Color",
            param_type=ParamType.COLOR,
            default=(10, 10, 20),   # Dark Navy
        ),
    ]

    def __init__(self):
        super().__init__()
        self._font = ImageFont.load_default()

    def render(
        self,
        width: int,
        height: int,
        time_seconds: float,
        params: Dict[str, Any],
    ) -> np.ndarray:
        text = str(params.get("text", "PIXELFORGE LIVE"))
        direction = params.get("direction", "Left")
        speed = max(0.1, float(params.get("speed", 1.5)))
        text_color = params.get("text_color", (255, 230, 0))
        bg_color = params.get("bg_color", (10, 10, 20))

        # Render high-resolution text strip
        font = ImageFont.load_default()
        bbox = font.getbbox(text)
        text_w = max(1, bbox[2] - bbox[0])
        text_h = max(1, bbox[3] - bbox[1])

        # Large virtual strip
        strip_w = text_w + width * 2
        strip_h = text_h + height * 2

        strip = Image.new("RGB", (strip_w, strip_h), bg_color)
        draw = ImageDraw.Draw(strip)
        draw.text((width, height), text, font=font, fill=text_color)

        # Calculate position based on direction and time
        total_cycle_x = text_w + width
        total_cycle_y = text_h + height

        offset_pixels_x = (time_seconds * speed * 25.0) % max(1.0, float(total_cycle_x))
        offset_pixels_y = (time_seconds * speed * 25.0) % max(1.0, float(total_cycle_y))

        if direction == "Left":
            crop_x = int(offset_pixels_x)
            crop_y = height
        elif direction == "Right":
            crop_x = int(total_cycle_x - offset_pixels_x)
            crop_y = height
        elif direction == "Up":
            crop_x = width
            crop_y = int(offset_pixels_y)
        elif direction == "Down":
            crop_x = width
            crop_y = int(total_cycle_y - offset_pixels_y)
        else:  # Static Center
            crop_x = width + (text_w - width) // 2
            crop_y = height + (text_h - height) // 2

        # Crop to target viewport
        crop_box = (crop_x, crop_y, crop_x + width, crop_y + height)
        cropped = strip.crop(crop_box)
        result = np.array(cropped)

        if result.shape != (height, width, 3):
            result = np.array(Image.fromarray(result).resize((width, height)))

        return result.astype(np.uint8)
