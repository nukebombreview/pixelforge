"""
PixelForge — Storage Places Grid Widget
Hardware-style preset grid for instant live recall, organization, and visual show management.
"""

from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon
from PyQt6.QtWidgets import (
    QColorDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pixelforge.core.deck import Deck
from pixelforge.core.storage import StorageBank, StoragePlace


class StorageTileButton(QPushButton):
    """An individual Storage Place tile."""

    def __init__(self, slot_index: int, accent_color: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.slot_index = slot_index
        self.accent_color = accent_color
        self.is_active: bool = False
        self.place: Optional[StoragePlace] = None

        self.setMinimumSize(60, 48)
        self.setSizePolicy(
            QPushButton.sizePolicy(self).Policy.Expanding,
            QPushButton.sizePolicy(self).Policy.Fixed,
        )
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    def update_place(self, place: StoragePlace, is_active: bool = False) -> None:
        self.place = place
        self.is_active = is_active

        slot_label = f"S{place.index + 1}"

        if place.is_empty:
            self.setText(f"{slot_label}\n- Empty -")
            self.setStyleSheet(
                f"QPushButton {{ background-color: #12151c; color: #434c5e; border: 1px dashed #262c3a; "
                f"border-radius: 4px; font-size: 10px; font-weight: normal; padding: 4px; }}"
                f"QPushButton:hover {{ background-color: #1c212c; border-color: #3b4252; color: #8892b0; }}"
            )
        else:
            name_display = place.name if len(place.name) <= 12 else place.name[:11] + "…"
            eff_display = place.effect_name.replace("SCE ", "").replace("S2L ", "")
            if len(eff_display) > 10:
                eff_display = eff_display[:9] + "…"

            self.setText(f"{slot_label}: {name_display}\n[{eff_display}]")

            bg_col = place.color
            border_css = f"2px solid {self.accent_color};" if is_active else "1px solid #4c566a;"
            glow = f"box-shadow: 0 0 8px {self.accent_color};" if is_active else ""

            self.setStyleSheet(
                f"QPushButton {{ background-color: {bg_col}; color: #ffffff; border: {border_css} "
                f"border-radius: 4px; font-size: 10px; font-weight: bold; padding: 4px; {glow} }}"
                f"QPushButton:hover {{ background-color: {QColor(bg_col).lighter(120).name()}; }}"
            )


class StorageGridWidget(QGroupBox):
    """Storage Place panel organizing 64 slots in 4 banks of 16 presets."""

    preset_recalled = pyqtSignal(int)
    preset_stored = pyqtSignal(int)

    PAGE_SIZE = 16

    def __init__(
        self,
        deck: Deck,
        bank: StorageBank,
        effect_loader_fn: Callable[[str], None],
        accent_color: str = "#00d2ff",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(f"STORAGE PLACES ({deck.name})", parent)
        self.deck = deck
        self.bank = bank
        self.effect_loader_fn = effect_loader_fn
        self.accent_color = accent_color
        self.current_bank_page: int = 0  # 0: 0-15, 1: 16-31, 2: 32-47, 3: 48-63

        self._buttons: list[StorageTileButton] = []
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 10, 6, 6)
        main_layout.setSpacing(6)

        # Top Bar: Bank Page Tabs + Store Button
        top_bar = QHBoxLayout()
        top_bar.setSpacing(4)

        self.btn_banks = []
        for b_idx in range(4):
            start = b_idx * self.PAGE_SIZE + 1
            end = (b_idx + 1) * self.PAGE_SIZE
            btn = QPushButton(f"Bank {b_idx + 1} ({start}–{end})")
            btn.setFixedHeight(22)
            btn.setCheckable(True)
            btn.setStyleSheet("font-size: 10px; padding: 2px 6px;")
            btn.clicked.connect(lambda checked, idx=b_idx: self._select_bank(idx))
            top_bar.addWidget(btn)
            self.btn_banks.append(btn)

        self.btn_banks[0].setChecked(True)
        top_bar.addStretch(1)

        btn_store = QPushButton("💾 Store Look")
        btn_store.setFixedHeight(22)
        btn_store.setStyleSheet(
            f"QPushButton {{ background-color: #1b3322; color: #81c784; border: 1px solid #285936; font-size: 10px; font-weight: bold; padding: 2px 8px; }}"
            f"QPushButton:hover {{ background-color: #264a31; }}"
        )
        btn_store.clicked.connect(self._store_current_to_next)
        top_bar.addWidget(btn_store)

        main_layout.addLayout(top_bar)

        # Grid of 16 tiles (2 rows of 8)
        grid_frame = QFrame()
        grid_frame.setStyleSheet("background-color: #0e1117; border: 1px solid #202636; border-radius: 4px; padding: 4px;")
        grid_layout = QGridLayout(grid_frame)
        grid_layout.setContentsMargins(4, 4, 4, 4)
        grid_layout.setSpacing(4)

        for i in range(self.PAGE_SIZE):
            btn = StorageTileButton(i, self.accent_color, self)
            btn.clicked.connect(lambda checked, idx=i: self._on_tile_clicked(idx))
            btn.customContextMenuRequested.connect(lambda pos, idx=i: self._on_tile_context_menu(pos, idx))
            r = i // 8
            c = i % 8
            grid_layout.addWidget(btn, r, c)
            self._buttons.append(btn)

        main_layout.addWidget(grid_frame)
        self.refresh_grid()

    def refresh_grid(self) -> None:
        """Update all 16 buttons on current page from storage bank."""
        base_idx = self.current_bank_page * self.PAGE_SIZE
        for i in range(self.PAGE_SIZE):
            slot = base_idx + i
            place = self.bank.get_place(slot) or StoragePlace(index=slot)
            is_active = (self.bank.active_index == slot)
            self._buttons[i].slot_index = slot
            self._buttons[i].update_place(place, is_active)

    def _select_bank(self, page_idx: int) -> None:
        self.current_bank_page = page_idx
        for i, btn in enumerate(self.btn_banks):
            btn.setChecked(i == page_idx)
        self.refresh_grid()

    def _on_tile_clicked(self, button_idx: int) -> None:
        slot = self.current_bank_page * self.PAGE_SIZE + button_idx
        place = self.bank.get_place(slot)
        if place and not place.is_empty:
            self.bank.recall_to_deck(slot, self.deck, self.effect_loader_fn)
            self.refresh_grid()
            self.preset_recalled.emit(slot)
        else:
            # Click on empty slot prompts to store current deck
            self._store_to_slot(slot)

    def _store_to_slot(self, slot: int) -> None:
        default_name = self.deck.effect_name or f"Look {slot + 1}"
        name, ok = QInputDialog.getText(
            self,
            "Store Preset",
            f"Enter name for Storage Place S{slot + 1}:",
            text=default_name,
        )
        if ok and name.strip():
            self.bank.store_deck(slot, self.deck, name=name.strip())
            self.refresh_grid()
            self.preset_stored.emit(slot)

    def _store_current_to_next(self) -> None:
        """Store into active slot or next empty slot."""
        target_slot = self.bank.active_index
        if target_slot is None:
            # Find first empty
            for i in range(self.bank.capacity):
                p = self.bank.get_place(i)
                if p is None or p.is_empty:
                    target_slot = i
                    break
        if target_slot is None:
            target_slot = 0
        self._store_to_slot(target_slot)

    def _on_tile_context_menu(self, pos, button_idx: int) -> None:
        slot = self.current_bank_page * self.PAGE_SIZE + button_idx
        place = self.bank.get_place(slot)
        sender_btn = self._buttons[button_idx]

        menu = QMenu(self)

        act_store = menu.addAction(f"Store Active Look to S{slot + 1}")
        act_store.triggered.connect(lambda: self._store_to_slot(slot))

        if place and not place.is_empty:
            menu.addSeparator()

            act_rename = menu.addAction("Rename Preset...")
            act_rename.triggered.connect(lambda: self._rename_slot(slot))

            act_color = menu.addAction("Change Tile Color...")
            act_color.triggered.connect(lambda: self._recolor_slot(slot))

            menu.addSeparator()

            act_clear = menu.addAction("Clear Storage Place")
            act_clear.triggered.connect(lambda: self._clear_slot(slot))

        menu.exec(sender_btn.mapToGlobal(pos))

    def _rename_slot(self, slot: int) -> None:
        place = self.bank.get_place(slot)
        if not place:
            return
        new_name, ok = QInputDialog.getText(
            self, "Rename Preset", "New Preset Name:", text=place.name
        )
        if ok and new_name.strip():
            place.name = new_name.strip()
            self.refresh_grid()

    def _recolor_slot(self, slot: int) -> None:
        place = self.bank.get_place(slot)
        if not place:
            return
        initial = QColor(place.color)
        chosen = QColorDialog.getColor(initial, self, "Select Tile Color")
        if chosen.isValid():
            place.color = chosen.name()
            self.refresh_grid()

    def _clear_slot(self, slot: int) -> None:
        self.bank.clear_place(slot)
        self.refresh_grid()

