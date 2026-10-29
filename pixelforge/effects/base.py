"""
PixelForge — Base Effect & Parameter System
All built-in effects inherit from BaseEffect.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np


# ======================================================================
# Parameter definitions
# ======================================================================

class ParamType(Enum):
    """Supported parameter widget types."""
    FLOAT = "float"
    INT = "int"
    COLOR = "color"       # (r, g, b) tuple 0-255
    ENUM = "enum"         # string choice
    BOOL = "bool"
    STRING = "string"     # string text / file path


@dataclass
class ParamDef:
    """Describes a single tweakable parameter for an effect."""
    name: str
    label: str
    param_type: ParamType
    default: Any
    min_val: float | None = None
    max_val: float | None = None
    step: float | None = None
    options: list[str] = field(default_factory=list)


# ======================================================================
# Effect category tags
# ======================================================================

class EffectCategory(Enum):
    SCE = "SCE"   # Static Color Effects
    S2L = "S2L"   # Sound2Light
    M2L = "M2L"   # Music2Light
    TRI = "TRI"   # Trigger
    MAS = "MAS"   # MADRIX Script / custom


# ======================================================================
# Base Effect class
# ======================================================================

class BaseEffect(ABC):
    """Abstract base class for all PixelForge effects.

    Subclasses must implement :meth:`render` and set the class-level
    metadata attributes.
    """

    # -- Metadata (override in subclasses) --
    name: str = "Unnamed Effect"
    description: str = ""
    category: EffectCategory = EffectCategory.SCE
    parameters: list[ParamDef] = []
    audio_state: Optional[Any] = None

    def initialize(self, width: int, height: int) -> None:
        """Called when the effect is first loaded or the matrix resizes.

        Override to allocate persistent state (e.g. particle arrays).
        """
        self._width = width
        self._height = height
        self.audio_state = None

    @abstractmethod
    def render(
        self,
        width: int,
        height: int,
        t: float,
        params: dict[str, Any],
    ) -> np.ndarray:
        """Produce one frame of pixel data.

        Parameters
        ----------
        width, height : int
            Dimensions of the virtual matrix.
        t : float
            Elapsed time in seconds (adjusted for deck speed).
        params : dict
            Current parameter values keyed by :attr:`ParamDef.name`.

        Returns
        -------
        np.ndarray
            ``(height, width, 3)`` array of ``uint8`` RGB values.
        """
        ...


# ======================================================================
# Colour-space helpers (used by many effects)
# ======================================================================

def hsv_to_rgb_array(h: np.ndarray, s: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Vectorised HSV → RGB conversion.

    All inputs and outputs are ``float64`` arrays in ``[0, 1]``.
    """
    h6 = (h % 1.0) * 6.0
    i = np.floor(h6).astype(np.int32)
    f = h6 - i
    p = v * (1.0 - s)
    q = v * (1.0 - s * f)
    t_ = v * (1.0 - s * (1.0 - f))

    r = np.where(i == 0, v, np.where(i == 1, q, np.where(i == 2, p, np.where(i == 3, p, np.where(i == 4, t_, v)))))
    g = np.where(i == 0, t_, np.where(i == 1, v, np.where(i == 2, v, np.where(i == 3, q, np.where(i == 4, p, p)))))
    b = np.where(i == 0, p, np.where(i == 1, p, np.where(i == 2, t_, np.where(i == 3, v, np.where(i == 4, v, q)))))

    return np.stack([r, g, b], axis=-1)
