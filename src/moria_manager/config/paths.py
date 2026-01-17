"""Default paths for game installations and saves"""

import os
from pathlib import Path


class GamePaths:
    """Default paths for game installations and saves.

    All paths use environment variable expansion for portability.
    """

    # Steam paths
    STEAM_GAME_DEFAULT = Path(r"C:\Program Files (x86)\Steam\steamapps\common\The Lord of the Rings Return to Moria™")
    STEAM_SAVE_DEFAULT = Path(os.path.expandvars(r"%LOCALAPPDATA%\Moria\Saved\SaveGamesSteam"))

    # Epic paths
    EPIC_GAME_DEFAULT = Path(r"C:\Program Files\Epic Games\ReturnToMoria")
    EPIC_SAVE_DEFAULT = Path(os.path.expandvars(r"%LOCALAPPDATA%\Moria\Saved\SaveGamesEpic"))

    # Default backup location
    BACKUP_DEFAULT = Path(os.path.expandvars(r"%USERPROFILE%\GameBackups"))

    # Configuration file location
    CONFIG_DIR = Path(os.path.expandvars(r"%APPDATA%\MoriaManager"))
    CONFIG_FILE = CONFIG_DIR / "configuration.xml"

    # Index files for backup tracking (stored in config dir, not backup dir)
    WORLDS_INDEX_FILE = CONFIG_DIR / "index_worlds.xml"
    CHARACTERS_INDEX_FILE = CONFIG_DIR / "index_characters.xml"

    # Server info files (one per installation type)
    SERVER_INFO_DIR = CONFIG_DIR / "servers"

    @classmethod
    def expand_path(cls, path_str: str) -> Path:
        """Expand environment variables in path string.

        Args:
            path_str: Path string potentially containing environment variables

        Returns:
            Path object with expanded variables
        """
        return Path(os.path.expandvars(path_str))

    @classmethod
    def ensure_config_dir(cls) -> Path:
        """Ensure the configuration directory exists.

        Returns:
            Path to the configuration directory
        """
        cls.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        return cls.CONFIG_DIR

    @classmethod
    def ensure_backup_dir(cls, backup_path: Path | None = None) -> Path:
        """Ensure the backup directory exists.

        Args:
            backup_path: Optional custom backup path, uses default if None

        Returns:
            Path to the backup directory
        """
        path = backup_path or cls.BACKUP_DEFAULT
        path.mkdir(parents=True, exist_ok=True)
        return path
