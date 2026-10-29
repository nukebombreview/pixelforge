"""
PixelForge — MIDI Configuration & Diagnostic Watcher Dialog
Interactive mapping manager, visual MIDI Learn mode, real-time event monitor,
virtual hardware simulator, and factory controller profiles.
"""

from __future__ import annotations

import datetime
from typing import Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pixelforge.midi.manager import (
    MidiBinding,
    MidiManager,
    MidiMappingTarget,
    MidiMessage,
    MidiMode,
    midi_note_to_name,
)
from pixelforge.ui.styles import COLOR_ACCENT, COLOR_DECK_A, COLOR_DECK_B, COLOR_MASTER


TARGET_LABELS = {
    MidiMappingTarget.CROSSFADER.value: "Crossfader (A ◄► B)",
    MidiMappingTarget.MASTER_DIMMER.value: "Master Dimmer (0..100%)",
    MidiMappingTarget.BLACKOUT.value: "Blackout (Toggle / Momentary)",
    MidiMappingTarget.FREEZE.value: "Freeze Output (Toggle)",
    MidiMappingTarget.WHITEOUT.value: "White-Out Flash (Momentary)",
    MidiMappingTarget.DECK_A_SPEED.value: "Deck A Speed Multiplier",
    MidiMappingTarget.DECK_B_SPEED.value: "Deck B Speed Multiplier",
    MidiMappingTarget.DECK_A_PARAM_0.value: "Deck A — Parameter 1",
    MidiMappingTarget.DECK_A_PARAM_1.value: "Deck A — Parameter 2",
    MidiMappingTarget.DECK_A_PARAM_2.value: "Deck A — Parameter 3",
    MidiMappingTarget.DECK_A_PARAM_3.value: "Deck A — Parameter 4",
    MidiMappingTarget.DECK_A_PARAM_4.value: "Deck A — Parameter 5",
    MidiMappingTarget.DECK_A_PARAM_5.value: "Deck A — Parameter 6",
    MidiMappingTarget.DECK_B_PARAM_0.value: "Deck B — Parameter 1",
    MidiMappingTarget.DECK_B_PARAM_1.value: "Deck B — Parameter 2",
    MidiMappingTarget.DECK_B_PARAM_2.value: "Deck B — Parameter 3",
    MidiMappingTarget.DECK_B_PARAM_3.value: "Deck B — Parameter 4",
    MidiMappingTarget.DECK_B_PARAM_4.value: "Deck B — Parameter 5",
    MidiMappingTarget.DECK_B_PARAM_5.value: "Deck B — Parameter 6",
    MidiMappingTarget.STORAGE_A_SLOT_1.value: "Deck A — Recall Slot 1",
    MidiMappingTarget.STORAGE_A_SLOT_2.value: "Deck A — Recall Slot 2",
    MidiMappingTarget.STORAGE_A_SLOT_3.value: "Deck A — Recall Slot 3",
    MidiMappingTarget.STORAGE_A_SLOT_4.value: "Deck A — Recall Slot 4",
    MidiMappingTarget.STORAGE_A_SLOT_5.value: "Deck A — Recall Slot 5",
    MidiMappingTarget.STORAGE_A_SLOT_6.value: "Deck A — Recall Slot 6",
    MidiMappingTarget.STORAGE_A_SLOT_7.value: "Deck A — Recall Slot 7",
    MidiMappingTarget.STORAGE_A_SLOT_8.value: "Deck A — Recall Slot 8",
    MidiMappingTarget.STORAGE_B_SLOT_1.value: "Deck B — Recall Slot 1",
    MidiMappingTarget.STORAGE_B_SLOT_2.value: "Deck B — Recall Slot 2",
    MidiMappingTarget.STORAGE_B_SLOT_3.value: "Deck B — Recall Slot 3",
    MidiMappingTarget.STORAGE_B_SLOT_4.value: "Deck B — Recall Slot 4",
    MidiMappingTarget.STORAGE_B_SLOT_5.value: "Deck B — Recall Slot 5",
    MidiMappingTarget.STORAGE_B_SLOT_6.value: "Deck B — Recall Slot 6",
    MidiMappingTarget.STORAGE_B_SLOT_7.value: "Deck B — Recall Slot 7",
    MidiMappingTarget.STORAGE_B_SLOT_8.value: "Deck B — Recall Slot 8",
}


class MidiConfigDialog(QDialog):
    """Configuration & Diagnostic dialog for MIDI controllers and mapping."""

    def __init__(self, midi_mgr: MidiManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.midi = midi_mgr

        self.setWindowTitle("PixelForge — MIDI Controller & Device Manager")
        self.resize(1000, 680)
        self.setMinimumSize(850, 550)

        self._build_ui()
        self._refresh_ports()
        self._populate_mapping_table()

        # Connect signals
        self.midi.message_received.connect(self._on_midi_message_received)
        self.midi.learn_completed.connect(self._on_learn_completed)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # --------------------------------------------------------------
        # 1. Hardware Ports Header
        # --------------------------------------------------------------
        grp_ports = QGroupBox("Hardware Ports & Connections")
        grp_ports_layout = QGridLayout(grp_ports)
        grp_ports_layout.setContentsMargins(10, 10, 10, 10)
        grp_ports_layout.setSpacing(8)

        # MIDI IN
        lbl_in = QLabel("MIDI Input Port:")
        lbl_in.setStyleSheet("font-weight: bold; color: #58a6ff;")
        self.combo_in = QComboBox()
        self.combo_in.setMinimumWidth(240)
        self.btn_connect_in = QPushButton("Connect Input")
        self.btn_connect_in.setCheckable(True)
        self.btn_connect_in.clicked.connect(self._toggle_input_port)

        # MIDI OUT
        lbl_out = QLabel("MIDI Feedback Output Port:")
        lbl_out.setStyleSheet("font-weight: bold; color: #bc8cff;")
        self.combo_out = QComboBox()
        self.combo_out.setMinimumWidth(240)
        self.btn_connect_out = QPushButton("Connect Output")
        self.btn_connect_out.setCheckable(True)
        self.btn_connect_out.clicked.connect(self._toggle_output_port)

        # Refresh
        self.btn_refresh = QPushButton("🔄 Refresh Devices")
        self.btn_refresh.clicked.connect(self._refresh_ports)

        # Status
        self.lbl_port_status = QLabel("Status: Standby")
        self.lbl_port_status.setStyleSheet("color: #8b949e; font-style: italic;")

        grp_ports_layout.addWidget(lbl_in, 0, 0)
        grp_ports_layout.addWidget(self.combo_in, 0, 1)
        grp_ports_layout.addWidget(self.btn_connect_in, 0, 2)
        grp_ports_layout.addWidget(self.btn_refresh, 0, 3)

        grp_ports_layout.addWidget(lbl_out, 1, 0)
        grp_ports_layout.addWidget(self.combo_out, 1, 1)
        grp_ports_layout.addWidget(self.btn_connect_out, 1, 2)
        grp_ports_layout.addWidget(self.lbl_port_status, 1, 3)

        layout.addWidget(grp_ports)

        # --------------------------------------------------------------
        # 2. Tab Widget (Mapping Matrix & MIDI Watcher)
        # --------------------------------------------------------------
        tabs = QTabWidget()
        tabs.addTab(self._build_mapping_tab(), "🎛 MIDI Mapping Matrix & Learn")
        tabs.addTab(self._build_watcher_tab(), "📡 Live MIDI Watcher & Simulator")
        layout.addWidget(tabs, stretch=1)

        # --------------------------------------------------------------
        # 3. Dialog Bottom Buttons
        # --------------------------------------------------------------
        bottom_bar = QHBoxLayout()
        lbl_hint = QLabel("💡 Tip: Click 'Learn' on any parameter, then turn a knob or press a pad on your MIDI device.")
        lbl_hint.setStyleSheet("color: #8b949e; font-size: 11px;")
        bottom_bar.addWidget(lbl_hint)
        bottom_bar.addStretch()

        btn_close = QPushButton("Close")
        btn_close.setFixedWidth(100)
        btn_close.clicked.connect(self.accept)
        bottom_bar.addWidget(btn_close)

        layout.addLayout(bottom_bar)

    # ------------------------------------------------------------------
    # Tab 1: Mapping Matrix
    # ------------------------------------------------------------------

    def _build_mapping_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Learn Banner
        self.banner_learn = QFrame()
        self.banner_learn.setStyleSheet(
            "background-color: #2e1065; border: 1px solid #7c3aed; border-radius: 4px; padding: 4px;"
        )
        self.banner_learn.setVisible(False)
        banner_layout = QHBoxLayout(self.banner_learn)
        banner_layout.setContentsMargins(8, 4, 8, 4)
        self.lbl_learn_text = QLabel("🎯 LEARNING IN PROGRESS: Move a fader or press a button on your controller...")
        self.lbl_learn_text.setStyleSheet("color: #f3e8ff; font-weight: bold;")
        btn_cancel_learn = QPushButton("Cancel Learn")
        btn_cancel_learn.setFixedWidth(110)
        btn_cancel_learn.clicked.connect(self._cancel_learn)
        banner_layout.addWidget(self.lbl_learn_text)
        banner_layout.addStretch()
        banner_layout.addWidget(btn_cancel_learn)
        layout.addWidget(self.banner_learn)

        # Table
        self.tbl_mappings = QTableWidget()
        self.tbl_mappings.setColumnCount(8)
        self.tbl_mappings.setHorizontalHeaderLabels([
            "Target Function", "Type", "Ch", "Control / Note", "Mode", "Invert", "Learn", "Clear"
        ])
        header = self.tbl_mappings.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)
        self.tbl_mappings.setColumnWidth(6, 80)
        self.tbl_mappings.setColumnWidth(7, 50)
        self.tbl_mappings.verticalHeader().setVisible(False)
        self.tbl_mappings.setAlternatingRowColors(True)
        layout.addWidget(self.tbl_mappings, stretch=1)

        # Bottom Profile bar
        profile_bar = QHBoxLayout()
        profile_bar.setSpacing(8)

        lbl_prof = QLabel("Factory Preset:")
        self.combo_presets = QComboBox()
        self.combo_presets.addItems(["Generic Controller", "Akai APC Mini", "Korg nanoKONTROL 2"])
        btn_load_preset = QPushButton("Apply Template")
        btn_load_preset.clicked.connect(self._load_selected_preset)

        profile_bar.addWidget(lbl_prof)
        profile_bar.addWidget(self.combo_presets)
        profile_bar.addWidget(btn_load_preset)
        profile_bar.addSpacing(16)

        btn_export = QPushButton("Export Profile (.pxm)...")
        btn_export.clicked.connect(self._export_profile)
        btn_import = QPushButton("Import Profile (.pxm)...")
        btn_import.clicked.connect(self._import_profile)
        btn_clear_all = QPushButton("Clear All")
        btn_clear_all.clicked.connect(self._clear_all_mappings)

        profile_bar.addWidget(btn_export)
        profile_bar.addWidget(btn_import)
        profile_bar.addWidget(btn_clear_all)
        profile_bar.addStretch()

        layout.addLayout(profile_bar)
        return w

    # ------------------------------------------------------------------
    # Tab 2: MIDI Watcher & Virtual Simulator
    # ------------------------------------------------------------------

    def _build_watcher_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Top Control / Filter Bar
        ctrl_bar = QHBoxLayout()
        ctrl_bar.setSpacing(8)

        lbl_filt = QLabel("Filter Channel:")
        self.combo_ch_filter = QComboBox()
        self.combo_ch_filter.addItem("All Channels", -1)
        for c in range(16):
            self.combo_ch_filter.addItem(f"Channel {c+1}", c)
        self.combo_ch_filter.currentIndexChanged.connect(self._refresh_watcher_log)

        self.chk_autoscroll = QCheckBox("Auto-scroll")
        self.chk_autoscroll.setChecked(True)

        self.btn_pause_watcher = QPushButton("⏸ Pause")
        self.btn_pause_watcher.setCheckable(True)
        self.btn_pause_watcher.toggled.connect(self._toggle_watcher_pause)

        btn_clear_log = QPushButton("🗑 Clear Log")
        btn_clear_log.clicked.connect(self._clear_watcher_log)

        ctrl_bar.addWidget(lbl_filt)
        ctrl_bar.addWidget(self.combo_ch_filter)
        ctrl_bar.addSpacing(10)
        ctrl_bar.addWidget(self.chk_autoscroll)
        ctrl_bar.addStretch()
        ctrl_bar.addWidget(self.btn_pause_watcher)
        ctrl_bar.addWidget(btn_clear_log)

        layout.addLayout(ctrl_bar)

        # Splitter: Watcher Log (Top) and Virtual Simulator (Bottom)
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Watcher Log Table
        self.tbl_watcher = QTableWidget()
        self.tbl_watcher.setColumnCount(6)
        self.tbl_watcher.setHorizontalHeaderLabels([
            "Time", "Ch", "Event", "Data 1 (Control/Pitch)", "Data 2 (Val/Vel)", "Triggered Target"
        ])
        wh = self.tbl_watcher.horizontalHeader()
        wh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        wh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        wh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        wh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        wh.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        wh.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.tbl_watcher.verticalHeader().setVisible(False)
        self.tbl_watcher.setAlternatingRowColors(True)
        splitter.addWidget(self.tbl_watcher)

        # Virtual MIDI Generator (Bottom)
        grp_sim = QGroupBox("Virtual MIDI Signal Generator (Diagnostic Hardware Simulator)")
        sim_layout = QGridLayout(grp_sim)
        sim_layout.setContentsMargins(10, 10, 10, 10)
        sim_layout.setSpacing(10)

        # Virtual Crossfader (CC 1)
        lbl_v_cf = QLabel("Crossfader (CC 1):")
        self.sld_v_cf = QSlider(Qt.Orientation.Horizontal)
        self.sld_v_cf.setRange(0, 127)
        self.sld_v_cf.setValue(64)
        self.sld_v_cf.valueChanged.connect(lambda v: self.midi.simulate_message("control_change", 0, 1, v))

        # Virtual Master Dimmer (CC 7)
        lbl_v_dim = QLabel("Master Dimmer (CC 7):")
        self.sld_v_dim = QSlider(Qt.Orientation.Horizontal)
        self.sld_v_dim.setRange(0, 127)
        self.sld_v_dim.setValue(127)
        self.sld_v_dim.valueChanged.connect(lambda v: self.midi.simulate_message("control_change", 0, 7, v))

        # Buttons
        btn_v_bo = QPushButton("Blackout (Note 36)")
        btn_v_bo.clicked.connect(lambda: self.midi.simulate_message("note_on", 0, 36, 127))

        btn_v_frz = QPushButton("Freeze (Note 37)")
        btn_v_frz.clicked.connect(lambda: self.midi.simulate_message("note_on", 0, 37, 127))

        btn_v_pad1 = QPushButton("Slot 1 (Note 48)")
        btn_v_pad1.clicked.connect(lambda: self.midi.simulate_message("note_on", 0, 48, 127))

        btn_v_pad2 = QPushButton("Slot 2 (Note 49)")
        btn_v_pad2.clicked.connect(lambda: self.midi.simulate_message("note_on", 0, 49, 127))

        sim_layout.addWidget(lbl_v_cf, 0, 0)
        sim_layout.addWidget(self.sld_v_cf, 0, 1)
        sim_layout.addWidget(btn_v_bo, 0, 2)
        sim_layout.addWidget(btn_v_pad1, 0, 3)

        sim_layout.addWidget(lbl_v_dim, 1, 0)
        sim_layout.addWidget(self.sld_v_dim, 1, 1)
        sim_layout.addWidget(btn_v_frz, 1, 2)
        sim_layout.addWidget(btn_v_pad2, 1, 3)

        splitter.addWidget(grp_sim)
        splitter.setSizes([320, 140])
        layout.addWidget(splitter, stretch=1)

        return w

    # ------------------------------------------------------------------
    # Port Handling
    # ------------------------------------------------------------------

    def _refresh_ports(self) -> None:
        self.combo_in.clear()
        self.combo_out.clear()

        in_ports = self.midi.get_input_ports()
        out_ports = self.midi.get_output_ports()

        if in_ports:
            self.combo_in.addItems(in_ports)
        else:
            self.combo_in.addItem("No MIDI Input Ports Detected")

        if out_ports:
            self.combo_out.addItems(out_ports)
        else:
            self.combo_out.addItem("No MIDI Output Ports Detected")

        # Update button states
        if self.midi.is_input_open:
            self.btn_connect_in.setText("Disconnect")
            self.btn_connect_in.setChecked(True)
            self.lbl_port_status.setText(f"Connected: {self.midi.active_inport_name}")
            self.lbl_port_status.setStyleSheet("color: #3fb950; font-weight: bold;")
        else:
            self.btn_connect_in.setText("Connect Input")
            self.btn_connect_in.setChecked(False)
            self.lbl_port_status.setText("Status: Standby (Not Connected)")
            self.lbl_port_status.setStyleSheet("color: #8b949e; font-style: italic;")

        if self.midi.is_output_open:
            self.btn_connect_out.setText("Disconnect")
            self.btn_connect_out.setChecked(True)
        else:
            self.btn_connect_out.setText("Connect Output")
            self.btn_connect_out.setChecked(False)

    def _toggle_input_port(self, checked: bool) -> None:
        if checked:
            port = self.combo_in.currentText()
            if port and not port.startswith("No MIDI"):
                success = self.midi.open_input_port(port)
                if success:
                    self.btn_connect_in.setText("Disconnect")
                    self.lbl_port_status.setText(f"Connected: {port}")
                    self.lbl_port_status.setStyleSheet("color: #3fb950; font-weight: bold;")
                else:
                    self.btn_connect_in.setChecked(False)
                    QMessageBox.warning(self, "Port Error", f"Could not open MIDI input port '{port}'.")
            else:
                self.btn_connect_in.setChecked(False)
        else:
            self.midi.close_input_port()
            self.btn_connect_in.setText("Connect Input")
            self.lbl_port_status.setText("Status: Disconnected")
            self.lbl_port_status.setStyleSheet("color: #8b949e;")

    def _toggle_output_port(self, checked: bool) -> None:
        if checked:
            port = self.combo_out.currentText()
            if port and not port.startswith("No MIDI"):
                success = self.midi.open_output_port(port)
                if success:
                    self.btn_connect_out.setText("Disconnect")
                else:
                    self.btn_connect_out.setChecked(False)
                    QMessageBox.warning(self, "Port Error", f"Could not open MIDI feedback output port '{port}'.")
            else:
                self.btn_connect_out.setChecked(False)
        else:
            self.midi.close_output_port()
            self.btn_connect_out.setText("Connect Output")

    # ------------------------------------------------------------------
    # Mapping Table Population
    # ------------------------------------------------------------------

    def _populate_mapping_table(self) -> None:
        targets = list(TARGET_LABELS.keys())
        self.tbl_mappings.setRowCount(len(targets))

        for row, target in enumerate(targets):
            b = self.midi.get_binding(target)

            # Column 0: Target Label
            item_lbl = QTableWidgetItem(TARGET_LABELS.get(target, target))
            item_lbl.setFlags(item_lbl.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.tbl_mappings.setItem(row, 0, item_lbl)

            # Column 1: Type
            type_str = "CC" if (b and b.msg_type == "control_change") else ("Note" if b else "—")
            item_type = QTableWidgetItem(type_str)
            item_type.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_type.setFlags(item_type.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.tbl_mappings.setItem(row, 1, item_type)

            # Column 2: Channel
            ch_str = "Omni" if (b and b.channel == -1) else (f"Ch {b.channel+1}" if b else "—")
            item_ch = QTableWidgetItem(ch_str)
            item_ch.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_ch.setFlags(item_ch.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.tbl_mappings.setItem(row, 2, item_ch)

            # Column 3: Control / Note
            if b:
                if b.msg_type == "note_on":
                    ctrl_str = midi_note_to_name(b.control)
                else:
                    ctrl_str = f"CC {b.control}"
            else:
                ctrl_str = "—"
            item_ctrl = QTableWidgetItem(ctrl_str)
            item_ctrl.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_ctrl.setFlags(item_ctrl.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if b:
                item_ctrl.setForeground(QColor("#58a6ff"))
            self.tbl_mappings.setItem(row, 3, item_ctrl)

            # Column 4: Mode Combobox
            combo_mode = QComboBox()
            combo_mode.addItems(["absolute", "toggle", "momentary", "relative"])
            if b:
                combo_mode.setCurrentText(b.mode)
            combo_mode.currentTextChanged.connect(lambda m, t=target: self._on_mode_changed(t, m))
            self.tbl_mappings.setCellWidget(row, 4, combo_mode)

            # Column 5: Invert Checkbox
            chk_inv = QCheckBox()
            chk_inv.setStyleSheet("margin-left: 10px;")
            if b:
                chk_inv.setChecked(b.invert)
            chk_inv.toggled.connect(lambda inv, t=target: self._on_invert_changed(t, inv))
            self.tbl_mappings.setCellWidget(row, 5, chk_inv)

            # Column 6: Learn Button
            btn_learn = QPushButton("🎯 Learn")
            btn_learn.setStyleSheet("background-color: #2e1065; color: #d8b4fe; font-weight: bold;")
            btn_learn.clicked.connect(lambda checked, t=target: self._start_learn(t))
            self.tbl_mappings.setCellWidget(row, 6, btn_learn)

            # Column 7: Clear Button
            btn_clear = QPushButton("✕")
            btn_clear.clicked.connect(lambda checked, t=target: self._clear_mapping(t))
            self.tbl_mappings.setCellWidget(row, 7, btn_clear)

    def _on_mode_changed(self, target: str, mode: str) -> None:
        b = self.midi.get_binding(target)
        if b:
            b.mode = mode

    def _on_invert_changed(self, target: str, invert: bool) -> None:
        b = self.midi.get_binding(target)
        if b:
            b.invert = invert

    def _clear_mapping(self, target: str) -> None:
        self.midi.remove_binding(target)
        self._populate_mapping_table()

    def _clear_all_mappings(self) -> None:
        reply = QMessageBox.question(
            self, "Clear All Mappings", "Remove all MIDI mappings?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.midi.clear_all_bindings()
            self._populate_mapping_table()

    # ------------------------------------------------------------------
    # Learn Mode Actions
    # ------------------------------------------------------------------

    def _start_learn(self, target: str) -> None:
        self.banner_learn.setVisible(True)
        lbl_target = TARGET_LABELS.get(target, target)
        self.lbl_learn_text.setText(f"🎯 LEARNING [{lbl_target}]: Move a fader or press a button on your controller...")
        self.midi.start_learning(target)

    def _cancel_learn(self) -> None:
        self.midi.cancel_learning()
        self.banner_learn.setVisible(False)

    def _on_learn_completed(self, binding: MidiBinding) -> None:
        self.banner_learn.setVisible(False)
        self._populate_mapping_table()

    # ------------------------------------------------------------------
    # Profiles / Presets
    # ------------------------------------------------------------------

    def _load_selected_preset(self) -> None:
        name = self.combo_presets.currentText()
        self.midi.load_preset_profile(name)
        self._populate_mapping_table()
        QMessageBox.information(self, "Preset Applied", f"Loaded factory MIDI template: {name}")

    def _export_profile(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export MIDI Mapping Profile", "midi_map.pxm", "PixelForge MIDI (*.pxm);;All Files (*.*)"
        )
        if not path:
            return
        if self.midi.save_profile_file(path):
            QMessageBox.information(self, "Exported", f"MIDI profile exported to:\n{path}")
        else:
            QMessageBox.critical(self, "Export Error", "Failed to export MIDI profile.")

    def _import_profile(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import MIDI Mapping Profile", "", "PixelForge MIDI (*.pxm);;All Files (*.*)"
        )
        if not path:
            return
        if self.midi.load_profile_file(path):
            self._populate_mapping_table()
            QMessageBox.information(self, "Imported", f"MIDI profile loaded successfully.")
        else:
            QMessageBox.critical(self, "Import Error", "Failed to load MIDI profile.")

    # ------------------------------------------------------------------
    # Watcher Diagnostics
    # ------------------------------------------------------------------

    def _on_midi_message_received(self, msg: MidiMessage) -> None:
        if self.btn_pause_watcher.isChecked():
            return

        # Check filter
        filt_ch = self.combo_ch_filter.currentData()
        if filt_ch != -1 and msg.channel != filt_ch:
            return

        # Add row to watcher
        row = self.tbl_watcher.rowCount()
        self.tbl_watcher.insertRow(row)

        now_str = datetime.datetime.fromtimestamp(msg.timestamp).strftime("%H:%M:%S.%f")[:-3]

        item_time = QTableWidgetItem(now_str)
        item_ch = QTableWidgetItem(str(msg.channel_display))
        item_ch.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        # Event
        item_ev = QTableWidgetItem(msg.msg_type.replace("_", " ").upper())
        if "note_on" in msg.msg_type:
            item_ev.setForeground(QColor("#3fb950"))
        elif "note_off" in msg.msg_type:
            item_ev.setForeground(QColor("#8b949e"))
        elif "control" in msg.msg_type:
            item_ev.setForeground(QColor("#58a6ff"))

        item_d1 = QTableWidgetItem(msg.control_display)
        item_d2 = QTableWidgetItem(str(msg.value))
        item_d2.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        # Mapped target
        matched = "—"
        for b in self.midi.bindings:
            if b.matches(msg):
                matched = TARGET_LABELS.get(b.target, b.target)
                break
        item_target = QTableWidgetItem(matched)
        if matched != "—":
            item_target.setForeground(QColor("#d29922"))

        for col, item in enumerate([item_time, item_ch, item_ev, item_d1, item_d2, item_target]):
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.tbl_watcher.setItem(row, col, item)

        # Cap rows
        if self.tbl_watcher.rowCount() > 250:
            self.tbl_watcher.removeRow(0)

        if self.chk_autoscroll.isChecked():
            self.tbl_watcher.scrollToBottom()

    def _refresh_watcher_log(self) -> None:
        self.tbl_watcher.setRowCount(0)
        for msg, target in self.midi.watcher_log:
            self._on_midi_message_received(msg)

    def _toggle_watcher_pause(self, paused: bool) -> None:
        self.midi.watcher_paused = paused
        self.btn_pause_watcher.setText("▶ Resume" if paused else "⏸ Pause")

    def _clear_watcher_log(self) -> None:
        self.midi.watcher_log.clear()
        self.tbl_watcher.setRowCount(0)

