"""Asset loading utilities for both development and packaged modes"""

import sys
from pathlib import Path


def get_asset_path(relative_path: str) -> Path:
    """Get the correct path for assets, works in both dev and packaged modes.

    Args:
        relative_path: Path relative to the assets directory (e.g., "icons/gear.png")

    Returns:
        Absolute path to the asset file
    """
    if getattr(sys, 'frozen', False):
        # Running as compiled executable (PyInstaller)
        base_path = Path(sys._MEIPASS) / "assets"
    else:
        # Running in development
        base_path = Path(__file__).parent

    return base_path / relative_path
