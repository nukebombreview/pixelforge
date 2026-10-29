"""
PixelForge — Effects Module & Registry
Central catalogue of all real-time generative effects (SCE and S2L).
"""

from __future__ import annotations

from typing import Type

from pixelforge.effects.base import BaseEffect, EffectCategory, ParamDef, ParamType

# SCE Effects (Phase 1)
from pixelforge.effects.sce_color import SCEColor
from pixelforge.effects.sce_color_scroll import SCEColorScroll
from pixelforge.effects.sce_plasma import SCEPlasma
from pixelforge.effects.sce_fire import SCEFire
from pixelforge.effects.sce_wave import SCEWave
from pixelforge.effects.sce_drops import SCEDrops
from pixelforge.effects.sce_starfield import SCEStarfield
from pixelforge.effects.sce_rainbow import SCERainbow
from pixelforge.effects.sce_checkerboard import SCECheckerboard
from pixelforge.effects.sce_strobe import SCEStrobe

# S2L Effects (Phase 2 - Sound2Light)
from pixelforge.effects.s2l_spectrum import S2LSpectrum
from pixelforge.effects.s2l_level import S2LLevel
from pixelforge.effects.s2l_waveform import S2LWaveform
from pixelforge.effects.s2l_drops import S2LDrops
from pixelforge.effects.s2l_level_shape import S2LLevelShape
from pixelforge.effects.s2l_flash import S2LFlash

# Media & MAS Effects (Phase 8 - Media Playback & Scripting)
from pixelforge.effects.sce_image import SceImageEffect
from pixelforge.effects.sce_ticker import SceTickerEffect
from pixelforge.effects.sce_video import SceVideoEffect
from pixelforge.effects.mas_script import MasScriptEffect


# Registered effect classes (SCE + S2L + MAS)
ALL_EFFECT_CLASSES: list[Type[BaseEffect]] = [
    # SCE
    SCEColor,
    SCEColorScroll,
    SCEPlasma,
    SCEFire,
    SCEWave,
    SCEDrops,
    SCEStarfield,
    SCERainbow,
    SCECheckerboard,
    SCEStrobe,
    SceImageEffect,
    SceTickerEffect,
    SceVideoEffect,
    # S2L
    S2LSpectrum,
    S2LLevel,
    S2LWaveform,
    S2LDrops,
    S2LLevelShape,
    S2LFlash,
    # MAS
    MasScriptEffect,
]

EFFECT_REGISTRY: dict[str, Type[BaseEffect]] = {
    cls.name: cls for cls in ALL_EFFECT_CLASSES
}


def get_effect_names() -> list[str]:
    """Return list of all available effect names sorted by category."""
    sce = [cls.name for cls in ALL_EFFECT_CLASSES if cls.category == EffectCategory.SCE]
    s2l = [cls.name for cls in ALL_EFFECT_CLASSES if cls.category == EffectCategory.S2L]
    mas = [cls.name for cls in ALL_EFFECT_CLASSES if cls.category == EffectCategory.MAS]
    return sorted(sce) + sorted(s2l) + sorted(mas)


def create_effect(name: str, width: int = 32, height: int = 32) -> BaseEffect:
    """Instantiate and initialize an effect by name."""
    cls = EFFECT_REGISTRY.get(name)
    if cls is None:
        raise ValueError(f"Unknown effect: {name!r}. Available: {list(EFFECT_REGISTRY.keys())}")
    instance = cls()
    instance.initialize(width, height)
    return instance


__all__ = [
    "BaseEffect",
    "EffectCategory",
    "ParamDef",
    "ParamType",
    "ALL_EFFECT_CLASSES",
    "EFFECT_REGISTRY",
    "get_effect_names",
    "create_effect",
    # SCE
    "SCEColor",
    "SCEColorScroll",
    "SCEPlasma",
    "SCEFire",
    "SCEWave",
    "SCEDrops",
    "SCEStarfield",
    "SCERainbow",
    "SCECheckerboard",
    "SCEStrobe",
    "SceImageEffect",
    "SceTickerEffect",
    "SceVideoEffect",
    # S2L
    "S2LSpectrum",
    "S2LLevel",
    "S2LWaveform",
    "S2LDrops",
    "S2LLevelShape",
    "S2LFlash",
    # MAS
    "MasScriptEffect",
]
