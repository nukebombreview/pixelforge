"""
PixelForge — Application Entry Point
Initializes Qt application, high-DPI scaling, and displays the main window.
"""

from __future__ import annotations

import sys
import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from pixelforge.ui.main_window import MainWindow


def main() -> int:
    """Launch PixelForge."""
    # Enable high-DPI scaling attributes if available
    if hasattr(Qt.ApplicationAttribute, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    if hasattr(Qt.ApplicationAttribute, "AA_UseHighDpiPixmaps"):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("PixelForge")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("PixelForge Lighting")

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
