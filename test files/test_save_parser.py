"""Tests for moria_manager.core.save_parser module."""

import struct
import zlib
from datetime import datetime
from pathlib import Path

import pytest

from moria_manager.core.save_parser import (
    CharacterSaveInfo,
    CharacterWithVersions,
    MoriaSaveParser,
    SaveFileVersion,
    WorldSaveInfo,
    WorldWithVersions,
    get_world_name,
)


class TestSaveFileVersion:
    """Tests for SaveFileVersion dataclass."""

    def test_filename_property(self, tmp_path):
        path = tmp_path / "MW_ABC123.sav"
        v = SaveFileVersion(file_path=path, version_type="main")
        assert v.filename == "MW_ABC123.sav"

    def test_display_name_main(self, tmp_path):
        v = SaveFileVersion(file_path=tmp_path / "test.sav", version_type="main")
        assert "Current Save" in v.display_name

    def test_display_name_fresh(self, tmp_path):
        v = SaveFileVersion(file_path=tmp_path / "test.sav.fresh", version_type="fresh")
        assert "Fresh" in v.display_name

    def test_display_name_backup(self, tmp_path):
        v = SaveFileVersion(
            file_path=tmp_path / "test.01.bak",
            version_type="backup",
            backup_number=1,
        )
        assert "Backup" in v.display_name
        assert "01" in v.display_name

    def test_display_name_bad(self, tmp_path):
        v = SaveFileVersion(
            file_path=tmp_path / "test.sav.02.bad",
            version_type="bad",
            backup_number=2,
        )
        assert "Bad" in v.display_name

    def test_display_name_unknown_type(self, tmp_path):
        v = SaveFileVersion(file_path=tmp_path / "weird.file", version_type="unknown")
        assert v.display_name == "weird.file"


class TestWorldSaveInfo:
    """Tests for WorldSaveInfo dataclass."""

    def test_filename_property(self, tmp_path):
        path = tmp_path / "MW_ABC123.sav"
        info = WorldSaveInfo(
            file_path=path, world_name="Test", world_guid="ABC123", map_name="Map1"
        )
        assert info.filename == "MW_ABC123.sav"

    def test_base_name_from_sav(self, tmp_path):
        path = tmp_path / "MW_ABC123.sav"
        info = WorldSaveInfo(
            file_path=path, world_name="Test", world_guid="ABC123", map_name="Map1"
        )
        assert info.base_name == "MW_ABC123"

    def test_base_name_from_fresh(self, tmp_path):
        path = tmp_path / "MW_ABC123.sav.fresh"
        info = WorldSaveInfo(
            file_path=path, world_name="Test", world_guid="ABC123", map_name="Map1"
        )
        assert info.base_name == "MW_ABC123"

    def test_base_name_from_bak(self, tmp_path):
        path = tmp_path / "MW_ABC123.01.bak"
        info = WorldSaveInfo(
            file_path=path, world_name="Test", world_guid="ABC123", map_name="Map1"
        )
        assert info.base_name == "MW_ABC123"


class TestCharacterSaveInfo:
    """Tests for CharacterSaveInfo dataclass."""

    def test_display_name_with_character_name(self, tmp_path):
        info = CharacterSaveInfo(
            file_path=tmp_path / "MC_DEF456.sav", character_name="Gimli"
        )
        assert info.display_name == "Gimli"

    def test_display_name_fallback_to_base_name(self, tmp_path):
        info = CharacterSaveInfo(
            file_path=tmp_path / "MC_DEF456.sav", character_name=None
        )
        assert info.display_name == "MC_DEF456"

    def test_base_name(self, tmp_path):
        info = CharacterSaveInfo(file_path=tmp_path / "MC_DEF456.sav")
        assert info.base_name == "MC_DEF456"


class TestWorldWithVersions:
    """Tests for WorldWithVersions dataclass."""

    def test_world_name_property(self, tmp_path):
        info = WorldSaveInfo(
            file_path=tmp_path / "MW_A.sav",
            world_name="TestWorld",
            world_guid="A",
            map_name="M",
        )
        wwv = WorldWithVersions(info=info)
        assert wwv.world_name == "TestWorld"

    def test_main_file_found(self, tmp_path):
        info = WorldSaveInfo(
            file_path=tmp_path / "MW_A.sav",
            world_name="TestWorld",
            world_guid="A",
            map_name="M",
        )
        main_ver = SaveFileVersion(file_path=tmp_path / "MW_A.sav", version_type="main")
        wwv = WorldWithVersions(info=info, versions=[main_ver])
        assert wwv.main_file is not None
        assert wwv.main_file.version_type == "main"

    def test_main_file_none_when_missing(self, tmp_path):
        info = WorldSaveInfo(
            file_path=tmp_path / "MW_A.01.bak",
            world_name="TestWorld",
            world_guid="A",
            map_name="M",
        )
        backup_ver = SaveFileVersion(
            file_path=tmp_path / "MW_A.01.bak", version_type="backup", backup_number=1
        )
        wwv = WorldWithVersions(info=info, versions=[backup_ver])
        assert wwv.main_file is None

    def test_fresh_file(self, tmp_path):
        info = WorldSaveInfo(
            file_path=tmp_path / "MW_A.sav",
            world_name="T",
            world_guid="A",
            map_name="M",
        )
        fresh = SaveFileVersion(file_path=tmp_path / "MW_A.sav.fresh", version_type="fresh")
        wwv = WorldWithVersions(info=info, versions=[fresh])
        assert wwv.fresh_file is not None

    def test_backup_files_sorted(self, tmp_path):
        info = WorldSaveInfo(
            file_path=tmp_path / "MW_A.sav",
            world_name="T",
            world_guid="A",
            map_name="M",
        )
        bak2 = SaveFileVersion(
            file_path=tmp_path / "MW_A.02.bak", version_type="backup", backup_number=2
        )
        bak0 = SaveFileVersion(
            file_path=tmp_path / "MW_A.00.bak", version_type="backup", backup_number=0
        )
        bak1 = SaveFileVersion(
            file_path=tmp_path / "MW_A.01.bak", version_type="backup", backup_number=1
        )
        wwv = WorldWithVersions(info=info, versions=[bak2, bak0, bak1])
        backups = wwv.backup_files
        assert [b.backup_number for b in backups] == [0, 1, 2]


class TestCharacterWithVersions:
    """Tests for CharacterWithVersions dataclass."""

    def test_display_name(self, tmp_path):
        info = CharacterSaveInfo(
            file_path=tmp_path / "MC_A.sav", character_name="Gimli"
        )
        cwv = CharacterWithVersions(info=info)
        assert cwv.display_name == "Gimli"

    def test_main_file(self, tmp_path):
        info = CharacterSaveInfo(file_path=tmp_path / "MC_A.sav")
        main = SaveFileVersion(file_path=tmp_path / "MC_A.sav", version_type="main")
        cwv = CharacterWithVersions(info=info, versions=[main])
        assert cwv.main_file is not None

    def test_backup_files_sorted(self, tmp_path):
        info = CharacterSaveInfo(file_path=tmp_path / "MC_A.sav")
        bak1 = SaveFileVersion(
            file_path=tmp_path / "MC_A.01.bak", version_type="backup", backup_number=1
        )
        bak0 = SaveFileVersion(
            file_path=tmp_path / "MC_A.00.bak", version_type="backup", backup_number=0
        )
        cwv = CharacterWithVersions(info=info, versions=[bak1, bak0])
        assert [b.backup_number for b in cwv.backup_files] == [0, 1]


class TestMoriaSaveParserBinaryHelpers:
    """Tests for binary parsing helper methods."""

    def _build_string_property(self, name: bytes, value: str) -> bytes:
        """Build a UE4 string property byte sequence for testing."""
        encoded = value.encode("utf-8") + b"\x00"
        return (
            name
            + b"\x00"  # null terminator
            + b"\x06"  # type byte for string
            + struct.pack("<i", len(encoded))
            + encoded
        )

    def _build_int_property(self, name: bytes, value: int) -> bytes:
        """Build a UE4 int property byte sequence for testing."""
        return (
            name
            + b"\x00"  # null terminator
            + b"\x02"  # type byte for int32
            + struct.pack("<I", value)
        )

    def test_extract_string_property_found(self):
        parser = MoriaSaveParser()
        data = b"HEADER" + self._build_string_property(b"SG_WN", "Test World") + b"FOOTER"
        result = parser._extract_string_property(data, b"SG_WN")
        assert result == "Test World"

    def test_extract_string_property_not_found(self):
        parser = MoriaSaveParser()
        data = b"NO PROPERTIES HERE"
        result = parser._extract_string_property(data, b"SG_WN")
        assert result is None

    def test_extract_string_property_unicode(self):
        parser = MoriaSaveParser()
        data = b"X" + self._build_string_property(b"SG_WN", "W\u00f6rld") + b"Y"
        result = parser._extract_string_property(data, b"SG_WN")
        assert result == "W\u00f6rld"

    def test_extract_int_property_found(self):
        parser = MoriaSaveParser()
        data = b"X" + self._build_int_property(b"SG_WS", 12345) + b"Y"
        result = parser._extract_int_property(data, b"SG_WS")
        assert result == 12345

    def test_extract_int_property_not_found(self):
        parser = MoriaSaveParser()
        data = b"NO PROPERTIES"
        result = parser._extract_int_property(data, b"SG_WS")
        assert result is None

    def test_extract_int_property_zero(self):
        parser = MoriaSaveParser()
        data = b"X" + self._build_int_property(b"SG_WS", 0) + b"Y"
        result = parser._extract_int_property(data, b"SG_WS")
        assert result == 0


class TestDecompressFirstCsdc:
    """Tests for _decompress_first_csdc."""

    def test_returns_none_for_no_csdc(self):
        parser = MoriaSaveParser()
        data = b"GVAS" + b"\x00" * 100
        result = parser._decompress_first_csdc(data)
        assert result is None

    def test_returns_none_for_invalid_compressed_data(self):
        parser = MoriaSaveParser()
        data = b"GVAS" + b"CSDC" + b"\x00" * 100
        result = parser._decompress_first_csdc(data)
        assert result is None

    def test_decompresses_valid_csdc(self):
        parser = MoriaSaveParser()
        # Build fake CSDC block with valid zlib data containing SG_ marker
        payload = b"SG_WN" + b"\x00" * 20
        compressed = zlib.compress(payload)
        # Pad to offset 60 (the first offset tried)
        data = b"CSDC" + b"\x00" * 56 + compressed
        result = parser._decompress_first_csdc(data)
        assert result is not None
        assert b"SG_WN" in result


class TestGetWorldSaves:
    """Tests for get_world_saves with mock files."""

    def test_empty_directory(self, mock_save_dir):
        parser = MoriaSaveParser()
        worlds = parser.get_world_saves(mock_save_dir)
        assert worlds == []

    def test_nonexistent_directory(self, tmp_path):
        parser = MoriaSaveParser()
        worlds = parser.get_world_saves(tmp_path / "nonexistent")
        assert worlds == []

    def test_ignores_non_sav_files(self, mock_save_dir):
        (mock_save_dir / "README.txt").write_text("ignore me")
        (mock_save_dir / "MW_ABC123.txt").write_text("not a save")
        parser = MoriaSaveParser()
        worlds = parser.get_world_saves(mock_save_dir)
        assert worlds == []

    def test_ignores_character_files(self, mock_save_dir):
        # Create a fake .sav that isn't a valid GVAS
        (mock_save_dir / "MC_DEF456.sav").write_bytes(b"GVAS" + b"\x00" * 100)
        parser = MoriaSaveParser()
        worlds = parser.get_world_saves(mock_save_dir)
        assert worlds == []


class TestGetCharacterSaves:
    """Tests for get_character_saves with mock files."""

    def test_empty_directory(self, mock_save_dir):
        parser = MoriaSaveParser()
        chars = parser.get_character_saves(mock_save_dir)
        assert chars == []

    def test_nonexistent_directory(self, tmp_path):
        parser = MoriaSaveParser()
        chars = parser.get_character_saves(tmp_path / "nonexistent")
        assert chars == []

    def test_ignores_world_files(self, mock_save_dir):
        (mock_save_dir / "MW_ABC123.sav").write_bytes(b"GVAS" + b"\x00" * 100)
        parser = MoriaSaveParser()
        chars = parser.get_character_saves(mock_save_dir)
        assert chars == []


class TestGetWorldsWithVersions:
    """Tests for get_worlds_with_versions."""

    def test_empty_directory(self, mock_save_dir):
        parser = MoriaSaveParser()
        result = parser.get_worlds_with_versions(mock_save_dir)
        assert result == []

    def test_nonexistent_directory(self, tmp_path):
        parser = MoriaSaveParser()
        result = parser.get_worlds_with_versions(tmp_path / "nonexistent")
        assert result == []


class TestGetWorldNameMapping:
    """Tests for get_world_name_mapping."""

    def test_empty_directory(self, mock_save_dir):
        parser = MoriaSaveParser()
        mapping = parser.get_world_name_mapping(mock_save_dir)
        assert mapping == {}


class TestGetWorldNameConvenience:
    """Tests for get_world_name convenience function."""

    def test_returns_none_for_invalid_file(self, tmp_path):
        fake_save = tmp_path / "MW_TEST.sav"
        fake_save.write_bytes(b"not a GVAS file")
        result = get_world_name(fake_save)
        assert result is None

    def test_returns_none_for_nonexistent_file(self, tmp_path):
        result = get_world_name(tmp_path / "nonexistent.sav")
        assert result is None
