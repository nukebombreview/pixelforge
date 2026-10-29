"""
PixelForge — Cue List & Timeline Show Automation Dialog
MADRIX 5-style sequential cue list with GO/BACK/PAUSE/STOP transport,
real-time progress bars, and NLE-style multi-track timeline sequencing.
"""

from __future__ import annotations

import datetime
from typing import Optional

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QMessageBox,
    QProgressBar,
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

from pixelforge.core.cue import Cue, CueList, CuePhase, CuePlayer, CuePlayerState
from pixelforge.core.timeline import (
    ArtNetTimecode,
    Timecode,
    Timeline,
    TimelineClip,
    TimelinePlayer,
    TimelineTrackType,
)
from pixelforge.ui.styles import (
    COLOR_BG_DARK,
    COLOR_BG_DARKEST,
    COLOR_BG_PANEL,
    COLOR_BG_SURFACE,
    COLOR_BORDER,
    COLOR_DECK_A,
    COLOR_DECK_B,
    COLOR_MASTER,
    COLOR_SUCCESS,
)


class TimelineCanvasWidget(QWidget):
    """Interactive visual multi-track timeline canvas with playhead and clips."""

    seek_requested = pyqtSignal(float)
    clip_selected = pyqtSignal(object)

    TRACK_HEIGHT = 52
    RULER_HEIGHT = 28
    HEADER_WIDTH = 130

    def __init__(self, timeline: Timeline, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.timeline = timeline
        self.playhead_time: float = 0.0
        self.pixels_per_second: float = 40.0  # Zoom level
        self.selected_clip: Optional[TimelineClip] = None
        self._dragging_playhead: bool = False

        self.setMinimumHeight(self.RULER_HEIGHT + 4 * self.TRACK_HEIGHT + 20)
        self.setMouseTracking(True)

    def set_playhead_time(self, t: float) -> None:
        self.playhead_time = t
        self.update()

    def set_zoom(self, px_per_sec: float) -> None:
        self.pixels_per_second = max(10.0, min(200.0, px_per_sec))
        self.update()

    def time_to_x(self, t: float) -> float:
        return self.HEADER_WIDTH + t * self.pixels_per_second

    def x_to_time(self, x: float) -> float:
        return max(0.0, min(self.timeline.duration, (x - self.HEADER_WIDTH) / self.pixels_per_second))

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # 1. Background
        p.fillRect(0, 0, w, h, QColor(COLOR_BG_DARKEST))

        # 2. Time Ruler (Top)
        p.fillRect(0, 0, w, self.RULER_HEIGHT, QColor(COLOR_BG_PANEL))
        p.setPen(QColor(COLOR_BORDER))
        p.drawLine(0, self.RULER_HEIGHT, w, self.RULER_HEIGHT)

        # Draw Ruler ticks
        sec_step = 5 if self.pixels_per_second < 30 else (2 if self.pixels_per_second < 80 else 1)
        total_secs = int(self.timeline.duration)

        p.setFont(QFont("Segoe UI", 8))
        for s in range(0, total_secs + 1, sec_step):
            x = self.time_to_x(float(s))
            if x > w:
                break
            p.setPen(QColor("#555f73"))
            p.drawLine(int(x), self.RULER_HEIGHT - 8, int(x), self.RULER_HEIGHT)
            m = s // 60
            sec_rem = s % 60
            p.drawText(int(x) + 3, self.RULER_HEIGHT - 10, f"{m:02d}:{sec_rem:02d}")

        # 3. Track lanes
        y = self.RULER_HEIGHT
        for i, track in enumerate(self.timeline.tracks):
            # Track header
            p.fillRect(0, y, self.HEADER_WIDTH, self.TRACK_HEIGHT, QColor(COLOR_BG_PANEL))
            p.setPen(QColor(COLOR_BORDER))
            p.drawRect(0, y, self.HEADER_WIDTH, self.TRACK_HEIGHT)

            # Header text
            p.setPen(QColor("#e6edf3"))
            p.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            p.drawText(8, y + 20, track.name)

            type_color = (
                COLOR_DECK_A if track.track_type == TimelineTrackType.DECK_A.value
                else (COLOR_DECK_B if track.track_type == TimelineTrackType.DECK_B.value
                else (COLOR_MASTER if track.track_type == TimelineTrackType.CROSSFADER.value
                else "#ffffff"))
            )
            p.setPen(QColor(type_color))
            p.setFont(QFont("Segoe UI", 8))
            p.drawText(8, y + 38, track.track_type.upper().replace("_", " "))

            # Track lane background
            lane_rect = QRectF(self.HEADER_WIDTH, y, w - self.HEADER_WIDTH, self.TRACK_HEIGHT)
            p.fillRect(lane_rect, QColor("#14171e" if i % 2 == 0 else "#161b24"))
            p.setPen(QColor(COLOR_BORDER))
            p.drawLine(self.HEADER_WIDTH, y + self.TRACK_HEIGHT, w, y + self.TRACK_HEIGHT)

            # Draw Clips
            for clip in track.clips:
                cx = self.time_to_x(clip.start_time)
                cw = clip.duration * self.pixels_per_second
                clip_rect = QRectF(cx, y + 4, max(4.0, cw), self.TRACK_HEIGHT - 8)

                # Clip body
                c_color = QColor(type_color)
                c_color.setAlpha(190)
                if clip == self.selected_clip:
                    p.setPen(QPen(QColor("#ffffff"), 2))
                else:
                    p.setPen(QPen(c_color.lighter(130), 1))

                p.setBrush(QBrush(c_color))
                p.drawRoundedRect(clip_rect, 4, 4)

                # Clip label
                p.setPen(QColor("#ffffff"))
                p.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
                clip_title = clip.name
                if cw > 40:
                    p.drawText(clip_rect.adjusted(6, 4, -4, -4), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, clip_title)

                # For crossfader/dimmer curve, draw mini slope inside clip
                if track.track_type in (TimelineTrackType.CROSSFADER.value, TimelineTrackType.MASTER_DIMMER.value):
                    s_val = float(clip.properties.get("start_val", 0.0))
                    e_val = float(clip.properties.get("end_val", 1.0))
                    p.setPen(QPen(QColor(255, 255, 255, 160), 2))
                    y1 = y + 4 + (self.TRACK_HEIGHT - 8) * (1.0 - s_val)
                    y2 = y + 4 + (self.TRACK_HEIGHT - 8) * (1.0 - e_val)
                    p.drawLine(int(cx + 2), int(y1), int(cx + cw - 2), int(y2))

            y += self.TRACK_HEIGHT

        # 4. Vertical Playhead Line & Handle
        px = self.time_to_x(self.playhead_time)
        if self.HEADER_WIDTH <= px <= w:
            p.setPen(QPen(QColor("#ff2d75"), 2))
            p.drawLine(int(px), 0, int(px), h)

            # Playhead triangle handle in ruler
            poly = QPolygonF([
                QPointF(px - 6, 0),
                QPointF(px + 6, 0),
                QPointF(px + 6, self.RULER_HEIGHT - 6),
                QPointF(px, self.RULER_HEIGHT),
                QPointF(px - 6, self.RULER_HEIGHT - 6),
            ])
            p.setBrush(QBrush(QColor("#ff2d75")))
            p.drawPolygon(poly)

    def mousePressEvent(self, event) -> None:
        x = event.position().x()
        y = event.position().y()

        if event.button() == Qt.MouseButton.LeftButton:
            if y <= self.RULER_HEIGHT or x >= self.HEADER_WIDTH:
                # Seek playhead
                self._dragging_playhead = True
                t = self.x_to_time(x)
                self.seek_requested.emit(t)

            # Check if clicked inside a clip
            track_idx = int((y - self.RULER_HEIGHT) // self.TRACK_HEIGHT)
            if 0 <= track_idx < len(self.timeline.tracks):
                track = self.timeline.tracks[track_idx]
                click_t = self.x_to_time(x)
                found = track.get_clip_at(click_t)
                self.selected_clip = found
                self.clip_selected.emit(found)
                self.update()

    def mouseMoveEvent(self, event) -> None:
        if self._dragging_playhead:
            x = event.position().x()
            t = self.x_to_time(x)
            self.seek_requested.emit(t)

    def mouseReleaseEvent(self, event) -> None:
        self._dragging_playhead = False


class CueDialog(QDialog):
    """Main Show Automation Dialog containing Sequential Cue List and Multi-Track Timeline."""

    def __init__(
        self,
        cue_player: CuePlayer,
        timeline_player: TimelinePlayer,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.cue_player = cue_player
        self.timeline_player = timeline_player

        self.setWindowTitle("PixelForge — Show Automation (Cue List & Timeline)")
        self.resize(1150, 720)
        self.setMinimumSize(950, 580)

        self._build_ui()
        self._refresh_cue_table()

        # Connect cue player signals
        self.cue_player.cue_changed.connect(self._on_cue_changed)
        self.cue_player.fade_progress.connect(self._on_fade_progress)
        self.cue_player.hold_progress.connect(self._on_hold_progress)
        self.cue_player.state_changed.connect(self._on_player_state_changed)

        # Connect timeline signals
        self.timeline_player.time_updated.connect(self._on_timeline_time_updated)
        self.timeline_player.play_state_changed.connect(self._on_timeline_play_state)

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_cuelist_tab(), "📋 Sequential Cue List")
        self.tabs.addTab(self._build_timeline_tab(), "⏱ Multi-Track Timeline & Timecode")
        main_layout.addWidget(self.tabs)

    # ==================================================================
    # Tab 1: Cue List
    # ==================================================================

    def _build_cuelist_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 1. Transport Bar
        trans_bar = QHBoxLayout()
        trans_bar.setSpacing(8)

        self.btn_go = QPushButton("▶ GO")
        self.btn_go.setFixedHeight(38)
        self.btn_go.setMinimumWidth(100)
        self.btn_go.setStyleSheet(
            "QPushButton { background-color: #238636; color: #ffffff; font-size: 14px; font-weight: bold; border-radius: 6px; } "
            "QPushButton:hover { background-color: #2ea043; }"
        )
        self.btn_go.clicked.connect(lambda: self.cue_player.go())

        self.btn_back = QPushButton("⏮ BACK")
        self.btn_back.setFixedHeight(38)
        self.btn_back.clicked.connect(self.cue_player.back)

        self.btn_pause = QPushButton("⏸ PAUSE")
        self.btn_pause.setFixedHeight(38)
        self.btn_pause.clicked.connect(self.cue_player.pause)

        self.btn_stop = QPushButton("⏹ STOP")
        self.btn_stop.setFixedHeight(38)
        self.btn_stop.clicked.connect(self.cue_player.stop)

        self.btn_loop = QPushButton("🔁 LOOP: ON")
        self.btn_loop.setCheckable(True)
        self.btn_loop.setChecked(True)
        self.btn_loop.setFixedHeight(38)
        self.btn_loop.toggled.connect(self._toggle_loop)

        trans_bar.addWidget(self.btn_go)
        trans_bar.addWidget(self.btn_back)
        trans_bar.addWidget(self.btn_pause)
        trans_bar.addWidget(self.btn_stop)
        trans_bar.addWidget(self.btn_loop)
        trans_bar.addSpacing(16)

        # Status Label
        self.lbl_cue_status = QLabel("State: STOPPED")
        self.lbl_cue_status.setStyleSheet("font-size: 13px; font-weight: bold; color: #8b949e;")
        trans_bar.addWidget(self.lbl_cue_status)
        trans_bar.addStretch()

        layout.addLayout(trans_bar)

        # 2. Live Progress Section
        prog_frame = QFrame()
        prog_frame.setStyleSheet(
            f"background-color: {COLOR_BG_PANEL}; border: 1px solid {COLOR_BORDER}; border-radius: 6px; padding: 6px;"
        )
        prog_layout = QGridLayout(prog_frame)
        prog_layout.setContentsMargins(8, 8, 8, 8)
        prog_layout.setSpacing(6)

        self.lbl_active_cue_info = QLabel("ACTIVE CUE: None (Press GO to start)")
        self.lbl_active_cue_info.setStyleSheet("font-size: 12px; font-weight: bold; color: #58a6ff;")

        self.lbl_next_cue_info = QLabel("NEXT CUE: —")
        self.lbl_next_cue_info.setStyleSheet("font-size: 11px; color: #8b949e;")

        lbl_fade = QLabel("Crossfade Progress:")
        lbl_fade.setStyleSheet("font-size: 10px; font-weight: bold; color: #8b949e;")
        self.bar_fade = QProgressBar()
        self.bar_fade.setRange(0, 100)
        self.bar_fade.setValue(0)
        self.bar_fade.setTextVisible(True)
        self.bar_fade.setFormat("%p% (0.0s / 0.0s)")

        lbl_hold = QLabel("Hold Countdown:")
        lbl_hold.setStyleSheet("font-size: 10px; font-weight: bold; color: #8b949e;")
        self.bar_hold = QProgressBar()
        self.bar_hold.setRange(0, 100)
        self.bar_hold.setValue(0)
        self.bar_hold.setTextVisible(True)
        self.bar_hold.setFormat("%p% (0.0s remaining)")

        prog_layout.addWidget(self.lbl_active_cue_info, 0, 0)
        prog_layout.addWidget(self.lbl_next_cue_info, 0, 1)
        prog_layout.addWidget(lbl_fade, 1, 0)
        prog_layout.addWidget(self.bar_fade, 2, 0)
        prog_layout.addWidget(lbl_hold, 1, 1)
        prog_layout.addWidget(self.bar_hold, 2, 1)

        layout.addWidget(prog_frame)

        # 3. Cue Table
        self.tbl_cues = QTableWidget()
        self.tbl_cues.setColumnCount(9)
        self.tbl_cues.setHorizontalHeaderLabels([
            "#", "Cue Name", "Deck A Preset", "Deck B Preset", "X-Fade", "Fade (s)", "Hold (s)", "Follow", "Master"
        ])
        th = self.tbl_cues.horizontalHeader()
        th.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        th.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        th.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        th.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        th.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        th.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        th.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        th.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        th.setSectionResizeMode(8, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_cues.verticalHeader().setVisible(False)
        self.tbl_cues.setAlternatingRowColors(True)
        self.tbl_cues.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tbl_cues.customContextMenuRequested.connect(self._on_cue_table_menu)
        self.tbl_cues.cellDoubleClicked.connect(lambda row, col: self.cue_player.go(row))
        layout.addWidget(self.tbl_cues, stretch=1)

        # 4. Bottom Action Bar
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(8)

        btn_add = QPushButton("➕ Add Blank Cue")
        btn_add.clicked.connect(self._add_blank_cue)

        btn_dup = QPushButton("📑 Duplicate Selected")
        btn_dup.clicked.connect(self._duplicate_selected_cue)

        btn_del = QPushButton("❌ Delete Selected")
        btn_del.clicked.connect(self._delete_selected_cue)

        btn_clear = QPushButton("🗑 Clear All")
        btn_clear.clicked.connect(self._clear_all_cues)

        bottom_bar.addWidget(btn_add)
        bottom_bar.addWidget(btn_dup)
        bottom_bar.addWidget(btn_del)
        bottom_bar.addWidget(btn_clear)
        bottom_bar.addStretch()

        btn_export = QPushButton("Export Cues...")
        btn_export.clicked.connect(self._export_cues)
        btn_import = QPushButton("Import Cues...")
        btn_import.clicked.connect(self._import_cues)
        bottom_bar.addWidget(btn_export)
        bottom_bar.addWidget(btn_import)

        layout.addLayout(bottom_bar)
        return w

    # ==================================================================
    # Tab 2: Timeline
    # ==================================================================

    def _build_timeline_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Top Timeline Bar
        tl_bar = QHBoxLayout()
        tl_bar.setSpacing(8)

        # SMPTE Digital Display
        self.lbl_smpte = QLabel("00:00:00:00")
        self.lbl_smpte.setStyleSheet(
            "font-family: 'Consolas', 'Courier New', monospace; font-size: 22px; font-weight: bold; "
            "color: #00e676; background-color: #0c0e12; border: 1px solid #1c3b24; border-radius: 4px; padding: 2px 10px;"
        )
        tl_bar.addWidget(self.lbl_smpte)

        self.btn_tl_play = QPushButton("▶ Play")
        self.btn_tl_play.setFixedWidth(70)
        self.btn_tl_play.clicked.connect(self._toggle_timeline_play)

        self.btn_tl_rewind = QPushButton("⏮ 0:00")
        self.btn_tl_rewind.setFixedWidth(65)
        self.btn_tl_rewind.clicked.connect(self.timeline_player.stop)

        tl_bar.addWidget(self.btn_tl_play)
        tl_bar.addWidget(self.btn_tl_rewind)
        tl_bar.addSpacing(12)

        lbl_src = QLabel("Timecode Sync:")
        lbl_src.setStyleSheet("color: #8b949e; font-weight: bold;")
        self.combo_tc_src = QComboBox()
        self.combo_tc_src.addItems(["Internal Clock (30 fps)", "Art-Net Timecode (OpTimeCode)", "MIDI Timecode (MTC)"])
        tl_bar.addWidget(lbl_src)
        tl_bar.addWidget(self.combo_tc_src)

        tl_bar.addStretch()

        # Zoom Slider
        lbl_zoom = QLabel("🔍 Zoom:")
        self.sld_zoom = QSlider(Qt.Orientation.Horizontal)
        self.sld_zoom.setRange(15, 120)
        self.sld_zoom.setValue(40)
        self.sld_zoom.setFixedWidth(120)
        self.sld_zoom.valueChanged.connect(lambda v: self.canvas.set_zoom(float(v)))

        tl_bar.addWidget(lbl_zoom)
        tl_bar.addWidget(self.sld_zoom)

        layout.addLayout(tl_bar)

        # Timeline Canvas
        self.canvas = TimelineCanvasWidget(self.timeline_player.timeline, self)
        self.canvas.seek_requested.connect(self.timeline_player.seek)
        self.canvas.clip_selected.connect(self._on_clip_selected)
        layout.addWidget(self.canvas, stretch=1)

        # Clip Inspector / Tools Bar
        clip_bar = QHBoxLayout()
        clip_bar.setSpacing(8)

        self.lbl_clip_info = QLabel("No clip selected. Click any clip on canvas to inspect or edit.")
        self.lbl_clip_info.setStyleSheet("color: #8b949e; font-style: italic;")
        clip_bar.addWidget(self.lbl_clip_info)
        clip_bar.addStretch()

        btn_add_clip = QPushButton("➕ Add Clip at Playhead")
        btn_add_clip.clicked.connect(self._add_clip_at_playhead)
        btn_del_clip = QPushButton("❌ Delete Selected Clip")
        btn_del_clip.clicked.connect(self._delete_selected_clip)

        clip_bar.addWidget(btn_add_clip)
        clip_bar.addWidget(btn_del_clip)
        layout.addLayout(clip_bar)

        return w

    # ==================================================================
    # Cue Table Management
    # ==================================================================

    def _refresh_cue_table(self) -> None:
        self.tbl_cues.setRowCount(len(self.cue_player.cue_list))

        for row, cue in enumerate(self.cue_player.cue_list.cues):
            # 0: Index
            item_id = QTableWidgetItem(f"{cue.cue_id}")
            item_id.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_id.setFlags(item_id.flags() & ~Qt.ItemFlag.ItemIsEditable)

            # Highlight currently playing row
            if row == self.cue_player.current_index:
                item_id.setBackground(QColor("#238636"))
                item_id.setForeground(QColor("#ffffff"))

            self.tbl_cues.setItem(row, 0, item_id)

            # 1: Name
            item_name = QTableWidgetItem(cue.name)
            self.tbl_cues.setItem(row, 1, item_name)

            # 2: Deck A (Bank/Slot)
            item_da = QTableWidgetItem(f"B{cue.deck_a_bank+1} : S{cue.deck_a_slot+1}")
            item_da.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_da.setForeground(QColor(COLOR_DECK_A))
            self.tbl_cues.setItem(row, 2, item_da)

            # 3: Deck B (Bank/Slot)
            item_db = QTableWidgetItem(f"B{cue.deck_b_bank+1} : S{cue.deck_b_slot+1}")
            item_db.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_db.setForeground(QColor(COLOR_DECK_B))
            self.tbl_cues.setItem(row, 3, item_db)

            # 4: X-Fade Position
            pct_b = int(round(cue.crossfader_pos * 100))
            item_xf = QTableWidgetItem(f"{pct_b}% B" if pct_b > 50 else f"{100-pct_b}% A")
            item_xf.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tbl_cues.setItem(row, 4, item_xf)

            # 5: Fade duration
            item_fade = QTableWidgetItem(f"{cue.fade_duration:.1f}s")
            item_fade.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tbl_cues.setItem(row, 5, item_fade)

            # 6: Hold duration
            item_hold = QTableWidgetItem(f"{cue.hold_duration:.1f}s")
            item_hold.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tbl_cues.setItem(row, 6, item_hold)

            # 7: Auto Follow
            item_fol = QTableWidgetItem("YES" if cue.auto_follow else "NO")
            item_fol.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if cue.auto_follow:
                item_fol.setForeground(QColor(COLOR_SUCCESS))
            self.tbl_cues.setItem(row, 7, item_fol)

            # 8: Master Dimmer
            item_dim = QTableWidgetItem(f"{int(cue.master_dimmer * 100)}%")
            item_dim.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tbl_cues.setItem(row, 8, item_dim)

    def _toggle_loop(self, checked: bool) -> None:
        self.cue_player.loop = checked
        self.btn_loop.setText("🔁 LOOP: ON" if checked else "🔁 LOOP: OFF")

    def _add_blank_cue(self) -> None:
        idx = len(self.cue_player.cue_list) + 1
        c = Cue(cue_id=idx, name=f"Cue {idx}", fade_duration=2.0, hold_duration=5.0, auto_follow=True)
        self.cue_player.cue_list.add_cue(c)
        self._refresh_cue_table()

    def _duplicate_selected_cue(self) -> None:
        row = self.tbl_cues.currentRow()
        if row >= 0:
            self.cue_player.cue_list.duplicate_cue(row)
            self._refresh_cue_table()

    def _delete_selected_cue(self) -> None:
        row = self.tbl_cues.currentRow()
        if row >= 0:
            self.cue_player.cue_list.remove_cue(row)
            self._refresh_cue_table()

    def _clear_all_cues(self) -> None:
        if len(self.cue_player.cue_list) == 0:
            return
        reply = QMessageBox.question(
            self, "Clear Cue List", "Delete all cues in this list?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.cue_player.stop()
            self.cue_player.cue_list.clear()
            self._refresh_cue_table()

    def _on_cue_table_menu(self, pos) -> None:
        row = self.tbl_cues.rowAt(pos.y())
        if row < 0:
            return
        menu = QMenu(self)
        act_go = menu.addAction(f"▶ Execute Cue {row+1}")
        menu.addSeparator()
        act_up = menu.addAction("Move Up")
        act_down = menu.addAction("Move Down")
        menu.addSeparator()
        act_dup = menu.addAction("Duplicate")
        act_del = menu.addAction("Delete")

        chosen = menu.exec(self.tbl_cues.viewport().mapToGlobal(pos))
        if chosen == act_go:
            self.cue_player.go(row)
        elif chosen == act_up and row > 0:
            self.cue_player.cue_list.move_cue(row, row - 1)
            self._refresh_cue_table()
        elif chosen == act_down and row < len(self.cue_player.cue_list) - 1:
            self.cue_player.cue_list.move_cue(row, row + 1)
            self._refresh_cue_table()
        elif chosen == act_dup:
            self.cue_player.cue_list.duplicate_cue(row)
            self._refresh_cue_table()
        elif chosen == act_del:
            self.cue_player.cue_list.remove_cue(row)
            self._refresh_cue_table()

    def _export_cues(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Cue List", "cues.json", "JSON Files (*.json);;All Files (*.*)"
        )
        if not path:
            return
        import json
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.cue_player.cue_list.to_list(), f, indent=2)
            QMessageBox.information(self, "Exported", f"Exported {len(self.cue_player.cue_list)} cues.")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to save: {e}")

    def _import_cues(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Cue List", "", "JSON Files (*.json);;All Files (*.*)"
        )
        if not path:
            return
        import json
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.cue_player.cue_list = CueList.from_list(data)
            self._refresh_cue_table()
            QMessageBox.information(self, "Imported", f"Loaded {len(self.cue_player.cue_list)} cues.")
        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to load: {e}")

    # ==================================================================
    # Cue Player Callbacks
    # ==================================================================

    def _on_cue_changed(self, index: int, cue: Cue) -> None:
        self.lbl_active_cue_info.setText(
            f"ACTIVE CUE #{cue.cue_id}: {cue.name}  [A: B{cue.deck_a_bank+1}:S{cue.deck_a_slot+1} | B: B{cue.deck_b_bank+1}:S{cue.deck_b_slot+1}]"
        )
        next_idx = (index + 1) % len(self.cue_player.cue_list) if len(self.cue_player.cue_list) > 0 else -1
        next_cue = self.cue_player.cue_list.get_cue(next_idx)
        if next_cue:
            self.lbl_next_cue_info.setText(
                f"NEXT CUE #{next_cue.cue_id}: {next_cue.name} (Fade: {next_cue.fade_duration:.1f}s, Hold: {next_cue.hold_duration:.1f}s)"
            )
        else:
            self.lbl_next_cue_info.setText("NEXT CUE: End of list")

        self._refresh_cue_table()

    def _on_fade_progress(self, progress: float, elapsed: float, total: float) -> None:
        pct = int(progress * 100)
        self.bar_fade.setValue(pct)
        self.bar_fade.setFormat(f"Fading: {pct}% ({elapsed:.1f}s / {total:.1f}s)")
        if progress >= 1.0:
            self.bar_fade.setFormat("Fade Complete (100%)")

    def _on_hold_progress(self, progress: float, remaining: float, total: float) -> None:
        pct = int(progress * 100)
        self.bar_hold.setValue(pct)
        self.bar_hold.setFormat(f"Holding: {remaining:.1f}s remaining (of {total:.1f}s)")

    def _on_player_state_changed(self, state_str: str) -> None:
        self.lbl_cue_status.setText(f"State: {state_str}")
        if state_str == CuePlayerState.PLAYING.value:
            self.lbl_cue_status.setStyleSheet("font-size: 13px; font-weight: bold; color: #3fb950;")
        elif state_str == CuePlayerState.PAUSED.value:
            self.lbl_cue_status.setStyleSheet("font-size: 13px; font-weight: bold; color: #d29922;")
        else:
            self.lbl_cue_status.setStyleSheet("font-size: 13px; font-weight: bold; color: #8b949e;")

    # ==================================================================
    # Timeline Callbacks & Actions
    # ==================================================================

    def _toggle_timeline_play(self) -> None:
        if self.timeline_player.is_playing:
            self.timeline_player.pause()
        else:
            self.timeline_player.play()

    def _on_timeline_time_updated(self, sec: float, smpte_str: str) -> None:
        self.lbl_smpte.setText(smpte_str)
        self.canvas.set_playhead_time(sec)

    def _on_timeline_play_state(self, is_playing: bool) -> None:
        self.btn_tl_play.setText("⏸ Pause" if is_playing else "▶ Play")

    def _on_clip_selected(self, clip: Optional[TimelineClip]) -> None:
        if clip:
            self.lbl_clip_info.setText(
                f"Selected Clip: '{clip.name}' on {clip.track_type.upper()} | Start: {clip.start_time:.1f}s | Duration: {clip.duration:.1f}s"
            )
        else:
            self.lbl_clip_info.setText("No clip selected.")

    def _add_clip_at_playhead(self) -> None:
        t = self.timeline_player.current_time
        track = self.timeline_player.timeline.get_track(TimelineTrackType.DECK_A.value)
        if track:
            clip = TimelineClip(
                track_type=TimelineTrackType.DECK_A.value,
                name=f"Look {len(track.clips)+1}",
                start_time=t,
                duration=6.0,
                properties={"bank": 0, "slot": 0},
            )
            track.add_clip(clip)
            self.canvas.update()

    def _delete_selected_clip(self) -> None:
        clip = self.canvas.selected_clip
        if clip:
            track = self.timeline_player.timeline.get_track(clip.track_type)
            if track:
                track.remove_clip(clip.clip_id)
                self.canvas.selected_clip = None
                self.canvas.update()
                self._on_clip_selected(None)

