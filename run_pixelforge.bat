@echo off
title PixelForge - Real-Time LED Lighting Control
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" run.py
) else (
    echo [ERROR] Virtual environment not found in "%~dp0.venv".
    echo Please install dependencies first.
    pause
)
