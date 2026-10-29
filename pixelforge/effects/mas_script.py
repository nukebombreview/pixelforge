"""
PixelForge — MAS Scripting Sandbox (MADRIX Script Equivalent)
Real-time programmable Python procedural effect generator with live code compilation,
audio state integration, and exception handling.
"""

from __future__ import annotations

import math
import sys
import traceback
from typing import Any, Dict, List, Optional

import numpy as np

from pixelforge.effects.base import BaseEffect, EffectCategory, ParamDef, ParamType


SAMPLE_SCRIPTS = {
    "Audio Pulsing Rings": '''def render(w, h, t, audio):
    y, x = np.ogrid[:h, :w]
    cx, cy = w / 2.0, h / 2.0
    dist = np.sqrt((x - cx)**2 + (y - cy)**2)
    
    # Audio bass expansion
    bass_boost = 1.0 + (audio.bass * 3.0 if audio else 0.0)
    rings = np.sin(dist * 0.5 / bass_boost - t * 4.0)
    mask = rings > 0.3
    
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    arr[mask, 0] = int(255 * (audio.bass if audio else 0.5))
    arr[mask, 1] = int(120 + 135 * math.sin(t))
    arr[mask, 2] = 255
    return arr
''',
    "Bouncing Metaballs": '''def render(w, h, t, audio):
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    y, x = np.ogrid[:h, :w]
    
    # 3 moving balls
    b1_x = (math.sin(t * 1.5) * 0.35 + 0.5) * w
    b1_y = (math.cos(t * 1.2) * 0.35 + 0.5) * h
    b2_x = (math.cos(t * 1.8) * 0.35 + 0.5) * w
    b2_y = (math.sin(t * 1.6) * 0.35 + 0.5) * h
    
    d1 = np.sqrt((x - b1_x)**2 + (y - b1_y)**2) + 0.1
    d2 = np.sqrt((x - b2_x)**2 + (y - b2_y)**2) + 0.1
    field = (4.0 / d1) + (4.0 / d2)
    
    mask = field > 0.8
    arr[mask, 0] = np.clip(field[mask] * 60, 0, 255).astype(np.uint8)
    arr[mask, 1] = np.clip(field[mask] * 30, 0, 255).astype(np.uint8)
    arr[mask, 2] = 255
    return arr
''',
    "Spiral Galaxy": '''def render(w, h, t, audio):
    y, x = np.ogrid[:h, :w]
    cx, cy = w / 2.0, h / 2.0
    r = np.sqrt((x - cx)**2 + (y - cy)**2)
    theta = np.arctan2(y - cy, x - cx)
    
    spiral = np.sin(theta * 3.0 + r * 0.4 - t * 3.0)
    glow = np.clip(1.0 - r / (w * 0.5), 0.0, 1.0)
    val = (np.clip(spiral, 0.0, 1.0) * glow * 255).astype(np.uint8)
    
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    arr[:, :, 0] = val
    arr[:, :, 1] = (val * 0.3).astype(np.uint8)
    arr[:, :, 2] = val
    return arr
''',
    "Matrix Digital Rain": '''def render(w, h, t, audio):
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    for col in range(w):
        # Column drop speed
        col_speed = 8.0 + (col % 5) * 4.0
        head_y = int((t * col_speed + col * 7) % (h * 1.6))
        for tail in range(8):
            py = head_y - tail
            if 0 <= py < h:
                bright = int(255 * (1.0 - tail / 8.0))
                if tail == 0:
                    arr[py, col] = [200, 255, 200]  # White lead
                else:
                    arr[py, col] = [0, bright, 0]     # Green trail
    return arr
''',
}


class MasScriptEffect(BaseEffect):
    """Programmable Python script effect engine (MADRIX Script equivalent)."""

    name = "MAS Script"
    category = EffectCategory.MAS
    description = "Live-coded procedural Python effect sandbox (MADRIX Script equivalent)."

    parameters = [
        ParamDef(
            name="preset_script",
            label="Sample Script",
            param_type=ParamType.ENUM,
            default="Audio Pulsing Rings",
            options=list(SAMPLE_SCRIPTS.keys()),
        ),
        ParamDef(
            name="custom_code",
            label="Script Code",
            param_type=ParamType.STRING,
            default="",
        ),
        ParamDef(
            name="speed_scale",
            label="Speed Scale",
            param_type=ParamType.FLOAT,
            default=1.0,
            min_val=0.1,
            max_val=5.0,
            step=0.1,
        ),
    ]

    def __init__(self):
        super().__init__()
        self._compiled_code = None
        self._compiled_fn = None
        self._last_script_text = ""
        self._error_msg: Optional[str] = None

    def _compile_script(self, code_str: str) -> bool:
        """Compile user script and extract render function."""
        try:
            scope: Dict[str, Any] = {
                "np": np,
                "math": math,
            }
            compiled = compile(code_str, "<mas_script>", "exec")
            exec(compiled, scope)
            if "render" in scope and callable(scope["render"]):
                self._compiled_fn = scope["render"]
                self._error_msg = None
                return True
            else:
                self._error_msg = "Script must define 'def render(w, h, t, audio):'"
                self._compiled_fn = None
                return False
        except Exception as e:
            self._error_msg = f"Syntax/Compile Error: {e}"
            self._compiled_fn = None
            return False

    def render(
        self,
        width: int,
        height: int,
        time_seconds: float,
        params: Dict[str, Any],
    ) -> np.ndarray:
        preset_name = params.get("preset_script", "Audio Pulsing Rings")
        custom_code = params.get("custom_code", "").strip()
        speed_scale = max(0.1, float(params.get("speed_scale", 1.0)))

        code_to_run = custom_code if custom_code else SAMPLE_SCRIPTS.get(preset_name, SAMPLE_SCRIPTS["Audio Pulsing Rings"])

        # Recompile if script changed
        if code_to_run != self._last_script_text:
            self._compile_script(code_to_run)
            self._last_script_text = code_to_run

        t = time_seconds * speed_scale

        # Execute compiled function
        if self._compiled_fn:
            try:
                frame = self._compiled_fn(width, height, t, self.audio_state)
                if isinstance(frame, np.ndarray) and frame.shape == (height, width, 3):
                    return frame.astype(np.uint8)
                else:
                    self._error_msg = f"render() must return ndarray shape ({height}, {width}, 3)"
            except Exception as e:
                self._error_msg = f"Runtime Error: {e}"

        # Error display: red warning indicator
        err_arr = np.zeros((height, width, 3), dtype=np.uint8)
        # Strobe red border
        blink = (math.sin(time_seconds * 8.0) > 0.0)
        if blink:
            err_arr[0, :] = [255, 0, 0]
            err_arr[-1, :] = [255, 0, 0]
            err_arr[:, 0] = [255, 0, 0]
            err_arr[:, -1] = [255, 0, 0]
            # Center X
            np.fill_diagonal(err_arr[:, :, 0], 255)
            np.fill_diagonal(np.fliplr(err_arr[:, :, 0]), 255)
        return err_arr
