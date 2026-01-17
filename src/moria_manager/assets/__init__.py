"""Asset loading utilities for icons and images.

This module handles loading assets in both development and packaged (PyInstaller) modes.

Submodules:
    loader: get_asset_path() function for resolving asset paths
    icon_generator: Script to generate placeholder icons (run with python -m)

Asset Directory Structure:
    assets/
        icons/
            gear.png      - Settings button icon
            backup.png    - Backup action icon
            restore.png   - Restore action icon
            app_icon.png  - Application icon (256x256)
            app_icon.ico  - Windows application icon (multi-size)
        background.png    - Main window background image
"""

from .loader import get_asset_path

__all__ = [
    "get_asset_path",
]
