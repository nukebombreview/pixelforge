"""
PixelForge — Audio & Sound2Light Configuration Dialog
Selects audio input interfaces (WASAPI, WDM, DirectSound), gain, and test generator.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from pixelforge.audio.analyzer import AudioAnalyzer


class AudioConfigDialog(QDialog):
    """Modal dialog for choosing audio device and adjusting Sound2Light reactivity."""

    def __init__(self, analyzer: AudioAnalyzer, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Sound2Light (S2L) Audio Configuration")
        self.setFixedWidth(440)
        self.setModal(True)

        self.analyzer = analyzer
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        grp = QGroupBox("Audio Input Interface")
        form = QFormLayout(grp)
        form.setSpacing(10)

        # Device selector
        self.combo_device = QComboBox()
        self.combo_device.addItem("Default System Input", None)

        devices = self.analyzer.get_input_devices()
        for dev in devices:
            label = f"{dev['name']} ({dev['channels']} ch)"
            self.combo_device.addItem(label, dev["index"])

        form.addRow("Input Device:", self.combo_device)

        # Pre-Amp Gain
        gain_box = QHBoxLayout()
        self.slider_gain = QSlider(Qt.Orientation.Horizontal)
        self.slider_gain.setRange(20, 400)  # 0.2x to 4.0x
        self.slider_gain.setValue(int(self.analyzer.gain * 100))

        self.spin_gain = QDoubleSpinBox()
        self.spin_gain.setRange(0.2, 4.0)
        self.spin_gain.setSingleStep(0.1)
        self.spin_gain.setValue(self.analyzer.gain)
        self.spin_gain.setSuffix("x")
        self.spin_gain.setFixedWidth(65)

        self.slider_gain.valueChanged.connect(lambda v: self.spin_gain.setValue(v / 100.0))
        self.spin_gain.valueChanged.connect(lambda v: self.slider_gain.setValue(int(v * 100)))

        gain_box.addWidget(self.slider_gain, stretch=1)
        gain_box.addWidget(self.spin_gain)
        form.addRow("Input Pre-Amp Gain:", gain_box)

        # Synthetic generator fallback toggle
        self.chk_gen = QCheckBox("Enable Synthetic Audio Synthesizer (Offline Demo Mode)")
        self.chk_gen.setChecked(self.analyzer.generator_mode)
        form.addRow("", self.chk_gen)

        layout.addWidget(grp)

        # S2L Info Box
        lbl_info = QLabel(
            "Frequency Bands:\n"
            "• Sub/Bass: 20 – 250 Hz (Kick drum, 808s)\n"
            "• Low-Mid: 250 – 500 Hz (Basslines, warmth)\n"
            "• Mid: 500 – 2000 Hz (Vocals, guitars)\n"
            "• High-Mid: 2000 – 4000 Hz (Snare attack)\n"
            "• High: 4000 – 20000 Hz (Hi-hats, cymbals)"
        )
        lbl_info.setStyleSheet(
            "background-color: #161b22; border: 1px solid #30363d; border-radius: 4px; padding: 8px; color: #7ee787; font-size: 11px;"
        )
        layout.addWidget(lbl_info)

        # Dialog Buttons
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _on_accept(self) -> None:
        chosen_dev = self.combo_device.currentData()
        self.analyzer.gain = self.spin_gain.value()
        self.analyzer.generator_mode = self.chk_gen.isChecked()
        if not self.chk_gen.isChecked():
            self.analyzer.start(chosen_dev)
        self.accept()
