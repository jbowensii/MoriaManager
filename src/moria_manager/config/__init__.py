"""Configuration management module.

This module provides configuration storage, loading, and data models for the application.

Submodules:
    manager: ConfigurationManager for loading/saving XML configuration
    schema: Data classes defining configuration structure (Installation, Settings, etc.)
    paths: GamePaths with default paths for Steam/Epic installations and config files
    security: Password encryption/decryption using Fernet symmetric encryption
    path_validator: Path validation utilities to prevent dangerous file operations

The configuration is stored as XML in %APPDATA%/MoriaManager/configuration.xml.
"""

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
