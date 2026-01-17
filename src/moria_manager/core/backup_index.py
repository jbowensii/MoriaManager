"""Backup index management for tracking world/character backups."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import xml.etree.ElementTree as ET

from ..config.paths import GamePaths


@dataclass
class BackupIndexEntry:
    """An entry in the backup index mapping filename to display name."""
    filename: str  # Base filename without extension (e.g., "MW_12345678")
    display_name: str  # World name or character name


class BackupIndexManager:
    """Manages the index.xml file for a backup category (worlds or characters).

    The index maps save file base names to their display names (world/character names).
    Each display name has a corresponding directory containing backups for that item.

    Index files are stored in %APPDATA%/MoriaManager/:
        index_worlds.xml
        index_characters.xml

    Backup data is stored in the user's configured backup location:
        backup_location/
            worlds/
                My World Name/
                    MW_12345678_20260116_143052.sav
                    MW_12345678_20260116_150000.sav
            characters/
                Gimli/
                    MC_12345678_20260116_143052.sav
    """

    def __init__(self, backup_root: Path, category: str):
        """Initialize the backup index manager.

        Args:
            backup_root: Root backup directory (user's configured backup location)
            category: Either "worlds" or "characters"
        """
        self.backup_root = backup_root
        self.category = category
        self.category_dir = backup_root / category

        # Index file is stored in config directory, not backup directory
        if category == "worlds":
            self.index_file = GamePaths.WORLDS_INDEX_FILE
        elif category == "characters":
            self.index_file = GamePaths.CHARACTERS_INDEX_FILE
        else:
            # Fallback for any other category
            self.index_file = GamePaths.CONFIG_DIR / f"index_{category}.xml"

        # Ensure directories exist
        self.category_dir.mkdir(parents=True, exist_ok=True)
        GamePaths.ensure_config_dir()

        # Load or create index
        self._entries: dict[str, BackupIndexEntry] = {}
        self._load_index()

    def _load_index(self):
        """Load the index from XML file."""
        if not self.index_file.exists():
            return

        try:
            tree = ET.parse(self.index_file)
            root = tree.getroot()

            for entry_elem in root.findall("entry"):
                filename = entry_elem.get("filename", "")
                display_name = entry_elem.get("name", "")
                if filename and display_name:
                    self._entries[filename] = BackupIndexEntry(
                        filename=filename,
                        display_name=display_name
                    )
        except ET.ParseError:
            # Corrupted index, start fresh
            self._entries = {}

    def _save_index(self):
        """Save the index to XML file."""
        root = ET.Element("backup_index")
        root.set("category", self.category)

        for entry in sorted(self._entries.values(), key=lambda e: e.display_name.lower()):
            entry_elem = ET.SubElement(root, "entry")
            entry_elem.set("filename", entry.filename)
            entry_elem.set("name", entry.display_name)

        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")
        tree.write(self.index_file, encoding="unicode", xml_declaration=True)

    def _sanitize_dirname(self, name: str) -> str:
        """Sanitize a display name for use as a directory name.

        Args:
            name: Display name to sanitize

        Returns:
            Safe directory name
        """
        # Replace invalid Windows filename characters
        invalid_chars = '<>:"/\\|?*'
        result = name
        for char in invalid_chars:
            result = result.replace(char, '_')

        # Remove leading/trailing whitespace and dots
        result = result.strip(' .')

        # Ensure not empty
        if not result:
            result = "Unknown"

        return result

    def get_entry(self, filename: str) -> Optional[BackupIndexEntry]:
        """Get an index entry by filename.

        Args:
            filename: Base filename without extension

        Returns:
            BackupIndexEntry or None if not found
        """
        return self._entries.get(filename)

    def get_backup_directory(self, filename: str, display_name: str) -> Path:
        """Get or create the backup directory for an item.

        This method handles:
        1. New items: Creates entry and directory
        2. Existing items with same name: Returns existing directory
        3. Existing items with changed name: Updates entry and renames directory

        Args:
            filename: Base filename without extension (e.g., "MW_12345678")
            display_name: Current world/character name

        Returns:
            Path to the backup directory for this item
        """
        existing_entry = self._entries.get(filename)
        safe_name = self._sanitize_dirname(display_name)

        if existing_entry is None:
            # New entry
            backup_dir = self.category_dir / safe_name

            # Handle case where directory name already exists for different file
            counter = 1
            while backup_dir.exists() and self._is_directory_in_use(safe_name, filename):
                backup_dir = self.category_dir / f"{safe_name}_{counter}"
                safe_name = f"{safe_name}_{counter}"
                counter += 1

            backup_dir.mkdir(parents=True, exist_ok=True)

            # Add to index
            self._entries[filename] = BackupIndexEntry(
                filename=filename,
                display_name=display_name
            )
            self._save_index()

            return backup_dir

        # Existing entry
        old_safe_name = self._sanitize_dirname(existing_entry.display_name)
        old_dir = self.category_dir / old_safe_name

        if existing_entry.display_name == display_name:
            # Name unchanged, ensure directory exists
            old_dir.mkdir(parents=True, exist_ok=True)
            return old_dir

        # Name changed - update index and rename directory
        new_dir = self.category_dir / safe_name

        # Handle case where new name conflicts with another entry
        counter = 1
        while new_dir.exists() and self._is_directory_in_use(safe_name, filename):
            new_dir = self.category_dir / f"{safe_name}_{counter}"
            safe_name = f"{safe_name}_{counter}"
            counter += 1

        # Rename directory if old one exists
        if old_dir.exists():
            try:
                old_dir.rename(new_dir)
            except OSError:
                # If rename fails, create new directory
                new_dir.mkdir(parents=True, exist_ok=True)
        else:
            new_dir.mkdir(parents=True, exist_ok=True)

        # Update index
        self._entries[filename] = BackupIndexEntry(
            filename=filename,
            display_name=display_name
        )
        self._save_index()

        return new_dir

    def _is_directory_in_use(self, safe_name: str, exclude_filename: str) -> bool:
        """Check if a directory name is already used by another entry.

        Args:
            safe_name: Sanitized directory name to check
            exclude_filename: Filename to exclude from check

        Returns:
            True if another entry uses this directory name
        """
        for entry in self._entries.values():
            if entry.filename != exclude_filename:
                if self._sanitize_dirname(entry.display_name) == safe_name:
                    return True
        return False

    def list_entries(self) -> list[BackupIndexEntry]:
        """List all entries in the index.

        Returns:
            List of all BackupIndexEntry objects
        """
        return list(self._entries.values())

    def get_backup_timestamps(self, entry: BackupIndexEntry) -> list[Path]:
        """Get all backup timestamp directories for an entry.

        Args:
            entry: The backup index entry

        Returns:
            List of Path objects for timestamp directories, sorted newest first
        """
        safe_name = self._sanitize_dirname(entry.display_name)
        item_dir = self.category_dir / safe_name

        if not item_dir.exists():
            return []

        # Get all subdirectories (timestamp directories)
        timestamps = []
        for subdir in item_dir.iterdir():
            if subdir.is_dir():
                timestamps.append(subdir)

        # Sort by name (which is timestamp format YYYY-MM-DD_HHMMSS) newest first
        timestamps.sort(key=lambda p: p.name, reverse=True)
        return timestamps

    def get_backup_files(self, timestamp_dir: Path) -> list[Path]:
        """Get all backup files in a timestamp directory.

        Args:
            timestamp_dir: Path to a timestamp subdirectory

        Returns:
            List of Path objects for backup files
        """
        if not timestamp_dir.exists():
            return []

        return [f for f in timestamp_dir.iterdir() if f.is_file() and f.suffix == ".sav"]
