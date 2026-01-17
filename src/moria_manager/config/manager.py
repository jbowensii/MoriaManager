"""Configuration management - load/save XML configuration"""

import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Optional
from xml.dom import minidom

from .paths import GamePaths
from .schema import (
    AppConfiguration,
    BackupRecord,
    Installation,
    InstallationType,
    ServerInfo,
    Settings,
)
from .security import decrypt_password, encrypt_password
from ..logging_config import get_logger

logger = get_logger("config_manager")


class ConfigurationManager:
    """Manages application configuration persistence.

    Handles loading and saving configuration to XML format,
    including first-run detection and default configuration creation.
    """

    def __init__(self):
        self.config_path = GamePaths.CONFIG_FILE
        self.config: Optional[AppConfiguration] = None

    def is_first_run(self) -> bool:
        """Check if this is the first run of the application.

        First run is detected if:
        - Configuration file does not exist, OR
        - Configuration exists but FirstRunComplete is False

        Returns:
            True if this is the first run
        """
        if not self.config_path.exists():
            return True

        try:
            self.load()
            return not self.config.settings.first_run_complete
        except (ET.ParseError, FileNotFoundError, ValueError, KeyError) as e:
            # Corrupted config = treat as first run
            logger.warning(f"Could not load config, treating as first run: {e}")
            return True

    def load(self) -> AppConfiguration:
        """Load configuration from XML file.

        Returns:
            AppConfiguration object with loaded settings

        Raises:
            FileNotFoundError: If config file doesn't exist
            ET.ParseError: If XML is malformed
        """
        logger.debug(f"Loading configuration from {self.config_path}")
        tree = ET.parse(self.config_path)
        root = tree.getroot()

        # Parse settings
        settings_elem = root.find("Settings")

        # Parse server info if present
        server_info = None
        if settings_elem is not None:
            server_elem = settings_elem.find("ServerInfo")
            if server_elem is not None:
                server_info = ServerInfo(
                    name=self._get_text(server_elem, "Name", ""),
                    address=self._get_text(server_elem, "Address", ""),
                    password=decrypt_password(self._get_text(server_elem, "Password", "")),
                    notes=self._get_text(server_elem, "Notes", ""),
                )

        # Use defaults if Settings element is missing
        if settings_elem is not None:
            settings = Settings(
                first_run_complete=self._parse_bool(settings_elem, "FirstRunComplete", False),
                backup_location=self._parse_path(settings_elem, "BackupLocation"),
                auto_backup_on_launch=self._parse_bool(settings_elem, "AutoBackupOnLaunch", False),
                server_info=server_info,
            )
        else:
            # Missing Settings element - use all defaults
            settings = Settings(
                first_run_complete=False,
                backup_location=None,
                auto_backup_on_launch=False,
                server_info=None,
            )

        # Parse installations
        installations = []
        installations_elem = root.find("Installations")
        if installations_elem is not None:
            for inst_elem in installations_elem.findall("Installation"):
                installation = Installation(
                    id=InstallationType(inst_elem.get("id")),
                    display_name=self._get_text(inst_elem, "DisplayName", ""),
                    game_path=self._parse_path(inst_elem, "GamePath"),
                    save_path=self._parse_path(inst_elem, "SavePath"),
                    enabled=inst_elem.get("enabled", "false").lower() == "true",
                )
                installations.append(installation)

        # Parse backups
        backups = []
        backups_elem = root.find("Backups")
        if backups_elem is not None:
            for backup_elem in backups_elem.findall("Backup"):
                try:
                    backup = BackupRecord(
                        id=backup_elem.get("id"),
                        installation=InstallationType(backup_elem.get("installation")),
                        timestamp=datetime.fromisoformat(backup_elem.get("timestamp")),
                        description=self._get_text(backup_elem, "Description", ""),
                        file_path=Path(self._get_text(backup_elem, "FilePath", "")),
                    )
                    backups.append(backup)
                except (ValueError, TypeError) as e:
                    # Skip malformed backup entries
                    logger.warning(f"Skipping malformed backup entry: {e}")
                    continue

        self.config = AppConfiguration(
            settings=settings,
            installations=installations,
            backups=backups,
        )
        logger.debug(f"Configuration loaded: {len(installations)} installations, {len(backups)} backups")
        return self.config

    def save(self) -> None:
        """Save current configuration to XML file.

        Creates the configuration directory if it doesn't exist.
        """
        if self.config is None:
            raise ValueError("No configuration to save")

        logger.debug(f"Saving configuration to {self.config_path}")

        # Ensure config directory exists
        GamePaths.ensure_config_dir()

        root = ET.Element("MoriaManager", version="1.0")

        # Settings section
        settings_elem = ET.SubElement(root, "Settings")
        ET.SubElement(settings_elem, "FirstRunComplete").text = str(self.config.settings.first_run_complete).lower()
        ET.SubElement(settings_elem, "BackupLocation").text = str(self.config.settings.backup_location or GamePaths.BACKUP_DEFAULT)
        ET.SubElement(settings_elem, "AutoBackupOnLaunch").text = str(self.config.settings.auto_backup_on_launch).lower()

        # Server info section
        if self.config.settings.server_info:
            server_elem = ET.SubElement(settings_elem, "ServerInfo")
            ET.SubElement(server_elem, "Name").text = self.config.settings.server_info.name or ""
            ET.SubElement(server_elem, "Address").text = self.config.settings.server_info.address or ""
            ET.SubElement(server_elem, "Password").text = encrypt_password(self.config.settings.server_info.password or "")
            ET.SubElement(server_elem, "Notes").text = self.config.settings.server_info.notes or ""

        # Installations section
        installations_elem = ET.SubElement(root, "Installations")
        for installation in self.config.installations:
            inst_elem = ET.SubElement(
                installations_elem,
                "Installation",
                id=installation.id.value,
                enabled=str(installation.enabled).lower(),
            )
            ET.SubElement(inst_elem, "DisplayName").text = installation.display_name
            ET.SubElement(inst_elem, "GamePath").text = str(installation.game_path) if installation.game_path else ""
            ET.SubElement(inst_elem, "SavePath").text = str(installation.save_path) if installation.save_path else ""

        # Backups section
        backups_elem = ET.SubElement(root, "Backups")
        for backup in self.config.backups:
            backup_elem = ET.SubElement(
                backups_elem,
                "Backup",
                id=backup.id,
                installation=backup.installation.value,
                timestamp=backup.timestamp.isoformat(),
            )
            ET.SubElement(backup_elem, "Description").text = backup.description
            ET.SubElement(backup_elem, "FilePath").text = str(backup.file_path)

        # Write pretty-printed XML
        xml_str = minidom.parseString(ET.tostring(root, encoding="unicode")).toprettyxml(indent="  ")
        # Remove extra blank lines that minidom adds
        lines = [line for line in xml_str.split('\n') if line.strip()]
        xml_str = '\n'.join(lines)

        self.config_path.write_text(xml_str, encoding="utf-8")

    def create_default(self, installations: list[Installation] | None = None) -> AppConfiguration:
        """Create a default configuration.

        Args:
            installations: Optional list of pre-detected installations

        Returns:
            New AppConfiguration with default values
        """
        if installations is None:
            installations = []

        self.config = AppConfiguration(
            settings=Settings(
                first_run_complete=False,
                backup_location=GamePaths.BACKUP_DEFAULT,
                auto_backup_on_launch=False,
            ),
            installations=installations,
            backups=[],
        )
        return self.config

    def add_backup(self, backup: BackupRecord) -> None:
        """Add a backup record and save configuration.

        Args:
            backup: The backup record to add
        """
        if self.config is None:
            raise ValueError("No configuration loaded")
        self.config.backups.append(backup)
        self.save()

    def remove_backup(self, backup_id: str) -> bool:
        """Remove a backup record by ID.

        Args:
            backup_id: UUID of the backup to remove

        Returns:
            True if backup was found and removed
        """
        if self.config is None:
            raise ValueError("No configuration loaded")

        for i, backup in enumerate(self.config.backups):
            if backup.id == backup_id:
                self.config.backups.pop(i)
                self.save()
                return True
        return False

    # Helper methods for XML parsing
    @staticmethod
    def _get_text(parent: ET.Element, tag: str, default: str = "") -> str:
        """Get text content of a child element."""
        elem = parent.find(tag)
        return elem.text if elem is not None and elem.text else default

    @staticmethod
    def _parse_bool(parent: ET.Element, tag: str, default: bool = False) -> bool:
        """Parse a boolean value from child element."""
        elem = parent.find(tag)
        if elem is not None and elem.text:
            return elem.text.lower() == "true"
        return default

    @staticmethod
    def _parse_path(parent: ET.Element, tag: str) -> Optional[Path]:
        """Parse a path value from child element."""
        elem = parent.find(tag)
        if elem is not None and elem.text and elem.text.strip():
            return GamePaths.expand_path(elem.text)
        return None
