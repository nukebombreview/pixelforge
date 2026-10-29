"""
PixelForge — Main Application Window
Unifies dual decks, OpenGL/QPainter preview visualizers, crossfader,
dynamic parameter inspectors, master controls, and Art-Net protocol output.
"""

from __future__ import annotations

import os
import sys
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QAction, QDesktopServices, QFont, QIcon
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QSplitter,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from pixelforge.core.cue import Cue, CueList, CuePlayer
from pixelforge.core.engine import RenderEngine
from pixelforge.core.storage import StorageBank, ProjectFile, populate_factory_presets
from pixelforge.core.timeline import Timeline, TimelineClip, TimelinePlayer, TimelineTrackType
from pixelforge.midi.manager import MidiManager, MidiMappingTarget
from pixelforge.protocols.http_server import HttpRemoteServer
from pixelforge.ui.artnet_dialog import ArtNetDialog
from pixelforge.ui.audio_dialog import AudioConfigDialog
from pixelforge.ui.cue_dialog import CueDialog
from pixelforge.ui.midi_dialog import MidiConfigDialog
from pixelforge.ui.protocol_dialog import ProtocolConfigDialog
from pixelforge.ui.crossfader_widget import CrossfaderWidget
from pixelforge.ui.deck_controls import DeckControlWidget
from pixelforge.ui.preview_widget import MatrixPreviewWidget
from pixelforge.ui.patch_editor import PatchEditorDialog, MatrixGeneratorDialog
from pixelforge.ui.storage_grid import StorageGridWidget
from pixelforge.ui.vu_meter import VUMeterWidget
from pixelforge.ui.styles import (
    COLOR_DECK_A,
    COLOR_DECK_B,
    COLOR_MASTER,
    DARK_THEME_QSS,
)


class MainWindow(QMainWindow):
    """Primary GUI window for the PixelForge application."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("PixelForge — Professional Real-Time LED Lighting & Pixel Mapping")
        self.resize(1340, 860)
        self.setMinimumSize(1024, 680)

        # Apply dark theme
        self.setStyleSheet(DARK_THEME_QSS)

        # Initialize rendering engine (default 32x32)
        self.engine = RenderEngine(width=32, height=32)

        # Storage banks (Deck A & Deck B)
        self.bank_a = StorageBank(64)
        self.bank_b = StorageBank(64)
        populate_factory_presets(self.bank_a, self.bank_b)

        # Art-Net state
        self.artnet_ip = "255.255.255.255"
        self.artnet_port = 6454
        self.artnet_universe = 0
        self.artnet_order = "RGB"

        # MIDI Subsystem
        self.midi = MidiManager(self)
        self.midi.binding_triggered.connect(self._on_midi_binding_triggered)

        # Show Automation: Cue Player & Timeline Player
        self.cue_player = CuePlayer(parent=self)
        self.timeline_player = TimelinePlayer(parent=self)
        self._init_factory_cues()

        self._build_menus()
        self._build_toolbar()
        self._build_central_ui()
        self._build_statusbar()

        # Connect Cue Player
        self.cue_player.crossfader_target_updated.connect(self.crossfader_widget.set_position)
        self.cue_player.dimmer_target_updated.connect(lambda v: self.slider_dimmer.setValue(int(round(v * 100))))
        self.cue_player.preset_recall_requested.connect(self._on_cue_preset_recall)
        self.cue_player.cue_changed.connect(self._on_cue_changed_status)

        # Connect Timeline Player
        self.timeline_player.crossfader_automated.connect(self.crossfader_widget.set_position)
        self.timeline_player.dimmer_automated.connect(lambda v: self.slider_dimmer.setValue(int(round(v * 100))))
        self.timeline_player.clip_triggered.connect(self._on_timeline_clip_triggered)

        # Web & HTTP REST Remote Server (port 8080)
        self.http_server = HttpRemoteServer(port=8080, parent=self)
        self.http_server.set_engine_reference(self.engine)
        self.http_server.crossfader_requested.connect(self.crossfader_widget.set_position)
        self.http_server.dimmer_requested.connect(lambda v: self.slider_dimmer.setValue(int(round(v * 100))))
        self.http_server.blackout_requested.connect(lambda: self.btn_blackout.setChecked(not self.btn_blackout.isChecked()))
        self.http_server.freeze_requested.connect(lambda: self.btn_freeze.setChecked(not self.btn_freeze.isChecked()))
        self.http_server.whiteout_requested.connect(lambda: self.btn_whiteout.setChecked(not self.btn_whiteout.isChecked()))
        self.http_server.cue_go_requested.connect(lambda: self.cue_player.go())
        self.http_server.cue_stop_requested.connect(self.cue_player.stop)
        self.http_server.start()

        # Connect engine signals
        self.engine.frame_rendered.connect(self._on_frame_rendered)
        self.engine.fps_updated.connect(self._on_fps_updated)
        self.engine.audio.levels_updated.connect(self.vu_meter.set_levels)
        self.engine.audio.beat_detected.connect(self.vu_meter.trigger_beat)

        # Connect MIDI feedback
        self.crossfader_widget.position_changed.connect(
            lambda pos: self.midi.send_feedback(MidiMappingTarget.CROSSFADER.value, pos)
        )
        self.midi.connection_status_changed.connect(self._on_midi_status_changed)

        # Default initial effects
        self.deck_a_controls.combo_effects.setCurrentText("S2L Spectrum")
        self.deck_b_controls.combo_effects.setCurrentText("S2L Level Shape")

        # Start 60fps render loop
        self.engine.start()

    # ------------------------------------------------------------------
    # Menus
    # ------------------------------------------------------------------

    def _build_menus(self) -> None:
        menubar = self.menuBar()

        # File Menu
        file_menu = menubar.addMenu("&File")

        act_new = QAction("&New Show", self)
        act_new.setShortcut("Ctrl+N")
        act_new.triggered.connect(self._new_project)
        file_menu.addAction(act_new)

        act_open = QAction("&Open Project...", self)
        act_open.setShortcut("Ctrl+O")
        act_open.triggered.connect(self._open_project)
        file_menu.addAction(act_open)

        act_save = QAction("&Save Project As...", self)
        act_save.setShortcut("Ctrl+S")
        act_save.triggered.connect(self._save_project)
        file_menu.addAction(act_save)

        file_menu.addSeparator()

        act_factory = QAction("Load Factory Showcase Presets", self)
        act_factory.triggered.connect(self._load_factory_presets)
        file_menu.addAction(act_factory)

        file_menu.addSeparator()

        act_exit = QAction("E&xit", self)
        act_exit.setShortcut("Ctrl+Q")
        act_exit.triggered.connect(self.close)
        file_menu.addAction(act_exit)

        # Matrix Menu
        matrix_menu = menubar.addMenu("&Matrix")
        for size in [(16, 16), (32, 32), (48, 48), (64, 64)]:
            act = QAction(f"{size[0]} × {size[1]}", self)
            act.triggered.connect(lambda checked, s=size: self.resize_matrix(s[0], s[1]))
            matrix_menu.addAction(act)

        matrix_menu.addSeparator()

        self.act_dot_mode = QAction("LED Dot Display Mode", self, checkable=True)
        self.act_dot_mode.setChecked(True)
        self.act_dot_mode.toggled.connect(self._toggle_dot_mode)
        matrix_menu.addAction(self.act_dot_mode)

        self.act_grid_mode = QAction("Show Fixture Grid Lines", self, checkable=True)
        self.act_grid_mode.setChecked(True)
        self.act_grid_mode.toggled.connect(self._toggle_grid_mode)
        matrix_menu.addAction(self.act_grid_mode)

        self.act_3d_mode = QAction("3D Volumetric Voxel View Mode", self, checkable=True)
        self.act_3d_mode.setChecked(False)
        self.act_3d_mode.toggled.connect(self._toggle_3d_voxels)
        matrix_menu.addAction(self.act_3d_mode)

        # Protocols Menu
        proto_menu = menubar.addMenu("&Protocols")

        act_proto_mgr = QAction("Device & Protocol Manager (Art-Net / sACN / DMX / DVI)...", self)
        act_proto_mgr.setShortcut("Ctrl+D")
        act_proto_mgr.triggered.connect(self._open_protocol_dialog)
        proto_menu.addAction(act_proto_mgr)

        act_web_remote = QAction("Open Web Remote Control Dashboard (Browser)...", self)
        act_web_remote.triggered.connect(self._open_web_remote)
        proto_menu.addAction(act_web_remote)

        proto_menu.addSeparator()

        act_artnet_cfg = QAction("Art-Net Quick Setup...", self)
        act_artnet_cfg.triggered.connect(self._open_artnet_dialog)
        proto_menu.addAction(act_artnet_cfg)

        self.act_artnet_toggle = QAction("Enable Art-Net Broadcast", self, checkable=True)
        self.act_artnet_toggle.toggled.connect(self._toggle_artnet)
        proto_menu.addAction(self.act_artnet_toggle)

        proto_menu.addSeparator()

        act_dvi_open = QAction("Launch DVI Video Wall Window", self)
        act_dvi_open.setShortcut("F11")
        act_dvi_open.triggered.connect(self._launch_dvi_output)
        proto_menu.addAction(act_dvi_open)

        act_dvi_close = QAction("Close DVI Video Wall Window", self)
        act_dvi_close.triggered.connect(self._close_dvi_output)
        proto_menu.addAction(act_dvi_close)

        # Patch Menu
        patch_menu = menubar.addMenu("&Patch")
        act_patch_editor = QAction("Open Visual Patch Editor...", self)
        act_patch_editor.setShortcut("Ctrl+P")
        act_patch_editor.triggered.connect(self._open_patch_editor)
        patch_menu.addAction(act_patch_editor)

        act_matrix_gen = QAction("Matrix Panel Generator...", self)
        act_matrix_gen.triggered.connect(self._open_matrix_generator)
        patch_menu.addAction(act_matrix_gen)

        patch_menu.addSeparator()
        act_add_rope = QAction("🎗 Quick Patch: 5m LED Rope Light (80 Pixels GRB)...", self)
        act_add_rope.triggered.connect(self._quick_patch_rope_light)
        patch_menu.addAction(act_add_rope)

        # Audio / S2L Menu
        audio_menu = menubar.addMenu("&Audio")
        act_audio_cfg = QAction("Audio & S2L Configuration...", self)
        act_audio_cfg.triggered.connect(self._open_audio_dialog)
        audio_menu.addAction(act_audio_cfg)

        self.act_audio_gen = QAction("Synthetic Demo Mode", self, checkable=True)
        self.act_audio_gen.setChecked(self.engine.audio.generator_mode)
        self.act_audio_gen.toggled.connect(lambda chk: setattr(self.engine.audio, "generator_mode", chk))
        audio_menu.addAction(self.act_audio_gen)

        # MIDI Menu
        midi_menu = menubar.addMenu("&MIDI")
        act_midi_cfg = QAction("MIDI Controller & Device Manager...", self)
        act_midi_cfg.setShortcut("Ctrl+M")
        act_midi_cfg.triggered.connect(self._open_midi_dialog)
        midi_menu.addAction(act_midi_cfg)

        act_midi_watcher = QAction("Live MIDI Watcher Diagnostics...", self)
        act_midi_watcher.setShortcut("F8")
        act_midi_watcher.triggered.connect(self._open_midi_watcher)
        midi_menu.addAction(act_midi_watcher)

        midi_menu.addSeparator()

        act_load_generic = QAction("Apply Generic Controller Template", self)
        act_load_generic.triggered.connect(lambda: self._apply_midi_template("Generic Controller"))
        midi_menu.addAction(act_load_generic)

        act_load_apc = QAction("Apply Akai APC Mini Template", self)
        act_load_apc.triggered.connect(lambda: self._apply_midi_template("Akai APC Mini"))
        midi_menu.addAction(act_load_apc)

        act_load_korg = QAction("Apply Korg nanoKONTROL 2 Template", self)
        act_load_korg.triggered.connect(lambda: self._apply_midi_template("Korg nanoKONTROL 2"))
        midi_menu.addAction(act_load_korg)

        # Automation Menu (Cue List & Timeline)
        auto_menu = menubar.addMenu("&Automation")
        act_cuelist = QAction("Show Automation (Cue List & Timeline)...", self)
        act_cuelist.setShortcut("Ctrl+L")
        act_cuelist.triggered.connect(self._open_cue_dialog)
        auto_menu.addAction(act_cuelist)

        act_timeline = QAction("Open Multi-Track Timeline...", self)
        act_timeline.setShortcut("Ctrl+T")
        act_timeline.triggered.connect(self._open_timeline_tab)
        auto_menu.addAction(act_timeline)

        auto_menu.addSeparator()

        act_go = QAction("Trigger Next Cue (GO)", self)
        act_go.setShortcut("Space")
        act_go.triggered.connect(lambda: self.cue_player.go())
        auto_menu.addAction(act_go)

        act_back = QAction("Step Back Cue", self)
        act_back.triggered.connect(self.cue_player.back)
        auto_menu.addAction(act_back)

        act_pause = QAction("Pause / Resume Cue", self)
        act_pause.triggered.connect(self.cue_player.pause)
        auto_menu.addAction(act_pause)

        act_stop = QAction("Stop Cue Playback", self)
        act_stop.setShortcut("Esc")
        act_stop.triggered.connect(self.cue_player.stop)
        auto_menu.addAction(act_stop)

        # Help Menu
        help_menu = menubar.addMenu("&Help")
        act_about = QAction("About PixelForge", self)
        act_about.triggered.connect(self._show_about)
        help_menu.addAction(act_about)

    # ------------------------------------------------------------------
    # Toolbar
    # ------------------------------------------------------------------

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Main Controls", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        lbl_res = QLabel(" Matrix: ")
        lbl_res.setStyleSheet("font-weight: bold; color: #8b949e;")
        toolbar.addWidget(lbl_res)

        for w, h in [(16, 16), (32, 32), (64, 64)]:
            btn = QPushButton(f"{w}×{h}")
            btn.setFixedWidth(54)
            btn.clicked.connect(lambda checked, pw=w, ph=h: self.resize_matrix(pw, ph))
            toolbar.addWidget(btn)

        toolbar.addSeparator()

        btn_dots = QPushButton("LED Dots")
        btn_dots.setCheckable(True)
        btn_dots.setChecked(True)
        btn_dots.toggled.connect(self._toggle_dot_mode)
        toolbar.addWidget(btn_dots)

        btn_grid = QPushButton("Grid")
        btn_grid.setCheckable(True)
        btn_grid.setChecked(True)
        btn_grid.toggled.connect(self._toggle_grid_mode)
        toolbar.addWidget(btn_grid)

        toolbar.addSeparator()

        # Audio VU & Controls
        lbl_audio = QLabel(" S2L: ")
        lbl_audio.setStyleSheet("font-weight: bold; color: #8b949e;")
        toolbar.addWidget(lbl_audio)

        self.vu_meter = VUMeterWidget(self)
        self.vu_meter.setFixedWidth(110)
        toolbar.addWidget(self.vu_meter)

        btn_audio_cfg = QPushButton("🎤 Audio")
        btn_audio_cfg.clicked.connect(self._open_audio_dialog)
        toolbar.addWidget(btn_audio_cfg)

        toolbar.addSeparator()

        # Art-Net Broadcast Button
        self.btn_artnet = QPushButton("📡 Art-Net Output: OFF")
        self.btn_artnet.setObjectName("btn_artnet_toggle")
        self.btn_artnet.setCheckable(True)
        self.btn_artnet.toggled.connect(self._toggle_artnet)
        toolbar.addWidget(self.btn_artnet)

        btn_cfg = QPushButton("⚙ Config")
        btn_cfg.clicked.connect(self._open_artnet_dialog)
        toolbar.addWidget(btn_cfg)

        toolbar.addSeparator()

        btn_midi = QPushButton("🎹 MIDI")
        btn_midi.setStyleSheet("background-color: #241734; color: #d8b4fe; font-weight: bold;")
        btn_midi.clicked.connect(self._open_midi_dialog)
        toolbar.addWidget(btn_midi)

        toolbar.addSeparator()

        btn_patch = QPushButton("🔲 Patch Editor")
        btn_patch.setStyleSheet("background-color: #1a2233; color: #58a6ff; font-weight: bold;")
        btn_patch.clicked.connect(self._open_patch_editor)
        toolbar.addWidget(btn_patch)

        toolbar.addSeparator()

        btn_cues = QPushButton("📋 Cue List")
        btn_cues.setStyleSheet("background-color: #172b1d; color: #3fb950; font-weight: bold;")
        btn_cues.clicked.connect(self._open_cue_dialog)
        toolbar.addWidget(btn_cues)

        toolbar.addSeparator()

        self.lbl_toolbar_fps = QLabel(" 60.0 FPS ")
        self.lbl_toolbar_fps.setStyleSheet(
            "font-weight: bold; color: #00e676; background-color: #0c1810; "
            "border: 1px solid #1c3b24; border-radius: 4px; padding: 2px 8px;"
        )
        toolbar.addWidget(self.lbl_toolbar_fps)

    # ------------------------------------------------------------------
    # Central Layout
    # ------------------------------------------------------------------

    def _build_central_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(10, 10, 10, 8)
        main_layout.setSpacing(10)

        # ==============================================================
        # Top Section: Previews (Deck A, Master, Deck B)
        # ==============================================================
        previews_box = QHBoxLayout()
        previews_box.setSpacing(10)

        self.preview_a = MatrixPreviewWidget(title="DECK A", accent_color=COLOR_DECK_A)
        self.preview_out = MatrixPreviewWidget(title="MASTER OUTPUT", accent_color=COLOR_MASTER)
        self.preview_b = MatrixPreviewWidget(title="DECK B", accent_color=COLOR_DECK_B)

        previews_box.addWidget(self.preview_a, stretch=3)
        previews_box.addWidget(self.preview_out, stretch=4)  # Master preview is slightly larger
        previews_box.addWidget(self.preview_b, stretch=3)

        main_layout.addLayout(previews_box, stretch=4)

        # ==============================================================
        # Middle Section: Crossfader
        # ==============================================================
        self.crossfader_widget = CrossfaderWidget(self.engine.crossfader)
        main_layout.addWidget(self.crossfader_widget)

        # ==============================================================
        # Bottom Section: Deck A Controls | Master Controls | Deck B Controls
        # ==============================================================
        controls_box = QHBoxLayout()
        controls_box.setSpacing(10)

        # Deck A Controls
        self.deck_a_controls = DeckControlWidget(self.engine.deck_a, accent_color=COLOR_DECK_A)
        controls_box.addWidget(self.deck_a_controls, stretch=4)

        # Master Panel
        master_panel = self._build_master_panel()
        controls_box.addWidget(master_panel, stretch=2)

        # Deck B Controls
        self.deck_b_controls = DeckControlWidget(self.engine.deck_b, accent_color=COLOR_DECK_B)
        controls_box.addWidget(self.deck_b_controls, stretch=4)

        main_layout.addLayout(controls_box, stretch=5)

        # ==============================================================
        # Storage Places Section (Deck A Storage | Deck B Storage)
        # ==============================================================
        storage_box = QHBoxLayout()
        storage_box.setSpacing(10)

        self.storage_a = StorageGridWidget(
            self.engine.deck_a,
            self.bank_a,
            self.deck_a_controls.load_effect,
            accent_color=COLOR_DECK_A,
        )
        self.storage_a.preset_recalled.connect(self._on_preset_recalled_a)
        storage_box.addWidget(self.storage_a, stretch=1)

        self.storage_b = StorageGridWidget(
            self.engine.deck_b,
            self.bank_b,
            self.deck_b_controls.load_effect,
            accent_color=COLOR_DECK_B,
        )
        self.storage_b.preset_recalled.connect(self._on_preset_recalled_b)
        storage_box.addWidget(self.storage_b, stretch=1)

        main_layout.addLayout(storage_box, stretch=4)

    def _build_master_panel(self) -> QGroupBox:
        grp = QGroupBox("MASTER")
        grp.setObjectName("master_group")
        layout = QVBoxLayout(grp)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(8)

        # Master Dimmer Slider + Label
        dim_row = QHBoxLayout()
        self.slider_dimmer = QSlider(Qt.Orientation.Vertical)
        self.slider_dimmer.setRange(0, 100)
        self.slider_dimmer.setValue(100)
        self.slider_dimmer.valueChanged.connect(self._on_dimmer_changed)
        dim_row.addWidget(self.slider_dimmer, alignment=Qt.AlignmentFlag.AlignCenter)

        dim_label_box = QVBoxLayout()
        lbl_dim_title = QLabel("DIMMER")
        lbl_dim_title.setStyleSheet("font-size: 10px; color: #8b949e; font-weight: bold;")
        self.lbl_dim_val = QLabel("100%")
        self.lbl_dim_val.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {COLOR_MASTER};")
        dim_label_box.addWidget(lbl_dim_title)
        dim_label_box.addWidget(self.lbl_dim_val)
        dim_label_box.addStretch(1)

        dim_row.addLayout(dim_label_box)
        layout.addLayout(dim_row, stretch=1)

        # Master Action Buttons
        self.btn_blackout = QPushButton("BLACKOUT (B.O.)")
        self.btn_blackout.setObjectName("btn_blackout")
        self.btn_blackout.setCheckable(True)
        self.btn_blackout.toggled.connect(self._on_blackout_toggled)
        layout.addWidget(self.btn_blackout)

        self.btn_freeze = QPushButton("FREEZE")
        self.btn_freeze.setObjectName("btn_freeze")
        self.btn_freeze.setCheckable(True)
        self.btn_freeze.toggled.connect(self._on_freeze_toggled)
        layout.addWidget(self.btn_freeze)

        self.btn_whiteout = QPushButton("WHITE-OUT")
        self.btn_whiteout.setCheckable(True)
        self.btn_whiteout.setStyleSheet(
            "QPushButton:checked { background-color: #ffffff; color: #000; font-weight: bold; }"
        )
        self.btn_whiteout.toggled.connect(self._on_whiteout_toggled)
        layout.addWidget(self.btn_whiteout)

        return grp

    # ------------------------------------------------------------------
    # Status Bar
    # ------------------------------------------------------------------

    def _build_statusbar(self) -> None:
        status = QStatusBar(self)
        self.setStatusBar(status)

        self.lbl_status_engine = QLabel("Engine: Running (32×32)")
        status.addWidget(self.lbl_status_engine, 1)

        self.lbl_status_artnet = QLabel("Art-Net: Standby (Not transmitting)")
        status.addWidget(self.lbl_status_artnet, 2)

        self.lbl_status_midi = QLabel("MIDI: Idle")
        status.addWidget(self.lbl_status_midi, 1)

        self.lbl_status_cue = QLabel("Cue: Manual")
        status.addWidget(self.lbl_status_cue, 1)

        self.lbl_status_fps = QLabel("FPS: 60.0")
        self.lbl_status_fps.setStyleSheet("font-weight: bold; color: #00e676; padding-right: 12px;")
        status.addPermanentWidget(self.lbl_status_fps)

    # ------------------------------------------------------------------
    # Engine Callbacks
    # ------------------------------------------------------------------

    def _on_frame_rendered(self, mat_a, mat_b, mat_out) -> None:
        self.preview_a.set_matrix(mat_a)
        self.preview_out.set_matrix(mat_out)
        self.preview_b.set_matrix(mat_b)

        if self.engine.artnet and self.engine.artnet.is_open:
            an = self.engine.artnet
            self.lbl_status_artnet.setText(
                f"Art-Net: Active → {an.target_ip}:{an.port} | {an.active_universes} Universes | {an.packets_sent} Pkts"
            )

    def _on_fps_updated(self, fps: float) -> None:
        fps_str = f"{fps:.1f} FPS"
        self.lbl_toolbar_fps.setText(f" {fps_str} ")
        self.lbl_status_fps.setText(f"FPS: {fps:.1f}")

    # ------------------------------------------------------------------
    # Control Callbacks
    # ------------------------------------------------------------------

    def _on_dimmer_changed(self, val: int) -> None:
        dim = val / 100.0
        self.engine.master_dimmer = dim
        self.lbl_dim_val.setText(f"{val}%")
        self.midi.send_feedback(MidiMappingTarget.MASTER_DIMMER.value, dim)

    def _on_blackout_toggled(self, checked: bool) -> None:
        self.engine.blackout = checked
        self.midi.send_feedback(MidiMappingTarget.BLACKOUT.value, 1.0 if checked else 0.0)

    def _on_freeze_toggled(self, checked: bool) -> None:
        self.engine.freeze = checked
        self.midi.send_feedback(MidiMappingTarget.FREEZE.value, 1.0 if checked else 0.0)

    def _on_whiteout_toggled(self, checked: bool) -> None:
        self.engine.white_out = checked
        self.midi.send_feedback(MidiMappingTarget.WHITEOUT.value, 1.0 if checked else 0.0)

    def _toggle_dot_mode(self, enabled: bool) -> None:
        self.preview_a.set_dot_mode(enabled)
        self.preview_out.set_dot_mode(enabled)
        self.preview_b.set_dot_mode(enabled)
        self.act_dot_mode.setChecked(enabled)

    def _toggle_grid_mode(self, enabled: bool) -> None:
        self.preview_a.set_show_grid(enabled)
        self.preview_out.set_show_grid(enabled)
        self.preview_b.set_show_grid(enabled)
        self.act_grid_mode.setChecked(enabled)

    def _toggle_3d_voxels(self, enabled: bool) -> None:
        self.preview_a.toggle_3d_mode(enabled)
        self.preview_out.toggle_3d_mode(enabled)
        self.preview_b.toggle_3d_mode(enabled)
        self.act_3d_mode.setChecked(enabled)

    def _open_web_remote(self) -> None:
        QDesktopServices.openUrl(QUrl("http://localhost:8080"))

    def resize_matrix(self, width: int, height: int) -> None:
        """Resize matrix dimensions across the entire engine and previews."""
        self.engine.resize_matrix(width, height)
        self.lbl_status_engine.setText(f"Engine: Running ({width}×{height})")

    # ------------------------------------------------------------------
    # Protocol & Hardware Management
    # ------------------------------------------------------------------

    def _open_protocol_dialog(self) -> None:
        dlg = ProtocolConfigDialog(self.engine.protocols, parent=self)
        dlg.exec()

    def _launch_dvi_output(self) -> None:
        self.engine.protocols.show_dvi_window()

    def _close_dvi_output(self) -> None:
        self.engine.protocols.close_dvi_window()

    # ------------------------------------------------------------------
    # Art-Net Dialog & Toggle
    # ------------------------------------------------------------------

    def _open_artnet_dialog(self) -> None:
        dlg = ArtNetDialog(
            current_ip=self.artnet_ip,
            current_port=self.artnet_port,
            start_universe=self.artnet_universe,
            channel_order=self.artnet_order,
            matrix_width=self.engine.width,
            matrix_height=self.engine.height,
            parent=self,
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            cfg = dlg.get_settings()
            self.artnet_ip = cfg["target_ip"]
            self.artnet_port = cfg["port"]
            self.artnet_universe = cfg["start_universe"]
            self.artnet_order = cfg["channel_order"]

            # If already broadcasting, restart with new settings
            if self.engine.artnet:
                self._restart_artnet()

    def _toggle_artnet(self, enabled: bool) -> None:
        if enabled:
            self.engine.enable_artnet(
                target_ip=self.artnet_ip,
                port=self.artnet_port,
                start_universe=self.artnet_universe,
            )
            if self.engine.artnet:
                self.engine.artnet.channel_order = self.artnet_order
            self.btn_artnet.setText("📡 Art-Net Output: ON")
            self.btn_artnet.setChecked(True)
            self.act_artnet_toggle.setChecked(True)
        else:
            self.engine.disable_artnet()
            self.btn_artnet.setText("📡 Art-Net Output: OFF")
            self.btn_artnet.setChecked(False)
            self.act_artnet_toggle.setChecked(False)
            self.lbl_status_artnet.setText("Art-Net: Standby (Not transmitting)")

    def _restart_artnet(self) -> None:
        self.engine.disable_artnet()
        self.engine.enable_artnet(
            target_ip=self.artnet_ip,
            port=self.artnet_port,
            start_universe=self.artnet_universe,
        )
        if self.engine.artnet:
            self.engine.artnet.channel_order = self.artnet_order

    def _open_audio_dialog(self) -> None:
        dlg = AudioConfigDialog(self.engine.audio, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            if hasattr(self, "act_audio_gen"):
                self.act_audio_gen.setChecked(self.engine.audio.generator_mode)

    # ------------------------------------------------------------------
    # MIDI Management & Callbacks
    # ------------------------------------------------------------------

    def _open_midi_dialog(self) -> None:
        dlg = MidiConfigDialog(self.midi, parent=self)
        dlg.exec()

    def _open_midi_watcher(self) -> None:
        dlg = MidiConfigDialog(self.midi, parent=self)
        # Switch directly to Tab 1 (Watcher)
        tabs = dlg.findChild(QTabWidget)
        if tabs:
            tabs.setCurrentIndex(1)
        dlg.exec()

    def _apply_midi_template(self, template_name: str) -> None:
        self.midi.load_preset_profile(template_name)
        QMessageBox.information(self, "MIDI Template", f"Applied template: {template_name}")

    def _on_midi_status_changed(self, status: str) -> None:
        self.lbl_status_midi.setText(f"MIDI: {status}")

    def _on_midi_binding_triggered(self, target: str, val: float) -> None:
        """Handle incoming dispatched MIDI action to update GUI and engine state."""
        if target == MidiMappingTarget.CROSSFADER.value:
            self.crossfader_widget.set_position(val)
        elif target == MidiMappingTarget.MASTER_DIMMER.value:
            self.slider_dimmer.setValue(int(round(val * 100)))
        elif target == MidiMappingTarget.BLACKOUT.value:
            self.btn_blackout.setChecked(val > 0.5)
        elif target == MidiMappingTarget.FREEZE.value:
            self.btn_freeze.setChecked(val > 0.5)
        elif target == MidiMappingTarget.WHITEOUT.value:
            self.btn_whiteout.setChecked(val > 0.5)
        elif target == MidiMappingTarget.DECK_A_SPEED.value:
            spd = max(0.1, min(5.0, val * 5.0))
            self.deck_a_controls.set_speed(spd)
        elif target == MidiMappingTarget.DECK_B_SPEED.value:
            spd = max(0.1, min(5.0, val * 5.0))
            self.deck_b_controls.set_speed(spd)
        elif target.startswith("deck_a_param_"):
            idx = int(target.split("_")[-1])
            self.deck_a_controls.set_param_by_index(idx, val)
        elif target.startswith("deck_b_param_"):
            idx = int(target.split("_")[-1])
            self.deck_b_controls.set_param_by_index(idx, val)
        elif target.startswith("storage_a_slot_"):
            slot = int(target.split("_")[-1]) - 1
            if val > 0.5:
                self._on_preset_recalled_a(slot)
        elif target.startswith("storage_b_slot_"):
            slot = int(target.split("_")[-1]) - 1
            if val > 0.5:
                self._on_preset_recalled_b(slot)

    # ------------------------------------------------------------------
    # Storage & Presets Callbacks
    # ------------------------------------------------------------------

    def _on_preset_recalled_a(self, slot: int) -> None:
        place = self.bank_a.get_place(slot)
        if place and not place.is_empty:
            self.deck_a_controls.load_preset_state(place.effect_name, place.params, place.speed)

    def _on_preset_recalled_b(self, slot: int) -> None:
        place = self.bank_b.get_place(slot)
        if place and not place.is_empty:
            self.deck_b_controls.load_preset_state(place.effect_name, place.params, place.speed)

    def _new_project(self) -> None:
        reply = QMessageBox.question(
            self,
            "New Show Project",
            "Start a new show project? All unsaved storage places will be cleared.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.bank_a = StorageBank(64)
            self.bank_b = StorageBank(64)
            self.storage_a.bank = self.bank_a
            self.storage_b.bank = self.bank_b
            self.storage_a.refresh_grid()
            self.storage_b.refresh_grid()
            self.deck_a_controls.load_effect(None)
            self.deck_b_controls.load_effect(None)

    def load_project_file(self, filepath: str) -> bool:
        """Load and apply a project file programmatically."""
        data = ProjectFile.load(filepath)
        if not data or data.get("format") != "PixelForgeProject":
            return False

        # Restore matrix size
        mat_cfg = data.get("matrix", {})
        if "width" in mat_cfg and "height" in mat_cfg:
            self.resize_matrix(mat_cfg["width"], mat_cfg["height"])

        # Restore storage banks
        if "storage_a" in data:
            self.bank_a.from_list(data["storage_a"])
            self.storage_a.refresh_grid()
        if "storage_b" in data:
            self.bank_b.from_list(data["storage_b"])
            self.storage_b.refresh_grid()

        # Restore decks
        if "deck_a" in data:
            da = data["deck_a"]
            if da.get("effect_name"):
                self.deck_a_controls.load_preset_state(
                    da.get("effect_name", ""), da.get("params", {}), da.get("speed", 1.0)
                )
        if "deck_b" in data:
            db = data["deck_b"]
            if db.get("effect_name"):
                self.deck_b_controls.load_preset_state(
                    db.get("effect_name", ""), db.get("params", {}), db.get("speed", 1.0)
                )

        # Restore patch
        if "patch" in data and data["patch"]:
            self.engine.patch.from_dict(data["patch"])

        # Restore crossfader
        if "crossfader" in data:
            cf = data["crossfader"]
            self.crossfader_widget.set_position(cf.get("position", 0.0))

        # Restore cue list
        if "cue_list" in data and data["cue_list"]:
            self.cue_player.cue_list = CueList.from_list(data["cue_list"])

        # Restore timeline
        if "timeline" in data and data["timeline"]:
            self.timeline_player.timeline = Timeline.from_dict(data["timeline"])

        return True

    def _open_project(self) -> None:
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Open PixelForge Show Project", "", "PixelForge Projects (*.pxf);;All Files (*.*)"
        )
        if not filepath:
            return
        success = self.load_project_file(filepath)
        if not success:
            QMessageBox.warning(self, "Invalid File", "Could not load file. Not a valid PixelForge project.")
            return

        QMessageBox.information(self, "Project Loaded", f"Show project loaded:\n{os.path.basename(filepath)}")

    def _init_factory_cues(self) -> None:
        """Populate initial showcase cues demonstrating automatic crossfades and hold times."""
        cues = [
            Cue(cue_id=1, name="Intro Pulse", deck_a_bank=0, deck_a_slot=0, deck_b_bank=0, deck_b_slot=0, crossfader_pos=0.0, fade_duration=1.5, hold_duration=4.0, auto_follow=True),
            Cue(cue_id=2, name="Psychedelic Magenta", deck_a_bank=0, deck_a_slot=1, deck_b_bank=0, deck_b_slot=1, crossfader_pos=1.0, fade_duration=2.5, hold_duration=4.0, auto_follow=True),
            Cue(cue_id=3, name="Hellfire & Matrix", deck_a_bank=0, deck_a_slot=2, deck_b_bank=0, deck_b_slot=2, crossfader_pos=0.5, fade_duration=2.0, hold_duration=5.0, auto_follow=True),
            Cue(cue_id=4, name="Sound2Light Finale", deck_a_bank=0, deck_a_slot=3, deck_b_bank=0, deck_b_slot=3, crossfader_pos=0.0, fade_duration=1.0, hold_duration=3.0, auto_follow=True),
        ]
        for c in cues:
            self.cue_player.cue_list.add_cue(c)

    def _open_cue_dialog(self) -> None:
        dlg = CueDialog(self.cue_player, self.timeline_player, parent=self)
        dlg.exec()

    def _open_timeline_tab(self) -> None:
        dlg = CueDialog(self.cue_player, self.timeline_player, parent=self)
        dlg.tabs.setCurrentIndex(1)
        dlg.exec()

    def _on_cue_changed_status(self, index: int, cue: Cue) -> None:
        self.lbl_status_cue.setText(f"Cue: #{cue.cue_id} ({cue.name})")

    def _on_cue_preset_recall(self, deck_letter: str, bank_idx: int, slot_idx: int) -> None:
        flat_slot = bank_idx * 16 + slot_idx
        if deck_letter == "A":
            self._on_preset_recalled_a(flat_slot)
        else:
            self._on_preset_recalled_b(flat_slot)

    def _on_timeline_clip_triggered(self, track_type: str, clip: TimelineClip) -> None:
        b_idx = int(clip.properties.get("bank", 0))
        s_idx = int(clip.properties.get("slot", 0))
        flat_slot = b_idx * 16 + s_idx
        if track_type == TimelineTrackType.DECK_A.value:
            self._on_preset_recalled_a(flat_slot)
        elif track_type == TimelineTrackType.DECK_B.value:
            self._on_preset_recalled_b(flat_slot)

    def _open_patch_editor(self) -> None:
        dlg = PatchEditorDialog(self.engine.patch, parent=self)
        dlg.exec()

    def _open_matrix_generator(self) -> None:
        from pixelforge.ui.patch_editor import MatrixGeneratorDialog
        dlg = MatrixGeneratorDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            v = dlg.get_values()
            self.engine.patch.generate_matrix(
                cols=v["cols"],
                rows=v["rows"],
                tile_w=v["tile_w"],
                tile_h=v["tile_h"],
                start_universe=v["start_universe"],
                start_channel=v["start_channel"],
                channel_order=v["channel_order"],
                routing=v["routing"],
            )
            self.resize_matrix(self.engine.patch.matrix_width, self.engine.patch.matrix_height)
            QMessageBox.information(
                self, "Matrix Generated",
                f"Generated {v['cols']}×{v['rows']} panel matrix ({self.engine.width}×{self.engine.height} pixels)."
            )

    def _quick_patch_rope_light(self) -> None:
        """Quickly add the 5M LED Rope fixture and configure engine dimensions."""
        if self.engine.width < 80:
            self.resize_matrix(80, max(16, self.engine.height))

        f = self.engine.patch.add_rope_light_fixture(
            name="5m LED Rope Light",
            x=0,
            y=0,
            start_universe=0,
            start_channel=1,
        )
        QMessageBox.information(
            self,
            "5M LED Rope Light Patched",
            f"Successfully patched '{f.name}'!\n\n"
            f"• Pixels: 80 (5 meters)\n"
            f"• DMX Channels: 240 (Channels 1–240)\n"
            f"• Channel Order: GRB (Green, Red, Blue)\n"
            f"• Art-Net Universe: 0 (Unreal Engine Universe 1)\n\n"
            f"Output is streaming live via Art-Net to 127.0.0.1:6454.",
        )

    def _save_project(self) -> None:
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save PixelForge Show Project", "my_show.pxf", "PixelForge Projects (*.pxf);;All Files (*.*)"
        )
        if not filepath:
            return
        data = ProjectFile.create_project_data(
            self.engine,
            self.bank_a,
            self.bank_b,
            cue_list=self.cue_player.cue_list,
            timeline=self.timeline_player.timeline,
        )
        success = ProjectFile.save(filepath, data)
        if success:
            QMessageBox.information(self, "Project Saved", f"Show project saved successfully to:\n{os.path.basename(filepath)}")
        else:
            QMessageBox.critical(self, "Save Error", "Failed to save project file.")

    def _load_factory_presets(self) -> None:
        populate_factory_presets(self.bank_a, self.bank_b)
        self.storage_a.refresh_grid()
        self.storage_b.refresh_grid()
        QMessageBox.information(self, "Showcase Presets", "Factory showcase presets loaded into Bank 1 for Deck A & Deck B.")

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About PixelForge",
            "<h3>PixelForge 1.0</h3>"
            "<p>A professional, real-time LED lighting control, 2D pixel mapping, and voxel mapping solution inspired by MADRIX 5.</p>"
            "<p><b>Features:</b></p>"
            "<ul>"
            "<li>Dual-deck VJ architecture with 11 blend modes</li>"
            "<li>60 FPS real-time procedural effects engine</li>"
            "<li>Art-Net IV multi-universe broadcast to physical LED fixtures</li>"
            "<li>Dynamic parameter tweaking and stage visualizer</li>"
            "</ul>",
        )

    def closeEvent(self, event) -> None:
        """Clean shutdown when application closes."""
        self.engine.stop()
        self.engine.disable_artnet()
        self.midi.close_input_port()
        self.midi.close_output_port()
        self.cue_player.stop()
        self.timeline_player.stop()
        self.http_server.stop()
        super().closeEvent(event)
