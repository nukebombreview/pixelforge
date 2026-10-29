"""
PixelForge — Deck Controls Panel
Complete control section for an individual deck (Deck A or Deck B).
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from pixelforge.core.deck import Deck
from pixelforge.effects import EFFECT_REGISTRY, create_effect, get_effect_names
from pixelforge.ui.effect_panel import ParameterPanel


class DeckControlWidget(QGroupBox):
    """Control panel for one deck (Deck A or Deck B).

    Signals
    -------
    effect_changed(str)
        Emitted when a new effect is selected.
    speed_changed(float)
        Emitted when playback speed is adjusted.
    mute_toggled(bool)
        Emitted when deck mute state changes.
    """

    effect_changed = pyqtSignal(str)
    speed_changed = pyqtSignal(float)
    mute_toggled = pyqtSignal(bool)

    def __init__(
        self,
        deck: Deck,
        accent_color: str = "#00d2ff",
        parent: Optional[QWidget] = None,
    ):
        group_id = f"deck_{deck.name.lower()}_group"
        super().__init__(f"DECK {deck.name}", parent)
        self.setObjectName(group_id)
        self.deck = deck
        self.accent_color = accent_color

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(6)

        # --- Top row: Effect Selector & Mute ---
        top_row = QHBoxLayout()
        top_row.setSpacing(6)

        self.combo_effects = QComboBox()
        self.combo_effects.addItem("-- None (Black) --", None)
        for name in get_effect_names():
            self.combo_effects.addItem(name, name)
        self.combo_effects.currentIndexChanged.connect(self._on_effect_selected)
        top_row.addWidget(self.combo_effects, stretch=1)

        self.btn_mute = QPushButton("MUTE")
        self.btn_mute.setCheckable(True)
        self.btn_mute.setFixedWidth(55)
        self.btn_mute.setStyleSheet(
            "QPushButton:checked { background-color: #ff1744; color: white; font-weight: bold; }"
        )
        self.btn_mute.toggled.connect(self._on_mute_toggled)
        top_row.addWidget(self.btn_mute)

        layout.addLayout(top_row)

        # --- Speed row ---
        speed_row = QHBoxLayout()
        speed_row.setSpacing(6)

        lbl_spd = QLabel("SPEED:")
        lbl_spd.setStyleSheet("color: #8b949e; font-size: 10px; font-weight: bold;")
        speed_row.addWidget(lbl_spd)

        self.slider_speed = QSlider(Qt.Orientation.Horizontal)
        self.slider_speed.setRange(10, 500)  # 0.1x to 5.0x
        self.slider_speed.setValue(100)       # 1.0x
        self.slider_speed.valueChanged.connect(self._on_speed_slider)
        speed_row.addWidget(self.slider_speed, stretch=1)

        self.spin_speed = QDoubleSpinBox()
        self.spin_speed.setRange(0.1, 5.0)
        self.spin_speed.setSingleStep(0.1)
        self.spin_speed.setValue(1.0)
        self.spin_speed.setSuffix("x")
        self.spin_speed.setFixedWidth(60)
        self.spin_speed.valueChanged.connect(self._on_speed_spin)
        speed_row.addWidget(self.spin_speed)

        self.btn_reset_speed = QPushButton("1.0")
        self.btn_reset_speed.setFixedWidth(32)
        self.btn_reset_speed.setStyleSheet("padding: 2px; font-size: 10px;")
        self.btn_reset_speed.clicked.connect(lambda: self.set_speed(1.0))
        speed_row.addWidget(self.btn_reset_speed)

        layout.addLayout(speed_row)

        # --- Parameter Inspector ---
        self.param_panel = ParameterPanel()
        self.param_panel.param_changed.connect(self._on_param_changed)
        layout.addWidget(self.param_panel, stretch=1)

    def load_preset_state(self, effect_name: str, params: dict, speed: float = 1.0) -> None:
        """Fully restore a preset state into the deck and UI controls."""
        self.combo_effects.blockSignals(True)
        idx = self.combo_effects.findText(effect_name)
        if idx >= 0:
            self.combo_effects.setCurrentIndex(idx)
        self.combo_effects.blockSignals(False)

        self.load_effect(effect_name)
        for k, v in params.items():
            self.deck.set_param(k, v)
        self.set_speed(speed)
        self.param_panel.set_effect(self.deck.effect, self.deck.params)

    def load_effect(self, name: Optional[str]) -> None:
        """Load an effect by name into this deck."""
        if not name:
            self.deck.effect = None
            self.param_panel.set_effect(None, {})
            self.effect_changed.emit("")
            return

        eff = create_effect(name, self.deck.matrix.width, self.deck.matrix.height)
        self.deck.effect = eff
        self.param_panel.set_effect(eff, self.deck.params)
        self.effect_changed.emit(name)

    def set_speed(self, speed: float) -> None:
        """Set deck playback speed."""
        clamped = max(0.1, min(5.0, speed))
        self.deck.speed = clamped
        self.slider_speed.blockSignals(True)
        self.spin_speed.blockSignals(True)
        self.slider_speed.setValue(int(clamped * 100))
        self.spin_speed.setValue(clamped)
        self.slider_speed.blockSignals(False)
        self.spin_speed.blockSignals(False)
        self.speed_changed.emit(clamped)

    def _on_effect_selected(self, index: int) -> None:
        eff_name = self.combo_effects.currentData()
        self.load_effect(eff_name)

    def _on_mute_toggled(self, checked: bool) -> None:
        self.deck.muted = checked
        self.mute_toggled.emit(checked)

    def _on_speed_slider(self, val: int) -> None:
        spd = val / 100.0
        self.spin_speed.blockSignals(True)
        self.spin_speed.setValue(spd)
        self.spin_speed.blockSignals(False)
        self.deck.speed = spd
        self.speed_changed.emit(spd)

    def _on_speed_spin(self, val: float) -> None:
        self.slider_speed.blockSignals(True)
        self.slider_speed.setValue(int(val * 100))
        self.slider_speed.blockSignals(False)
        self.deck.speed = val
        self.speed_changed.emit(val)

    def _on_param_changed(self, name: str, value: object) -> None:
        self.deck.set_param(name, value)

    def set_param_by_index(self, index: int, normalized_val: float) -> None:
        """Update an effect parameter by index from 0.0..1.0 normalized value."""
        if not self.deck.effect:
            return
        params = self.deck.effect.parameters
        if 0 <= index < len(params):
            pdef = params[index]
            min_v = pdef.min_val if pdef.min_val is not None else 0.0
            max_v = pdef.max_val if pdef.max_val is not None else 1.0
            val = min_v + normalized_val * (max_v - min_v)
            if hasattr(pdef, "param_type") and pdef.param_type.name == "INT":
                val = int(round(val))
            elif hasattr(pdef, "param_type") and pdef.param_type.name == "BOOL":
                val = normalized_val > 0.5
            self.deck.set_param(pdef.name, val)
            # Update UI inspector
            self.param_panel.set_effect(self.deck.effect, self.deck.params)
