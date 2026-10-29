"""
PixelForge — Multi-Track Timeline & Timecode Synchronization Engine
NLE-style multi-track sequencing, SMPTE / Art-Net Timecode synchronization,
and real-time parameter automation.
"""

from __future__ import annotations

import math
import struct
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from PyQt6.QtCore import QObject, QTimer, pyqtSignal


class TimecodeType(int, Enum):
    FPS_24 = 0    # 24 fps (Film)
    FPS_25 = 1    # 25 fps (EBU / PAL)
    FPS_29_97 = 2 # 29.97 fps (NTSC Drop-Frame)
    FPS_30 = 3    # 30 fps (SMPTE)


@dataclass
class Timecode:
    """SMPTE timecode representation (Hours:Minutes:Seconds:Frames)."""

    hours: int = 0
    minutes: int = 0
    seconds: int = 0
    frames: int = 0
    fps: float = 30.0

    @classmethod
    def from_seconds(cls, total_seconds: float, fps: float = 30.0) -> Timecode:
        if total_seconds < 0:
            total_seconds = 0.0
        hrs = int(total_seconds // 3600)
        rem = total_seconds % 3600
        mins = int(rem // 60)
        secs = int(rem % 60)
        frac = rem - int(rem)
        frms = int(frac * fps)
        return cls(hours=hrs, minutes=mins, seconds=secs, frames=frms, fps=fps)

    def to_seconds(self) -> float:
        return self.hours * 3600.0 + self.minutes * 60.0 + self.seconds + (self.frames / max(1.0, self.fps))

    def to_string(self) -> str:
        return f"{self.hours:02d}:{self.minutes:02d}:{self.seconds:02d}:{self.frames:02d}"

    def __str__(self) -> str:
        return self.to_string()


class ArtNetTimecode:
    """Parser & builder for Art-Net OpTimeCode (OpCode 0x9700) packets."""

    OPCODE_TIMECODE = 0x9700

    @staticmethod
    def build_packet(timecode: Timecode) -> bytes:
        """Construct an Art-Net OpTimeCode packet."""
        pkt = bytearray()
        pkt.extend(b"Art-Net\x00")                    # ID (8 bytes)
        pkt.extend(struct.pack("<H", 0x9700))          # OpCode 0x9700 (little endian)
        pkt.extend(struct.pack(">H", 14))              # ProtVer 14
        pkt.extend(b"\x00\x00")                        # Filler 1 & 2
        pkt.append(timecode.frames & 0xFF)             # Frames
        pkt.append(timecode.seconds & 0xFF)            # Seconds
        pkt.append(timecode.minutes & 0xFF)            # Minutes
        pkt.append(timecode.hours & 0xFF)              # Hours

        tc_type = TimecodeType.FPS_30
        if abs(timecode.fps - 24.0) < 0.1:
            tc_type = TimecodeType.FPS_24
        elif abs(timecode.fps - 25.0) < 0.1:
            tc_type = TimecodeType.FPS_25
        elif abs(timecode.fps - 29.97) < 0.1:
            tc_type = TimecodeType.FPS_29_97
        pkt.append(int(tc_type))                       # Type
        return bytes(pkt)

    @staticmethod
    def parse_packet(data: bytes, fps: float = 30.0) -> Optional[Timecode]:
        """Parse Art-Net OpTimeCode payload."""
        if len(data) < 19 or not data.startswith(b"Art-Net\x00"):
            return None
        opcode = struct.unpack("<H", data[8:10])[0]
        if opcode != 0x9700:
            return None

        frames = data[14]
        seconds = data[15]
        minutes = data[16]
        hours = data[17]
        tc_type = data[18]

        type_to_fps = {0: 24.0, 1: 25.0, 2: 29.97, 3: 30.0}
        actual_fps = type_to_fps.get(tc_type, fps)
        return Timecode(hours=hours, minutes=minutes, seconds=seconds, frames=frames, fps=actual_fps)


class TimelineTrackType(str, Enum):
    DECK_A = "deck_a"
    DECK_B = "deck_b"
    CROSSFADER = "crossfader"
    MASTER_DIMMER = "master_dimmer"


@dataclass
class TimelineClip:
    """A single automation clip placed on a timeline track."""

    clip_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    track_type: str = TimelineTrackType.DECK_A.value
    name: str = "Clip"
    start_time: float = 0.0    # In seconds
    duration: float = 5.0      # In seconds
    color: str = "#00d2ff"     # HEX visual color

    # Payload parameters:
    # For Deck: {"bank": 0, "slot": 0, "effect_name": "S2L Spectrum"}
    # For Curve (Crossfader / Dimmer): {"start_val": 0.0, "end_val": 1.0, "curve": "linear"}
    properties: Dict[str, Any] = field(default_factory=dict)

    @property
    def end_time(self) -> float:
        return self.start_time + self.duration

    def contains(self, t: float) -> bool:
        return self.start_time <= t < self.end_time

    def get_progress(self, t: float) -> float:
        if self.duration <= 0.0:
            return 1.0
        return max(0.0, min(1.0, (t - self.start_time) / self.duration))

    def evaluate_curve(self, t: float) -> float:
        """Evaluate continuous value for automation tracks (Crossfader, Master Dimmer)."""
        prog = self.get_progress(t)
        start_v = float(self.properties.get("start_val", 0.0))
        end_v = float(self.properties.get("end_val", 1.0))
        curve = self.properties.get("curve", "linear")

        if curve == "smooth":
            # Cosine ease-in-out
            s_prog = 0.5 * (1.0 - math.cos(math.pi * prog))
            return start_v + s_prog * (end_v - start_v)
        elif curve == "hold_start":
            return start_v
        elif curve == "hold_end":
            return end_v
        else:  # Linear
            return start_v + prog * (end_v - start_v)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TimelineClip:
        return cls(**data)


@dataclass
class TimelineTrack:
    """An individual horizontal track on the timeline canvas."""

    track_id: str
    name: str
    track_type: str = TimelineTrackType.DECK_A.value
    clips: List[TimelineClip] = field(default_factory=list)
    muted: bool = False

    def add_clip(self, clip: TimelineClip) -> None:
        clip.track_type = self.track_type
        self.clips.append(clip)
        self.clips.sort(key=lambda c: c.start_time)

    def remove_clip(self, clip_id: str) -> Optional[TimelineClip]:
        for i, c in enumerate(self.clips):
            if c.clip_id == clip_id:
                return self.clips.pop(i)
        return None

    def get_clip_at(self, t: float) -> Optional[TimelineClip]:
        for c in self.clips:
            if c.contains(t):
                return c
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "track_id": self.track_id,
            "name": self.name,
            "track_type": self.track_type,
            "clips": [c.to_dict() for c in self.clips],
            "muted": self.muted,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TimelineTrack:
        clips = [TimelineClip.from_dict(c) for c in data.get("clips", [])]
        return cls(
            track_id=data["track_id"],
            name=data["name"],
            track_type=data["track_type"],
            clips=clips,
            muted=data.get("muted", False),
        )


class Timeline:
    """Complete multi-track show arrangement."""

    def __init__(self, duration: float = 300.0, fps: float = 30.0):
        self.duration: float = duration  # Total length in seconds (default 5 minutes)
        self.fps: float = fps
        self.tracks: List[TimelineTrack] = []
        self._init_default_tracks()

    def _init_default_tracks(self) -> None:
        self.tracks = [
            TimelineTrack(track_id="tr_deck_a", name="Deck A Presets", track_type=TimelineTrackType.DECK_A.value),
            TimelineTrack(track_id="tr_deck_b", name="Deck B Presets", track_type=TimelineTrackType.DECK_B.value),
            TimelineTrack(track_id="tr_xfade", name="Crossfader Curve", track_type=TimelineTrackType.CROSSFADER.value),
            TimelineTrack(track_id="tr_dimmer", name="Master Dimmer", track_type=TimelineTrackType.MASTER_DIMMER.value),
        ]

    def get_track(self, track_type: str) -> Optional[TimelineTrack]:
        for tr in self.tracks:
            if tr.track_type == track_type:
                return tr
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "duration": self.duration,
            "fps": self.fps,
            "tracks": [t.to_dict() for t in self.tracks],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Timeline:
        tl = cls(duration=data.get("duration", 300.0), fps=data.get("fps", 30.0))
        tl.tracks = [TimelineTrack.from_dict(t) for t in data.get("tracks", [])]
        return tl


class TimelinePlayer(QObject):
    """Transport and real-time execution engine for multi-track timeline."""

    time_updated = pyqtSignal(float, str)       # (current_seconds, "HH:MM:SS:FF")
    play_state_changed = pyqtSignal(bool)       # is_playing
    clip_triggered = pyqtSignal(str, object)    # (track_type, TimelineClip)
    crossfader_automated = pyqtSignal(float)    # crossfader target (0..1)
    dimmer_automated = pyqtSignal(float)        # dimmer target (0..1)

    def __init__(self, timeline: Optional[Timeline] = None, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.timeline = timeline if timeline is not None else Timeline()

        self.current_time: float = 0.0
        self.is_playing: bool = False
        self.timecode_source: str = "internal"  # "internal" | "artnet"

        self._last_perf_time: float = 0.0
        self._active_clips: Dict[str, Optional[str]] = {
            TimelineTrackType.DECK_A.value: None,
            TimelineTrackType.DECK_B.value: None,
        }

        # 60 FPS transport update loop
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)

    # ------------------------------------------------------------------
    # Transport Operations
    # ------------------------------------------------------------------

    def play(self) -> None:
        if self.is_playing:
            return
        self.is_playing = True
        self._last_perf_time = time.perf_counter()
        self._timer.start()
        self.play_state_changed.emit(True)

    def pause(self) -> None:
        if not self.is_playing:
            return
        self.is_playing = False
        self._timer.stop()
        self.play_state_changed.emit(False)

    def stop(self) -> None:
        self.pause()
        self.seek(0.0)

    def seek(self, target_seconds: float) -> None:
        self.current_time = max(0.0, min(self.timeline.duration, target_seconds))
        tc = Timecode.from_seconds(self.current_time, self.timeline.fps)
        self.time_updated.emit(self.current_time, tc.to_string())
        self._evaluate_tracks()

    def set_timecode(self, tc: Timecode) -> None:
        """External sync injection (Art-Net / MIDI timecode)."""
        self.seek(tc.to_seconds())

    # ------------------------------------------------------------------
    # Clock Tick & Track Evaluation
    # ------------------------------------------------------------------

    def _tick(self) -> None:
        if not self.is_playing:
            return

        now = time.perf_counter()
        dt = now - self._last_perf_time
        self._last_perf_time = now

        if self.timecode_source == "internal":
            self.current_time += dt
            if self.current_time >= self.timeline.duration:
                self.current_time = 0.0  # Loop timeline

        tc = Timecode.from_seconds(self.current_time, self.timeline.fps)
        self.time_updated.emit(self.current_time, tc.to_string())
        self._evaluate_tracks()

    def _evaluate_tracks(self) -> None:
        """Inspect all timeline tracks and dispatch automation commands."""
        for track in self.timeline.tracks:
            if track.muted:
                continue

            clip = track.get_clip_at(self.current_time)

            if track.track_type in (TimelineTrackType.DECK_A.value, TimelineTrackType.DECK_B.value):
                # Trigger preset recall when entering a new clip
                last_clip_id = self._active_clips.get(track.track_type)
                current_clip_id = clip.clip_id if clip else None

                if current_clip_id != last_clip_id:
                    self._active_clips[track.track_type] = current_clip_id
                    if clip:
                        self.clip_triggered.emit(track.track_type, clip)

            elif track.track_type == TimelineTrackType.CROSSFADER.value:
                if clip:
                    val = clip.evaluate_curve(self.current_time)
                    self.crossfader_automated.emit(val)

            elif track.track_type == TimelineTrackType.MASTER_DIMMER.value:
                if clip:
                    val = clip.evaluate_curve(self.current_time)
                    self.dimmer_automated.emit(val)

