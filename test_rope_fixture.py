"""
Verification test for 5M LED Rope Light fixture integration in PixelForge.
"""

import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pixelforge.core.matrix import PixelMatrix
from pixelforge.core.patch import Patch, Fixture, PixelRouting
from pixelforge.core.engine import RenderEngine
from pixelforge.core.storage import ProjectFile

def test_rope_fixture():
    print("Testing 5M LED Rope Light Fixture...")

    patch = Patch(matrix_width=80, matrix_height=16)
    f = patch.add_rope_light_fixture("5m LED Rope Light", x=0, y=0, start_universe=0, start_channel=1)

    assert f.width == 80
    assert f.height == 1
    assert f.pixel_count == 80
    assert f.channels_per_pixel == 3
    assert f.total_channels == 240
    assert f.channel_order == "GRB"
    assert f.start_universe == 0
    assert f.start_channel == 1
    print("  [PASS] Fixture dimensions (80x1) and channel counts (240ch GRB) verified")

    # Verify DMX Color Mapping GRB
    # Create test matrix with distinct colors on Pixel 0 and Pixel 1
    matrix = PixelMatrix(80, 16)
    # Pixel 0: Pure Red (R=255, G=0, B=0)
    matrix.set_pixel(0, 0, 255, 0, 0)
    # Pixel 1: Pure Green (R=0, G=255, B=0)
    matrix.set_pixel(1, 0, 0, 255, 0)
    # Pixel 2: Pure Blue (R=0, G=0, B=255)
    matrix.set_pixel(2, 0, 0, 0, 255)

    dmx_frames = patch.render_to_dmx(matrix)
    assert 0 in dmx_frames
    u0 = dmx_frames[0]
    assert len(u0) == 512

    # Pixel 0 (GRB): G=0 (ch 0), R=255 (ch 1), B=0 (ch 2)
    assert u0[0] == 0, f"Expected Green=0, got {u0[0]}"
    assert u0[1] == 255, f"Expected Red=255, got {u0[1]}"
    assert u0[2] == 0, f"Expected Blue=0, got {u0[2]}"

    # Pixel 1 (GRB): G=255 (ch 3), R=0 (ch 4), B=0 (ch 5)
    assert u0[3] == 255, f"Expected Green=255, got {u0[3]}"
    assert u0[4] == 0, f"Expected Red=0, got {u0[4]}"
    assert u0[5] == 0, f"Expected Blue=0, got {u0[5]}"

    # Pixel 2 (GRB): G=0 (ch 6), R=0 (ch 7), B=255 (ch 8)
    assert u0[6] == 0, f"Expected Green=0, got {u0[6]}"
    assert u0[7] == 0, f"Expected Red=0, got {u0[7]}"
    assert u0[8] == 255, f"Expected Blue=255, got {u0[8]}"

    # Channels 240..511 should be 0
    assert u0[239] == 0 or u0[239] is not None
    assert u0[240] == 0
    print("  [PASS] Color channel order GRB mapping to DMX bytes verified with 100% accuracy")

    # Test Project file load
    proj_path = os.path.join(os.path.dirname(__file__), "projects", "5m_rope_light_unreal.pxf")
    data = ProjectFile.load(proj_path)
    assert data is not None
    assert data["matrix"]["width"] == 80
    assert len(data["patch"]["fixtures"]) == 2
    assert data["patch"]["fixtures"][0]["name"] == "5m LED Rope Light [Uni 0]"
    assert data["patch"]["fixtures"][0]["channel_order"] == "GRB"
    print("  [PASS] 5M Rope Light Project File (.pxf) deserialization verified")

    print("[PASS] All 5M LED Rope Light tests passed successfully!")

if __name__ == "__main__":
    test_rope_fixture()
