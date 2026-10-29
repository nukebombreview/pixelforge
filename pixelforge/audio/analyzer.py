"""
PixelForge — Audio Analyzer & S2L (Sound2Light) Processing Engine
Captures real-time audio from system/mic via sounddevice, performs windowed FFT,
multi-band frequency decomposition, peak hold, and transient beat detection.
"""

from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal


@dataclass
class AudioState:
    """Snapshot of the current audio spectrum and reactivity metrics."""
    level: float = 0.0          # RMS volume [0.0, 1.0]
    peak: float = 0.0           # Instantaneous peak [0.0, 1.0]
    bass: float = 0.0           # 20 - 250 Hz [0.0, 1.0]
    low_mid: float = 0.0        # 250 - 500 Hz [0.0, 1.0]
    mid: float = 0.0            # 500 - 2000 Hz [0.0, 1.0]
    high_mid: float = 0.0       # 2000 - 4000 Hz [0.0, 1.0]
    high: float = 0.0           # 4000 - 20000 Hz [0.0, 1.0]
    spectrum: np.ndarray = field(default_factory=lambda: np.zeros(64, dtype=np.float64))
    spectrum_peaks: np.ndarray = field(default_factory=lambda: np.zeros(64, dtype=np.float64))
    waveform: np.ndarray = field(default_factory=lambda: np.zeros(512, dtype=np.float64))
    is_beat: bool = False
    beat_intensity: float = 0.0  # [0.0, 1.0] strength of last beat
    bpm: float = 120.0
    gain: float = 1.0


class AudioAnalyzer(QObject):
    """Real-time sound analyzer driving all Sound2Light (S2L) effects.

    Signals
    -------
    beat_detected(float)
        Emitted on transient beat with intensity [0.0, 1.0].
    levels_updated(float, float)
        Emitted with (RMS level, Peak level) for UI VU meter.
    """

    beat_detected = pyqtSignal(float)
    levels_updated = pyqtSignal(float, float)

    DEFAULT_SAMPLE_RATE = 44100
    BUFFER_SIZE = 1024
    NUM_SPECTRUM_BANDS = 64

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)

        self.sample_rate = self.DEFAULT_SAMPLE_RATE
        self.gain: float = 1.0
        self.generator_mode: bool = False  # Offline demo beat synthesizer

        self._stream = None
        self._is_running = False
        self._lock = threading.Lock()

        # Audio buffers
        self._window = np.hanning(self.BUFFER_SIZE)
        self._raw_waveform = np.zeros(512, dtype=np.float64)
        self._smoothed_spectrum = np.zeros(self.NUM_SPECTRUM_BANDS, dtype=np.float64)
        self._peak_hold = np.zeros(self.NUM_SPECTRUM_BANDS, dtype=np.float64)
        self._current_state = AudioState()

        # Beat detection state
        self._energy_history = []
        self._last_beat_time = 0.0
        self._beat_decay = 0.0

        # Frequency band boundaries for 44.1kHz sample rate
        freqs = np.fft.rfftfreq(self.BUFFER_SIZE, d=1.0 / self.sample_rate)
        self._freqs = freqs
        self._bass_indices = np.where((freqs >= 20) & (freqs <= 250))[0]
        self._low_mid_indices = np.where((freqs > 250) & (freqs <= 500))[0]
        self._mid_indices = np.where((freqs > 500) & (freqs <= 2000))[0]
        self._high_mid_indices = np.where((freqs > 2000) & (freqs <= 4000))[0]
        self._high_indices = np.where((freqs > 4000) & (freqs <= 20000))[0]

        # Logarithmic band indices for 64 bands
        log_freqs = np.logspace(np.log10(20), np.log10(20000), self.NUM_SPECTRUM_BANDS + 1)
        self._band_bin_ranges = []
        for i in range(self.NUM_SPECTRUM_BANDS):
            low_f, high_f = log_freqs[i], log_freqs[i + 1]
            bins = np.where((freqs >= low_f) & (freqs <= high_f))[0]
            if len(bins) == 0:
                bins = [np.argmin(np.abs(freqs - low_f))]
            self._band_bin_ranges.append(bins)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self, device_index: Optional[int] = None) -> bool:
        """Start capturing audio. Returns True on success, False if fallback to generator."""
        if self._is_running:
            self.stop()

        try:
            import sounddevice as sd

            def audio_callback(indata, frames, time_info, status):
                if status:
                    pass
                # Convert to mono
                if indata.shape[1] > 1:
                    mono = np.mean(indata, axis=1)
                else:
                    mono = indata[:, 0]
                self._process_samples(mono)

            # Check if valid input device is requested
            device = device_index if device_index is not None else self._find_best_input_device()

            self._stream = sd.InputStream(
                device=device,
                channels=1 if device is None else None,
                samplerate=self.sample_rate,
                blocksize=self.BUFFER_SIZE,
                callback=audio_callback,
            )
            self._stream.start()
            self._is_running = True
            self.generator_mode = False
            return True

        except Exception as e:
            # Fall back to synthetic audio generator
            self.generator_mode = True
            self._is_running = True
            return False

    def stop(self) -> None:
        """Stop audio stream."""
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        self._is_running = False

    @property
    def is_running(self) -> bool:
        return self._is_running

    # ------------------------------------------------------------------
    # Audio Processing & Feature Extraction
    # ------------------------------------------------------------------

    def _process_samples(self, samples: np.ndarray) -> None:
        """Process incoming audio block with FFT and beat detection."""
        if len(samples) < self.BUFFER_SIZE:
            return

        chunk = samples[:self.BUFFER_SIZE].astype(np.float64) * self.gain

        # RMS & Peak
        peak = float(np.max(np.abs(chunk)))
        rms = float(np.sqrt(np.mean(chunk ** 2)))

        # Waveform ring buffer (downsampled to 512 for oscilloscope)
        step = max(1, len(chunk) // 512)
        downsampled_wave = np.clip(chunk[::step][:512], -1.0, 1.0)

        # Windowed FFT
        windowed = chunk * self._window
        fft_complex = np.fft.rfft(windowed)
        magnitudes = np.abs(fft_complex) / (self.BUFFER_SIZE / 2.0)

        # Multi-band extraction
        bass = float(np.mean(magnitudes[self._bass_indices])) * 2.5 if len(self._bass_indices) else 0.0
        low_mid = float(np.mean(magnitudes[self._low_mid_indices])) * 3.0 if len(self._low_mid_indices) else 0.0
        mid = float(np.mean(magnitudes[self._mid_indices])) * 4.0 if len(self._mid_indices) else 0.0
        high_mid = float(np.mean(magnitudes[self._high_mid_indices])) * 5.0 if len(self._high_mid_indices) else 0.0
        high = float(np.mean(magnitudes[self._high_indices])) * 8.0 if len(self._high_indices) else 0.0

        # 64-band log spectrum
        raw_spectrum = np.zeros(self.NUM_SPECTRUM_BANDS, dtype=np.float64)
        for i, bins in enumerate(self._band_bin_ranges):
            val = np.mean(magnitudes[bins]) if len(bins) > 0 else 0.0
            # Apply progressive high-frequency pre-emphasis
            boost = 1.0 + (i / self.NUM_SPECTRUM_BANDS) * 3.5
            raw_spectrum[i] = val * boost

        # Smooth spectrum with exponential decay
        decay_factor = 0.65
        self._smoothed_spectrum = np.maximum(
            raw_spectrum,
            self._smoothed_spectrum * decay_factor,
        )

        # Peak hold decay
        self._peak_hold = np.maximum(
            self._smoothed_spectrum,
            self._peak_hold - 0.02,
        )

        # Beat detection (bass energy acceleration)
        now = time.perf_counter()
        is_beat = False
        beat_intensity = 0.0

        self._energy_history.append(bass)
        if len(self._energy_history) > 40:
            self._energy_history.pop(0)

        if len(self._energy_history) >= 10:
            avg_energy = float(np.mean(self._energy_history))
            energy_variance = float(np.var(self._energy_history))
            # Dynamic sensitivity threshold
            c = -15.0 * energy_variance + 1.55
            threshold = avg_energy * max(1.15, c)

            if bass > threshold and (now - self._last_beat_time) > 0.22:
                is_beat = True
                self._last_beat_time = now
                beat_intensity = min(1.0, float((bass - avg_energy) * 2.0))
                self._beat_decay = 1.0

        if not is_beat and self._beat_decay > 0.0:
            self._beat_decay = max(0.0, self._beat_decay - 0.05)
            beat_intensity = self._beat_decay

        # Update thread-safe state
        with self._lock:
            self._raw_waveform = downsampled_wave
            self._current_state = AudioState(
                level=min(1.0, rms * 3.5),
                peak=min(1.0, peak * 2.0),
                bass=min(1.0, bass),
                low_mid=min(1.0, low_mid),
                mid=min(1.0, mid),
                high_mid=min(1.0, high_mid),
                high=min(1.0, high),
                spectrum=np.clip(self._smoothed_spectrum, 0.0, 1.0),
                spectrum_peaks=np.clip(self._peak_hold, 0.0, 1.0),
                waveform=downsampled_wave,
                is_beat=is_beat,
                beat_intensity=beat_intensity,
                bpm=128.0,
                gain=self.gain,
            )

        if is_beat:
            self.beat_detected.emit(beat_intensity)
        self.levels_updated.emit(self._current_state.level, self._current_state.peak)

    def get_state(self) -> AudioState:
        """Retrieve current audio state for effect rendering."""
        if self.generator_mode:
            return self._generate_synthetic_state()

        with self._lock:
            return self._current_state

    # ------------------------------------------------------------------
    # Synthetic Generator (for offline demo or when no mic connected)
    # ------------------------------------------------------------------

    def _generate_synthetic_state(self) -> AudioState:
        t = time.perf_counter()
        bpm = 124.0
        beat_interval = 60.0 / bpm
        phase = (t % beat_interval) / beat_interval

        is_beat = phase < 0.08
        beat_decay = max(0.0, 1.0 - phase * 3.0)

        bass = beat_decay * 0.9 + 0.1 * math.sin(t * 8.0)
        mid = 0.4 + 0.3 * math.sin(t * 14.0)
        high = 0.3 + 0.25 * math.cos(t * 22.0)
        level = (bass * 0.6 + mid * 0.3 + high * 0.1)

        # Synthetic 64-band equalizer spectrum
        bands = np.zeros(self.NUM_SPECTRUM_BANDS, dtype=np.float64)
        for i in range(self.NUM_SPECTRUM_BANDS):
            freq_factor = math.exp(-i / 18.0)
            wave = 0.5 + 0.5 * math.sin(t * 6.0 + i * 0.25)
            bands[i] = (freq_factor * bass * 0.7 + wave * mid * 0.5) * (1.0 - i / 80.0)

        # Oscilloscope wave
        wave_pts = np.sin(np.linspace(0, 4 * np.pi, 512) + t * 20.0) * level

        return AudioState(
            level=min(1.0, max(0.0, level)),
            peak=min(1.0, max(0.0, level * 1.3)),
            bass=min(1.0, max(0.0, bass)),
            low_mid=min(1.0, max(0.0, (bass + mid) * 0.5)),
            mid=min(1.0, max(0.0, mid)),
            high_mid=min(1.0, max(0.0, (mid + high) * 0.5)),
            high=min(1.0, max(0.0, high)),
            spectrum=np.clip(bands, 0.0, 1.0),
            spectrum_peaks=np.clip(bands * 1.15, 0.0, 1.0),
            waveform=wave_pts,
            is_beat=is_beat,
            beat_intensity=beat_decay,
            bpm=bpm,
            gain=self.gain,
        )

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def get_input_devices() -> list[dict[str, Any]]:
        """List all available sound input devices."""
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            results = []
            for idx, dev in enumerate(devices):
                if dev.get("max_input_channels", 0) > 0:
                    results.append({
                        "index": idx,
                        "name": dev.get("name", f"Device {idx}"),
                        "channels": dev.get("max_input_channels", 1),
                        "default_samplerate": dev.get("default_samplerate", 44100),
                    })
            return results
        except Exception:
            return []

    def _find_best_input_device(self) -> Optional[int]:
        """Automatically select Stereo Mix or default microphone."""
        devices = self.get_input_devices()
        # Prefer Stereo Mix for internal audio loopback if available
        for d in devices:
            if "stereo mix" in d["name"].lower():
                return d["index"]
        # Otherwise default input
        return None
