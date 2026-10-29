# PixelForge PowerShell Launcher
Set-Location -Path $PSScriptRoot

$VenvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if (Test-Path $VenvPython) {
    & $VenvPython run.py
} else {
    Write-Host "[ERROR] Virtual environment not found at $VenvPython" -ForegroundColor Red
    Read-Host "Press Enter to exit..."
}

