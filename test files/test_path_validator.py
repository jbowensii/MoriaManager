"""Tests for moria_manager.config.path_validator module."""

import os
from pathlib import Path

import pytest

from moria_manager.config.path_validator import (
    _get_protected_paths,
    is_path_under_root,
    is_safe_path,
    sanitize_filename,
    validate_backup_path,
    validate_game_path,
    validate_save_path,
)


class TestGetProtectedPaths:
    """Tests for _get_protected_paths()."""

    def test_returns_non_empty_set(self):
        paths = _get_protected_paths()
        assert isinstance(paths, set)
        assert len(paths) > 0

    def test_includes_windows_dir(self):
        paths = _get_protected_paths()
        windir = os.environ.get("WINDIR")
        if windir:
            assert Path(windir).resolve() in paths

    def test_includes_program_files(self):
        paths = _get_protected_paths()
        pf = os.environ.get("PROGRAMFILES")
        if pf:
            assert Path(pf).resolve() in paths


class TestIsSafePath:
    """Tests for is_safe_path()."""

    def test_rejects_windows_dir(self):
        windir = os.environ.get("WINDIR", r"C:\Windows")
        assert is_safe_path(Path(windir)) is False

    def test_rejects_program_files(self):
        pf = os.environ.get("PROGRAMFILES", r"C:\Program Files")
        assert is_safe_path(Path(pf)) is False

    def test_accepts_user_dir(self, tmp_path):
        assert is_safe_path(tmp_path) is True

    def test_accepts_subdirectory_of_protected(self):
        # Subdirectories of protected dirs are OK (e.g., game installs in Program Files)
        windir = os.environ.get("WINDIR", r"C:\Windows")
        subdir = Path(windir) / "Temp"
        assert is_safe_path(subdir) is True

    def test_with_allowed_roots_accepts_under_root(self, tmp_path):
        child = tmp_path / "sub" / "file.txt"
        assert is_safe_path(child, allowed_roots=[tmp_path]) is True

    def test_with_allowed_roots_rejects_outside(self, tmp_path):
        other = Path(r"C:\some\other\path")
        assert is_safe_path(other, allowed_roots=[tmp_path]) is False

    def test_with_allowed_roots_accepts_root_itself(self, tmp_path):
        assert is_safe_path(tmp_path, allowed_roots=[tmp_path]) is True


class TestIsPathUnderRoot:
    """Tests for is_path_under_root()."""

    def test_child_is_under_root(self, tmp_path):
        child = tmp_path / "subdir" / "file.txt"
        assert is_path_under_root(child, tmp_path) is True

    def test_root_itself(self, tmp_path):
        assert is_path_under_root(tmp_path, tmp_path) is True

    def test_sibling_not_under_root(self, tmp_path):
        root = tmp_path / "dir_a"
        other = tmp_path / "dir_b"
        root.mkdir()
        other.mkdir()
        assert is_path_under_root(other, root) is False

    def test_parent_not_under_child(self, tmp_path):
        child = tmp_path / "subdir"
        child.mkdir()
        assert is_path_under_root(tmp_path, child) is False

    def test_rejects_traversal(self, tmp_path):
        root = tmp_path / "safe"
        root.mkdir()
        traversal = root / ".." / ".." / "etc"
        # After resolution, should not be under root
        assert is_path_under_root(traversal, root) is False


class TestValidateBackupPath:
    """Tests for validate_backup_path()."""

    def test_valid_path_under_root(self, tmp_path):
        backup_root = tmp_path / "backups"
        backup_root.mkdir()
        backup_path = backup_root / "world1" / "save.sav"
        valid, msg = validate_backup_path(backup_path, backup_root)
        assert valid is True
        assert msg == ""

    def test_rejects_outside_root(self, tmp_path):
        backup_root = tmp_path / "backups"
        backup_root.mkdir()
        outside = tmp_path / "other" / "save.sav"
        valid, msg = validate_backup_path(outside, backup_root)
        assert valid is False
        assert "backup directory" in msg.lower() or "under" in msg.lower()

    def test_rejects_traversal(self, tmp_path):
        backup_root = tmp_path / "backups"
        backup_root.mkdir()
        traversal = backup_root / ".." / "secret" / "file.txt"
        valid, msg = validate_backup_path(traversal, backup_root)
        assert valid is False


class TestValidateSavePath:
    """Tests for validate_save_path()."""

    def test_valid_save_path_under_localappdata(self):
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            save_path = Path(local_appdata) / "Moria" / "Saved"
            valid, msg = validate_save_path(save_path)
            assert valid is True

    def test_valid_save_path_under_userprofile(self):
        userprofile = os.environ.get("USERPROFILE")
        if userprofile:
            save_path = Path(userprofile) / "AppData" / "Local" / "Moria"
            valid, msg = validate_save_path(save_path)
            assert valid is True


class TestValidateGamePath:
    """Tests for validate_game_path()."""

    def test_valid_game_path(self, tmp_path):
        game_dir = tmp_path / "game"
        game_dir.mkdir()
        valid, msg = validate_game_path(game_dir)
        assert valid is True
        assert msg == ""

    def test_nonexistent_path(self, tmp_path):
        game_dir = tmp_path / "nonexistent"
        valid, msg = validate_game_path(game_dir)
        assert valid is False
        assert "not exist" in msg.lower()

    def test_file_not_directory(self, tmp_path):
        game_file = tmp_path / "file.txt"
        game_file.write_text("not a dir")
        valid, msg = validate_game_path(game_file)
        assert valid is False
        assert "not a directory" in msg.lower()


class TestSanitizeFilename:
    """Tests for sanitize_filename()."""

    def test_safe_filename_unchanged(self):
        assert sanitize_filename("my_world_save") == "my_world_save"

    def test_removes_dangerous_chars(self):
        result = sanitize_filename('file<>:"/\\|?*name')
        assert "<" not in result
        assert ">" not in result
        assert ":" not in result
        assert '"' not in result
        assert "/" not in result
        assert "\\" not in result
        assert "|" not in result
        assert "?" not in result
        assert "*" not in result

    def test_replaces_with_underscore(self):
        result = sanitize_filename("file:name")
        assert result == "file_name"

    def test_strips_leading_trailing_dots_spaces(self):
        result = sanitize_filename("...filename...")
        assert not result.startswith(".")
        assert not result.endswith(".")

    def test_strips_spaces(self):
        result = sanitize_filename("  filename  ")
        assert not result.startswith(" ")
        assert not result.endswith(" ")

    def test_empty_string_returns_unnamed(self):
        assert sanitize_filename("") == "unnamed"

    def test_only_dots_returns_unnamed(self):
        assert sanitize_filename("...") == "unnamed"

    def test_only_spaces_returns_unnamed(self):
        assert sanitize_filename("   ") == "unnamed"

    def test_truncates_long_names(self):
        long_name = "a" * 300
        result = sanitize_filename(long_name)
        assert len(result) <= 200

    def test_preserves_unicode(self):
        result = sanitize_filename("w\u00f6rld_n\u00e4me")
        assert "\u00f6" in result
        assert "\u00e4" in result

    def test_null_char_replaced(self):
        result = sanitize_filename("file\x00name")
        assert "\x00" not in result
