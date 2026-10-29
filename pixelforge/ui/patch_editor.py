"""
PixelForge — Visual 2D Patch Editor & Matrix Generator
CAD-style 2D visual fixture canvas, DMX universe addressing, matrix generator, and CSV import/export.
"""

from __future__ import annotations

import math
from typing import Optional

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from pixelforge.core.patch import Fixture, Patch, PixelRouting


class PatchCanvasWidget(QWidget):
    """Interactive 2D stage canvas rendering patched fixtures with DMX address badges."""

    fixture_selected = pyqtSignal(object)  # Fixture or None
    patch_modified = pyqtSignal()

    def __init__(self, patch: Patch, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.patch = patch
        self.selected_fixture: Optional[Fixture] = None

        self._grid_size: int = 16  # pixels per matrix unit
        self._drag_fixture: Optional[Fixture] = None
        self._drag_start_pos: Optional[QPointF] = None
        self._drag_orig_pos: Optional[tuple[int, int]] = None

        self.setMinimumSize(400, 350)
        self.setMouseTracking(True)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w = self.width()
        h = self.height()

        # Canvas dark background
        painter.fillRect(0, 0, w, h, QColor("#0c0e14"))

        # Grid lines
        grid_pen = QPen(QColor("#181d28"), 1)
        painter.setPen(grid_pen)
        scale = self._grid_size

        for x in range(0, w, scale):
            painter.drawLine(x, 0, x, h)
        for y in range(0, h, scale):
            painter.drawLine(0, y, w, y)

        # Virtual matrix boundary outline
        mw = self.patch.matrix_width * scale
        mh = self.patch.matrix_height * scale
        boundary_pen = QPen(QColor("#3d4963"), 1, Qt.PenStyle.DashLine)
        painter.setPen(boundary_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(0, 0, mw, mh)

        # Draw fixtures
        for f in self.patch.fixtures:
            self._draw_fixture(painter, f, scale)

    def _draw_fixture(self, painter: QPainter, f: Fixture, scale: int) -> None:
        fx = f.x * scale
        fy = f.y * scale
        fw = f.width * scale
        fh = f.height * scale

        is_sel = (self.selected_fixture and self.selected_fixture.id == f.id)
        base_color = QColor(f.color_label)

        # Body fill
        fill_col = QColor(base_color.red(), base_color.green(), base_color.blue(), 60 if not is_sel else 110)
        painter.setBrush(QBrush(fill_col))

        # Outline
        if is_sel:
            border_pen = QPen(QColor("#ffffff"), 2)
        else:
            border_pen = QPen(base_color, 1.5)
        painter.setPen(border_pen)
        painter.drawRoundedRect(QRectF(fx, fy, fw, fh), 4, 4)

        # Fixture pixel grid dots
        dot_rad = max(1.0, min(scale * 0.25, 3.0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(base_color.red(), base_color.green(), base_color.blue(), 180)))
        for py in range(f.height):
            for px in range(f.width):
                dot_x = fx + (px + 0.5) * scale
                dot_y = fy + (py + 0.5) * scale
                painter.drawEllipse(QPointF(dot_x, dot_y), dot_rad, dot_rad)

        # Label badge
        if fw >= 40:
            if fh >= 24:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(QColor(12, 16, 24, 210)))
                painter.drawRoundedRect(QRectF(fx + 3, fy + 3, min(fw - 6, 200), 20), 3, 3)

                painter.setPen(QPen(QColor("#ffffff")))
                painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
                painter.drawText(int(fx + 6), int(fy + 17), f"#{f.id} {f.name}")

                # DMX Universe:Channel address
                addr_str = f"U{f.start_universe}:{f.start_channel} ({f.width}×{f.height})"
                painter.setPen(QPen(QColor(base_color).lighter(140)))
                painter.setFont(QFont("Segoe UI", 7))
                painter.drawText(int(fx + 6), int(fy + fh - 5), addr_str)
            else:
                # 1D Strip / Rope Light label
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(QColor(12, 16, 24, 210)))
                painter.drawRoundedRect(QRectF(fx + 2, fy + 1, min(fw - 4, 300), max(14, fh - 2)), 2, 2)

                painter.setPen(QPen(QColor("#ffffff")))
                painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
                painter.drawText(int(fx + 5), int(fy + fh - 3), f"#{f.id} {f.name} — U{f.start_universe}:{f.start_channel} ({f.width}px {f.channel_order})")

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            scale = self._grid_size
            clicked_f = None
            # Hit test in reverse order (topmost first)
            for f in reversed(self.patch.fixtures):
                fx = f.x * scale
                fy = f.y * scale
                fw = f.width * scale
                fh = f.height * scale
                if fx <= pos.x() <= fx + fw and fy <= pos.y() <= fy + fh:
                    clicked_f = f
                    break

            self.selected_fixture = clicked_f
            self.fixture_selected.emit(clicked_f)

            if clicked_f:
                self._drag_fixture = clicked_f
                self._drag_start_pos = pos
                self._drag_orig_pos = (clicked_f.x, clicked_f.y)

            self.update()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_fixture and self._drag_start_pos and self._drag_orig_pos:
            delta = event.position() - self._drag_start_pos
            scale = self._grid_size
            dx = int(round(delta.x() / scale))
            dy = int(round(delta.y() / scale))

            new_x = max(0, self._drag_orig_pos[0] + dx)
            new_y = max(0, self._drag_orig_pos[1] + dy)

            if new_x != self._drag_fixture.x or new_y != self._drag_fixture.y:
                self._drag_fixture.x = new_x
                self._drag_fixture.y = new_y
                self.patch.invalidate_cache()
                self.patch_modified.emit()
                self.update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_fixture = None
            self._drag_start_pos = None
            self._drag_orig_pos = None


class MatrixGeneratorDialog(QDialog):
    """One-click dialog to generate modular LED panels across rows & columns."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Matrix Panel Generator")
        self.setFixedWidth(380)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.spin_cols = QSpinBox()
        self.spin_cols.setRange(1, 32)
        self.spin_cols.setValue(2)
        form.addRow("Panel Columns (X):", self.spin_cols)

        self.spin_rows = QSpinBox()
        self.spin_rows.setRange(1, 32)
        self.spin_rows.setValue(2)
        form.addRow("Panel Rows (Y):", self.spin_rows)

        self.spin_w = QSpinBox()
        self.spin_w.setRange(1, 128)
        self.spin_w.setValue(16)
        form.addRow("Panel Width (pixels):", self.spin_w)

        self.spin_h = QSpinBox()
        self.spin_h.setRange(1, 128)
        self.spin_h.setValue(16)
        form.addRow("Panel Height (pixels):", self.spin_h)

        self.spin_u = QSpinBox()
        self.spin_u.setRange(0, 32767)
        self.spin_u.setValue(0)
        form.addRow("Starting Universe:", self.spin_u)

        self.spin_ch = QSpinBox()
        self.spin_ch.setRange(1, 512)
        self.spin_ch.setValue(1)
        form.addRow("Starting DMX Channel:", self.spin_ch)

        self.combo_order = QComboBox()
        self.combo_order.addItems(["RGB", "GRB", "BGR", "RGBW"])
        form.addRow("Color Order:", self.combo_order)

        self.combo_routing = QComboBox()
        self.combo_routing.addItem("Horizontal (Left to Right)", PixelRouting.HORIZONTAL_LTR)
        self.combo_routing.addItem("Horizontal Snake (Serpentine)", PixelRouting.HORIZONTAL_SNAKE)
        self.combo_routing.addItem("Vertical (Top to Bottom)", PixelRouting.VERTICAL_TTB)
        self.combo_routing.addItem("Vertical Snake (Serpentine)", PixelRouting.VERTICAL_SNAKE)
        form.addRow("Snake Wiring Order:", self.combo_routing)

        layout.addLayout(form)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_values(self) -> dict[str, Any]:
        return {
            "cols": self.spin_cols.value(),
            "rows": self.spin_rows.value(),
            "tile_w": self.spin_w.value(),
            "tile_h": self.spin_h.value(),
            "start_universe": self.spin_u.value(),
            "start_channel": self.spin_ch.value(),
            "channel_order": self.combo_order.currentText(),
            "routing": self.combo_routing.currentData(),
        }


class PatchEditorDialog(QDialog):
    """Full-featured visual patch management window."""

    def __init__(self, patch: Patch, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("PixelForge — Visual Patch Editor & Stage Layout")
        self.resize(1100, 720)
        self.setMinimumSize(850, 550)

        self.patch = patch
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        # Top Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        btn_add = QPushButton("➕ Add Fixture")
        btn_add.clicked.connect(self._add_fixture)
        toolbar.addWidget(btn_add)

        btn_add_rope = QPushButton("🎗 Add 5m LED Rope (80px GRB)")
        btn_add_rope.setStyleSheet("background-color: #0e3322; color: #00ff88; font-weight: bold; border: 1px solid #00aa55;")
        btn_add_rope.setToolTip("Quick-patch the 5M 80-pixel LED rope light (240 channels GRB) for Unreal Engine / QLC+")
        btn_add_rope.clicked.connect(self._add_rope_light)
        toolbar.addWidget(btn_add_rope)

        btn_matrix = QPushButton("🔲 Matrix Generator")
        btn_matrix.clicked.connect(self._open_matrix_generator)
        toolbar.addWidget(btn_matrix)

        btn_csv_exp = QPushButton("📄 Export CSV")
        btn_csv_exp.clicked.connect(self._export_csv)
        toolbar.addWidget(btn_csv_exp)

        btn_csv_imp = QPushButton("📂 Import CSV")
        btn_csv_imp.clicked.connect(self._import_csv)
        toolbar.addWidget(btn_csv_imp)

        btn_clear = QPushButton("🗑 Clear All")
        btn_clear.clicked.connect(self._clear_patch)
        toolbar.addWidget(btn_clear)

        toolbar.addStretch(1)

        self.lbl_stats = QLabel("Fixtures: 0 | Pixels: 0 | Universes: 0")
        self.lbl_stats.setStyleSheet("font-weight: bold; color: #58a6ff; font-family: monospace;")
        toolbar.addWidget(self.lbl_stats)

        main_layout.addLayout(toolbar)

        # Main splitter (Canvas + Inspector)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Center/Left: 2D Stage Canvas inside scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.canvas = PatchCanvasWidget(self.patch, self)
        self.canvas.fixture_selected.connect(self._on_fixture_selected)
        self.canvas.patch_modified.connect(self._update_table_and_stats)
        scroll.setWidget(self.canvas)
        splitter.addWidget(scroll)

        # Right: Fixture Inspector Panel
        inspector = self._build_inspector()
        splitter.addWidget(inspector)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter, stretch=4)

        # Bottom Table: Fixture Roster
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "ID", "Name", "Pos (X,Y)", "Size (W×H)", "Pixels", "Start Address", "Color Order", "Routing"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setFixedHeight(160)
        self.table.cellClicked.connect(self._on_table_row_clicked)
        main_layout.addWidget(self.table, stretch=1)

        # Close / Apply Button Box
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn_box.rejected.connect(self.accept)
        main_layout.addWidget(btn_box)

        self._update_table_and_stats()

    def _build_inspector(self) -> QGroupBox:
        grp = QGroupBox("FIXTURE PROPERTIES")
        form = QFormLayout(grp)
        form.setSpacing(8)

        self.edit_name = QLineEdit()
        self.edit_name.textChanged.connect(self._apply_inspector_changes)
        form.addRow("Name:", self.edit_name)

        pos_box = QHBoxLayout()
        self.spin_x = QSpinBox()
        self.spin_x.setRange(0, 2048)
        self.spin_x.valueChanged.connect(self._apply_inspector_changes)
        self.spin_y = QSpinBox()
        self.spin_y.setRange(0, 2048)
        self.spin_y.valueChanged.connect(self._apply_inspector_changes)
        pos_box.addWidget(QLabel("X:")); pos_box.addWidget(self.spin_x)
        pos_box.addWidget(QLabel("Y:")); pos_box.addWidget(self.spin_y)
        form.addRow("Position:", pos_box)

        size_box = QHBoxLayout()
        self.spin_w = QSpinBox()
        self.spin_w.setRange(1, 512)
        self.spin_w.valueChanged.connect(self._apply_inspector_changes)
        self.spin_h = QSpinBox()
        self.spin_h.setRange(1, 512)
        self.spin_h.valueChanged.connect(self._apply_inspector_changes)
        size_box.addWidget(QLabel("W:")); size_box.addWidget(self.spin_w)
        size_box.addWidget(QLabel("H:")); size_box.addWidget(self.spin_h)
        form.addRow("Size:", size_box)

        self.spin_start_u = QSpinBox()
        self.spin_start_u.setRange(0, 32767)
        self.spin_start_u.valueChanged.connect(self._apply_inspector_changes)
        form.addRow("Start Universe:", self.spin_start_u)

        self.spin_start_ch = QSpinBox()
        self.spin_start_ch.setRange(1, 512)
        self.spin_start_ch.valueChanged.connect(self._apply_inspector_changes)
        form.addRow("Start Channel:", self.spin_start_ch)

        self.combo_order = QComboBox()
        self.combo_order.addItems(["RGB", "GRB", "BGR", "RGBW"])
        self.combo_order.currentTextChanged.connect(self._apply_inspector_changes)
        form.addRow("Color Order:", self.combo_order)

        self.combo_routing = QComboBox()
        self.combo_routing.addItem("Horizontal LTR", PixelRouting.HORIZONTAL_LTR)
        self.combo_routing.addItem("Horizontal Snake", PixelRouting.HORIZONTAL_SNAKE)
        self.combo_routing.addItem("Vertical TTB", PixelRouting.VERTICAL_TTB)
        self.combo_routing.addItem("Vertical Snake", PixelRouting.VERTICAL_SNAKE)
        self.combo_routing.currentIndexChanged.connect(self._apply_inspector_changes)
        form.addRow("Snake Routing:", self.combo_routing)

        btn_del = QPushButton("❌ Delete Selected Fixture")
        btn_del.setStyleSheet("background-color: #3b141a; color: #ff6b81; font-weight: bold;")
        btn_del.clicked.connect(self._delete_selected)
        form.addRow("", btn_del)

        return grp

    def _on_fixture_selected(self, fixture: Optional[Fixture]) -> None:
        if not fixture:
            return
        self.edit_name.blockSignals(True)
        self.spin_x.blockSignals(True)
        self.spin_y.blockSignals(True)
        self.spin_w.blockSignals(True)
        self.spin_h.blockSignals(True)
        self.spin_start_u.blockSignals(True)
        self.spin_start_ch.blockSignals(True)
        self.combo_order.blockSignals(True)
        self.combo_routing.blockSignals(True)

        self.edit_name.setText(fixture.name)
        self.spin_x.setValue(fixture.x)
        self.spin_y.setValue(fixture.y)
        self.spin_w.setValue(fixture.width)
        self.spin_h.setValue(fixture.height)
        self.spin_start_u.setValue(fixture.start_universe)
        self.spin_start_ch.setValue(fixture.start_channel)
        self.combo_order.setCurrentText(fixture.channel_order)

        idx = self.combo_routing.findData(fixture.routing)
        if idx >= 0:
            self.combo_routing.setCurrentIndex(idx)

        self.edit_name.blockSignals(False)
        self.spin_x.blockSignals(False)
        self.spin_y.blockSignals(False)
        self.spin_w.blockSignals(False)
        self.spin_h.blockSignals(False)
        self.spin_start_u.blockSignals(False)
        self.spin_start_ch.blockSignals(False)
        self.combo_order.blockSignals(False)
        self.combo_routing.blockSignals(False)

    def _apply_inspector_changes(self) -> None:
        f = self.canvas.selected_fixture
        if not f:
            return
        f.name = self.edit_name.text().strip() or f"Fixture {f.id}"
        f.x = self.spin_x.value()
        f.y = self.spin_y.value()
        f.width = self.spin_w.value()
        f.height = self.spin_h.value()
        f.start_universe = self.spin_start_u.value()
        f.start_channel = self.spin_start_ch.value()
        f.channel_order = self.combo_order.currentText()
        f.routing = self.combo_routing.currentData() or PixelRouting.HORIZONTAL_LTR

        self.patch.invalidate_cache()
        self.canvas.update()
        self._update_table_and_stats()

    def _delete_selected(self) -> None:
        f = self.canvas.selected_fixture
        if f:
            self.patch.remove_fixture(f.id)
            self.canvas.selected_fixture = None
            self.canvas.update()
            self._update_table_and_stats()

    def _add_fixture(self) -> None:
        f = Fixture(
            id=self.patch._next_id,
            name=f"Fixture {self.patch._next_id}",
            x=0,
            y=0,
            width=16,
            height=16,
            start_universe=0,
            start_channel=1,
        )
        self.patch.add_fixture(f)
        self.canvas.selected_fixture = f
        self._on_fixture_selected(f)
        self.canvas.update()
        self._update_table_and_stats()

    def _add_rope_light(self) -> None:
        next_u = 0
        next_ch = 1
        if self.patch.fixtures:
            last_f = self.patch.fixtures[-1]
            last_tot = (last_f.start_channel - 1) + last_f.total_channels
            next_u = last_f.start_universe + (last_tot // 512)
            next_ch = (last_tot % 512) + 1

        next_y = 0
        if self.patch.fixtures:
            next_y = max(f.y + f.height for f in self.patch.fixtures)

        f = self.patch.add_rope_light_fixture(
            name=f"5m LED Rope Light [{len(self.patch.fixtures) + 1}]",
            x=0,
            y=next_y,
            start_universe=next_u,
            start_channel=next_ch,
        )
        self.canvas.selected_fixture = f
        self._on_fixture_selected(f)
        self.canvas.update()
        self._update_table_and_stats()

    def _open_matrix_generator(self) -> None:
        dlg = MatrixGeneratorDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            v = dlg.get_values()
            self.patch.generate_matrix(
                cols=v["cols"],
                rows=v["rows"],
                tile_w=v["tile_w"],
                tile_h=v["tile_h"],
                start_universe=v["start_universe"],
                start_channel=v["start_channel"],
                channel_order=v["channel_order"],
                routing=v["routing"],
            )
            self.canvas.selected_fixture = None
            self.canvas.update()
            self._update_table_and_stats()

    def _update_table_and_stats(self) -> None:
        self.table.setRowCount(len(self.patch.fixtures))
        total_pixels = sum(f.pixel_count for f in self.patch.fixtures)
        universes_set = set()

        for row, f in enumerate(self.patch.fixtures):
            universes_set.add(f.start_universe)
            self.table.setItem(row, 0, QTableWidgetItem(str(f.id)))
            self.table.setItem(row, 1, QTableWidgetItem(f.name))
            self.table.setItem(row, 2, QTableWidgetItem(f"({f.x}, {f.y})"))
            self.table.setItem(row, 3, QTableWidgetItem(f"{f.width}×{f.height}"))
            self.table.setItem(row, 4, QTableWidgetItem(str(f.pixel_count)))
            self.table.setItem(row, 5, QTableWidgetItem(f"U{f.start_universe}:Ch{f.start_channel}"))
            self.table.setItem(row, 6, QTableWidgetItem(f.channel_order))
            self.table.setItem(row, 7, QTableWidgetItem(f.routing.value))

        self.lbl_stats.setText(
            f"Fixtures: {len(self.patch.fixtures)} | Pixels: {total_pixels} | Universes Used: {len(universes_set)}"
        )

    def _on_table_row_clicked(self, row: int, col: int) -> None:
        if 0 <= row < len(self.patch.fixtures):
            f = self.patch.fixtures[row]
            self.canvas.selected_fixture = f
            self._on_fixture_selected(f)
            self.canvas.update()

    def _export_csv(self) -> None:
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export Fixture Patch CSV", "patch.csv", "CSV Files (*.csv)"
        )
        if filepath:
            csv_str = self.patch.export_csv()
            with open(filepath, "w", encoding="utf-8") as file:
                file.write(csv_str)
            QMessageBox.information(self, "Export Complete", "Fixture patch CSV exported successfully!")

    def _import_csv(self) -> None:
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Import Fixture Patch CSV", "", "CSV Files (*.csv)"
        )
        if filepath:
            with open(filepath, "r", encoding="utf-8") as file:
                content = file.read()
            if self.patch.import_csv(content):
                self.canvas.selected_fixture = None
                self.canvas.update()
                self._update_table_and_stats()
                QMessageBox.information(self, "Import Complete", "Fixture patch CSV imported successfully!")
            else:
                QMessageBox.warning(self, "Import Error", "Failed to parse CSV patch file.")

    def _clear_patch(self) -> None:
        if QMessageBox.question(
            self, "Clear Patch", "Remove all fixtures from the patch?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            self.patch.clear()
            self.canvas.selected_fixture = None
            self.canvas.update()
            self._update_table_and_stats()

