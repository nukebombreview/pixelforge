"""
PixelForge — Storage Places & Preset Management System
Manages preset serialization, storage banks (up to 256 slots), and .pxf project files.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from pixelforge.core.deck import Deck


@dataclass
class StoragePlace:
    """Represents a single saved look in a Storage Place slot."""
    index: int = 0
    name: str = ""
    effect_name: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    speed: float = 1.0
    color: str = "#252b38"  # Background tile accent color
    is_empty: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "name": self.name,
            "effect_name": self.effect_name,
            "params": self.params,
            "speed": self.speed,
            "color": self.color,
            "is_empty": self.is_empty,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StoragePlace:
        return cls(
            index=data.get("index", 0),
            name=data.get("name", ""),
            effect_name=data.get("effect_name", ""),
            params=data.get("params", {}),
            speed=data.get("speed", 1.0),
            color=data.get("color", "#252b38"),
            is_empty=data.get("is_empty", True),
        )


class StorageBank:
    """A collection of storage places for one deck (default 64 slots, expandable)."""

    DEFAULT_CAPACITY = 64

    def __init__(self, capacity: int = DEFAULT_CAPACITY):
        self.capacity = capacity
        self.places: list[StoragePlace] = [
            StoragePlace(index=i) for i in range(capacity)
        ]
        self.active_index: Optional[int] = None

    def get_place(self, index: int) -> Optional[StoragePlace]:
        if 0 <= index < len(self.places):
            return self.places[index]
        return None

    def store_deck(
        self,
        index: int,
        deck: Deck,
        name: str = "",
        color: Optional[str] = None,
    ) -> bool:
        """Capture the current state of a deck into a storage slot."""
        if not (0 <= index < len(self.places)):
            return False

        preset_name = name or deck.effect_name or f"Look {index + 1}"
        tile_color = color or self._suggest_color(deck.effect_name)

        self.places[index] = StoragePlace(
            index=index,
            name=preset_name,
            effect_name=deck.effect_name,
            params=dict(deck.params),
            speed=deck.speed,
            color=tile_color,
            is_empty=False if deck.effect_name else True,
        )
        self.active_index = index
        return True

    def recall_to_deck(self, index: int, deck: Deck, effect_loader_fn) -> bool:
        """Recall a stored preset into the given deck."""
        place = self.get_place(index)
        if place is None or place.is_empty or not place.effect_name:
            return False

        # Load effect into deck
        effect_loader_fn(place.effect_name)
        # Restore parameters
        for k, v in place.params.items():
            deck.set_param(k, v)
        deck.speed = place.speed
        self.active_index = index
        return True

    def clear_place(self, index: int) -> None:
        if 0 <= index < len(self.places):
            self.places[index] = StoragePlace(index=index)
            if self.active_index == index:
                self.active_index = None

    def to_list(self) -> list[dict[str, Any]]:
        return [p.to_dict() for p in self.places]

    def from_list(self, data: list[dict[str, Any]]) -> None:
        self.places = [StoragePlace.from_dict(d) for d in data]
        if len(self.places) < self.capacity:
            start = len(self.places)
            for i in range(start, self.capacity):
                self.places.append(StoragePlace(index=i))

    @staticmethod
    def _suggest_color(effect_name: str) -> str:
        """Provide automatic vibrant tile coloring based on effect category."""
        if not effect_name:
            return "#252b38"
        name_lower = effect_name.lower()
        if "s2l" in name_lower or "spectrum" in name_lower:
            return "#0d47a1"  # Royal Blue for S2L audio
        if "fire" in name_lower:
            return "#b71c1c"  # Crimson Red
        if "plasma" in name_lower or "rainbow" in name_lower:
            return "#4a148c"  # Electric Purple
        if "wave" in name_lower or "drops" in name_lower:
            return "#006064"  # Deep Cyan
        if "starfield" in name_lower:
            return "#1a237e"  # Midnight Blue
        if "strobe" in name_lower or "flash" in name_lower:
            return "#f57f17"  # Amber
        return "#2e7d32"      # Forest Green


class ProjectFile:
    """Serializes and restores entire PixelForge workstations (.pxf JSON)."""

    VERSION = "1.0.0"

    @classmethod
    def create_project_data(
        cls,
        engine,
        bank_a: StorageBank,
        bank_b: StorageBank,
        cue_list: Optional[Any] = None,
        timeline: Optional[Any] = None,
        meta: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return {
            "format": "PixelForgeProject",
            "version": cls.VERSION,
            "meta": meta or {"name": "Untitled Show", "author": "PixelForge"},
            "matrix": {
                "width": engine.width,
                "height": engine.height,
            },
            "master": {
                "dimmer": engine.master_dimmer,
                "blackout": engine.blackout,
                "freeze": engine.freeze,
            },
            "crossfader": {
                "position": engine.crossfader.position,
                "blend_mode": engine.crossfader.blend_mode.value,
            },
            "audio": {
                "gain": engine.audio.gain,
                "generator_mode": engine.audio.generator_mode,
            },
            "patch": engine.patch.to_dict() if hasattr(engine, "patch") else {},
            "storage_a": bank_a.to_list(),
            "storage_b": bank_b.to_list(),
            "deck_a": {
                "effect_name": engine.deck_a.effect_name,
                "params": engine.deck_a.params,
                "speed": engine.deck_a.speed,
            },
            "deck_b": {
                "effect_name": engine.deck_b.effect_name,
                "params": engine.deck_b.params,
                "speed": engine.deck_b.speed,
            },
            "cue_list": cue_list.to_list() if cue_list and hasattr(cue_list, "to_list") else (cue_list or []),
            "timeline": timeline.to_dict() if timeline and hasattr(timeline, "to_dict") else (timeline or {}),
        }

    @classmethod
    def save(cls, filepath: str, data: dict[str, Any]) -> bool:
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return True
        except Exception:
            return False

    @classmethod
    def load(cls, filepath: str) -> Optional[dict[str, Any]]:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None


def populate_factory_presets(bank_a: StorageBank, bank_b: StorageBank) -> None:
    """Pre-load curated showcase presets for instant live use."""
    # Deck A Showcase Looks
    presets_a = [
        ("S2L Spectrum", "Audio EQ", "#0d47a1", {"mode": "Bars Bottom", "color_mode": "Frequency Hue", "sensitivity": 1.4}),
        ("SCE Plasma", "Psy Plasma", "#4a148c", {"speed": 2.0, "scale": 1.5, "palette": "Neon Cyan-Magenta"}),
        ("SCE Fire", "Hellfire", "#b71c1c", {"cooling": 0.03, "sparking": 0.7, "intensity": 1.4, "palette": "Classic"}),
        ("S2L Waveform", "Scope Line", "#006064", {"style": "Oscilloscope Line", "line_color": (0, 255, 120), "gain": 1.8}),
        ("SCE Starfield", "Hyperspace", "#1a237e", {"speed": 2.5, "star_count": 220, "warp": 1.2, "direction": "Forward"}),
        ("SCE Rainbow", "Rainbow Spin", "#6a1b9a", {"speed": 1.5, "frequency": 1.5, "rotation_speed": 0.5}),
        ("S2L Drops", "Beat Explosion", "#00838f", {"mode": "Radial Burst", "color_mode": "Rainbow", "count": 250}),
        ("SCE Strobe", "High Strobe", "#e65100", {"frequency": 14.0, "duty_cycle": 15.0, "mode": "Strobe"}),
    ]

    for idx, (eff, name, col, params) in enumerate(presets_a):
        bank_a.places[idx] = StoragePlace(
            index=idx,
            name=name,
            effect_name=eff,
            params=params,
            speed=1.0,
            color=col,
            is_empty=False,
        )

    # Deck B Showcase Looks
    presets_b = [
        ("S2L Level Shape", "Bass Diamond", "#ad1457", {"shape": "Diamond", "band": "Bass", "fill": "Concentric Echo", "scale": 1.5}),
        ("S2L Flash", "Sub Strobe", "#d84315", {"trigger": "Bass / Kick Drum", "decay": 0.2, "threshold": 0.5}),
        ("SCE Wave", "Cyan Ripple", "#00695c", {"speed": 2.5, "frequency": 8.0, "wave_type": "Concentric"}),
        ("S2L Level", "VU Rings", "#2e7d32", {"mode": "Expanding Circle", "color_scheme": "Neon Cyan-Magenta", "gain": 1.5}),
        ("SCE Checkerboard", "Geo Zoom", "#37474f", {"speed_x": 1.5, "speed_y": 1.5, "cell_size": 4.0}),
        ("SCE Color Scroll", "Sunset Strip", "#ef6c00", {"speed": 2.0, "palette": "Sunset"}),
        ("S2L Waveform", "Circular Radar", "#0277bd", {"style": "Circular Oscilloscope", "gain": 2.0}),
        ("SCE Drops", "Matrix Rain", "#1b5e20", {"speed": 2.0, "density": 0.25, "direction": "Down"}),
    ]

    for idx, (eff, name, col, params) in enumerate(presets_b):
        bank_b.places[idx] = StoragePlace(
            index=idx,
            name=name,
            effect_name=eff,
            params=params,
            speed=1.0,
            color=col,
            is_empty=False,
        )

