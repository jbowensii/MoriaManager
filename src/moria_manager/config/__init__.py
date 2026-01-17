"""Configuration management module"""

from .manager import ConfigurationManager
from .schema import AppConfiguration, Installation, InstallationType, Settings, BackupRecord
from .paths import GamePaths

__all__ = [
    "ConfigurationManager",
    "AppConfiguration",
    "Installation",
    "InstallationType",
    "Settings",
    "BackupRecord",
    "GamePaths",
]
