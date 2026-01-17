"""GUI module using CustomTkinter for a modern interface.

This module provides all user interface components for the application.

Components:
    MainWindow: Main application window with vertical tabs for:
        - Worlds tab: World save management with version history
        - Characters tab: Character save management
        - Mods tab: Mod installation and management
        - Trade Manager tab: Merchant order tracking
        - Servers tab: Server information storage

    ConfigDialog: Settings dialog for first-run setup and configuration

Submodules:
    styles: Theme constants (colors, fonts, padding, window sizes)
    widgets: Reusable widget components (PathSelector)
"""

from .main_window import MainWindow
from .config_dialog import ConfigDialog

__all__ = [
    "MainWindow",
    "ConfigDialog",
]
