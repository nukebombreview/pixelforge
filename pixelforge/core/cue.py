"""
PixelForge — Cue List & Automation Engine
Sequential show automation, crossfade transitions, auto-follow timing,
and cue list playback execution inspired by MADRIX 5 Cue List.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from pixelforge.core.deck import Deck
from pixelforge.core.storage import StorageBank


@dataclass
class Cue:
    """A single automated show cue."""

    cue_id: int
    name: str = "Cue"

    # Presets recall
    deck_a_bank: int = 0      # 0..3 (Bank 1..4)
    deck_a_slot: int = 0      # 0..15 (Slot 1..16)
    deck_b_bank: int = 0      # 0..3
    deck_b_slot: int = 0      # 0..15

    # Crossfader & Output target
    crossfader_pos: float = 0.0   # 0.0 = 100% Deck A, 1.0 = 100% Deck B
    fade_duration: float = 2.0    # Duration of crossfade transition in seconds (0 = snap)
    hold_duration: float = 5.0    # Time to hold look before auto-follow triggers (seconds)
    auto_follow: bool = True      # Whether to automatically advance to next cue
    master_dimmer: float = 1.0    # Master dimmer target (0.0 to 1.0)
    speed_a: float = 1.0          # Playback speed override for Deck A
    speed_b: float = 1.0          # Playback speed override for Deck B

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Cue:
        return cls(**data)


class CuePlayerState(str, Enum):
    STOPPED = "STOPPED"
    PLAYING = "PLAYING"
    PAUSED = "PAUSED"


class CuePhase(str, Enum):
    FADING = "FADING"
    HOLDING = "HOLDING"


class CueList:
    """Ordered collection of show cues."""

    def __init__(self, cues: Optional[List[Cue]] = None):
        self.cues: List[Cue] = cues if cues is not None else []

    def add_cue(self, cue: Cue) -> None:
        self.cues.append(cue)
        self._reindex()

    def insert_cue(self, index: int, cue: Cue) -> None:
        self.cues.insert(index, cue)
        self._reindex()

    def remove_cue(self, index: int) -> Optional[Cue]:
        if 0 <= index < len(self.cues):
            c = self.cues.pop(index)
            self._reindex()
            return c
        return None

    def move_cue(self, from_idx: int, to_idx: int) -> bool:
        if 0 <= from_idx < len(self.cues) and 0 <= to_idx < len(self.cues):
            cue = self.cues.pop(from_idx)
            self.cues.insert(to_idx, cue)
            self._reindex()
            return True
        return False

    def duplicate_cue(self, index: int) -> Optional[Cue]:
        if 0 <= index < len(self.cues):
            src = self.cues[index]
            data = src.to_dict()
            data["name"] = f"{src.name} (Copy)"
            dup = Cue.from_dict(data)
            self.insert_cue(index + 1, dup)
            return dup
        return None

    def get_cue(self, index: int) -> Optional[Cue]:
        if 0 <= index < len(self.cues):
            return self.cues[index]
        return None

    def clear(self) -> None:
        self.cues.clear()

    def _reindex(self) -> None:
        for idx, c in enumerate(self.cues):
            c.cue_id = idx + 1

    def to_list(self) -> List[Dict[str, Any]]:
        return [c.to_dict() for c in self.cues]

    @classmethod
    def from_list(cls, data: List[Dict[str, Any]]) -> CueList:
        cues = [Cue.from_dict(d) for d in data]
        return cls(cues)

    def __len__(self) -> int:
        return len(self.cues)


class CuePlayer(QObject):
    """Execution engine for cue list transitions and automated show playback.

    Signals
    -------
    cue_changed(int, Cue)
        Emitted when a new cue is activated (current_index, cue).
    fade_progress(float, float, float)
        Emitted during crossfade: (progress 0..1, elapsed_seconds, total_duration).
    hold_progress(float, float, float)
        Emitted during hold phase: (progress 0..1, remaining_seconds, total_duration).
    state_changed(str)
        Emitted when playback state changes ("STOPPED", "PLAYING", "PAUSED").
    crossfader_target_updated(float)
        Emitted with the interpolated crossfader position (0.0 to 1.0).
    dimmer_target_updated(float)
        Emitted with the interpolated master dimmer level (0.0 to 1.0).
    preset_recall_requested(str, int, int)
        Emitted when a deck preset recall is triggered: (deck_letter "A"/"B", bank_idx, slot_idx).
    """

    cue_changed = pyqtSignal(int, object)
    fade_progress = pyqtSignal(float, float, float)
    hold_progress = pyqtSignal(float, float, float)
    state_changed = pyqtSignal(str)
    crossfader_target_updated = pyqtSignal(float)
    dimmer_target_updated = pyqtSignal(float)
    preset_recall_requested = pyqtSignal(str, int, int)

    def __init__(self, cue_list: Optional[CueList] = None, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.cue_list = cue_list if cue_list is not None else CueList()

        self.current_index: int = -1
        self.state: CuePlayerState = CuePlayerState.STOPPED
        self.phase: CuePhase = CuePhase.HOLDING
        self.loop: bool = True

        # Timing tracking
        self._phase_start_time: float = 0.0
        self._pause_time: float = 0.0
        self._start_crossfader_pos: float = 0.0
        self._target_crossfader_pos: float = 0.0
        self._start_dimmer: float = 1.0
        self._target_dimmer: float = 1.0

        # High resolution tick timer (30 Hz update for smooth fades)
        self._timer = QTimer(self)
        self._timer.setInterval(33)  # ~30 Hz
        self._timer.timeout.connect(self._on_timer_tick)

    # ------------------------------------------------------------------
    # Transport Controls
    # ------------------------------------------------------------------

    def go(self, target_index: Optional[int] = None) -> None:
        """Trigger GO: advance to the next cue or start the specified cue."""
        if len(self.cue_list) == 0:
            return

        if target_index is not None:
            next_idx = max(0, min(len(self.cue_list) - 1, target_index))
        else:
            if self.current_index < 0:
                next_idx = 0
            else:
                next_idx = self.current_index + 1
                if next_idx >= len(self.cue_list):
                    if self.loop:
                        next_idx = 0
                    else:
                        self.stop()
                        return

        self._execute_cue(next_idx)

    def back(self) -> None:
        """Step backward to the previous cue."""
        if len(self.cue_list) == 0:
            return
        prev_idx = self.current_index - 1
        if prev_idx < 0:
            prev_idx = len(self.cue_list) - 1 if self.loop else 0
        self._execute_cue(prev_idx)

    def pause(self) -> None:
        """Toggle Pause / Resume."""
        if self.state == CuePlayerState.PLAYING:
            self.state = CuePlayerState.PAUSED
            self._pause_time = time.perf_counter()
            self._timer.stop()
            self.state_changed.emit(self.state.value)
        elif self.state == CuePlayerState.PAUSED:
            # Resume: shift start time by paused duration
            paused_duration = time.perf_counter() - self._pause_time
            self._phase_start_time += paused_duration
            self.state = CuePlayerState.PLAYING
            self._timer.start()
            self.state_changed.emit(self.state.value)

    def stop(self) -> None:
        """Stop playback and reset cue player."""
        self._timer.stop()
        self.state = CuePlayerState.STOPPED
        self.phase = CuePhase.HOLDING
        self.current_index = -1
        self.state_changed.emit(self.state.value)
        self.fade_progress.emit(0.0, 0.0, 0.0)
        self.hold_progress.emit(0.0, 0.0, 0.0)

    # ------------------------------------------------------------------
    # Cue Execution
    # ------------------------------------------------------------------

    def _execute_cue(self, index: int) -> None:
        cue = self.cue_list.get_cue(index)
        if not cue:
            return

        self.current_index = index
        self._phase_start_time = time.perf_counter()
        self.state = CuePlayerState.PLAYING

        # Recall presets for Deck A and Deck B
        self.preset_recall_requested.emit("A", cue.deck_a_bank, cue.deck_a_slot)
        self.preset_recall_requested.emit("B", cue.deck_b_bank, cue.deck_b_slot)

        # Setup fade interpolation
        self._start_crossfader_pos = self._target_crossfader_pos
        self._target_crossfader_pos = cue.crossfader_pos
        self._start_dimmer = self._target_dimmer
        self._target_dimmer = cue.master_dimmer

        if cue.fade_duration > 0.0:
            self.phase = CuePhase.FADING
        else:
            # Snap immediately
            self.phase = CuePhase.HOLDING
            self.crossfader_target_updated.emit(self._target_crossfader_pos)
            self.dimmer_target_updated.emit(self._target_dimmer)

        self.cue_changed.emit(self.current_index, cue)
        self.state_changed.emit(self.state.value)

        if not self._timer.isActive():
            self._timer.start()

    # ------------------------------------------------------------------
    # High-Resolution Timer Tick
    # ------------------------------------------------------------------

    def _on_timer_tick(self) -> None:
        if self.state != CuePlayerState.PLAYING:
            return

        cue = self.cue_list.get_cue(self.current_index)
        if not cue:
            return

        now = time.perf_counter()
        elapsed = now - self._phase_start_time

        if self.phase == CuePhase.FADING:
            duration = max(0.001, cue.fade_duration)
            progress = min(1.0, elapsed / duration)

            # Smooth ease-in-out cosine interpolation
            # s-curve: 0.5 * (1 - cos(pi * t))
            import math
            smooth_t = 0.5 * (1.0 - math.cos(math.pi * progress))

            current_pos = self._start_crossfader_pos + smooth_t * (self._target_crossfader_pos - self._start_crossfader_pos)
            current_dim = self._start_dimmer + smooth_t * (self._target_dimmer - self._start_dimmer)

            self.crossfader_target_updated.emit(current_pos)
            self.dimmer_target_updated.emit(current_dim)
            self.fade_progress.emit(progress, elapsed, duration)

            if progress >= 1.0:
                # Transition to HOLDING phase
                self.phase = CuePhase.HOLDING
                self._phase_start_time = now
                self.crossfader_target_updated.emit(self._target_crossfader_pos)
                self.dimmer_target_updated.emit(self._target_dimmer)
                self.fade_progress.emit(1.0, duration, duration)

        elif self.phase == CuePhase.HOLDING:
            if not cue.auto_follow or cue.hold_duration <= 0.0:
                # Manual advance only
                self.hold_progress.emit(1.0, 0.0, cue.hold_duration)
                return

            duration = cue.hold_duration
            remaining = max(0.0, duration - elapsed)
            progress = min(1.0, elapsed / duration)
            self.hold_progress.emit(progress, remaining, duration)

            if elapsed >= duration:
                # Auto follow triggered: trigger next cue!
                self.go()

