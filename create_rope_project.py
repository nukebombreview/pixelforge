"""
Generate 5M LED Rope Light Showcase Project for PixelForge & Unreal Engine.
"""

import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pixelforge.core.engine import RenderEngine
from pixelforge.core.storage import StorageBank, StoragePlace, ProjectFile
from pixelforge.core.cue import Cue, CueList
from pixelforge.core.patch import Fixture, PixelRouting

def build_rope_project():
    engine = RenderEngine(80, 16)

    # Configure Patch with 5M LED Rope Fixture
    engine.patch.clear()

    # Fixture 1: 5M Rope on Universe 0 (UE Inbound Universe 1)
    f1 = Fixture(
        id=1,
        name="5m LED Rope Light [Uni 0]",
        x=0,
        y=0,
        width=80,
        height=1,
        start_universe=0,
        start_channel=1,
        channel_order="GRB",
        routing=PixelRouting.HORIZONTAL_LTR,
        color_label="#00ff88",
    )
    engine.patch.add_fixture(f1)

    # Fixture 2: 2nd 5M Rope on Universe 1 (UE Inbound Universe 2)
    f2 = Fixture(
        id=2,
        name="5m LED Rope Light [Uni 1]",
        x=0,
        y=1,
        width=80,
        height=1,
        start_universe=1,
        start_channel=1,
        channel_order="GRB",
        routing=PixelRouting.HORIZONTAL_LTR,
        color_label="#00d2ff",
    )
    engine.patch.add_fixture(f2)
    engine.patch.compile_mapping()

    # Setup Storage Banks
    bank_a = StorageBank()
    bank_b = StorageBank()

    # Presets for testing rope light
    rope_presets_a = [
        ("SCE Color Scroll", "Cylon Red Chase", "#b71c1c", {"speed": 2.5, "angle": 0.0, "palette": "Red-Black", "width": 8.0}),
        ("S2L Spectrum", "Audio EQ Strip", "#0d47a1", {"mode": "Bars Bottom", "color_mode": "Frequency Hue", "sensitivity": 1.5}),
        ("SCE Rainbow", "Rainbow Flow", "#6a1b9a", {"speed": 1.5, "frequency": 2.0, "direction": "Horizontal"}),
        ("SCE Wave", "Cyan Ripple", "#00838f", {"frequency": 3.0, "speed": 1.8, "amplitude": 1.0}),
    ]

    rope_presets_b = [
        ("SCE Fire", "Rope Fire", "#d84315", {"cooling": 0.04, "sparking": 0.6, "intensity": 1.2}),
        ("S2L Flash", "Bass Strobe", "#f57f17", {"sensitivity": 1.4, "flash_duration": 0.08}),
        ("SCE Plasma", "Neon Plasma", "#4a148c", {"speed": 1.6, "scale": 2.0}),
        ("SCE Strobe", "White Strobe", "#ffffff", {"frequency": 12.0, "duty_cycle": 10.0}),
    ]

    for idx, (eff, name, col, params) in enumerate(rope_presets_a):
        bank_a.places[idx] = StoragePlace(
            index=idx, name=name, effect_name=eff, params=params, speed=1.0, color=col, is_empty=False
        )

    for idx, (eff, name, col, params) in enumerate(rope_presets_b):
        bank_b.places[idx] = StoragePlace(
            index=idx, name=name, effect_name=eff, params=params, speed=1.0, color=col, is_empty=False
        )

    # Set Deck A & B active looks
    from pixelforge.effects import create_effect
    eff_a = create_effect("SCE Color Scroll", 80, 16)
    engine.deck_a.effect = eff_a
    for k, v in rope_presets_a[0][3].items():
        engine.deck_a.set_param(k, v)

    eff_b = create_effect("S2L Spectrum", 80, 16)
    engine.deck_b.effect = eff_b
    for k, v in rope_presets_a[1][3].items():
        engine.deck_b.set_param(k, v)

    engine.crossfader.position = 0.0

    # Cue List
    cue_list = CueList()
    cue_list.add_cue(Cue(
        cue_id=1, name="Red Meteor Chase", deck_a_slot=0, deck_b_slot=0, crossfader_pos=0.0,
        fade_duration=1.0, hold_duration=5.0, auto_follow=True
    ))
    cue_list.add_cue(Cue(
        cue_id=2, name="Audio Reactive EQ", deck_a_slot=1, deck_b_slot=0, crossfader_pos=0.0,
        fade_duration=1.5, hold_duration=8.0, auto_follow=True
    ))
    cue_list.add_cue(Cue(
        cue_id=3, name="Rainbow Flow", deck_a_slot=2, deck_b_slot=0, crossfader_pos=0.0,
        fade_duration=2.0, hold_duration=6.0, auto_follow=True
    ))
    cue_list.add_cue(Cue(
        cue_id=4, name="Fire & Plasma Mix", deck_a_slot=2, deck_b_slot=0, crossfader_pos=0.5,
        fade_duration=2.0, hold_duration=10.0, auto_follow=False
    ))

    # Save Project
    meta = {
        "name": "5M LED Rope Light Unreal Showcase",
        "description": "Pre-configured project for 5M LED Rope Light (80 pixels, GRB, 240 channels) in Unreal Engine",
        "author": "PixelForge",
    }
    data = ProjectFile.create_project_data(
        engine=engine,
        bank_a=bank_a,
        bank_b=bank_b,
        cue_list=cue_list,
        meta=meta,
    )

    projects_dir = os.path.join(os.path.dirname(__file__), "projects")
    os.makedirs(projects_dir, exist_ok=True)
    out_path = os.path.join(projects_dir, "5m_rope_light_unreal.pxf")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"[OK] Successfully built 5M Rope Light Project: {out_path}")
    return out_path

if __name__ == "__main__":
    build_rope_project()
