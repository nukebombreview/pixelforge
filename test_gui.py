"""
PixelForge — Off-screen GUI Smoke Test
Tests QApplication and MainWindow instantiation, rendering 10 frames in off-screen mode.
"""

from __future__ import annotations

import os
import sys

# Force offscreen Qt platform for test validation
os.environ["QT_QPA_PLATFORM"] = "offscreen"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication
from pixelforge.ui.main_window import MainWindow


def test_gui_run():
    print("Testing GUI initialization in off-screen mode...")
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()

    frame_count = 0

    def on_frame(a, b, out):
        nonlocal frame_count
        frame_count += 1
        if frame_count >= 10:
            print(f"[PASS] Successfully rendered {frame_count} live frames through UI pipeline!")
            app.quit()

    window.engine.frame_rendered.connect(on_frame)

    # Test dialogs creation
    from pixelforge.ui.midi_dialog import MidiConfigDialog
    from pixelforge.ui.protocol_dialog import ProtocolConfigDialog
    from pixelforge.ui.cue_dialog import CueDialog
    midi_dlg = MidiConfigDialog(window.midi, parent=window)
    assert midi_dlg is not None
    proto_dlg = ProtocolConfigDialog(window.engine.protocols, parent=window)
    assert proto_dlg is not None
    cue_dlg = CueDialog(window.cue_player, window.timeline_player, parent=window)
    assert cue_dlg is not None
    print("[PASS] MidiConfigDialog, ProtocolConfigDialog, and CueDialog instantiated successfully!")

    # Test cue execution
    window.cue_player.go(0)
    assert window.cue_player.current_index == 0
    print("[PASS] Cue execution triggered through live UI!")

    # Test Phase 8 3D Voxel Viewport
    assert not window.preview_out.is_3d_mode
    window.preview_out.toggle_3d_mode(True)
    assert window.preview_out.is_3d_mode
    window.preview_out.toggle_3d_mode(False)
    assert not window.preview_out.is_3d_mode
    print("[PASS] 3D Volumetric Voxel Viewport toggling verified!")

    # Test Phase 8 HTTP Server Status
    assert window.http_server.is_running
    print(f"[PASS] HTTP Remote Server active on port {window.http_server.port}!")

    # Test Project File Loading through UI
    proj_path = os.path.join(os.path.dirname(__file__), "projects", "5m_rope_light_unreal.pxf")
    assert os.path.exists(proj_path)
    loaded = window.load_project_file(proj_path)
    assert loaded, "Failed to load 5m_rope_light_unreal.pxf project file"
    assert window.engine.width == 80
    assert len(window.engine.patch.fixtures) == 2
    assert window.engine.patch.fixtures[0].channel_order == "GRB"
    print("[PASS] 5M Rope Light Project File loaded and verified through GUI!")

    # Safety timeout
    QTimer.singleShot(3000, lambda: app.quit())

    app.exec()
    assert frame_count >= 5, f"Expected at least 5 frames, got {frame_count}"
    window.close()
    print("[PASS] MainWindow offscreen test completed cleanly!")


if __name__ == "__main__":
    test_gui_run()
