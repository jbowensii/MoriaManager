"""Tests for moria_manager.config.paths module."""

import os
from pathlib import Path

import pytest

from moria_manager.config.paths import GamePaths


class TestClassAttributes:
    """Tests for GamePaths class attributes."""

    def test_steam_game_default_is_path(self):
        assert isinstance(GamePaths.STEAM_GAME_DEFAULT, Path)

    def test_steam_save_default_is_path(self):
        assert isinstance(GamePaths.STEAM_SAVE_DEFAULT, Path)

    def test_epic_game_default_is_path(self):
        assert isinstance(GamePaths.EPIC_GAME_DEFAULT, Path)

    def test_epic_save_default_is_path(self):
        assert isinstance(GamePaths.EPIC_SAVE_DEFAULT, Path)

    def test_backup_default_is_path(self):
        assert isinstance(GamePaths.BACKUP_DEFAULT, Path)

    def test_config_dir_is_path(self):
        assert isinstance(GamePaths.CONFIG_DIR, Path)

    def test_config_file_is_xml(self):
        assert GamePaths.CONFIG_FILE.suffix == ".xml"

    def test_config_file_under_config_dir(self):
        assert GamePaths.CONFIG_FILE.parent == GamePaths.CONFIG_DIR

    def test_worlds_index_file_is_xml(self):
        assert GamePaths.WORLDS_INDEX_FILE.suffix == ".xml"

    def test_characters_index_file_is_xml(self):
        assert GamePaths.CHARACTERS_INDEX_FILE.suffix == ".xml"

    def test_trade_config_file_is_xml(self):
        assert GamePaths.TRADE_CONFIG_FILE.suffix == ".xml"


class TestExpandPath:
    """Tests for GamePaths.expand_path()."""

    def test_expands_env_var(self):
        result = GamePaths.expand_path(r"%USERPROFILE%\test")
        userprofile = os.environ.get("USERPROFILE", "")
        if userprofile:
            assert str(result).startswith(userprofile)

    def test_no_env_var_unchanged(self):
        result = GamePaths.expand_path(r"C:\plain\path")
        assert str(result) == r"C:\plain\path"

    def test_returns_path_object(self):
        result = GamePaths.expand_path(r"C:\test")
        assert isinstance(result, Path)

    def test_expands_localappdata(self):
        result = GamePaths.expand_path(r"%LOCALAPPDATA%\test")
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        if local_appdata:
            assert str(result).startswith(local_appdata)

    def test_unknown_env_var_kept(self):
        result = GamePaths.expand_path(r"%TOTALLY_FAKE_VAR_XYZ%\test")
        assert "TOTALLY_FAKE_VAR_XYZ" in str(result)


class TestEnsureConfigDir:
    """Tests for GamePaths.ensure_config_dir()."""

    def test_creates_directory(self, tmp_path, monkeypatch):
        config_dir = tmp_path / "new_config"
        monkeypatch.setattr(GamePaths, "CONFIG_DIR", config_dir)
        result = GamePaths.ensure_config_dir()
        assert result == config_dir
        assert config_dir.exists()

    def test_idempotent(self, tmp_path, monkeypatch):
        config_dir = tmp_path / "config"
        monkeypatch.setattr(GamePaths, "CONFIG_DIR", config_dir)
        GamePaths.ensure_config_dir()
        GamePaths.ensure_config_dir()  # Should not raise
        assert config_dir.exists()

    def test_returns_path(self, tmp_path, monkeypatch):
        config_dir = tmp_path / "config"
        monkeypatch.setattr(GamePaths, "CONFIG_DIR", config_dir)
        result = GamePaths.ensure_config_dir()
        assert isinstance(result, Path)


class TestEnsureBackupDir:
    """Tests for GamePaths.ensure_backup_dir()."""

    def test_creates_custom_directory(self, tmp_path):
        backup_dir = tmp_path / "custom_backup"
        result = GamePaths.ensure_backup_dir(backup_dir)
        assert result == backup_dir
        assert backup_dir.exists()

    def test_uses_default_when_none(self, tmp_path, monkeypatch):
        default_dir = tmp_path / "default_backup"
        monkeypatch.setattr(GamePaths, "BACKUP_DEFAULT", default_dir)
        result = GamePaths.ensure_backup_dir(None)
        assert result == default_dir
        assert default_dir.exists()

    def test_idempotent(self, tmp_path):
        backup_dir = tmp_path / "backup"
        GamePaths.ensure_backup_dir(backup_dir)
        GamePaths.ensure_backup_dir(backup_dir)  # Should not raise
        assert backup_dir.exists()
