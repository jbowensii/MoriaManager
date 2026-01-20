"""Configuration data models"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional


class InstallationType(Enum):
    """Types of game installations"""
    STEAM = "steam"
    EPIC = "epic"
    CUSTOM = "custom"


@dataclass
class Installation:
    """Represents a game installation (Steam, Epic, or Custom)"""
    id: InstallationType
    display_name: str
    game_path: Optional[Path] = None
    save_path: Optional[Path] = None
    enabled: bool = False

    def is_valid(self) -> bool:
        """Check if the installation has valid paths configured.

        Returns:
            True if save_path exists and is configured
        """
        return self.save_path is not None and self.save_path.exists()


@dataclass
class ServerInfo:
    """Server information for multiplayer"""
    name: str = ""
    address: str = ""
    password: str = ""
    notes: str = ""


@dataclass
class Settings:
    """Application settings"""
    first_run_complete: bool = False
    backup_location: Optional[Path] = None
    auto_backup_on_launch: bool = False
    enable_deletion: bool = False
    server_info: Optional[ServerInfo] = None


@dataclass
class BackupRecord:
    """Record of a single backup"""
    id: str  # UUID
    installation: InstallationType
    timestamp: datetime
    description: str
    file_path: Path

    def exists(self) -> bool:
        """Check if the backup file still exists.

        Returns:
            True if the backup file exists on disk
        """
        return self.file_path.exists()

    def get_size_mb(self) -> float:
        """Get the backup file size in megabytes.

        Returns:
            File size in MB, or 0 if file doesn't exist
        """
        if self.exists():
            return self.file_path.stat().st_size / (1024 * 1024)
        return 0.0


@dataclass
class AppConfiguration:
    """Complete application configuration"""
    settings: Settings = field(default_factory=Settings)
    installations: list[Installation] = field(default_factory=list)
    backups: list[BackupRecord] = field(default_factory=list)

    def get_installation(self, installation_type: InstallationType) -> Optional[Installation]:
        """Get an installation by type.

        Args:
            installation_type: The type of installation to find

        Returns:
            The Installation object or None if not found
        """
        for installation in self.installations:
            if installation.id == installation_type:
                return installation
        return None

    def get_enabled_installations(self) -> list[Installation]:
        """Get all enabled installations.

        Returns:
            List of enabled Installation objects
        """
        return [inst for inst in self.installations if inst.enabled]

    def get_backups_for_installation(self, installation_type: InstallationType) -> list[BackupRecord]:
        """Get all backups for a specific installation.

        Args:
            installation_type: The installation type to filter by

        Returns:
            List of BackupRecord objects sorted by timestamp (newest first)
        """
        backups = [b for b in self.backups if b.installation == installation_type]
        return sorted(backups, key=lambda b: b.timestamp, reverse=True)
