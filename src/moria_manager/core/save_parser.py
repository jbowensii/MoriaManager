"""Parser for Return to Moria save game files.

The game uses Unreal Engine 4.27 GVAS save format with zlib compression.
Save files contain CSDC (Compressed Save Data Container) blocks.

File types:
- MW_*.sav - World saves (contain world name, seed, etc.)
- MC_*.sav - Character saves
- MA_*.sav - Account/common data

Related files for a world (e.g., MW_ABC123):
- MW_ABC123.sav - Main save file
- MW_ABC123.sav.fresh - Fresh/template backup
- MW_ABC123.00.bak - Numbered backup (oldest)
- MW_ABC123.01.bak - Numbered backup
- MW_ABC123.02.bak - Numbered backup (newest)
"""

import re
import struct
import zlib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..logging_config import get_logger

logger = get_logger("save_parser")


@dataclass
class SaveFileVersion:
    """A single version of a save file (main, fresh, backup, or bad)."""
    file_path: Path
    version_type: str  # "main", "fresh", "backup", "bad"
    backup_number: Optional[int] = None  # For .XX.bak or .XX.bad files
    modified_time: Optional[datetime] = None
    file_size: int = 0

    @property
    def filename(self) -> str:
        return self.file_path.name

    @property
    def display_name(self) -> str:
        """Human-readable name for this version."""
        if self.version_type == "main":
            return "Current Save (.sav)"
        elif self.version_type == "fresh":
            return "Fresh Backup (.sav.fresh)"
        elif self.version_type == "backup":
            return f"Backup #{self.backup_number:02d} (.{self.backup_number:02d}.bak)"
        elif self.version_type == "bad":
            return f"Marked Bad #{self.backup_number:02d} (.sav.{self.backup_number:02d}.bad)"
        return self.filename


@dataclass
class WorldSaveInfo:
    """Information extracted from a world save file."""
    file_path: Path
    world_name: str
    world_guid: str
    map_name: str
    world_seed: Optional[int] = None
    modified_time: Optional[datetime] = None

    @property
    def filename(self) -> str:
        return self.file_path.name

    @property
    def base_name(self) -> str:
        """Get the base filename without extension (e.g., MW_ABC123).

        Handles all file types:
        - MW_ABC123.sav -> MW_ABC123
        - MW_ABC123.sav.fresh -> MW_ABC123
        - MW_ABC123.01.bak -> MW_ABC123
        - MW_ABC123.sav.01.bad -> MW_ABC123
        """
        name = self.file_path.name
        # Extract everything before the first '.'
        if '.' in name:
            return name.split('.')[0]
        return name


@dataclass
class WorldWithVersions:
    """A world save with all its related file versions."""
    info: WorldSaveInfo
    versions: list[SaveFileVersion] = field(default_factory=list)

    @property
    def world_name(self) -> str:
        return self.info.world_name

    @property
    def base_name(self) -> str:
        return self.info.base_name

    @property
    def main_file(self) -> Optional[SaveFileVersion]:
        """Get the main .sav file."""
        for v in self.versions:
            if v.version_type == "main":
                return v
        return None

    @property
    def fresh_file(self) -> Optional[SaveFileVersion]:
        """Get the .sav.fresh file if it exists."""
        for v in self.versions:
            if v.version_type == "fresh":
                return v
        return None

    @property
    def backup_files(self) -> list[SaveFileVersion]:
        """Get all .XX.bak files sorted by number."""
        backups = [v for v in self.versions if v.version_type == "backup"]
        return sorted(backups, key=lambda v: v.backup_number or 0)


@dataclass
class CharacterSaveInfo:
    """Information extracted from a character save file."""
    file_path: Path
    character_name: Optional[str] = None
    modified_time: Optional[datetime] = None

    @property
    def filename(self) -> str:
        return self.file_path.name

    @property
    def base_name(self) -> str:
        """Get the base filename without extension (e.g., MC_ABC123).

        Handles all file types:
        - MC_ABC123.sav -> MC_ABC123
        - MC_ABC123.sav.fresh -> MC_ABC123
        - MC_ABC123.01.bak -> MC_ABC123
        - MC_ABC123.sav.01.bad -> MC_ABC123
        """
        name = self.file_path.name
        # Extract everything before the first '.'
        if '.' in name:
            return name.split('.')[0]
        return name

    @property
    def display_name(self) -> str:
        """Get display name (character name or filename)."""
        return self.character_name or self.base_name


@dataclass
class CharacterWithVersions:
    """A character save with all its related file versions."""
    info: CharacterSaveInfo
    versions: list[SaveFileVersion] = field(default_factory=list)

    @property
    def display_name(self) -> str:
        return self.info.display_name

    @property
    def base_name(self) -> str:
        return self.info.base_name

    @property
    def main_file(self) -> Optional[SaveFileVersion]:
        """Get the main .sav file."""
        for v in self.versions:
            if v.version_type == "main":
                return v
        return None

    @property
    def fresh_file(self) -> Optional[SaveFileVersion]:
        """Get the .sav.fresh file if it exists."""
        for v in self.versions:
            if v.version_type == "fresh":
                return v
        return None

    @property
    def backup_files(self) -> list[SaveFileVersion]:
        """Get all .XX.bak files sorted by number."""
        backups = [v for v in self.versions if v.version_type == "backup"]
        return sorted(backups, key=lambda v: v.backup_number or 0)


class MoriaSaveParser:
    """Parser for Return to Moria save game files.

    Handles the GVAS format with CSDC compression used by UE4.27.
    """

    # Save file prefixes
    WORLD_PREFIX = "MW_"
    CHARACTER_PREFIX = "MC_"
    ACCOUNT_PREFIX = "MA_"

    # Property keys in the save data
    PROP_WORLD_NAME = b"SG_WN"  # World Name
    PROP_WORLD_GUID = b"SG_WGUID"  # World GUID
    PROP_WORLD_SEED = b"SG_WS"  # World Seed
    PROP_MAP_NAME = b"SG_MN"  # Map Name

    def __init__(self):
        pass

    def parse_world_save(self, file_path: Path) -> Optional[WorldSaveInfo]:
        """Parse a world save file and extract metadata.

        Args:
            file_path: Path to the MW_*.sav file

        Returns:
            WorldSaveInfo with extracted data, or None if parsing fails
        """
        try:
            with open(file_path, "rb") as f:
                data = f.read()

            # Validate GVAS header
            if not data.startswith(b"GVAS"):
                return None

            # Decompress the first CSDC block
            decompressed = self._decompress_first_csdc(data)
            if decompressed is None:
                return None

            # Extract properties
            world_name = self._extract_string_property(decompressed, self.PROP_WORLD_NAME)
            world_guid = self._extract_string_property(decompressed, self.PROP_WORLD_GUID)
            map_name = self._extract_string_property(decompressed, self.PROP_MAP_NAME)
            world_seed = self._extract_int_property(decompressed, self.PROP_WORLD_SEED)

            # Get file modification time
            modified_time = datetime.fromtimestamp(file_path.stat().st_mtime)

            return WorldSaveInfo(
                file_path=file_path,
                world_name=world_name or "Unknown World",
                world_guid=world_guid or "",
                map_name=map_name or "",
                world_seed=world_seed,
                modified_time=modified_time,
            )

        except (OSError, IOError, ValueError, struct.error) as e:
            # Log error but don't crash
            logger.warning("Error parsing world save %s: %s", file_path, e)
            return None

    def parse_character_save(self, file_path: Path) -> Optional[CharacterSaveInfo]:
        """Parse a character save file and extract metadata.

        Character saves have two CSDC blocks:
        - First block: Small header with "PSTR" marker
        - Second block: "SDCP" section with character name at offset 29

        Args:
            file_path: Path to the MC_*.sav file

        Returns:
            CharacterSaveInfo with extracted data, or None if parsing fails
        """
        try:
            with open(file_path, "rb") as f:
                data = f.read()

            # Validate GVAS header
            if not data.startswith(b"GVAS"):
                return None

            # Get file modification time
            modified_time = datetime.fromtimestamp(file_path.stat().st_mtime)

            # Extract character name from second CSDC block
            character_name = self._extract_character_name(data)

            return CharacterSaveInfo(
                file_path=file_path,
                character_name=character_name,
                modified_time=modified_time,
            )

        except (OSError, IOError, ValueError, struct.error) as e:
            logger.warning("Error parsing character save %s: %s", file_path, e)
            return None

    def get_world_saves(self, save_directory: Path) -> list[WorldSaveInfo]:
        """Get all world saves from a directory.

        Args:
            save_directory: Path to the save games directory

        Returns:
            List of WorldSaveInfo for each valid world save
        """
        worlds = []

        if not save_directory.exists():
            return worlds

        for save_file in save_directory.glob(f"{self.WORLD_PREFIX}*.sav"):
            # Skip backup files
            if ".bak" in save_file.suffixes:
                continue

            info = self.parse_world_save(save_file)
            if info:
                worlds.append(info)

        # Sort by modification time, newest first
        worlds.sort(key=lambda w: w.modified_time or datetime.min, reverse=True)
        return worlds

    def get_character_saves(self, save_directory: Path) -> list[CharacterSaveInfo]:
        """Get all character saves from a directory.

        Args:
            save_directory: Path to the save games directory

        Returns:
            List of CharacterSaveInfo for each valid character save
        """
        characters = []

        if not save_directory.exists():
            return characters

        for save_file in save_directory.glob(f"{self.CHARACTER_PREFIX}*.sav"):
            if ".bak" in save_file.suffixes:
                continue

            info = self.parse_character_save(save_file)
            if info:
                characters.append(info)

        characters.sort(key=lambda c: c.modified_time or datetime.min, reverse=True)
        return characters

    def get_worlds_with_versions(self, save_directory: Path) -> list[WorldWithVersions]:
        """Get all world saves with their related file versions.

        Scans the directory for MW_* files, parses them for world names,
        and groups all related files (.sav, .sav.fresh, .XX.bak) together.
        Also discovers worlds that only have backup files (no main .sav).

        Args:
            save_directory: Path to the save games directory

        Returns:
            List of WorldWithVersions, sorted by modification time (newest first)
        """
        if not save_directory.exists():
            return []

        # First, get all world saves (main .sav files only)
        worlds = self.get_world_saves(save_directory)

        # Build a mapping of base_name -> WorldWithVersions
        world_map: dict[str, WorldWithVersions] = {}
        for world_info in worlds:
            base_name = world_info.base_name
            world_map[base_name] = WorldWithVersions(info=world_info, versions=[])

        # Patterns for related files
        backup_pattern = re.compile(r"^(MW_[A-F0-9]+)\.(\d{2})\.bak$", re.IGNORECASE)
        fresh_pattern = re.compile(r"^(MW_[A-F0-9]+)\.sav\.fresh$", re.IGNORECASE)
        bad_pattern = re.compile(r"^(MW_[A-F0-9]+)\.sav\.(\d{2})\.bad$", re.IGNORECASE)

        # Collect orphan files (files without a main .sav) to process later
        orphan_files: dict[str, list[tuple[Path, str, Optional[int]]]] = {}  # base_name -> [(path, type, num)]

        for file_path in save_directory.iterdir():
            if not file_path.is_file():
                continue

            filename = file_path.name

            # Skip non-MW files
            if not filename.startswith(self.WORLD_PREFIX):
                continue

            try:
                stat = file_path.stat()
                modified_time = datetime.fromtimestamp(stat.st_mtime)
                file_size = stat.st_size
            except OSError:
                modified_time = None
                file_size = 0

            # Check file type
            if filename.endswith(".sav") and not ".sav." in filename:
                # Main save file
                base_name = filename[:-4]  # Remove .sav
                if base_name in world_map:
                    world_map[base_name].versions.append(SaveFileVersion(
                        file_path=file_path,
                        version_type="main",
                        modified_time=modified_time,
                        file_size=file_size,
                    ))

            elif fresh_pattern.match(filename):
                # Fresh backup
                match = fresh_pattern.match(filename)
                base_name = match.group(1)
                if base_name in world_map:
                    world_map[base_name].versions.append(SaveFileVersion(
                        file_path=file_path,
                        version_type="fresh",
                        modified_time=modified_time,
                        file_size=file_size,
                    ))
                else:
                    # Orphan fresh file
                    if base_name not in orphan_files:
                        orphan_files[base_name] = []
                    orphan_files[base_name].append((file_path, "fresh", None))

            elif backup_pattern.match(filename):
                # .XX.bak backup
                match = backup_pattern.match(filename)
                base_name = match.group(1)
                backup_num = int(match.group(2))
                if base_name in world_map:
                    world_map[base_name].versions.append(SaveFileVersion(
                        file_path=file_path,
                        version_type="backup",
                        backup_number=backup_num,
                        modified_time=modified_time,
                        file_size=file_size,
                    ))
                else:
                    # Orphan backup file
                    if base_name not in orphan_files:
                        orphan_files[base_name] = []
                    orphan_files[base_name].append((file_path, "backup", backup_num))

            elif bad_pattern.match(filename):
                # .sav.XX.bad file (marked as bad)
                match = bad_pattern.match(filename)
                base_name = match.group(1)
                bad_num = int(match.group(2))
                if base_name in world_map:
                    world_map[base_name].versions.append(SaveFileVersion(
                        file_path=file_path,
                        version_type="bad",
                        backup_number=bad_num,
                        modified_time=modified_time,
                        file_size=file_size,
                    ))
                else:
                    # Orphan bad file
                    if base_name not in orphan_files:
                        orphan_files[base_name] = []
                    orphan_files[base_name].append((file_path, "bad", bad_num))

        # Process orphan files - create WorldWithVersions entries for them
        for base_name, files in orphan_files.items():
            if base_name in world_map:
                # Already processed, just add versions
                continue

            # Try to parse one of the files to get the world name
            world_name = None
            best_file = None

            # Prefer fresh > backup > bad for parsing
            for file_path, file_type, _ in sorted(files, key=lambda x: {"fresh": 0, "backup": 1, "bad": 2}.get(x[1], 3)):
                parsed = self.parse_world_save(file_path)
                if parsed and parsed.world_name:
                    world_name = parsed.world_name
                    best_file = file_path
                    break

            if not world_name:
                # Use base name as fallback
                world_name = base_name

            # Get modification time from first available file
            first_file = files[0][0]
            try:
                modified_time = datetime.fromtimestamp(first_file.stat().st_mtime)
            except OSError:
                modified_time = None

            # Create a WorldSaveInfo for the orphan
            world_info = WorldSaveInfo(
                file_path=best_file or first_file,
                world_name=world_name,
                world_guid=base_name.replace("MW_", ""),
                map_name="",
                modified_time=modified_time,
            )

            world_map[base_name] = WorldWithVersions(info=world_info, versions=[])

            # Add all the orphan files as versions
            for file_path, file_type, num in files:
                try:
                    stat = file_path.stat()
                    mod_time = datetime.fromtimestamp(stat.st_mtime)
                    file_size = stat.st_size
                except OSError:
                    mod_time = None
                    file_size = 0

                world_map[base_name].versions.append(SaveFileVersion(
                    file_path=file_path,
                    version_type=file_type,
                    backup_number=num,
                    modified_time=mod_time,
                    file_size=file_size,
                ))

        # Convert to list and sort by modification time (newest first)
        result = list(world_map.values())
        result.sort(
            key=lambda w: w.info.modified_time or datetime.min,
            reverse=True
        )

        return result

    def get_world_name_mapping(self, save_directory: Path) -> dict[str, str]:
        """Get a mapping of base filenames to world names.

        Args:
            save_directory: Path to the save games directory

        Returns:
            Dictionary mapping base_name (e.g., "MW_ABC123") to world_name
        """
        worlds = self.get_world_saves(save_directory)
        return {world.base_name: world.world_name for world in worlds}

    def get_characters_with_versions(self, save_directory: Path) -> list[CharacterWithVersions]:
        """Get all character saves with their related file versions.

        Scans the directory for MC_* files and groups all related files
        (.sav, .sav.fresh, .XX.bak) together. Also discovers characters
        that only have backup files (no main .sav).

        Args:
            save_directory: Path to the save games directory

        Returns:
            List of CharacterWithVersions, sorted by modification time (newest first)
        """
        if not save_directory.exists():
            return []

        # First, get all character saves (main .sav files only)
        characters = self.get_character_saves(save_directory)

        # Build a mapping of base_name -> CharacterWithVersions
        char_map: dict[str, CharacterWithVersions] = {}
        for char_info in characters:
            base_name = char_info.base_name
            char_map[base_name] = CharacterWithVersions(info=char_info, versions=[])

        # Patterns for related files
        backup_pattern = re.compile(r"^(MC_[A-F0-9]+)\.(\d{2})\.bak$", re.IGNORECASE)
        fresh_pattern = re.compile(r"^(MC_[A-F0-9]+)\.sav\.fresh$", re.IGNORECASE)
        bad_pattern = re.compile(r"^(MC_[A-F0-9]+)\.sav\.(\d{2})\.bad$", re.IGNORECASE)

        # Collect orphan files (files without a main .sav) to process later
        orphan_files: dict[str, list[tuple[Path, str, Optional[int]]]] = {}

        for file_path in save_directory.iterdir():
            if not file_path.is_file():
                continue

            filename = file_path.name

            # Skip non-MC files
            if not filename.startswith(self.CHARACTER_PREFIX):
                continue

            try:
                stat = file_path.stat()
                modified_time = datetime.fromtimestamp(stat.st_mtime)
                file_size = stat.st_size
            except OSError:
                modified_time = None
                file_size = 0

            # Check file type
            if filename.endswith(".sav") and not ".sav." in filename:
                # Main save file
                base_name = filename[:-4]  # Remove .sav
                if base_name in char_map:
                    char_map[base_name].versions.append(SaveFileVersion(
                        file_path=file_path,
                        version_type="main",
                        modified_time=modified_time,
                        file_size=file_size,
                    ))

            elif fresh_pattern.match(filename):
                # Fresh backup
                match = fresh_pattern.match(filename)
                base_name = match.group(1)
                if base_name in char_map:
                    char_map[base_name].versions.append(SaveFileVersion(
                        file_path=file_path,
                        version_type="fresh",
                        modified_time=modified_time,
                        file_size=file_size,
                    ))
                else:
                    # Orphan fresh file
                    if base_name not in orphan_files:
                        orphan_files[base_name] = []
                    orphan_files[base_name].append((file_path, "fresh", None))

            elif backup_pattern.match(filename):
                # .XX.bak backup
                match = backup_pattern.match(filename)
                base_name = match.group(1)
                backup_num = int(match.group(2))
                if base_name in char_map:
                    char_map[base_name].versions.append(SaveFileVersion(
                        file_path=file_path,
                        version_type="backup",
                        backup_number=backup_num,
                        modified_time=modified_time,
                        file_size=file_size,
                    ))
                else:
                    # Orphan backup file
                    if base_name not in orphan_files:
                        orphan_files[base_name] = []
                    orphan_files[base_name].append((file_path, "backup", backup_num))

            elif bad_pattern.match(filename):
                # .sav.XX.bad file (marked as bad)
                match = bad_pattern.match(filename)
                base_name = match.group(1)
                bad_num = int(match.group(2))
                if base_name in char_map:
                    char_map[base_name].versions.append(SaveFileVersion(
                        file_path=file_path,
                        version_type="bad",
                        backup_number=bad_num,
                        modified_time=modified_time,
                        file_size=file_size,
                    ))
                else:
                    # Orphan bad file
                    if base_name not in orphan_files:
                        orphan_files[base_name] = []
                    orphan_files[base_name].append((file_path, "bad", bad_num))

        # Process orphan files - create CharacterWithVersions entries for them
        for base_name, files in orphan_files.items():
            if base_name in char_map:
                continue

            # Try to parse one of the files to get the character name
            char_name = None
            best_file = None

            for file_path, file_type, _ in sorted(files, key=lambda x: {"fresh": 0, "backup": 1, "bad": 2}.get(x[1], 3)):
                parsed = self.parse_character_save(file_path)
                if parsed and parsed.character_name:
                    char_name = parsed.character_name
                    best_file = file_path
                    break

            if not char_name:
                char_name = base_name  # Fallback

            # Get modification time from first available file
            first_file = files[0][0]
            try:
                modified_time = datetime.fromtimestamp(first_file.stat().st_mtime)
            except OSError:
                modified_time = None

            # Create a CharacterSaveInfo for the orphan
            char_info = CharacterSaveInfo(
                file_path=best_file or first_file,
                character_name=char_name,
                modified_time=modified_time,
            )

            char_map[base_name] = CharacterWithVersions(info=char_info, versions=[])

            # Add all the orphan files as versions
            for file_path, file_type, num in files:
                try:
                    stat = file_path.stat()
                    mod_time = datetime.fromtimestamp(stat.st_mtime)
                    file_size = stat.st_size
                except OSError:
                    mod_time = None
                    file_size = 0

                char_map[base_name].versions.append(SaveFileVersion(
                    file_path=file_path,
                    version_type=file_type,
                    backup_number=num,
                    modified_time=mod_time,
                    file_size=file_size,
                ))

        # Convert to list and sort by modification time (newest first)
        result = list(char_map.values())
        result.sort(
            key=lambda c: c.info.modified_time or datetime.min,
            reverse=True
        )

        return result

    def _decompress_first_csdc(self, data: bytes) -> Optional[bytes]:
        """Find and decompress the first CSDC block.

        Args:
            data: Raw save file data

        Returns:
            Decompressed data or None if decompression fails
        """
        csdc_pos = data.find(b"CSDC")
        if csdc_pos == -1:
            return None

        # Try various offsets for zlib data (header size varies)
        for offset_add in [60, 24, 36, 48, 52, 56, 64]:
            try:
                decompressed = zlib.decompress(data[csdc_pos + offset_add:])
                # Validate we got reasonable data
                if len(decompressed) > 10 and b"SG_" in decompressed:
                    return decompressed
            except zlib.error:
                continue

        return None

    def _extract_character_name(self, data: bytes) -> Optional[str]:
        """Extract character name from a character save file.

        Character saves have multiple CSDC blocks. The block containing
        the "SDCP" marker has the character name at offset 29/33.

        Name encoding:
        - Positive length: UTF-8 encoded, length is byte count including null
        - Negative length: UTF-16-LE encoded, abs(length) is char count including null

        Args:
            data: Raw save file data

        Returns:
            Character name or None if extraction fails
        """
        # Find all CSDC blocks and look for one with SDCP marker
        pos = 0
        while True:
            csdc_pos = data.find(b"CSDC", pos)
            if csdc_pos == -1:
                return None

            # Try to decompress this block
            try:
                decompressed = zlib.decompress(data[csdc_pos + 60:])
            except zlib.error:
                pos = csdc_pos + 4
                continue

            # Check for SDCP marker at offset 4
            if len(decompressed) >= 40 and decompressed[4:8] == b"SDCP":
                # Found the SDCP block - extract name
                try:
                    # Name length is at offset 29 (signed int32)
                    name_len = struct.unpack("<i", decompressed[29:33])[0]

                    if name_len > 0:
                        # Positive: UTF-8 encoded, length is byte count including null
                        if name_len > 100:  # Sanity check
                            return None
                        name = decompressed[33:33 + name_len - 1].decode("utf-8", errors="replace")
                        return name
                    elif name_len < 0:
                        # Negative: UTF-16-LE encoded, abs(length) is char count including null
                        char_count = abs(name_len)
                        if char_count > 100:  # Sanity check
                            return None
                        byte_count = char_count * 2
                        # Exclude null terminator (2 bytes for UTF-16)
                        name = decompressed[33:33 + byte_count - 2].decode("utf-16-le", errors="replace")
                        return name
                    else:
                        return None
                except (struct.error, IndexError, UnicodeDecodeError):
                    return None

            # Move to next CSDC block
            pos = csdc_pos + 4

    def _extract_string_property(self, data: bytes, property_name: bytes) -> Optional[str]:
        """Extract a string property from decompressed save data.

        UE4 string format: property_name + null + type_byte + int32_length + string + null

        In UE4, string length encoding:
        - Positive length: UTF-8 encoded string, length is byte count including null terminator
        - Negative length: UTF-16-LE encoded string, abs(length) is character count including null

        Args:
            data: Decompressed save data
            property_name: Property name to find (e.g., b"SG_WN")

        Returns:
            Extracted string or None if not found
        """
        pos = data.find(property_name)
        if pos == -1:
            return None

        try:
            # Skip property name + null terminator
            pos += len(property_name) + 1

            # Read type byte (0x06 for string)
            type_byte = data[pos]
            pos += 1

            if type_byte == 0x06:  # String type
                # Read length as signed int32 (negative = UTF-16)
                str_len = struct.unpack("<i", data[pos:pos + 4])[0]
                pos += 4

                if str_len < 0:
                    # Negative length indicates UTF-16-LE encoding
                    # abs(length) is character count including null terminator
                    char_count = -str_len
                    byte_count = char_count * 2  # UTF-16 = 2 bytes per char
                    raw_bytes = data[pos:pos + byte_count - 2]  # Exclude null terminator (2 bytes)
                    value = raw_bytes.decode("utf-16-le", errors="replace")
                else:
                    # Positive length is UTF-8, length includes null terminator
                    value = data[pos:pos + str_len - 1].decode("utf-8", errors="replace")

                return value

        except (struct.error, IndexError):
            pass

        return None

    def _extract_int_property(self, data: bytes, property_name: bytes) -> Optional[int]:
        """Extract an integer property from decompressed save data.

        Args:
            data: Decompressed save data
            property_name: Property name to find

        Returns:
            Extracted integer or None if not found
        """
        pos = data.find(property_name)
        if pos == -1:
            return None

        try:
            # Skip property name + null terminator
            pos += len(property_name) + 1

            # Read type byte
            type_byte = data[pos]
            pos += 1

            if type_byte == 0x02:  # Int32 type
                value = struct.unpack("<I", data[pos:pos + 4])[0]
                return value

        except (struct.error, IndexError):
            pass

        return None


# Convenience function
def get_world_name(save_file: Path) -> Optional[str]:
    """Quick helper to get just the world name from a save file.

    Args:
        save_file: Path to a MW_*.sav file

    Returns:
        World name or None if parsing fails
    """
    parser = MoriaSaveParser()
    info = parser.parse_world_save(save_file)
    return info.world_name if info else None
