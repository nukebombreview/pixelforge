#!/usr/bin/env python3
"""PixelForge — Professional Real-Time LED Lighting Control"""
import sys
import os

# Ensure the project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pixelforge.main import main

if __name__ == "__main__":
    sys.exit(main())
