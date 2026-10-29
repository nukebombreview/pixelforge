"""
PixelForge — Dynamic Effect Parameter Inspector Panel
Generates UI controls dynamically from an effect's ParamDef specifications.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pixelforge.effects.base import BaseEffect, ParamDef, ParamType


class ParameterPanel(QScrollArea):
    """Dynamic inspector panel that renders tweakable parameters for an active effect.

    Signals
    -------
    param_changed(str, object)
        Emitted with (param_name, new_value) when any control is tweaked.
    """

    param_changed = pyqtSignal(str, object)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._container = QWidget()
        self._layout = QFormLayout(self._container)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(8)
        self._layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.setWidget(self._container)

        self._current_effect: Optional[BaseEffect] = None
        self._controls: dict[str, QWidget] = {}

    def set_effect(self, effect: Optional[BaseEffect], current_params: dict[str, Any]) -> None:
        """Clear existing controls and generate new ones for the given effect."""
        self._current_effect = effect
        self._controls.clear()

        # Clear existing layout
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if effect is None:
            lbl = QLabel("No effect selected")
            lbl.setStyleSheet("color: #555f73; font-style: italic; padding: 12px;")
            self._layout.addRow(lbl)
            return

        for pdef in effect.parameters:
            val = current_params.get(pdef.name, pdef.default)
            lbl = QLabel(pdef.label + ":")
            lbl.setStyleSheet("color: #8b949e; font-weight: bold; font-size: 11px;")

            ctrl_widget = self._create_control(pdef, val)
            self._controls[pdef.name] = ctrl_widget
            self._layout.addRow(lbl, ctrl_widget)

    def _create_control(self, pdef: ParamDef, value: Any) -> QWidget:
        if pdef.param_type == ParamType.FLOAT:
            return self._build_float_control(pdef, float(value))
        elif pdef.param_type == ParamType.INT:
            return self._build_int_control(pdef, int(value))
        elif pdef.param_type == ParamType.COLOR:
            return self._build_color_control(pdef, value)
        elif pdef.param_type == ParamType.ENUM:
            return self._build_enum_control(pdef, str(value))
        elif pdef.param_type == ParamType.BOOL:
            return self._build_bool_control(pdef, bool(value))
        elif pdef.param_type == ParamType.STRING:
            return self._build_string_control(pdef, str(value))
        return QLabel(str(value))

    def _build_float_control(self, pdef: ParamDef, current_val: float) -> QWidget:
        container = QWidget()
        h_layout = QHBoxLayout(container)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(6)

        min_v = pdef.min_val if pdef.min_val is not None else 0.0
        max_v = pdef.max_val if pdef.max_val is not None else 10.0
        step = pdef.step if pdef.step is not None else 0.1

        # Multiplier to map float to integer slider
        scale = 100

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(int(min_v * scale), int(max_v * scale))
        slider.setValue(int(current_val * scale))

        spin = QDoubleSpinBox()
        spin.setRange(min_v, max_v)
        spin.setSingleStep(step)
        spin.setValue(current_val)
        spin.setFixedWidth(65)

        def on_slider(val: int):
            f_val = val / scale
            spin.blockSignals(True)
            spin.setValue(f_val)
            spin.blockSignals(False)
            self.param_changed.emit(pdef.name, f_val)

        def on_spin(val: float):
            slider.blockSignals(True)
            slider.setValue(int(val * scale))
            slider.blockSignals(False)
            self.param_changed.emit(pdef.name, val)

        slider.valueChanged.connect(on_slider)
        spin.valueChanged.connect(on_spin)

        h_layout.addWidget(slider, stretch=1)
        h_layout.addWidget(spin)
        return container

    def _build_int_control(self, pdef: ParamDef, current_val: int) -> QWidget:
        container = QWidget()
        h_layout = QHBoxLayout(container)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(6)

        min_v = int(pdef.min_val) if pdef.min_val is not None else 0
        max_v = int(pdef.max_val) if pdef.max_val is not None else 100
        step = int(pdef.step) if pdef.step is not None else 1

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_v, max_v)
        slider.setValue(current_val)

        spin = QSpinBox()
        spin.setRange(min_v, max_v)
        spin.setSingleStep(step)
        spin.setValue(current_val)
        spin.setFixedWidth(65)

        def on_slider(val: int):
            spin.blockSignals(True)
            spin.setValue(val)
            spin.blockSignals(False)
            self.param_changed.emit(pdef.name, val)

        def on_spin(val: int):
            slider.blockSignals(True)
            slider.setValue(val)
            slider.blockSignals(False)
            self.param_changed.emit(pdef.name, val)

        slider.valueChanged.connect(on_slider)
        spin.valueChanged.connect(on_spin)

        h_layout.addWidget(slider, stretch=1)
        h_layout.addWidget(spin)
        return container

    def _build_color_control(self, pdef: ParamDef, current_val: tuple[int, int, int]) -> QWidget:
        btn = QPushButton()
        btn.setFixedHeight(26)

        def update_button_style(rgb: tuple[int, int, int]):
            r, g, b = int(rgb[0]), int(rgb[1]), int(rgb[2])
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            txt_color = "#000000" if lum > 130 else "#ffffff"
            btn.setText(f"RGB({r}, {g}, {b})")
            btn.setStyleSheet(
                f"background-color: rgb({r}, {g}, {b}); color: {txt_color}; "
                f"font-weight: bold; border: 1px solid #444; border-radius: 4px;"
            )

        update_button_style(current_val)

        def choose_color():
            r, g, b = current_val
            initial = QColor(int(r), int(g), int(b))
            chosen = QColorDialog.getColor(initial, self, f"Select {pdef.label}")
            if chosen.isValid():
                new_rgb = (chosen.red(), chosen.green(), chosen.blue())
                update_button_style(new_rgb)
                self.param_changed.emit(pdef.name, new_rgb)

        btn.clicked.connect(choose_color)
        return btn

    def _build_enum_control(self, pdef: ParamDef, current_val: str) -> QWidget:
        combo = QComboBox()
        for opt in pdef.options:
            combo.addItem(opt)
        idx = combo.findText(current_val)
        if idx >= 0:
            combo.setCurrentIndex(idx)

        combo.currentTextChanged.connect(lambda val: self.param_changed.emit(pdef.name, val))
        return combo

    def _build_bool_control(self, pdef: ParamDef, current_val: bool) -> QWidget:
        chk = QCheckBox()
        chk.setChecked(current_val)
        chk.toggled.connect(lambda val: self.param_changed.emit(pdef.name, val))
        return chk

    def _build_string_control(self, pdef: ParamDef, current_val: str) -> QWidget:
        line = QLineEdit(current_val)
        line.setStyleSheet("background-color: #0c0e12; border: 1px solid #32394a; border-radius: 4px; padding: 3px 6px; color: #e6edf3;")
        line.textChanged.connect(lambda val: self.param_changed.emit(pdef.name, val))
        return line
