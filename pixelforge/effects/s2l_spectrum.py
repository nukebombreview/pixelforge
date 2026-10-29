"""
S2L Spectrum — Real-time multi-band frequency spectrum graphic equalizer.
"""

from __future__ import annotations

from typing import Any
import numpy as np

from pixelforge.effects.base import (
    BaseEffect, EffectCategory, ParamDef, ParamType, hsv_to_rgb_array,
)


class S2LSpectrum(BaseEffect):
    name = "S2L Spectrum"
    description = "Real-time graphic equalizer spectrum visualizer mapped to audio frequency bands"
    category = EffectCategory.S2L
    parameters = [
        ParamDef("mode", "Mode", ParamType.ENUM, "Bars Bottom",
                 options=["Bars Bottom", "Bars Center", "Bars Top", "Radial", "Mirrored V"]),
        ParamDef("color_mode", "Color Mode", ParamType.ENUM, "Frequency Hue",
                 options=["Frequency Hue", "Solid", "Bass Red / High Blue"]),
        ParamDef("bar_color", "Bar Color", ParamType.COLOR, (0, 220, 255)),
        ParamDef("peak_color", "Peak Color", ParamType.COLOR, (255, 50, 80)),
        ParamDef("sensitivity", "Sensitivity", ParamType.FLOAT, 1.2, 0.2, 5.0, 0.1),
        ParamDef("show_peaks", "Peak Dots", ParamType.BOOL, True),
    ]

    def render(self, width: int, height: int, t: float,
               params: dict[str, Any]) -> np.ndarray:
        mode = params.get("mode", "Bars Bottom")
        col_mode = params.get("color_mode", "Frequency Hue")
        base_color = np.array(params.get("bar_color", (0, 220, 255)), dtype=np.float64)
        peak_color = np.array(params.get("peak_color", (255, 50, 80)), dtype=np.float64)
        sensitivity = params.get("sensitivity", 1.2)
        show_peaks = params.get("show_peaks", True)

        buf = np.zeros((height, width, 3), dtype=np.float64)

        # Get spectrum from audio state
        if self.audio_state is not None and hasattr(self.audio_state, "spectrum"):
            raw_spectrum = self.audio_state.spectrum
            raw_peaks = self.audio_state.spectrum_peaks
        else:
            # Fallback synthetic frequency wave
            phase = t * 4.0
            raw_spectrum = 0.5 + 0.4 * np.sin(np.linspace(0, 3 * np.pi, 64) + phase)
            raw_peaks = raw_spectrum * 1.1

        # Resample spectrum to matrix width
        indices = np.linspace(0, len(raw_spectrum) - 1, width).astype(int)
        spectrum_vals = np.clip(raw_spectrum[indices] * sensitivity, 0.0, 1.0)
        peak_vals = np.clip(raw_peaks[indices] * sensitivity, 0.0, 1.0)

        if mode == "Bars Bottom":
            for x in range(width):
                bar_h = int(spectrum_vals[x] * height)
                pk_y = min(height - 1, int(peak_vals[x] * (height - 1)))
                col = self._get_col(x, width, col_mode, base_color)

                if bar_h > 0:
                    buf[height - bar_h:height, x] = col
                if show_peaks and pk_y < height:
                    buf[height - 1 - pk_y, x] = peak_color

        elif mode == "Bars Center":
            mid_y = height / 2.0
            for x in range(width):
                half_h = (spectrum_vals[x] * height) / 2.0
                y1 = max(0, int(mid_y - half_h))
                y2 = min(height, int(mid_y + half_h + 1))
                col = self._get_col(x, width, col_mode, base_color)
                buf[y1:y2, x] = col

                if show_peaks:
                    pk_half = (peak_vals[x] * height) / 2.0
                    pk1 = max(0, int(mid_y - pk_half))
                    pk2 = min(height - 1, int(mid_y + pk_half))
                    buf[pk1, x] = peak_color
                    buf[pk2, x] = peak_color

        elif mode == "Bars Top":
            for x in range(width):
                bar_h = int(spectrum_vals[x] * height)
                pk_y = min(height - 1, int(peak_vals[x] * (height - 1)))
                col = self._get_col(x, width, col_mode, base_color)

                if bar_h > 0:
                    buf[0:bar_h, x] = col
                if show_peaks and pk_y < height:
                    buf[pk_y, x] = peak_color

        elif mode == "Mirrored V":
            half_w = width // 2
            for x in range(half_w):
                val = spectrum_vals[x * 2]
                bar_h = int(val * height)
                col = self._get_col(x, half_w, col_mode, base_color)
                # Left & Right mirror
                if bar_h > 0:
                    buf[height - bar_h:height, half_w - 1 - x] = col
                    buf[height - bar_h:height, half_w + x] = col

        elif mode == "Radial":
            # Circular radial spectrum from center
            cy, cx = height / 2.0, width / 2.0
            max_r = min(cx, cy)
            yy, xx = np.mgrid[0:height, 0:width]
            angles = (np.arctan2(yy - cy, xx - cx) + np.pi) / (2.0 * np.pi)  # [0, 1]
            dists = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)

            band_idx = (angles * (len(spectrum_vals) - 1)).astype(int)
            band_heights = spectrum_vals[band_idx] * max_r

            inside = dists <= band_heights
            buf[inside] = base_color

        return np.clip(buf, 0, 255).astype(np.uint8)

    @staticmethod
    def _get_col(x: int, w: int, mode: str, base_color: np.ndarray) -> np.ndarray:
        if mode == "Frequency Hue":
            hue = (x / max(w - 1, 1)) * 0.8
            # Simple hue to rgb
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

        elif mode == "Bass Red / High Blue":
            frac = x / max(w - 1, 1)
            r = (1.0 - frac) * 255.0
            g = np.sin(frac * np.pi) * 200.0
            b = frac * 255.0
            return np.array([r, g, b], dtype=np.float64)

        return base_color
