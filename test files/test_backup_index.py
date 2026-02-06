"""Tests for moria_manager.core.backup_index module."""

from pathlib import Path

import pytest

from moria_manager.core.backup_index import BackupIndexEntry, BackupIndexManager


class TestBackupIndexEntry:
    """Tests for BackupIndexEntry dataclass."""

    def test_creation(self):
        entry = BackupIndexEntry(filename="MW_ABC123", display_name="Test World")
        assert entry.filename == "MW_ABC123"
        assert entry.display_name == "Test World"


class TestBackupIndexManagerInit:
    """Tests for BackupIndexManager initialization."""

    def test_creates_category_dir(self, tmp_backup_dir, tmp_config_dir):
        manager = BackupIndexManager(tmp_backup_dir, "worlds")
        assert (tmp_backup_dir / "worlds").exists()

    def test_creates_config_dir(self, tmp_backup_dir, tmp_config_dir):
        manager = BackupIndexManager(tmp_backup_dir, "worlds")
        assert tmp_config_dir.exists()

    def test_worlds_index_file(self, tmp_backup_dir, tmp_config_dir):
        manager = BackupIndexManager(tmp_backup_dir, "worlds")
        assert manager.index_file == tmp_config_dir / "index_worlds.xml"

    def test_characters_index_file(self, tmp_backup_dir, tmp_config_dir):
        manager = BackupIndexManager(tmp_backup_dir, "characters")
        assert manager.index_file == tmp_config_dir / "index_characters.xml"

    def test_custom_category_index_file(self, tmp_backup_dir, tmp_config_dir):
        manager = BackupIndexManager(tmp_backup_dir, "custom")
        assert manager.index_file == tmp_config_dir / "index_custom.xml"


class TestSanitizeDirname:
    """Tests for BackupIndexManager._sanitize_dirname()."""

    def test_normal_name(self, tmp_backup_dir, tmp_config_dir):
        manager = BackupIndexManager(tmp_backup_dir, "worlds")
        assert manager._sanitize_dirname("My World") == "My World"

    def test_invalid_chars_replaced(self, tmp_backup_dir, tmp_config_dir):
        manager = BackupIndexManager(tmp_backup_dir, "worlds")
        result = manager._sanitize_dirname('Test<>:"/\\|?*World')
        assert "<" not in result
        assert ">" not in result
        assert ":" not in result

    def test_strips_dots_and_spaces(self, tmp_backup_dir, tmp_config_dir):
        manager = BackupIndexManager(tmp_backup_dir, "worlds")
        result = manager._sanitize_dirname("...test...")
        assert not result.startswith(".")
        assert not result.endswith(".")

    def test_empty_name_returns_unknown(self, tmp_backup_dir, tmp_config_dir):
        manager = BackupIndexManager(tmp_backup_dir, "worlds")
        assert manager._sanitize_dirname("") == "Unknown"

    def test_unicode_names(self, tmp_backup_dir, tmp_config_dir):
        manager = BackupIndexManager(tmp_backup_dir, "worlds")
        result = manager._sanitize_dirname("W\u00f6rld \u00c4dventure")
        assert "\u00f6" in result


class TestGetEntry:
    """Tests for get_entry() and list_entries()."""

    def test_returns_none_for_unknown(self, tmp_backup_dir, tmp_config_dir):
        manager = BackupIndexManager(tmp_backup_dir, "worlds")
        assert manager.get_entry("MW_NONEXIST") is None

    def test_returns_entry_after_registration(self, tmp_backup_dir, tmp_config_dir):
        manager = BackupIndexManager(tmp_backup_dir, "worlds")
        manager.get_backup_directory("MW_ABC123", "Test World")
        entry = manager.get_entry("MW_ABC123")
        assert entry is not None
        assert entry.display_name == "Test World"

    def test_list_entries_empty(self, tmp_backup_dir, tmp_config_dir):
        manager = BackupIndexManager(tmp_backup_dir, "worlds")
        assert manager.list_entries() == []

    def test_list_entries_after_add(self, tmp_backup_dir, tmp_config_dir):
        manager = BackupIndexManager(tmp_backup_dir, "worlds")
        manager.get_backup_directory("MW_ABC123", "World A")
        manager.get_backup_directory("MW_DEF456", "World B")
        entries = manager.list_entries()
        assert len(entries) == 2
        names = {e.display_name for e in entries}
        assert names == {"World A", "World B"}


class TestGetBackupDirectory:
    """Tests for get_backup_directory()."""

    def test_creates_directory(self, tmp_backup_dir, tmp_config_dir):
        manager = BackupIndexManager(tmp_backup_dir, "worlds")
        backup_dir = manager.get_backup_directory("MW_ABC123", "Test World")
        assert backup_dir.exists()
        assert backup_dir.is_dir()

    def test_consistent_for_same_entry(self, tmp_backup_dir, tmp_config_dir):
        manager = BackupIndexManager(tmp_backup_dir, "worlds")
        dir1 = manager.get_backup_directory("MW_ABC123", "Test World")
        dir2 = manager.get_backup_directory("MW_ABC123", "Test World")
        assert dir1 == dir2

    def test_directory_named_after_display_name(self, tmp_backup_dir, tmp_config_dir):
        manager = BackupIndexManager(tmp_backup_dir, "worlds")
        backup_dir = manager.get_backup_directory("MW_ABC123", "My Cool World")
        assert backup_dir.name == "My Cool World"

    def test_rename_on_name_change(self, tmp_backup_dir, tmp_config_dir):
        manager = BackupIndexManager(tmp_backup_dir, "worlds")
        dir1 = manager.get_backup_directory("MW_ABC123", "Old Name")
        # Put a file in there to verify rename
        (dir1 / "test.sav").write_text("test")
        dir2 = manager.get_backup_directory("MW_ABC123", "New Name")
        assert dir2.name == "New Name"
        assert (dir2 / "test.sav").exists()
        assert not dir1.exists()

    def test_different_files_get_different_dirs(self, tmp_backup_dir, tmp_config_dir):
        manager = BackupIndexManager(tmp_backup_dir, "worlds")
        dir1 = manager.get_backup_directory("MW_ABC123", "World A")
        dir2 = manager.get_backup_directory("MW_DEF456", "World B")
        assert dir1 != dir2

    def test_name_collision_resolved(self, tmp_backup_dir, tmp_config_dir):
        manager = BackupIndexManager(tmp_backup_dir, "worlds")
        dir1 = manager.get_backup_directory("MW_ABC123", "Same Name")
        dir2 = manager.get_backup_directory("MW_DEF456", "Same Name")
        assert dir1 != dir2
        assert dir1.exists()
        assert dir2.exists()


class TestCleanupStaleEntries:
    """Tests for cleanup_stale_entries()."""

    def test_removes_missing_directory(self, tmp_backup_dir, tmp_config_dir):
        manager = BackupIndexManager(tmp_backup_dir, "worlds")
        backup_dir = manager.get_backup_directory("MW_ABC123", "Test World")
        # Remove the directory to make entry stale
        backup_dir.rmdir()
        removed = manager.cleanup_stale_entries()
        assert removed == 1
        assert manager.get_entry("MW_ABC123") is None

    def test_removes_empty_directory(self, tmp_backup_dir, tmp_config_dir):
        manager = BackupIndexManager(tmp_backup_dir, "worlds")
        manager.get_backup_directory("MW_ABC123", "Test World")
        # Directory exists but has no timestamp subdirectories
        removed = manager.cleanup_stale_entries()
        assert removed == 1

    def test_keeps_valid_entries(self, tmp_backup_dir, tmp_config_dir):
        manager = BackupIndexManager(tmp_backup_dir, "worlds")
        backup_dir = manager.get_backup_directory("MW_ABC123", "Test World")
        # Create a timestamp subdirectory
        ts_dir = backup_dir / "2025-01-15_143052"
        ts_dir.mkdir()
        removed = manager.cleanup_stale_entries()
        assert removed == 0
        assert manager.get_entry("MW_ABC123") is not None

    def test_returns_zero_when_no_stale(self, tmp_backup_dir, tmp_config_dir):
        manager = BackupIndexManager(tmp_backup_dir, "worlds")
        removed = manager.cleanup_stale_entries()
        assert removed == 0


class TestGetBackupTimestamps:
    """Tests for get_backup_timestamps()."""

    def test_returns_empty_for_no_backups(self, tmp_backup_dir, tmp_config_dir):
        manager = BackupIndexManager(tmp_backup_dir, "worlds")
        manager.get_backup_directory("MW_ABC123", "Test World")
        entry = manager.get_entry("MW_ABC123")
        timestamps = manager.get_backup_timestamps(entry)
        assert timestamps == []

    def test_returns_sorted_timestamps(self, tmp_backup_dir, tmp_config_dir):
        manager = BackupIndexManager(tmp_backup_dir, "worlds")
        backup_dir = manager.get_backup_directory("MW_ABC123", "Test World")
        # Create timestamp dirs
        (backup_dir / "2025-01-10_100000").mkdir()
        (backup_dir / "2025-01-15_143052").mkdir()
        (backup_dir / "2025-01-12_120000").mkdir()
        entry = manager.get_entry("MW_ABC123")
        timestamps = manager.get_backup_timestamps(entry)
        assert len(timestamps) == 3
        # Should be newest first
        assert timestamps[0].name == "2025-01-15_143052"
        assert timestamps[2].name == "2025-01-10_100000"

    def test_ignores_files(self, tmp_backup_dir, tmp_config_dir):
        manager = BackupIndexManager(tmp_backup_dir, "worlds")
        backup_dir = manager.get_backup_directory("MW_ABC123", "Test World")
        (backup_dir / "2025-01-15_143052").mkdir()
        (backup_dir / "notes.txt").write_text("ignore me")
        entry = manager.get_entry("MW_ABC123")
        timestamps = manager.get_backup_timestamps(entry)
        assert len(timestamps) == 1


class TestGetBackupFiles:
    """Tests for get_backup_files()."""

    def test_returns_sav_files(self, tmp_backup_dir, tmp_config_dir):
        manager = BackupIndexManager(tmp_backup_dir, "worlds")
        backup_dir = manager.get_backup_directory("MW_ABC123", "Test World")
        ts_dir = backup_dir / "2025-01-15_143052"
        ts_dir.mkdir()
        (ts_dir / "MW_ABC123.sav").write_bytes(b"test")
        (ts_dir / "MW_ABC123.sav.fresh").write_bytes(b"test")
        files = manager.get_backup_files(ts_dir)
        # Only .sav files
        assert len(files) == 1
        assert files[0].name == "MW_ABC123.sav"

    def test_returns_empty_for_nonexistent_dir(self, tmp_backup_dir, tmp_config_dir):
        manager = BackupIndexManager(tmp_backup_dir, "worlds")
        fake_dir = tmp_backup_dir / "nonexistent"
        assert manager.get_backup_files(fake_dir) == []


class TestPersistence:
    """Tests for index persistence across instances."""

    def test_entries_survive_reload(self, tmp_backup_dir, tmp_config_dir):
        # Create entries with first manager
        manager1 = BackupIndexManager(tmp_backup_dir, "worlds")
        manager1.get_backup_directory("MW_ABC123", "World A")
        manager1.get_backup_directory("MW_DEF456", "World B")

        # Create new manager instance
        manager2 = BackupIndexManager(tmp_backup_dir, "worlds")
        entries = manager2.list_entries()
        assert len(entries) == 2
        names = {e.display_name for e in entries}
        assert names == {"World A", "World B"}

    def test_corrupted_xml_handled_gracefully(self, tmp_backup_dir, tmp_config_dir):
        manager = BackupIndexManager(tmp_backup_dir, "worlds")
        manager.get_backup_directory("MW_ABC123", "Test World")

        # Corrupt the index file
        manager.index_file.write_text("not valid xml!!!", encoding="utf-8")

        # New manager should start with empty index
        manager2 = BackupIndexManager(tmp_backup_dir, "worlds")
        assert manager2.list_entries() == []
