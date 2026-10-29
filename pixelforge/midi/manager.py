"""
PixelForge — MIDI Hardware & Control Manager
Asynchronous low-latency MIDI I/O, dynamic parameter mapping,
interactive MIDI Learn mode, bidirectional feedback, and preset profiles.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from PyQt6.QtCore import QObject, pyqtSignal

try:
    import mido
    MIDO_AVAILABLE = True
except ImportError:
    mido = None
    MIDO_AVAILABLE = False


NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def midi_note_to_name(note: int) -> str:
    """Convert MIDI note number (0..127) to standard scientific pitch notation (e.g., 60 -> C4)."""
    if not (0 <= note <= 127):
        return f"Note {note}"
    octave = (note // 12) - 1
    name = NOTE_NAMES[note % 12]
    return f"{name}{octave} ({note})"


class MidiMode(str, Enum):
    ABSOLUTE = "absolute"       # Continuous 0..127 scaled linearly to [min_val, max_val]
    TOGGLE = "toggle"           # Non-zero value toggles binary state (ON <-> OFF)
    MOMENTARY = "momentary"     # Value > 0 is ON (max_val), value == 0 is OFF (min_val)
    RELATIVE = "relative"       # Relative encoder (+1 / -1 steps)


class MidiMappingTarget(str, Enum):
    CROSSFADER = "crossfader"
    MASTER_DIMMER = "master_dimmer"
    BLACKOUT = "blackout"
    FREEZE = "freeze"
    WHITEOUT = "whiteout"

    DECK_A_SPEED = "deck_a_speed"
    DECK_B_SPEED = "deck_b_speed"

    DECK_A_PARAM_0 = "deck_a_param_0"
    DECK_A_PARAM_1 = "deck_a_param_1"
    DECK_A_PARAM_2 = "deck_a_param_2"
    DECK_A_PARAM_3 = "deck_a_param_3"
    DECK_A_PARAM_4 = "deck_a_param_4"
    DECK_A_PARAM_5 = "deck_a_param_5"

    DECK_B_PARAM_0 = "deck_b_param_0"
    DECK_B_PARAM_1 = "deck_b_param_1"
    DECK_B_PARAM_2 = "deck_b_param_2"
    DECK_B_PARAM_3 = "deck_b_param_3"
    DECK_B_PARAM_4 = "deck_b_param_4"
    DECK_B_PARAM_5 = "deck_b_param_5"

    STORAGE_A_PREV = "storage_a_prev"
    STORAGE_A_NEXT = "storage_a_next"
    STORAGE_B_PREV = "storage_b_prev"
    STORAGE_B_NEXT = "storage_b_next"

    STORAGE_A_SLOT_1 = "storage_a_slot_1"
    STORAGE_A_SLOT_2 = "storage_a_slot_2"
    STORAGE_A_SLOT_3 = "storage_a_slot_3"
    STORAGE_A_SLOT_4 = "storage_a_slot_4"
    STORAGE_A_SLOT_5 = "storage_a_slot_5"
    STORAGE_A_SLOT_6 = "storage_a_slot_6"
    STORAGE_A_SLOT_7 = "storage_a_slot_7"
    STORAGE_A_SLOT_8 = "storage_a_slot_8"

    STORAGE_B_SLOT_1 = "storage_b_slot_1"
    STORAGE_B_SLOT_2 = "storage_b_slot_2"
    STORAGE_B_SLOT_3 = "storage_b_slot_3"
    STORAGE_B_SLOT_4 = "storage_b_slot_4"
    STORAGE_B_SLOT_5 = "storage_b_slot_5"
    STORAGE_B_SLOT_6 = "storage_b_slot_6"
    STORAGE_B_SLOT_7 = "storage_b_slot_7"
    STORAGE_B_SLOT_8 = "storage_b_slot_8"


@dataclass
class MidiMessage:
    msg_type: str      # "control_change", "note_on", "note_off", "pitchwheel"
    channel: int       # 0..15 (display as 1..16)
    control: int       # CC controller number or Note pitch (0..127)
    value: int         # Velocity or CC value (0..127)
    timestamp: float = 0.0

    @property
    def channel_display(self) -> int:
        return self.channel + 1

    @property
    def control_display(self) -> str:
        if "note" in self.msg_type:
            return midi_note_to_name(self.control)
        return f"CC {self.control}"


@dataclass
class MidiBinding:
    target: str
    msg_type: str = "control_change"  # "control_change" or "note_on"
    channel: int = -1                 # -1 = Omni (any channel), 0..15 for specific
    control: int = 0                  # 0..127
    mode: str = MidiMode.ABSOLUTE.value
    min_val: float = 0.0
    max_val: float = 1.0
    invert: bool = False
    feedback_enabled: bool = True

    def matches(self, msg: MidiMessage) -> bool:
        """Check if incoming MIDI message matches this binding."""
        # Message type match
        if self.msg_type == "note_on":
            if msg.msg_type not in ("note_on", "note_off"):
                return False
        elif self.msg_type != msg.msg_type:
            return False

        # Channel match (-1 is Omni)
        if self.channel != -1 and self.channel != msg.channel:
            return False

        # Control or Note match
        if self.control != msg.control:
            return False

        return True

    def compute_value(self, msg: MidiMessage, current_val: float = 0.0) -> float:
        """Calculate normalized target value from incoming message."""
        raw_val = msg.value

        # For note_off or note_on with velocity 0
        if msg.msg_type == "note_off" or (msg.msg_type == "note_on" and raw_val == 0):
            raw_norm = 0.0
        else:
            raw_norm = raw_val / 127.0

        if self.mode == MidiMode.TOGGLE.value:
            # On note press or CC > 63, toggle state
            if raw_val > 0:
                is_on = current_val > ((self.min_val + self.max_val) / 2.0)
                return self.min_val if is_on else self.max_val
            return current_val

        elif self.mode == MidiMode.MOMENTARY.value:
            val = self.max_val if raw_val > 0 else self.min_val
            return (self.max_val + self.min_val - val) if self.invert else val

        elif self.mode == MidiMode.RELATIVE.value:
            # 2's complement or 64-center
            step = 1.0 if raw_val < 64 else -1.0
            new_val = current_val + step * ((self.max_val - self.min_val) / 64.0)
            return max(self.min_val, min(self.max_val, new_val))

        else:  # ABSOLUTE
            if self.invert:
                raw_norm = 1.0 - raw_norm
            return self.min_val + raw_norm * (self.max_val - self.min_val)


class MidiManager(QObject):
    """Central manager for hardware MIDI interfaces, mapping dispatch, and feedback."""

    message_received = pyqtSignal(object)       # MidiMessage
    binding_triggered = pyqtSignal(str, float)  # (target_name, new_value)
    learn_completed = pyqtSignal(object)        # MidiBinding
    ports_changed = pyqtSignal()
    connection_status_changed = pyqtSignal(str) # e.g. "Connected: APC Mini"

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)

        self._inport = None
        self._outport = None
        self._active_inport_name: Optional[str] = None
        self._active_outport_name: Optional[str] = None

        # Bindings registry: list of MidiBinding
        self.bindings: List[MidiBinding] = []

        # Current state cache for toggle/relative computation
        self._current_values: Dict[str, float] = {
            MidiMappingTarget.CROSSFADER.value: 0.5,
            MidiMappingTarget.MASTER_DIMMER.value: 1.0,
            MidiMappingTarget.BLACKOUT.value: 0.0,
            MidiMappingTarget.FREEZE.value: 0.0,
            MidiMappingTarget.WHITEOUT.value: 0.0,
            MidiMappingTarget.DECK_A_SPEED.value: 1.0,
            MidiMappingTarget.DECK_B_SPEED.value: 1.0,
        }

        # Learn mode
        self.learning_target: Optional[str] = None
        self.learning_mode: str = MidiMode.ABSOLUTE.value

        # Event log for MIDI Watcher
        self.watcher_log: List[Tuple[MidiMessage, Optional[str]]] = []
        self.max_log_entries = 500
        self.watcher_paused: bool = False

        # Load default bindings
        self.load_preset_profile("Generic Controller")

    # ------------------------------------------------------------------
    # Port Discovery & Connection
    # ------------------------------------------------------------------

    def get_input_ports(self) -> List[str]:
        if not MIDO_AVAILABLE or mido is None:
            return []
        try:
            return list(mido.get_input_names())
        except Exception:
            return []

    def get_output_ports(self) -> List[str]:
        if not MIDO_AVAILABLE or mido is None:
            return []
        try:
            return list(mido.get_output_names())
        except Exception:
            return []

    def open_input_port(self, port_name: str) -> bool:
        if not MIDO_AVAILABLE or mido is None:
            return False
        self.close_input_port()
        try:
            self._inport = mido.open_input(port_name, callback=self._on_mido_message)
            self._active_inport_name = port_name
            self.connection_status_changed.emit(f"MIDI IN: {port_name}")
            return True
        except Exception as e:
            self._inport = None
            self._active_inport_name = None
            self.connection_status_changed.emit(f"MIDI Error: {e}")
            return False

    def close_input_port(self) -> None:
        if self._inport:
            try:
                self._inport.close()
            except Exception:
                pass
            self._inport = None
            self._active_inport_name = None
            self.connection_status_changed.emit("MIDI IN: Disconnected")

    def open_output_port(self, port_name: str) -> bool:
        if not MIDO_AVAILABLE or mido is None:
            return False
        self.close_output_port()
        try:
            self._outport = mido.open_output(port_name)
            self._active_outport_name = port_name
            return True
        except Exception:
            self._outport = None
            self._active_outport_name = None
            return False

    def close_output_port(self) -> None:
        if self._outport:
            try:
                self._outport.close()
            except Exception:
                pass
            self._outport = None
            self._active_outport_name = None

    @property
    def is_input_open(self) -> bool:
        return self._inport is not None

    @property
    def is_output_open(self) -> bool:
        return self._outport is not None

    @property
    def active_inport_name(self) -> Optional[str]:
        return self._active_inport_name

    @property
    def active_outport_name(self) -> Optional[str]:
        return self._active_outport_name

    # ------------------------------------------------------------------
    # Message Dispatch & Processing
    # ------------------------------------------------------------------

    def _on_mido_message(self, msg: Any) -> None:
        """Callback executed by mido background thread when hardware sends message."""
        if msg.type not in ("note_on", "note_off", "control_change", "pitchwheel"):
            return

        ctrl = getattr(msg, "control", getattr(msg, "note", 0))
        val = getattr(msg, "value", getattr(msg, "velocity", 0))
        channel = getattr(msg, "channel", 0)

        # Normalize note_on with 0 velocity to note_off
        msg_type = msg.type
        if msg_type == "note_on" and val == 0:
            msg_type = "note_off"

        parsed = MidiMessage(
            msg_type=msg_type,
            channel=channel,
            control=ctrl,
            value=val,
            timestamp=time.time(),
        )
        self.process_message(parsed)

    def process_message(self, msg: MidiMessage) -> None:
        """Process a parsed MIDI message (callable from hardware callback or virtual simulator)."""
        # Learn mode intercept
        matched_target: Optional[str] = None
        if self.learning_target:
            target = self.learning_target
            # Filter out note_off from completing learn
            if msg.msg_type in ("note_on", "control_change") and msg.value > 0:
                new_binding = MidiBinding(
                    target=target,
                    msg_type=msg.msg_type,
                    channel=msg.channel,
                    control=msg.control,
                    mode=self.learning_mode,
                )
                self.set_binding(new_binding)
                self.learning_target = None
                self.learn_completed.emit(new_binding)
                matched_target = f"[Learned: {target}]"

        # Regular dispatch
        if not matched_target:
            for b in self.bindings:
                if b.matches(msg):
                    cur_val = self._current_values.get(b.target, 0.0)
                    computed_val = b.compute_value(msg, cur_val)
                    self._current_values[b.target] = computed_val
                    self.binding_triggered.emit(b.target, computed_val)
                    matched_target = b.target
                    break

        # Log to Watcher
        if not self.watcher_paused:
            self.watcher_log.append((msg, matched_target))
            if len(self.watcher_log) > self.max_log_entries:
                self.watcher_log.pop(0)

        self.message_received.emit(msg)

    def simulate_message(
        self,
        msg_type: str = "control_change",
        channel: int = 0,
        control: int = 1,
        value: int = 127,
    ) -> None:
        """Inject virtual MIDI message for diagnostics, testing, or UI generation."""
        msg = MidiMessage(
            msg_type=msg_type,
            channel=channel,
            control=control,
            value=value,
            timestamp=time.time(),
        )
        self.process_message(msg)

    # ------------------------------------------------------------------
    # Learn Mode
    # ------------------------------------------------------------------

    def start_learning(self, target: str, mode: str = MidiMode.ABSOLUTE.value) -> None:
        """Arm MIDI Learn for a specific target parameter."""
        self.learning_target = target
        self.learning_mode = mode

    def cancel_learning(self) -> None:
        self.learning_target = None

    @property
    def is_learning(self) -> bool:
        return self.learning_target is not None

    # ------------------------------------------------------------------
    # Binding Management
    # ------------------------------------------------------------------

    def set_binding(self, binding: MidiBinding) -> None:
        """Add or update a binding for a given target."""
        self.bindings = [b for b in self.bindings if b.target != binding.target]
        self.bindings.append(binding)

    def remove_binding(self, target: str) -> None:
        self.bindings = [b for b in self.bindings if b.target != target]

    def get_binding(self, target: str) -> Optional[MidiBinding]:
        for b in self.bindings:
            if b.target == target:
                return b
        return None

    def clear_all_bindings(self) -> None:
        self.bindings.clear()

    # ------------------------------------------------------------------
    # Bidirectional Feedback (LEDs / Motorized Faders)
    # ------------------------------------------------------------------

    def send_feedback(self, target: str, value: float) -> None:
        """Send state update back to physical controller if output is open."""
        self._current_values[target] = value
        if not self.is_output_open or mido is None or self._outport is None:
            return

        b = self.get_binding(target)
        if not b or not b.feedback_enabled:
            return

        try:
            norm = (value - b.min_val) / max(0.001, (b.max_val - b.min_val))
            norm = max(0.0, min(1.0, norm))
            if b.invert:
                norm = 1.0 - norm
            midi_val = int(round(norm * 127))

            ch = b.channel if b.channel >= 0 else 0
            if b.msg_type == "control_change":
                out_msg = mido.Message("control_change", channel=ch, control=b.control, value=midi_val)
                self._outport.send(out_msg)
            elif b.msg_type == "note_on":
                vel = 127 if midi_val > 63 else 0
                out_msg = mido.Message("note_on", channel=ch, note=b.control, velocity=vel)
                self._outport.send(out_msg)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Profiles & Presets
    # ------------------------------------------------------------------

    def export_profile(self) -> List[dict]:
        return [asdict(b) for b in self.bindings]

    def import_profile(self, data: List[dict]) -> None:
        self.bindings.clear()
        for item in data:
            self.bindings.append(MidiBinding(**item))

    def save_profile_file(self, filepath: str) -> bool:
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(self.export_profile(), f, indent=2)
            return True
        except Exception:
            return False

    def load_profile_file(self, filepath: str) -> bool:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.import_profile(data)
            return True
        except Exception:
            return False

    def load_preset_profile(self, preset_name: str) -> None:
        """Load curated factory mapping templates."""
        self.clear_all_bindings()

        if preset_name == "Akai APC Mini":
            # APC Mini Faders 1..9 (CC 48..56)
            self.set_binding(MidiBinding(target=MidiMappingTarget.MASTER_DIMMER.value, control=56))
            self.set_binding(MidiBinding(target=MidiMappingTarget.CROSSFADER.value, control=52))
            self.set_binding(MidiBinding(target=MidiMappingTarget.DECK_A_SPEED.value, control=48))
            self.set_binding(MidiBinding(target=MidiMappingTarget.DECK_B_SPEED.value, control=49))
            self.set_binding(MidiBinding(target=MidiMappingTarget.DECK_A_PARAM_0.value, control=50))
            self.set_binding(MidiBinding(target=MidiMappingTarget.DECK_B_PARAM_0.value, control=51))
            # APC Mini Buttons (Notes 0..15 for slots)
            for i in range(8):
                self.set_binding(MidiBinding(
                    target=f"storage_a_slot_{i+1}", msg_type="note_on", control=i, mode=MidiMode.MOMENTARY.value
                ))
                self.set_binding(MidiBinding(
                    target=f"storage_b_slot_{i+1}", msg_type="note_on", control=i+8, mode=MidiMode.MOMENTARY.value
                ))
            # Soft keys
            self.set_binding(MidiBinding(target=MidiMappingTarget.BLACKOUT.value, msg_type="note_on", control=64, mode=MidiMode.TOGGLE.value))
            self.set_binding(MidiBinding(target=MidiMappingTarget.FREEZE.value, msg_type="note_on", control=65, mode=MidiMode.TOGGLE.value))

        elif preset_name == "Korg nanoKONTROL 2":
            # nanoKONTROL 2 Faders (CC 0..7) & Knobs (CC 16..23)
            self.set_binding(MidiBinding(target=MidiMappingTarget.MASTER_DIMMER.value, control=0))
            self.set_binding(MidiBinding(target=MidiMappingTarget.CROSSFADER.value, control=1))
            self.set_binding(MidiBinding(target=MidiMappingTarget.DECK_A_SPEED.value, control=2))
            self.set_binding(MidiBinding(target=MidiMappingTarget.DECK_B_SPEED.value, control=3))
            self.set_binding(MidiBinding(target=MidiMappingTarget.DECK_A_PARAM_0.value, control=16))
            self.set_binding(MidiBinding(target=MidiMappingTarget.DECK_A_PARAM_1.value, control=17))
            self.set_binding(MidiBinding(target=MidiMappingTarget.DECK_B_PARAM_0.value, control=18))
            self.set_binding(MidiBinding(target=MidiMappingTarget.DECK_B_PARAM_1.value, control=19))
            # S/M/R Buttons (CC 32..71)
            self.set_binding(MidiBinding(target=MidiMappingTarget.BLACKOUT.value, control=32, mode=MidiMode.TOGGLE.value))
            self.set_binding(MidiBinding(target=MidiMappingTarget.FREEZE.value, control=48, mode=MidiMode.TOGGLE.value))
            self.set_binding(MidiBinding(target=MidiMappingTarget.WHITEOUT.value, control=64, mode=MidiMode.MOMENTARY.value))

        else:  # Generic Controller
            # Standard CC 1..8
            self.set_binding(MidiBinding(target=MidiMappingTarget.CROSSFADER.value, control=1))
            self.set_binding(MidiBinding(target=MidiMappingTarget.MASTER_DIMMER.value, control=7))
            self.set_binding(MidiBinding(target=MidiMappingTarget.DECK_A_SPEED.value, control=2))
            self.set_binding(MidiBinding(target=MidiMappingTarget.DECK_B_SPEED.value, control=3))
            self.set_binding(MidiBinding(target=MidiMappingTarget.DECK_A_PARAM_0.value, control=4))
            self.set_binding(MidiBinding(target=MidiMappingTarget.DECK_A_PARAM_1.value, control=5))
            self.set_binding(MidiBinding(target=MidiMappingTarget.DECK_B_PARAM_0.value, control=6))
            self.set_binding(MidiBinding(target=MidiMappingTarget.DECK_B_PARAM_1.value, control=8))
            # Notes 36..43 (C2..G2)
            self.set_binding(MidiBinding(target=MidiMappingTarget.BLACKOUT.value, msg_type="note_on", control=36, mode=MidiMode.TOGGLE.value))
            self.set_binding(MidiBinding(target=MidiMappingTarget.FREEZE.value, msg_type="note_on", control=37, mode=MidiMode.TOGGLE.value))
            self.set_binding(MidiBinding(target=MidiMappingTarget.WHITEOUT.value, msg_type="note_on", control=38, mode=MidiMode.MOMENTARY.value))
            for i in range(8):
                self.set_binding(MidiBinding(
                    target=f"storage_a_slot_{i+1}", msg_type="note_on", control=48+i, mode=MidiMode.MOMENTARY.value
                ))

