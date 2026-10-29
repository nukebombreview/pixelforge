#!/usr/bin/env bash
# PixelForge macOS / Linux Launcher
cd "$(dirname "$0")"

if [ -f ".venv/bin/python" ]; then
    .venv/bin/python run.py
elif command -v python3 &>/dev/null; then
    python3 run.py
else
    echo "[ERROR] Python 3 not found."
    exit 1
fi

