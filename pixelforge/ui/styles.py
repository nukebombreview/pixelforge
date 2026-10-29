"""
PixelForge — Professional MADRIX 5 Dark Theme Styling
QSS (Qt Style Sheets) design system tailored for high-contrast stage/lighting environments.
"""

# Palette Constants
COLOR_BG_DARKEST = "#0c0e12"
COLOR_BG_DARK = "#14171e"
COLOR_BG_PANEL = "#1c202a"
COLOR_BG_SURFACE = "#252b38"
COLOR_BG_HOVER = "#2f3647"

COLOR_BORDER = "#32394a"
COLOR_BORDER_FOCUS = "#48536b"

COLOR_TEXT_PRIMARY = "#e6edf3"
COLOR_TEXT_SECONDARY = "#8b949e"
COLOR_TEXT_MUTED = "#555f73"

COLOR_DECK_A = "#00d2ff"      # Electric Cyan
COLOR_DECK_B = "#ff2d75"      # Neon Magenta
COLOR_MASTER = "#ffb703"      # Amber Gold
COLOR_ACCENT = "#58a6ff"      # Sky Blue
COLOR_SUCCESS = "#00e676"     # Bright Green
COLOR_DANGER = "#ff1744"      # Bright Red

DARK_THEME_QSS = f"""
/* Global Reset */
QWidget {{
    background-color: {COLOR_BG_DARK};
    color: {COLOR_TEXT_PRIMARY};
    font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, "Roboto", sans-serif;
    font-size: 12px;
    selection-background-color: {COLOR_DECK_A};
    selection-color: {COLOR_BG_DARKEST};
}}

/* Main Window & Menus */
QMainWindow {{
    background-color: {COLOR_BG_DARKEST};
}}

QMenuBar {{
    background-color: {COLOR_BG_DARKEST};
    color: {COLOR_TEXT_PRIMARY};
    border-bottom: 1px solid {COLOR_BORDER};
    padding: 3px 6px;
}}

QMenuBar::item:selected {{
    background-color: {COLOR_BG_SURFACE};
    border-radius: 4px;
}}

QMenu {{
    background-color: {COLOR_BG_PANEL};
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER};
    padding: 4px;
    border-radius: 6px;
}}

QMenu::item {{
    padding: 6px 24px 6px 12px;
    border-radius: 4px;
}}

QMenu::item:selected {{
    background-color: {COLOR_DECK_A};
    color: {COLOR_BG_DARKEST};
    font-weight: bold;
}}

QMenu::separator {{
    height: 1px;
    background-color: {COLOR_BORDER};
    margin: 4px 6px;
}}

/* Toolbars & Status Bar */
QToolBar {{
    background-color: {COLOR_BG_DARK};
    border-bottom: 1px solid {COLOR_BORDER};
    spacing: 6px;
    padding: 4px 8px;
}}

QStatusBar {{
    background-color: {COLOR_BG_DARKEST};
    border-top: 1px solid {COLOR_BORDER};
    color: {COLOR_TEXT_SECONDARY};
    font-size: 11px;
    padding: 2px 10px;
}}

/* Panels / Group Boxes */
QGroupBox {{
    background-color: {COLOR_BG_PANEL};
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    margin-top: 14px;
    padding: 12px 8px 8px 8px;
    font-weight: bold;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
    color: {COLOR_TEXT_SECONDARY};
    text-transform: uppercase;
    font-size: 10px;
    letter-spacing: 1px;
}}

/* Deck A Panel Accent */
QGroupBox#deck_a_group {{
    border-top: 2px solid {COLOR_DECK_A};
}}
QGroupBox#deck_a_group::title {{
    color: {COLOR_DECK_A};
}}

/* Deck B Panel Accent */
QGroupBox#deck_b_group {{
    border-top: 2px solid {COLOR_DECK_B};
}}
QGroupBox#deck_b_group::title {{
    color: {COLOR_DECK_B};
}}

/* Master Panel Accent */
QGroupBox#master_group {{
    border-top: 2px solid {COLOR_MASTER};
}}
QGroupBox#master_group::title {{
    color: {COLOR_MASTER};
}}

/* Buttons */
QPushButton {{
    background-color: {COLOR_BG_SURFACE};
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER};
    border-radius: 4px;
    padding: 6px 12px;
    font-weight: 600;
    min-height: 18px;
}}

QPushButton:hover {{
    background-color: {COLOR_BG_HOVER};
    border-color: {COLOR_BORDER_FOCUS};
}}

QPushButton:pressed {{
    background-color: {COLOR_BG_DARKEST};
}}

QPushButton:checked {{
    background-color: {COLOR_DECK_A};
    color: {COLOR_BG_DARKEST};
    border-color: {COLOR_DECK_A};
}}

/* Specialized Action Buttons */
QPushButton#btn_blackout {{
    background-color: #3b141a;
    border: 1px solid #771d2b;
    color: #ff6b81;
    font-weight: bold;
}}
QPushButton#btn_blackout:checked {{
    background-color: {COLOR_DANGER};
    color: white;
}}

QPushButton#btn_freeze {{
    background-color: #12283a;
    border: 1px solid #1a4f78;
    color: #64b5f6;
}}
QPushButton#btn_freeze:checked {{
    background-color: #1e88e5;
    color: white;
}}

QPushButton#btn_artnet_toggle {{
    background-color: #1b3322;
    border: 1px solid #285936;
    color: #81c784;
}}
QPushButton#btn_artnet_toggle:checked {{
    background-color: {COLOR_SUCCESS};
    color: {COLOR_BG_DARKEST};
    font-weight: bold;
}}

/* Sliders */
QSlider::groove:horizontal {{
    height: 6px;
    background: {COLOR_BG_DARKEST};
    border: 1px solid {COLOR_BORDER};
    border-radius: 3px;
}}

QSlider::sub-page:horizontal {{
    background: {COLOR_DECK_A};
    border-radius: 3px;
}}

QSlider::handle:horizontal {{
    background: {COLOR_TEXT_PRIMARY};
    border: 2px solid {COLOR_DECK_A};
    width: 14px;
    margin-top: -5px;
    margin-bottom: -5px;
    border-radius: 7px;
}}

QSlider::handle:horizontal:hover {{
    background: #ffffff;
    border-color: #ffffff;
}}

/* Crossfader Specific Slider */
QSlider#crossfader::groove:horizontal {{
    height: 12px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {COLOR_DECK_A}, stop:0.5 {COLOR_BG_DARKEST}, stop:1 {COLOR_DECK_B});
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
}}

QSlider#crossfader::handle:horizontal {{
    background: #ffffff;
    border: 2px solid #222;
    width: 22px;
    height: 24px;
    margin-top: -7px;
    margin-bottom: -7px;
    border-radius: 5px;
}}

/* Vertical Sliders (Dimmer) */
QSlider::groove:vertical {{
    width: 8px;
    background: {COLOR_BG_DARKEST};
    border: 1px solid {COLOR_BORDER};
    border-radius: 4px;
}}

QSlider::sub-page:vertical {{
    background: {COLOR_MASTER};
    border-radius: 4px;
}}

QSlider::handle:vertical {{
    background: {COLOR_TEXT_PRIMARY};
    border: 2px solid {COLOR_MASTER};
    height: 14px;
    margin-left: -4px;
    margin-right: -4px;
    border-radius: 7px;
}}

/* Combo Boxes */
QComboBox {{
    background-color: {COLOR_BG_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: 4px;
    padding: 4px 10px;
    color: {COLOR_TEXT_PRIMARY};
    min-height: 22px;
}}

QComboBox:hover {{
    border-color: {COLOR_BORDER_FOCUS};
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 20px;
    border-left: 1px solid {COLOR_BORDER};
}}

QComboBox QAbstractItemView {{
    background-color: {COLOR_BG_PANEL};
    border: 1px solid {COLOR_BORDER};
    selection-background-color: {COLOR_DECK_A};
    selection-color: {COLOR_BG_DARKEST};
    padding: 4px;
}}

/* Spin Boxes & Text Inputs */
QSpinBox, QDoubleSpinBox, QLineEdit {{
    background-color: {COLOR_BG_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: 4px;
    padding: 3px 6px;
    color: {COLOR_TEXT_PRIMARY};
}}

QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus {{
    border-color: {COLOR_DECK_A};
}}

/* Scroll Bars */
QScrollBar:vertical {{
    background: {COLOR_BG_DARKEST};
    width: 8px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background: {COLOR_BORDER};
    border-radius: 4px;
    min-height: 20px;
}}

QScrollBar::handle:vertical:hover {{
    background: {COLOR_TEXT_SECONDARY};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
"""
