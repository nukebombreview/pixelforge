"""
PixelForge — Headless Smoke Test & Verification Suite
Verifies all 16 effects (SCE + S2L), audio FFT decomposition, beat detection,
blending modes, matrix operations, and Art-Net packet building.
"""

from __future__ import annotations

import sys
import os
import time
import json
import numpy as np

# Ensure root on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pixelforge.core.matrix import PixelMatrix
from pixelforge.core.crossfader import Crossfader, BlendMode
from pixelforge.core.deck import Deck
from pixelforge.core.cue import Cue, CueList, CuePlayer, CuePlayerState
from pixelforge.core.timeline import (
    Timecode,
    ArtNetTimecode,
    Timeline,
    TimelineClip,
    TimelineTrack,
    TimelineTrackType,
    TimelinePlayer,
)
from pixelforge.core.storage import StoragePlace, StorageBank, ProjectFile, populate_factory_presets
from pixelforge.core.patch import Fixture, Patch, PixelRouting
from pixelforge.effects import EFFECT_REGISTRY, create_effect, get_effect_names
from pixelforge.protocols.artnet import ArtNetOutput
from pixelforge.protocols.sacn import sACNOutput
from pixelforge.protocols.usb_dmx import UsbDmxOutput
from pixelforge.protocols.manager import ProtocolManager
from pixelforge.audio.analyzer import AudioAnalyzer, AudioState
from pixelforge.midi.manager import (
    MidiManager,
    MidiMessage,
    MidiBinding,
    MidiMode,
    MidiMappingTarget,
    midi_note_to_name,
)


def test_matrix():
    print("Testing PixelMatrix...")
    m = PixelMatrix(32, 32)
    assert m.buffer.shape == (32, 32, 3)
    assert m.buffer.dtype == np.uint8

    m.fill(255, 100, 50)
    assert m.get_pixel(0, 0) == (255, 100, 50)
    assert m.get_pixel(31, 31) == (255, 100, 50)

    dimmed = m.apply_master_dimmer(0.5)
    assert dimmed.get_pixel(0, 0) == (127, 50, 25)

    dmx = m.to_dmx_bytes("RGB")
    assert len(dmx) == 32 * 32 * 3
    print("[PASS] PixelMatrix tests passed!")


def test_audio_analyzer():
    print("Testing AudioAnalyzer & FFT Processing...")
    analyzer = AudioAnalyzer()
    analyzer.generator_mode = True

    state = analyzer.get_state()
    assert isinstance(state, AudioState)
    assert len(state.spectrum) == 64
    assert len(state.waveform) == 512
    assert 0.0 <= state.level <= 1.0
    assert 0.0 <= state.bass <= 1.0

    # Test processing arbitrary audio samples at 44.1kHz
    t = np.arange(1024) / 44100.0
    # 100Hz sine wave (bass) + 2000Hz (mid)
    samples = 0.6 * np.sin(2 * np.pi * 100 * t) + 0.3 * np.sin(2 * np.pi * 2000 * t)
    analyzer.generator_mode = False
    analyzer._process_samples(samples)

    live_state = analyzer.get_state()
    assert live_state.bass > 0.05, f"Expected bass energy, got {live_state.bass}"
    assert live_state.level > 0.05, f"Expected RMS level, got {live_state.level}"

    print("[PASS] AudioAnalyzer FFT decomposition verified!")


def test_all_effects():
    print("Testing 16 Procedural & S2L Effects...")
    names = get_effect_names()
    assert len(names) >= 16, f"Expected at least 16 effects, got {len(names)}: {names}"

    analyzer = AudioAnalyzer()
    analyzer.generator_mode = True
    audio_state = analyzer.get_state()

    for name in names:
        eff = create_effect(name, 32, 32)
        eff.audio_state = audio_state
        params = {p.name: p.default for p in eff.parameters}
        frame = eff.render(32, 32, 1.5, params)
        assert isinstance(frame, np.ndarray), f"{name} did not return ndarray"
        assert frame.shape == (32, 32, 3), f"{name} shape mismatch: {frame.shape}"
        assert frame.dtype == np.uint8, f"{name} dtype mismatch: {frame.dtype}"
        print(f"  [PASS] Effect: {name:<20} rendered valid frame")

    print("[PASS] All 16 effects passed!")


def test_crossfader_blend_modes():
    print("Testing Crossfader Blend Modes...")
    cf = Crossfader()
    m_a = PixelMatrix(16, 16)
    m_a.fill(200, 50, 0)

    m_b = PixelMatrix(16, 16)
    m_b.fill(0, 50, 200)

    for mode in BlendMode:
        cf.blend_mode = mode
        cf.position = 0.5
        out = cf.mix(m_a, m_b)
        assert out.buffer.shape == (16, 16, 3)
        assert out.buffer.dtype == np.uint8
        print(f"  [PASS] BlendMode: {mode.name:<12} mixed successfully")

    print("[PASS] Crossfader tests passed!")


def test_artnet_packets():
    print("Testing Art-Net Protocol Packaging...")
    an = ArtNetOutput(target_ip="127.0.0.1", port=6454, start_universe=0)
    matrix = PixelMatrix(32, 32)
    matrix.fill(255, 0, 128)

    # 32x32 = 1024 pixels = 3072 channels
    # 3072 / 510 = 6 chunks of 510 + 1 chunk of 12 = 7 universes
    dmx_data = matrix.to_dmx_bytes("RGB")
    assert len(dmx_data) == 3072

    packet_0 = an.build_packet(universe=0, dmx_data=dmx_data[:510])
    assert packet_0.startswith(b"Art-Net\x00")
    # OpCode 0x5000 in little endian
    assert packet_0[8:10] == b"\x00\x50"
    # ProtVer 14 in big endian
    assert packet_0[10:12] == b"\x00\x0e"
    # Universe byte (SubUni)
    assert packet_0[14] == 0
    # Length big endian
    assert packet_0[16:18] == b"\x01\xfe" # 510 in hex = 0x01FE
    assert len(packet_0) == 18 + 510

    packet_1 = an.build_packet(universe=1, dmx_data=dmx_data[510:1020])
    assert packet_1[14] == 1

    print("[PASS] Art-Net packet validation passed!")


def test_storage_and_project():
    print("Testing Storage Places & Project Management...")
    bank_a = StorageBank(64)
    bank_b = StorageBank(64)
    populate_factory_presets(bank_a, bank_b)

    # Validate populated presets
    assert not bank_a.places[0].is_empty
    assert bank_a.places[0].effect_name == "S2L Spectrum"
    assert not bank_b.places[0].is_empty
    assert bank_b.places[0].effect_name == "S2L Level Shape"

    # Test storing deck state
    deck = Deck("A", 32, 32)
    eff = create_effect("SCE Fire", 32, 32)
    deck.effect = eff
    deck.set_param("cooling", 0.08)
    deck.speed = 1.7

    bank_a.store_deck(10, deck, name="My Hot Fire", color="#ff1100")
    p10 = bank_a.get_place(10)
    assert p10 is not None
    assert p10.name == "My Hot Fire"
    assert p10.effect_name == "SCE Fire"
    assert p10.params["cooling"] == 0.08
    assert p10.speed == 1.7
    assert p10.color == "#ff1100"

    # Test project JSON serialization
    from pixelforge.core.engine import RenderEngine
    engine = RenderEngine(32, 32)
    project_data = ProjectFile.create_project_data(engine, bank_a, bank_b)
    assert project_data["format"] == "PixelForgeProject"
    assert len(project_data["storage_a"]) == 64
    assert len(project_data["storage_b"]) == 64

    # Save to temp file and load back
    test_pxf = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_temp.pxf")
    try:
        ok = ProjectFile.save(test_pxf, project_data)
        assert ok, "ProjectFile.save returned False"

        loaded = ProjectFile.load(test_pxf)
        assert loaded is not None
        assert loaded["format"] == "PixelForgeProject"
        assert loaded["storage_a"][10]["name"] == "My Hot Fire"
        print("[PASS] Storage places and .pxf project file verified!")
    finally:
        if os.path.exists(test_pxf):
            os.remove(test_pxf)


def test_patch_engine():
    print("Testing Patch & DMX Routing Engine...")
    patch = Patch(32, 32)

    # Test matrix generator (2x2 grid of 16x16 panels)
    patch.generate_matrix(
        cols=2,
        rows=2,
        tile_w=16,
        tile_h=16,
        start_universe=0,
        start_channel=1,
        channel_order="RGB",
        routing=PixelRouting.HORIZONTAL_SNAKE,
    )
    assert len(patch.fixtures) == 4, f"Expected 4 panels, got {len(patch.fixtures)}"
    f0 = patch.fixtures[0]
    assert f0.width == 16 and f0.height == 16
    assert f0.pixel_count == 256
    assert f0.total_channels == 768

    # Verify snake pixel order: row 0 is 0..15, row 1 is 15..0
    seq = f0.get_pixel_sequence()
    assert seq[0] == (0, 0)
    assert seq[15] == (15, 0)
    assert seq[16] == (15, 1) # Snake reversed!
    assert seq[31] == (0, 1)

    # Test mapping rendering to DMX universes
    matrix = PixelMatrix(32, 32)
    matrix.fill(200, 100, 50)
    dmx_dict = patch.render_to_dmx(matrix)
    assert len(dmx_dict) >= 6, f"Expected at least 6 universes, got {len(dmx_dict)}"
    for u, u_bytes in dmx_dict.items():
        assert len(u_bytes) == 512, f"Expected 512 bytes for universe {u}, got {len(u_bytes)}"

    # Test CSV export and re-import
    csv_str = patch.export_csv()
    assert "Panel [1,1]" in csv_str
    new_patch = Patch()
    ok = new_patch.import_csv(csv_str)
    assert ok, "import_csv failed"
    assert len(new_patch.fixtures) == 4
    assert new_patch.fixtures[0].routing == PixelRouting.HORIZONTAL_SNAKE

    print("[PASS] Visual Patch & DMX Routing Engine verified!")


def test_protocols():
    print("Testing Multi-Protocol Output (sACN, USB DMX, ProtocolManager)...")
    
    # --- sACN ANSI E1.31 ---
    sacn = sACNOutput(start_universe=1, priority=120)
    assert sacn.get_multicast_ip(1) == "239.255.0.1"
    assert sacn.get_multicast_ip(258) == "239.255.1.2"
    
    dmx_data = b"\xaa" * 512
    p1 = sacn.build_packet(universe=1, dmx_data=dmx_data)
    assert len(p1) == 638, f"Expected 638 bytes sACN packet, got {len(p1)}"
    assert p1[:2] == b"\x00\x10"                   # Preamble
    assert p1[2:4] == b"\x00\x00"                   # Postamble
    assert p1[4:16] == b"ASC-E1.17\x00\x00\x00"     # ACN ID
    assert p1[18:22] == b"\x00\x00\x00\x04"        # Root Vector 0x00000004
    assert p1[108] == 120                           # Priority
    
    p2 = sacn.build_packet(universe=1, dmx_data=dmx_data)
    # Check sequence increment
    assert (p1[111] + 1) % 256 == p2[111], f"Sequence did not increment: {p1[111]} -> {p2[111]}"
    print("  [PASS] sACN ANSI E1.31 3-layer packet structure verified")

    # --- USB DMX (ENTTEC Pro) ---
    usb = UsbDmxOutput(port_name="COM99")
    enttec_pkt = usb.build_enttec_packet(dmx_data)
    assert len(enttec_pkt) == 518, f"Expected 518 bytes ENTTEC packet, got {len(enttec_pkt)}"
    assert enttec_pkt[0] == 0x7E                    # SOM
    assert enttec_pkt[1] == 6                       # Label Output DMX
    assert enttec_pkt[2:4] == b"\x01\x02"           # Length 513 little-endian (0x0201)
    assert enttec_pkt[4] == 0x00                    # DMX Start code
    assert enttec_pkt[5:517] == dmx_data            # Payload
    assert enttec_pkt[517] == 0xE7                  # EOM
    print("  [PASS] ENTTEC DMX USB Pro packet framing verified")

    # --- Unified ProtocolManager ---
    from PyQt6.QtCore import QCoreApplication
    app = QCoreApplication.instance() or QCoreApplication([])
    mgr = ProtocolManager()
    mat = PixelMatrix(16, 16)
    mat.fill(255, 128, 64)
    # Broadcasting when ports/sockets are closed must gracefully no-op without error
    mgr.broadcast_frame(mat)
    mgr.shutdown_all()
    print("  [PASS] ProtocolManager unified broadcast & shutdown verified")
    print("[PASS] Multi-Protocol Engine tests passed!")


def test_midi():
    print("Testing MIDI Subsystem (Parsing, Learn Mode, Mapping Dispatch, Profiles)...")
    from PyQt6.QtCore import QCoreApplication
    app = QCoreApplication.instance() or QCoreApplication([])

    # Note name conversion
    assert midi_note_to_name(60) == "C4 (60)"
    assert midi_note_to_name(69) == "A4 (69)"
    assert midi_note_to_name(36) == "C2 (36)"

    # MIDI Binding value computation
    # Absolute mode
    b_abs = MidiBinding(target="crossfader", msg_type="control_change", control=1, mode=MidiMode.ABSOLUTE.value)
    msg_mid = MidiMessage(msg_type="control_change", channel=0, control=1, value=64)
    val_mid = b_abs.compute_value(msg_mid)
    assert abs(val_mid - (64 / 127.0)) < 0.001

    msg_max = MidiMessage(msg_type="control_change", channel=0, control=1, value=127)
    assert b_abs.compute_value(msg_max) == 1.0

    msg_min = MidiMessage(msg_type="control_change", channel=0, control=1, value=0)
    assert b_abs.compute_value(msg_min) == 0.0

    # Invert
    b_inv = MidiBinding(target="crossfader", msg_type="control_change", control=1, mode=MidiMode.ABSOLUTE.value, invert=True)
    assert b_inv.compute_value(msg_max) == 0.0
    assert b_inv.compute_value(msg_min) == 1.0

    # Toggle mode
    b_tog = MidiBinding(target="blackout", msg_type="note_on", control=36, mode=MidiMode.TOGGLE.value)
    msg_press = MidiMessage(msg_type="note_on", channel=0, control=36, value=127)
    val_t1 = b_tog.compute_value(msg_press, current_val=0.0)
    assert val_t1 == 1.0
    val_t2 = b_tog.compute_value(msg_press, current_val=1.0)
    assert val_t2 == 0.0

    # Momentary mode
    b_mom = MidiBinding(target="whiteout", msg_type="note_on", control=38, mode=MidiMode.MOMENTARY.value)
    msg_release = MidiMessage(msg_type="note_off", channel=0, control=38, value=0)
    assert b_mom.compute_value(msg_press) == 1.0
    assert b_mom.compute_value(msg_release) == 0.0

    print("  [PASS] MIDI Message & Binding computations verified")

    # MidiManager signal emission and dispatching
    midi = MidiManager()
    dispatched = {}

    def on_triggered(target, val):
        dispatched[target] = val

    midi.binding_triggered.connect(on_triggered)

    # Trigger Crossfader via simulated CC 1
    midi.simulate_message(msg_type="control_change", channel=0, control=1, value=127)
    assert "crossfader" in dispatched
    assert dispatched["crossfader"] == 1.0

    # Trigger Master Dimmer via simulated CC 7
    midi.simulate_message(msg_type="control_change", channel=0, control=7, value=64)
    assert "master_dimmer" in dispatched
    assert abs(dispatched["master_dimmer"] - (64 / 127.0)) < 0.001

    print("  [PASS] Simulated MIDI message dispatching verified")

    # MIDI Learn Mode
    midi.start_learning("deck_a_speed", mode=MidiMode.ABSOLUTE.value)
    assert midi.is_learning
    # Send CC 23 to learn
    midi.simulate_message(msg_type="control_change", channel=1, control=23, value=100)
    assert not midi.is_learning
    learned = midi.get_binding("deck_a_speed")
    assert learned is not None
    assert learned.control == 23
    assert learned.channel == 1
    print("  [PASS] Interactive MIDI Learn mode verified")

    # Factory Profiles
    midi.load_preset_profile("Akai APC Mini")
    assert midi.get_binding("master_dimmer").control == 56
    assert midi.get_binding("storage_a_slot_1").control == 0
    assert midi.get_binding("storage_b_slot_1").control == 8

    midi.load_preset_profile("Korg nanoKONTROL 2")
    assert midi.get_binding("master_dimmer").control == 0
    assert midi.get_binding("crossfader").control == 1

    # Profile Serialization (export/import)
    exported = midi.export_profile()
    assert len(exported) > 0
    midi.clear_all_bindings()
    assert len(midi.bindings) == 0
    midi.import_profile(exported)
    assert len(midi.bindings) == len(exported)
    print("  [PASS] Hardware templates & profile import/export verified")

    # Feedback safe no-op
    midi.send_feedback("crossfader", 0.75)
    print("  [PASS] Bidirectional feedback handling verified")
    print("[PASS] MIDI Subsystem tests passed!")


def test_cue_and_timeline():
    print("Testing Cue List & Multi-Track Timeline Automation...")
    from PyQt6.QtCore import QCoreApplication
    app = QCoreApplication.instance() or QCoreApplication([])

    # 1. Cue List Operations & Serialization
    c1 = Cue(cue_id=1, name="Intro", crossfader_pos=0.0, fade_duration=1.0, hold_duration=2.0)
    c2 = Cue(cue_id=2, name="Verse", crossfader_pos=1.0, fade_duration=2.0, hold_duration=4.0)
    c3 = Cue(cue_id=3, name="Chorus", crossfader_pos=0.5, fade_duration=1.5, hold_duration=3.0)

    cue_list = CueList([c1, c2, c3])
    assert len(cue_list) == 3
    assert cue_list.get_cue(1).name == "Verse"

    # Duplicate
    dup = cue_list.duplicate_cue(1)
    assert dup is not None
    assert len(cue_list) == 4
    assert cue_list.get_cue(2).name == "Verse (Copy)"

    # Remove
    cue_list.remove_cue(2)
    assert len(cue_list) == 3
    assert cue_list.get_cue(2).name == "Chorus"

    # Serialization roundtrip
    serialized = cue_list.to_list()
    assert len(serialized) == 3
    reloaded_list = CueList.from_list(serialized)
    assert len(reloaded_list) == 3
    assert reloaded_list.get_cue(0).name == "Intro"
    print("  [PASS] Cue & CueList CRUD and serialization verified")

    # 2. Cue Player Execution & Signals
    player = CuePlayer(cue_list)
    assert player.state == CuePlayerState.STOPPED

    recalls = []
    xfade_vals = []
    player.preset_recall_requested.connect(lambda d, b, s: recalls.append((d, b, s)))
    player.crossfader_target_updated.connect(lambda v: xfade_vals.append(v))

    # Trigger GO
    player.go()
    assert player.state == CuePlayerState.PLAYING
    assert player.current_index == 0
    assert len(recalls) == 2  # Recalled Deck A and Deck B presets

    # Pause & Resume
    player.pause()
    assert player.state == CuePlayerState.PAUSED
    player.pause()
    assert player.state == CuePlayerState.PLAYING

    # Step Back
    player.back()
    assert player.current_index == 2  # Wrapped to last in loop mode

    # Stop
    player.stop()
    assert player.state == CuePlayerState.STOPPED
    assert player.current_index == -1
    print("  [PASS] CuePlayer transport state machine & signal dispatch verified")

    # 3. SMPTE Timecode & Art-Net Packet
    tc = Timecode.from_seconds(75.5, fps=30.0)
    assert tc.minutes == 1
    assert tc.seconds == 15
    assert tc.frames == 15
    assert tc.to_string() == "00:01:15:15"
    assert abs(tc.to_seconds() - 75.5) < 0.001

    # Art-Net OpTimeCode builder and parser
    artnet_pkt = ArtNetTimecode.build_packet(tc)
    assert len(artnet_pkt) == 19
    assert artnet_pkt.startswith(b"Art-Net\x00")
    parsed_tc = ArtNetTimecode.parse_packet(artnet_pkt)
    assert parsed_tc is not None
    assert parsed_tc.minutes == 1
    assert parsed_tc.seconds == 15
    assert parsed_tc.frames == 15
    print("  [PASS] SMPTE Timecode & Art-Net OpTimeCode framing verified")

    # 4. Multi-Track Timeline & Curves
    timeline = Timeline(duration=120.0, fps=30.0)
    assert len(timeline.tracks) == 4

    tr_a = timeline.get_track(TimelineTrackType.DECK_A.value)
    clip_a = TimelineClip(name="Intro Look", start_time=5.0, duration=10.0, properties={"bank": 0, "slot": 0})
    tr_a.add_clip(clip_a)
    assert tr_a.get_clip_at(4.0) is None
    assert tr_a.get_clip_at(7.5) == clip_a
    assert tr_a.get_clip_at(16.0) is None

    # Crossfader curve clip
    tr_cf = timeline.get_track(TimelineTrackType.CROSSFADER.value)
    clip_cf = TimelineClip(
        name="Fade A to B",
        start_time=10.0,
        duration=5.0,
        properties={"start_val": 0.0, "end_val": 1.0, "curve": "smooth"},
    )
    tr_cf.add_clip(clip_cf)
    val_mid = clip_cf.evaluate_curve(12.5)  # 50% through smooth curve
    assert abs(val_mid - 0.5) < 0.01

    # TimelinePlayer transport
    tl_player = TimelinePlayer(timeline)
    assert not tl_player.is_playing
    tl_player.play()
    assert tl_player.is_playing
    tl_player.seek(12.5)
    assert tl_player.current_time == 12.5
    tl_player.stop()
    assert not tl_player.is_playing
    assert tl_player.current_time == 0.0
    print("  [PASS] Timeline multi-track sequencing & curve evaluation verified")

    # 5. Project File Serialization with Cues & Timeline
    bank_a = StorageBank(16)
    bank_b = StorageBank(16)
    from pixelforge.core.engine import RenderEngine
    engine = RenderEngine(16, 16)
    proj_data = ProjectFile.create_project_data(
        engine, bank_a, bank_b, cue_list=cue_list, timeline=timeline
    )
    assert "cue_list" in proj_data
    assert len(proj_data["cue_list"]) == 3
    assert "timeline" in proj_data
    assert len(proj_data["timeline"]["tracks"]) == 4
    print("  [PASS] ProjectFile .pxf integration with cues & timeline verified")
    print("[PASS] Cue List & Timeline Automation tests passed!")


def test_advanced_features():
    print("Testing Phase 8 Advanced Features (Media Playback, MAS Sandbox, HTTP Server)...")
    import urllib.request
    from pixelforge.protocols.http_server import HttpRemoteServer

    # 1. Media Playback Effects
    # SCE Image
    eff_img = create_effect("SCE Image", 32, 32)
    for pat in ["SMPTE Color Bars", "PixelForge Logo", "Radial Gradient", "Checker Test"]:
        f = eff_img.render(32, 32, 1.0, {"pattern": pat, "fit_mode": "Stretch"})
        assert f.shape == (32, 32, 3)
        assert f.dtype == np.uint8
    print("  [PASS] SCE Image procedural test patterns rendered")

    # SCE Ticker
    eff_txt = create_effect("SCE Ticker", 32, 32)
    for d in ["Left", "Right", "Up", "Down", "Static"]:
        f = eff_txt.render(32, 32, 2.5, {"text": "HELLO WORLD", "direction": d, "speed": 2.0})
        assert f.shape == (32, 32, 3)
        assert f.dtype == np.uint8
    print("  [PASS] SCE Ticker multi-directional marquee text rendered")

    # SCE Video
    eff_vid = create_effect("SCE Video", 32, 32)
    for src in ["Techno Tunnel", "Radar Sweep", "Retro Grid"]:
        f = eff_vid.render(32, 32, 1.5, {"source": src, "speed": 1.5})
        assert f.shape == (32, 32, 3)
        assert f.dtype == np.uint8
    print("  [PASS] SCE Video procedural video loops rendered")

    # 2. MAS Python Scripting Sandbox
    eff_mas = create_effect("MAS Script", 32, 32)
    for sample in ["Audio Pulsing Rings", "Bouncing Metaballs", "Spiral Galaxy", "Matrix Digital Rain"]:
        f = eff_mas.render(32, 32, 1.0, {"preset_script": sample})
        assert f.shape == (32, 32, 3)
        assert f.dtype == np.uint8

    # Custom Script Execution
    custom_py = """def render(w, h, t, audio):
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    arr[:, :] = [100, 150, 200]
    return arr
"""
    f_cust = eff_mas.render(32, 32, 1.0, {"custom_code": custom_py})
    assert f_cust[0, 0, 0] == 100
    assert f_cust[0, 0, 1] == 150
    assert f_cust[0, 0, 2] == 200

    # Script Error Handling (must not raise exception, displays safe error frame)
    bad_py = "def render(w, h, t, audio):\n    return 1 / 0"
    f_err = eff_mas.render(32, 32, 1.0, {"custom_code": bad_py})
    assert f_err.shape == (32, 32, 3)
    print("  [PASS] MAS Python Script Sandbox live execution & error safety verified")

    # 3. HTTP REST & Web Remote Control Server
    from PyQt6.QtCore import QCoreApplication
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication(sys.argv)

    from pixelforge.core.engine import RenderEngine
    engine = RenderEngine(16, 16)
    server = HttpRemoteServer(port=8899)
    server.set_engine_reference(engine)

    received_requests = []
    server.crossfader_requested.connect(lambda v: received_requests.append(("xfade", v)))
    server.blackout_requested.connect(lambda: received_requests.append(("bo", True)))

    started = server.start()
    assert started, "HTTP server failed to start on port 8899"

    try:
        # Test GET /api/status
        req = urllib.request.urlopen("http://127.0.0.1:8899/api/status", timeout=2)
        assert req.status == 200
        body = json.loads(req.read().decode("utf-8"))
        assert "fps" in body
        assert body["width"] == 16

        # Test POST /api/crossfader
        post_data = json.dumps({"position": 0.85}).encode("utf-8")
        req_post = urllib.request.Request(
            "http://127.0.0.1:8899/api/crossfader",
            data=post_data,
            headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req_post, timeout=2)
        assert resp.status == 200
        time.sleep(0.05)
        app.processEvents()
        assert ("xfade", 0.85) in received_requests

        # Test GET / (HTML Dashboard)
        html_req = urllib.request.urlopen("http://127.0.0.1:8899/", timeout=2)
        assert html_req.status == 200
        assert b"PixelForge Web Remote" in html_req.read()
        print("  [PASS] HTTP REST API & Web Remote Dashboard verified")
    finally:
        server.stop()
        assert not server.is_running

    print("[PASS] Phase 8 Advanced Features verified!")


def main():
    print("=== PIXELFORGE TEST SUITE ===")
    test_matrix()
    test_audio_analyzer()
    test_all_effects()
    test_crossfader_blend_modes()
    test_artnet_packets()
    test_storage_and_project()
    test_patch_engine()
    test_protocols()
    test_midi()
    test_cue_and_timeline()
    test_advanced_features()
    print("=== ALL SUITE TESTS PASSED SUCCESSFULLY! ===")


if __name__ == "__main__":
    main()
