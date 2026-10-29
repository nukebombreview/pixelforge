"""
PixelForge — Fixture Patch & DMX Routing Engine
Provides fixture profile modeling, serpentine pixel routing, matrix generation,
and high-speed transformation of virtual matrices into DMX universe payloads.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional

import numpy as np

from pixelforge.core.matrix import PixelMatrix


class PixelRouting(Enum):
    """Fixture internal pixel wiring and snake trajectory."""
    HORIZONTAL_LTR = "horizontal_ltr"       # Left-to-right, row by row
    HORIZONTAL_SNAKE = "horizontal_snake"   # Left-to-right, then right-to-left
    VERTICAL_TTB = "vertical_ttb"           # Top-to-bottom, column by column
    VERTICAL_SNAKE = "vertical_snake"       # Top-to-bottom, then bottom-to-top


FIXTURE_TEMPLATES: dict[str, dict[str, Any]] = {
    "5m_led_rope": {
        "name": "5m LED Rope Light",
        "description": "5M LED Rope (80 Pixels, 240 DMX Channels, GRB Order - Unreal Engine)",
        "width": 80,
        "height": 1,
        "channel_order": "GRB",
        "routing": PixelRouting.HORIZONTAL_LTR,
        "color_label": "#00ff88",
    },
    "panel_16x16": {
        "name": "16x16 RGB Panel",
        "description": "Modular 16x16 LED Matrix (256 Pixels, RGB Order)",
        "width": 16,
        "height": 16,
        "channel_order": "RGB",
        "routing": PixelRouting.HORIZONTAL_LTR,
        "color_label": "#00d2ff",
    },
    "strip_1m_60": {
        "name": "1m Strip (60px)",
        "description": "1 Meter Digital LED Strip (60 Pixels, RGB Order)",
        "width": 60,
        "height": 1,
        "channel_order": "RGB",
        "routing": PixelRouting.HORIZONTAL_LTR,
        "color_label": "#ffaa00",
    },
}


@dataclass
class Fixture:
    """A physical LED fixture placed on the virtual matrix."""
    id: int
    name: str = "LED Panel"
    x: int = 0
    y: int = 0
    width: int = 16
    height: int = 16
    start_universe: int = 0
    start_channel: int = 1          # 1-based (1 to 512)
    channel_order: str = "RGB"      # "RGB", "GRB", "BGR", "RGBW"
    routing: PixelRouting = PixelRouting.HORIZONTAL_LTR
    color_label: str = "#00d2ff"

    @property
    def pixel_count(self) -> int:
        return self.width * self.height

    @property
    def channels_per_pixel(self) -> int:
        return len(self.channel_order)

    @property
    def total_channels(self) -> int:
        return self.pixel_count * self.channels_per_pixel

    def get_pixel_sequence(self) -> list[tuple[int, int]]:
        """Return list of (local_x, local_y) tuples in physical wiring order."""
        seq = []
        if self.routing == PixelRouting.HORIZONTAL_LTR:
            for ly in range(self.height):
                for lx in range(self.width):
                    seq.append((lx, ly))

        elif self.routing == PixelRouting.HORIZONTAL_SNAKE:
            for ly in range(self.height):
                row = range(self.width) if (ly % 2 == 0) else reversed(range(self.width))
                for lx in row:
                    seq.append((lx, ly))

        elif self.routing == PixelRouting.VERTICAL_TTB:
            for lx in range(self.width):
                for ly in range(self.height):
                    seq.append((lx, ly))

        elif self.routing == PixelRouting.VERTICAL_SNAKE:
            for lx in range(self.width):
                col = range(self.height) if (lx % 2 == 0) else reversed(range(self.height))
                for ly in col:
                    seq.append((lx, ly))

        return seq

    def get_address_mapping(self) -> list[tuple[int, int, int, int]]:
        """Generate list of (matrix_x, matrix_y, universe, dmx_channel_0_indexed)."""
        mapping = []
        cur_u = self.start_universe
        cur_ch = self.start_channel - 1  # Convert 1-based to 0-based index (0 to 511)
        ch_per_px = self.channels_per_pixel

        for lx, ly in self.get_pixel_sequence():
            mx = self.x + lx
            my = self.y + ly

            # If pixel doesn't fit in current universe (512 max), wrap to next
            if cur_ch + ch_per_px > 512:
                cur_u += 1
                cur_ch = 0

            mapping.append((mx, my, cur_u, cur_ch))
            cur_ch += ch_per_px

        return mapping

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "start_universe": self.start_universe,
            "start_channel": self.start_channel,
            "channel_order": self.channel_order,
            "routing": self.routing.value,
            "color_label": self.color_label,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Fixture:
        routing_val = data.get("routing", PixelRouting.HORIZONTAL_LTR.value)
        try:
            routing = PixelRouting(routing_val)
        except ValueError:
            routing = PixelRouting.HORIZONTAL_LTR

        return cls(
            id=data.get("id", 1),
            name=data.get("name", "LED Fixture"),
            x=data.get("x", 0),
            y=data.get("y", 0),
            width=data.get("width", 16),
            height=data.get("height", 16),
            start_universe=data.get("start_universe", 0),
            start_channel=data.get("start_channel", 1),
            channel_order=data.get("channel_order", "RGB"),
            routing=routing,
            color_label=data.get("color_label", "#00d2ff"),
        )


class Patch:
    """Comprehensive stage fixture layout and DMX universe packager."""

    def __init__(self, matrix_width: int = 32, matrix_height: int = 32):
        self.matrix_width = matrix_width
        self.matrix_height = matrix_height
        self.fixtures: list[Fixture] = []
        self._next_id: int = 1

        # Pre-compiled mapping cache: (mx, my, universe, ch_offset, channel_indices)
        self._compiled_map: list[tuple[int, int, int, int, list[int]]] = []
        self._active_universes: list[int] = []

    def clear(self) -> None:
        self.fixtures.clear()
        self._next_id = 1
        self.invalidate_cache()

    def add_fixture(self, fixture: Fixture) -> None:
        if fixture.id >= self._next_id:
            self._next_id = fixture.id + 1
        self.fixtures.append(fixture)
        self.invalidate_cache()

    def remove_fixture(self, fixture_id: int) -> bool:
        before = len(self.fixtures)
        self.fixtures = [f for f in self.fixtures if f.id != fixture_id]
        if len(self.fixtures) < before:
            self.invalidate_cache()
            return True
        return False

    def get_fixture(self, fixture_id: int) -> Optional[Fixture]:
        for f in self.fixtures:
            if f.id == fixture_id:
                return f
        return None

    def invalidate_cache(self) -> None:
        self._compiled_map = []
        self._active_universes = []

    def compile_mapping(self) -> None:
        """Pre-compute lookup table mapping (mx, my) -> (universe, byte_offset)."""
        order_map = {"R": 0, "G": 1, "B": 2, "W": 0}
        compiled = []
        universes_set = set()

        for f in self.fixtures:
            ch_order = f.channel_order.upper()
            indices = [order_map.get(c, 0) for c in ch_order]

            for mx, my, u, ch in f.get_address_mapping():
                compiled.append((mx, my, u, ch, indices))
                universes_set.add(u)

        self._compiled_map = compiled
        self._active_universes = sorted(list(universes_set))

    def render_to_dmx(self, matrix: PixelMatrix) -> dict[int, bytes]:
        """Convert a PixelMatrix into standard 512-byte DMX universe payloads."""
        if not self._compiled_map and self.fixtures:
            self.compile_mapping()

        if not self._compiled_map:
            # Fallback 1:1 linear mapping across 170-pixel chunks
            return self._linear_fallback(matrix)

        # Allocate 512 bytes per active universe
        buffers = {u: bytearray(512) for u in self._active_universes}
        mat_buf = matrix.buffer
        mw, mh = matrix.width, matrix.height

        for mx, my, u, ch, indices in self._compiled_map:
            if 0 <= mx < mw and 0 <= my < mh:
                pixel = mat_buf[my, mx]
                u_buf = buffers[u]
                for offset, c_idx in enumerate(indices):
                    target_ch = ch + offset
                    if target_ch < 512:
                        u_buf[target_ch] = pixel[c_idx]

        return {u: bytes(b) for u, b in buffers.items()}

    def _linear_fallback(self, matrix: PixelMatrix) -> dict[int, bytes]:
        """Simple default 1-to-1 linear sequential packing."""
        raw = matrix.to_dmx_bytes("RGB")
        chunk_size = 510
        result = {}
        u = 0
        for offset in range(0, len(raw), chunk_size):
            chunk = bytearray(512)
            data = raw[offset:offset + chunk_size]
            chunk[:len(data)] = data
            result[u] = bytes(chunk)
            u += 1
        return result

    # ------------------------------------------------------------------
    # Fixture Templates & Rope Light
    # ------------------------------------------------------------------

    def add_from_template(
        self,
        template_key: str,
        x: int = 0,
        y: int = 0,
        start_universe: int = 0,
        start_channel: int = 1,
    ) -> Optional[Fixture]:
        """Add a fixture instance from standard template definitions."""
        tmpl = FIXTURE_TEMPLATES.get(template_key)
        if not tmpl:
            return None
        f = Fixture(
            id=self._next_id,
            name=tmpl["name"],
            x=x,
            y=y,
            width=tmpl["width"],
            height=tmpl["height"],
            start_universe=start_universe,
            start_channel=start_channel,
            channel_order=tmpl["channel_order"],
            routing=tmpl["routing"],
            color_label=tmpl["color_label"],
        )
        self.add_fixture(f)
        if self.matrix_width < x + tmpl["width"]:
            self.matrix_width = max(self.matrix_width, x + tmpl["width"])
        if self.matrix_height < y + tmpl["height"]:
            self.matrix_height = max(self.matrix_height, y + tmpl["height"])
        self.compile_mapping()
        return f

    def add_rope_light_fixture(
        self,
        name: str = "5m LED Rope Light",
        x: int = 0,
        y: int = 0,
        start_universe: int = 0,
        start_channel: int = 1,
    ) -> Fixture:
        """Add the 5M LED Rope Light fixture (80 pixels, GRB, 240 channels for Unreal Engine / QLC+)."""
        f = Fixture(
            id=self._next_id,
            name=name,
            x=x,
            y=y,
            width=80,
            height=1,
            start_universe=start_universe,
            start_channel=start_channel,
            channel_order="GRB",
            routing=PixelRouting.HORIZONTAL_LTR,
            color_label="#00ff88",
        )
        self.add_fixture(f)
        if self.matrix_width < x + 80:
            self.matrix_width = max(self.matrix_width, x + 80)
        if self.matrix_height < y + 1:
            self.matrix_height = max(self.matrix_height, y + 1)
        self.compile_mapping()
        return f

    # ------------------------------------------------------------------
    # Matrix Generator Helper
    # ------------------------------------------------------------------

    def generate_matrix(
        self,
        cols: int = 2,
        rows: int = 2,
        tile_w: int = 16,
        tile_h: int = 16,
        start_universe: int = 0,
        start_channel: int = 1,
        channel_order: str = "RGB",
        routing: PixelRouting = PixelRouting.HORIZONTAL_LTR,
        panel_color: str = "#00d2ff",
    ) -> None:
        """Clear patch and generate a grid of modular LED panels."""
        self.clear()
        cur_u = start_universe
        cur_ch = start_channel
        ch_per_px = len(channel_order)
        channels_per_panel = tile_w * tile_h * ch_per_px

        for r in range(rows):
            for c in range(cols):
                f = Fixture(
                    id=self._next_id,
                    name=f"Panel [{c+1},{r+1}]",
                    x=c * tile_w,
                    y=r * tile_h,
                    width=tile_w,
                    height=tile_h,
                    start_universe=cur_u,
                    start_channel=cur_ch,
                    channel_order=channel_order,
                    routing=routing,
                    color_label=panel_color,
                )
                self.add_fixture(f)

                # Compute next start universe and channel
                total_used = cur_ch - 1 + channels_per_panel
                universes_spanned = total_used // 512
                rem_ch = total_used % 512

                cur_u += universes_spanned
                cur_ch = rem_ch + 1

        self.matrix_width = cols * tile_w
        self.matrix_height = rows * tile_h
        self.compile_mapping()

    # ------------------------------------------------------------------
    # Serialization & CSV Export / Import
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "matrix_width": self.matrix_width,
            "matrix_height": self.matrix_height,
            "fixtures": [f.to_dict() for f in self.fixtures],
        }

    def from_dict(self, data: dict[str, Any]) -> None:
        self.clear()
        self.matrix_width = data.get("matrix_width", 32)
        self.matrix_height = data.get("matrix_height", 32)
        for fd in data.get("fixtures", []):
            self.add_fixture(Fixture.from_dict(fd))
        self.compile_mapping()

    def export_csv(self) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "Name", "X", "Y", "Width", "Height", "Start_Universe", "Start_Channel", "Channel_Order", "Routing"])
        for f in self.fixtures:
            writer.writerow([
                f.id, f.name, f.x, f.y, f.width, f.height,
                f.start_universe, f.start_channel, f.channel_order, f.routing.value
            ])
        return output.getvalue()

    def import_csv(self, csv_text: str) -> bool:
        try:
            reader = csv.DictReader(io.StringIO(csv_text))
            self.clear()
            for row in reader:
                try:
                    routing = PixelRouting(row.get("Routing", PixelRouting.HORIZONTAL_LTR.value))
                except ValueError:
                    routing = PixelRouting.HORIZONTAL_LTR

                f = Fixture(
                    id=int(row["ID"]),
                    name=row.get("Name", "LED Fixture"),
                    x=int(row["X"]),
                    y=int(row["Y"]),
                    width=int(row["Width"]),
                    height=int(row["Height"]),
                    start_universe=int(row["Start_Universe"]),
                    start_channel=int(row["Start_Channel"]),
                    channel_order=row.get("Channel_Order", "RGB"),
                    routing=routing,
                )
                self.add_fixture(f)
            self.compile_mapping()
            return True
        except Exception:
            return False

