# PixelForge — Professional Real-Time LED Lighting Control & Pixel Mapping

**PixelForge** is a production-grade, 64-bit real-time LED lighting controller, 2D pixel mapper, and 3D volumetric voxel simulator engineered in Python (PyQt6 + NumPy). Designed as a modern, high-performance alternative to MADRIX 5, PixelForge combines a dual-deck VJ engine, hardware protocol streaming (Art-Net IV, ANSI E1.31 sACN, USB DMX512, DVI), live audio reactivity, MIDI controller integration, show cue/timeline automation, and remote control over Web/REST.

---

## Key Features & Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PIXELFORGE ARCHITECTURE                           │
├───────────────────────────────┬─────────────────────────────────────────────┤
│  CONTENT GENERATION           │  PROTOCOL ROUTING & HARDWARE INTERFACES     │
│  • 10 SCE Procedural Effects  │  • Art-Net IV (OpOutput / OpDmx UDP 6454)   │
│  • 6 S2L Sound2Light Effects  │  • ANSI E1.31 sACN (Multicast/Unicast 5568) │
│  • Media (SCE Image, Video)   │  • USB DMX512 (ENTTEC DMX USB Pro FTDI)     │
│  • Scrolling Text (SCE Ticker)│  • DVI Fullscreen Secondary Video Wall      │
│  • Live Python (MAS Script)   │  • Mobile Web Remote Dashboard & REST API   │
├───────────────────────────────┴─────────────────────────────────────────────┤
│  DUAL-DECK VJ RENDER PIPELINE                                               │
│  • Deck A (60 FPS) ───┐                                                     │
│                       ├──► [13 Blend Modes Crossfader] ──► Output (60 FPS)  │
│  • Deck B (60 FPS) ───┘                                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│  CONTROL & SHOW AUTOMATION                                                  │
│  • 256×256 Storage Places (65,536 slots) with .pxf Project Serialization   │
│  • 2D Visual Patch Editor with 4 Serpentine Snake Topologies & CSV Export   │
│  • Hardware MIDI Subsystem with MIDI Learn, APC Mini / nanoKONTROL2 Profiles │
│  • Sequential Cue List (GO / BACK / PAUSE) with S-Curve Fades & Auto-Follow │
│  • Multi-Track NLE Timeline with SMPTE & Art-Net OpTimeCode (0x9700) Sync   │
│  • Interactive 3D Volumetric Voxel Viewport with 360° Orbital Controls      │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Installation & Requirements

### System Requirements
- Windows 10/11, macOS, or Linux (64-bit)
- Python 3.10+
- OpenGL / DirectX capable graphics hardware

### Setup Virtual Environment
```bash
cd PixelForge
python -m venv .venv

# Activate on Windows (PowerShell):
.\.venv\Scripts\Activate.ps1

# Install dependencies:
pip install -r requirements.txt
```

### Dependencies
- `PyQt6` & `PyQt6-Qt6`: High-performance dark-themed modern GUI with custom styling.
- `numpy`: High-speed vectorized buffer rendering and FFT frequency binning.
- `pillow`: Image decoding, font rendering, and animated GIF parsing.
- `sounddevice`: Low-latency audio stream capture.
- `pyserial`: FTDI serial interface for USB DMX hardware interfaces.
- `mido` & `python-rtmidi`: Asynchronous, low-latency MIDI I/O.

---

## Quick Start

### Launching the Application
```bash
python run.py
```
Or double-click `run_pixelforge.bat` on Windows.

### Running Test Suites
```bash
# Complete headless engine, protocol, audio, effects & automation test suite:
python test_engine.py

# Complete off-screen GUI smoke test:
python test_gui.py
```

---

## Detailed Component Documentation

### 1. Dual-Deck Render Engine & Crossfader
- **Deck A & Deck B**: Mirror pipelines running independent visual effects at 60 FPS.
- **Crossfader Slider**: Horizontal slider (0.0 = 100% Deck A, 1.0 = 100% Deck B).
- **13 Professional Blend Modes**:
  1. `FADE`: Standard linear crossfade.
  2. `EQUAL_POWER`: Constant-luminance sine/cosine acoustic fade curve.
  3. `HARD_CUT`: Sudden step transition at center threshold.
  4. `WIPE_LEFT`: Horizontal wipe from right to left.
  5. `WIPE_RIGHT`: Horizontal wipe from left to right.
  6. `WIPE_UP`: Vertical wipe from bottom to top.
  7. `WIPE_DOWN`: Vertical wipe from top to bottom.
  8. `ADD`: Clamped additive color blend.
  9. `MULTIPLY`: Multiplicative normalized luminance blend.
  10. `MAXIMUM`: Per-channel maximum color pass-through.
  11. `MINIMUM`: Per-channel minimum color pass-through.
  12. `OVERLAY`: Contrast-enhancing photographic overlay blend.
  13. `DIFFERENCE`: Subtractive inversion comparison.

### 2. Comprehensive Effects Library (20 Built-in Effects)

#### Static & Procedural Color Effects (SCE)
1. **SCE Color**: Solid single-color wash with adjustable RGB channels.
2. **SCE Color Scroll**: Smooth linear color gradients scrolling at controllable angles and speeds.
3. **SCE Wave**: Sinusoidal color wave ripples with frequency, phase, and amplitude controls.
4. **SCE Drops**: Simulated water ripples expanding outward from random coordinate impacts.
5. **SCE Rainbow**: Multicolored continuous spectral shift across rows or columns.
6. **SCE Plasma**: Trigonometric multi-frequency fluid plasma interference patterns.
7. **SCE Fire**: Realistic procedural cellular fire simulation with upward cooling drift and sparks.
8. **SCE Starfield**: 3D parallax hyperspace warp drive star flight effect.
9. **SCE Checkerboard**: Alternating dual-color grid tiles with animated scrolling offsets.
10. **SCE Strobe**: High-intensity strobe with adjustable frequency (Hz), duty cycle, and color flash.

#### Sound2Light Audio-Reactive Effects (S2L)
11. **S2L Level**: Classic multi-band or stereo LED level meter reacting to instantaneous audio peak power.
12. **S2L Level Shape**: Expanding geometric rings (circle, diamond, square) pulsed by bass beat transients.
13. **S2L Spectrum**: 64-band logarithmic FFT graphic equalizer bars with smooth decay and peak holds.
14. **S2L Waveform**: Live oscilloscope audio waveform oscilloscope rendering with glow trace.
15. **S2L Flash**: Beat-reactive strobe firing flashes synchronously on bass drum detections.
16. **S2L Drops**: Liquid drops spawned and accelerated dynamically by audio peak energy bursts.

#### Media Playback, Marquee & Live Scripting (SCE / MAS)
17. **SCE Image**: High-resolution image renderer with support for external PNG/JPG/BMP files or built-in test patterns (SMPTE Color Bars, PixelForge Logo, Radial Gradient, Checker). Features `FIT`, `FILL`, `STRETCH`, and `TILE` scaling, continuous 360° rotation, and pan/zoom offsets.
18. **SCE Ticker**: Scrolling marquee text banner with configurable font size, foreground/background colors, speed, and 4 scroll directions (`LEFT`, `RIGHT`, `UP`, `DOWN`).
19. **SCE Video**: Animated media player supporting animated GIF files as well as built-in procedural visual loops:
    - *Techno Tunnel*: Infinite 3D perspective wireframe tunnel with depth lines.
    - *Radar Sweep*: Rotating sweeping radar beam with phosphor decay trails.
    - *Retro Grid*: 80s synthwave perspective grid horizon with glowing sunset.
20. **MAS Script**: Python live scripting sandbox with dynamic hot-reloading, per-frame execution, and built-in safe exception capture. Bundled with 4 factory scripts:
    - *RGB Spiral*: Hypnotic logarithmic Archimedean spiral.
    - *Sine Interference*: Overlapping wave interference moiré patterns.
    - *Audio Plasma*: Frequency-modulated audio-reactive plasma formula.
    - *Digital Matrix Rain*: Classic cascading glowing green binary glyph streaks.

### 3. Hardware Protocols & Network Output

| Protocol | Transport | Port / Rate | Description |
|:---|:---|:---|:---|
| **Art-Net IV** | UDP Broadcast / Unicast | Port 6454 | `OpOutput` / `OpDmx` packet packaging, up to 512 channels per universe, subnet/universe addressing. |
| **ANSI E1.31 sACN** | UDP Multicast / Unicast | Port 5568 | Full 3-layer architecture (Root, Framing, DMP), multicast address calculation (`239.255.u.u`), sequence numbering, and priority control (0–200). |
| **USB DMX512** | FTDI Serial COM Port | 250,000 baud | ENTTEC DMX USB Pro protocol framing: SOM (`0x7E`), Label 6, Length LSB/MSB, Start Code (`0x00`), Channels (1–512), EOM (`0xE7`). |
| **DVI Output** | Win32 / Qt Frameless Window | Native Refresh | Borderless fullscreen display on secondary monitors, projectors, or LED video processors (Novastar, Brompton, Colorlight). |
| **HTTP Remote** | TCP HTTP / REST | Port 8080 | Lightweight built-in web server serving an HTML5 mobile remote dashboard and JSON REST API. |

### 4. Visual 2D Patch Editor & Matrix Generator
- **Built-in Fixture Profiles & Templates**:
  - `5m LED Rope Light`: 80 pixels across 5 meters, 240 DMX channels, native **GRB** channel order for Unreal Engine (`BP_5mRopeLight`) and QLC+.
  - `16x16 RGB Panel`: Modular 256-pixel panel for video walls.
  - `1m LED Strip`: 60-pixel digital tape.
- **Flexible Matrix Generator**: Quickly generates fixture grids across any width, height, and starting address.
- **Wiring Topologies**:
  - `Horizontal Snake`: Alternating left-to-right and right-to-left rows (standard LED strip tape zig-zag).
  - `Vertical Snake`: Alternating top-to-bottom and bottom-to-top columns.
  - `Row-by-Row`: Left-to-right raster scan across every row.
  - `Column-by-Column`: Top-to-bottom raster scan down each column.
- **Fixture DMX Offsets**: Automatic universe boundary wrapping (e.g. 512 DMX channels per universe) with configurable color ordering (`RGB`, `GRB`, `BGR`, `RGBW`).
- **Stage Production Export**: Export and import entire patch tables to and from industry-standard CSV files.

### 5. Storage Places & `.pxf` Project Files
- **Storage Place Matrix**: 256 banks × 256 slots = 65,536 total preset locations per deck.
- **State Capture**: Stores effect type, all parameter values, colors, filter configurations, and layer metadata.
- **Instant Recall**: One-click recall with preview thumbnails and Deck A / Deck B routing buttons.
- **Project Serialization (`.pxf`)**: JSON-structured project file storing matrix settings, audio thresholds, patch layouts, storage places, cue lists, and timeline automation.
- **Factory Presets**: Built-in curated banks:
  - *Bank 1: Acid Club* (Neon strobes, high-energy plasma, fast color sweeps).
  - *Bank 2: Cyberpunk* (Cyan/magenta waveforms, dark retro grids, neon starfields).
  - *Bank 3: Ambient Chill* (Warm embers, deep ocean waves, slow liquid drops).
  - *Bank 4: Audio Reactive* (Equalizer bars, beat-pulsed diamonds, sub-bass strobe).

### 6. Hardware MIDI Subsystem
- **Low-Latency Asynchronous Engine**: Backed by `mido` and `python-rtmidi`.
- **Interactive MIDI Learn**: Click any UI parameter (Crossfader, Master Dimmer, Blackout, Effect Knobs), press "MIDI Learn", and move any physical hardware slider or knob to establish instantaneous binding.
- **Bidirectional Hardware Feedback**: Sends status sysex / note-on messages back to hardware controllers to light up physical button LEDs (e.g., active cue, blackout status, beat blinker).
- **Hardware Profile Templates**:
  - *Akai APC Mini*: 8×8 button matrix storage place launch, 8 track volume faders, master fader.
  - *Korg nanoKONTROL 2*: Transport buttons (PLAY, STOP, REC), 8 rotary knobs, 8 sliders, MUTE/SOLO buttons.
- **Live MIDI Watcher**: Real-time diagnostic window displaying incoming channel, message type, control number, value, and timestamp, equipped with a virtual signal generator for staging without physical hardware.

### 7. Show Automation (Cue List & Timeline)
- **Sequential Cue List**:
  - Transport controls: **GO**, **BACK**, **PAUSE**, **STOP**.
  - Fade Time (0.0s to 60.0s) with smooth S-curve cosine crossfading.
  - Hold Time with live countdown display.
  - Auto-Follow trigger mode for unattended architectural or club sequences.
- **Multi-Track NLE Timeline**:
  - Tracks: Deck A Slot, Deck B Slot, Crossfader Curve, Master Dimmer Curve.
  - Keyframe interpolation: Linear, Cosine Smooth, Instant Jump.
  - Scrubbable playhead with live matrix output preview.
- **SMPTE Timecode & Art-Net Sync**:
  - Full SMPTE frame timecode formatting (`HH:MM:SS:FF`) at 24, 25, 29.97, and 30 FPS.
  - Art-Net `OpTimeCode` (0x9700) broadcast and reception for external grandMA / ChamSys / QLab lighting desk synchronization.

### 8. 3D Volumetric Voxel Visualizer & Web Remote
- **3D Orbital Voxel Viewport**:
  - Switch any preview window (Deck A, Deck B, Output) into 3D Volumetric Voxel mode.
  - Drag mouse to rotate (Yaw and Pitch orbital navigation).
  - Volumetric depth sorting with 3D coordinate projection and perspective scaling.
  - Subtle 3D perspective ground reference grid.
- **Mobile Web Remote Dashboard**:
  - Access at `http://localhost:8080` (or local IP) from any smartphone, tablet, or web browser.
  - Responsive dark UI with touch-friendly controls.
  - Real-time status polling (FPS, Master Dimmer, Crossfader position, active cues).
  - Control Crossfader, Master Dimmer, Blackout, Freeze, and trigger Cue List **GO** / **BACK** remotely.

---

## REST API Reference

When the built-in HTTP server is active, external systems (Bitfocus Companion, TouchOSC, Node-RED, custom web apps) can monitor and control PixelForge via JSON REST endpoints:

### Endpoints
- `GET /` — Serves the interactive mobile Web Remote dashboard.
- `GET /api/status` — Returns system status, matrix dimensions, render FPS, crossfader position, blackout state, and current cue.
- `POST /api/crossfader` — Set crossfader position (`{"position": 0.0 - 1.0}`).
- `POST /api/dimmer` — Set master dimmer brightness (`{"dimmer": 0.0 - 1.0}`).
- `POST /api/blackout` — Toggle blackout (`{"blackout": true | false}`).
- `POST /api/freeze` — Toggle output freeze (`{"freeze": true | false}`).
- `POST /api/cue/go` — Trigger next cue or jump to specific index (`{"index": 0}`).
- `POST /api/cue/back` — Step back to previous cue.
- `POST /api/cue/pause` — Pause running cue fade/hold.
- `POST /api/cue/stop` — Stop cue player.

---

## File Structure

```
PixelForge/
├── pixelforge/
│   ├── audio/
│   │   └── analyzer.py          # Sounddevice capture, 64-band FFT, beat detector
│   ├── core/
│   │   ├── crossfader.py        # 13 hardware blend modes & T-Bar crossfader
│   │   ├── cue.py               # Cue List data model & transport player
│   │   ├── deck.py              # Visual deck pipeline & layer management
│   │   ├── engine.py            # 60 FPS master render loop & frame dispatcher
│   │   ├── matrix.py            # NumPy pixel matrix buffer (uint8 RGB)
│   │   ├── patch.py             # DMX routing & serpentine snake matrix patcher
│   │   ├── storage.py           # 256x256 storage places & .pxf project serializer
│   │   └── timeline.py          # Multi-track NLE timeline & SMPTE/Art-Net timecode
│   ├── effects/
│   │   ├── base.py              # BaseEffect abstract class & Parameter metadata
│   │   ├── mas_script.py        # MAS Python live code sandbox & factory scripts
│   │   ├── s2l_*.py             # 6 Sound2Light audio-reactive effects
│   │   ├── sce_*.py             # 10 procedural SCE effects
│   │   ├── sce_image.py         # Image playback (PNG/JPG/test patterns)
│   │   ├── sce_ticker.py        # Marquee scrolling text banner
│   │   └── sce_video.py         # GIF player & procedural video loops
│   ├── midi/
│   │   └── manager.py           # Low-latency MIDI I/O, MIDI Learn, device profiles
│   ├── protocols/
│   │   ├── artnet.py            # Art-Net IV OpOutput packet encoder
│   │   ├── dvi_output.py        # Frameless DVI video wall output window
│   │   ├── http_server.py       # REST API server & HTML5 mobile web remote
│   │   ├── manager.py           # Multi-protocol broadcast coordinator
│   │   ├── sacn.py              # ANSI E1.31 sACN multicast/unicast transmitter
│   │   └── usb_dmx.py           # ENTTEC DMX USB Pro FTDI serial driver
│   └── ui/
│       ├── audio_dialog.py      # Audio input device & FFT band tuning dialog
│       ├── cue_dialog.py        # Cue List & Multi-track Timeline UI window
│       ├── deck_panel.py        # Deck control panel with effect selection
│       ├── dvi_dialog.py        # DVI output monitor configuration dialog
│       ├── effect_panel.py      # Dynamic parameter control panel with string support
│       ├── main_window.py       # Complete PixelForge desktop application window
│       ├── midi_dialog.py       # MIDI setup, controller mapping & live watcher UI
│       ├── patch_editor.py      # Visual 2D Patch Editor with interactive grid
│       ├── preview_widget.py    # High-DPI LED 2D Dot Matrix & 3D Voxel Viewport
│       ├── protocol_dialog.py   # Multi-protocol routing configuration dialog
│       ├── storage_grid.py      # 256x256 storage place visual preset grid
│       ├── styles.py            # Modern dark pro-audio stylesheet constants
│       └── vu_meter.py          # Stereo & multi-band LED VU meter widgets
├── requirements.txt             # Locked Python package specifications
├── run.py                       # Desktop launcher
├── run_pixelforge.bat           # Windows quick-launch script
├── test_artnet_live.py          # Hardware Art-Net live network verification
├── test_engine.py               # Comprehensive headless test suite (100% PASS)
└── test_gui.py                  # Off-screen GUI rendering & dialogs test (100% PASS)
```

---

## License

PixelForge is distributed under the MIT License.

