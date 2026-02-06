"""Tests for moria_manager.config.manager module."""

import shutil
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import pytest

from moria_manager.config.manager import ConfigurationManager
from moria_manager.config.schema import (
    AppConfiguration,
    BackupRecord,
    Installation,
    InstallationType,
    ServerInfo,
    Settings,
)


class TestIsFirstRun:
    """Tests for ConfigurationManager.is_first_run()."""

    def test_true_when_no_config_file(self, tmp_config_dir):
        manager = ConfigurationManager()
        assert manager.is_first_run() is True

    def test_false_after_save_with_first_run_complete(self, tmp_config_dir):
        manager = ConfigurationManager()
        manager.config = AppConfiguration(
            settings=Settings(first_run_complete=True)
        )
        manager.save()
        assert manager.is_first_run() is False

    def test_true_when_first_run_not_complete(self, tmp_config_dir):
        manager = ConfigurationManager()
        manager.config = AppConfiguration(
            settings=Settings(first_run_complete=False)
        )
        manager.save()
        assert manager.is_first_run() is True

    def test_true_on_corrupted_config(self, tmp_config_dir):
        config_file = tmp_config_dir / "configuration.xml"
        config_file.write_text("not valid xml", encoding="utf-8")
        manager = ConfigurationManager()
        assert manager.is_first_run() is True


class TestCreateDefault:
    """Tests for ConfigurationManager.create_default()."""

    def test_returns_app_configuration(self, tmp_config_dir):
        manager = ConfigurationManager()
        config = manager.create_default()
        assert isinstance(config, AppConfiguration)

    def test_default_settings(self, tmp_config_dir):
        manager = ConfigurationManager()
        config = manager.create_default()
        assert config.settings.first_run_complete is False
        assert config.settings.auto_backup_on_launch is False
        assert config.settings.backup_location is not None

    def test_with_installations(self, tmp_config_dir):
        installations = [
            Installation(
                id=InstallationType.STEAM,
                display_name="Steam",
                enabled=True,
            )
        ]
        manager = ConfigurationManager()
        config = manager.create_default(installations=installations)
        assert len(config.installations) == 1
        assert config.installations[0].display_name == "Steam"

    def test_empty_backups(self, tmp_config_dir):
        manager = ConfigurationManager()
        config = manager.create_default()
        assert config.backups == []


class TestSaveLoadRoundtrip:
    """Tests for save/load roundtrip."""

    def test_basic_roundtrip(self, tmp_config_dir):
        manager = ConfigurationManager()
        manager.config = AppConfiguration(
            settings=Settings(
                first_run_complete=True,
                auto_backup_on_launch=True,
                enable_deletion=True,
            )
        )
        manager.save()

        manager2 = ConfigurationManager()
        loaded = manager2.load()
        assert loaded.settings.first_run_complete is True
        assert loaded.settings.auto_backup_on_launch is True
        assert loaded.settings.enable_deletion is True

    def test_installations_roundtrip(self, tmp_config_dir, tmp_path):
        game_path = tmp_path / "game"
        save_path = tmp_path / "saves"
        game_path.mkdir()
        save_path.mkdir()

        manager = ConfigurationManager()
        manager.config = AppConfiguration(
            settings=Settings(first_run_complete=True),
            installations=[
                Installation(
                    id=InstallationType.STEAM,
                    display_name="Steam",
                    game_path=game_path,
                    save_path=save_path,
                    enabled=True,
                ),
                Installation(
                    id=InstallationType.EPIC,
                    display_name="Epic Games",
                    game_path=None,
                    save_path=None,
                    enabled=False,
                ),
            ],
        )
        manager.save()

        manager2 = ConfigurationManager()
        loaded = manager2.load()
        assert len(loaded.installations) == 2
        steam = loaded.get_installation(InstallationType.STEAM)
        assert steam is not None
        assert steam.display_name == "Steam"
        assert steam.enabled is True
        epic = loaded.get_installation(InstallationType.EPIC)
        assert epic is not None
        assert epic.enabled is False

    def test_server_info_roundtrip(self, tmp_config_dir):
        manager = ConfigurationManager()
        manager.config = AppConfiguration(
            settings=Settings(
                first_run_complete=True,
                server_info=ServerInfo(
                    name="My Server",
                    address="192.168.1.100",
                    password="secret123",
                    notes="Test notes",
                ),
            )
        )
        manager.save()

        manager2 = ConfigurationManager()
        loaded = manager2.load()
        si = loaded.settings.server_info
        assert si is not None
        assert si.name == "My Server"
        assert si.address == "192.168.1.100"
        assert si.password == "secret123"
        assert si.notes == "Test notes"

    def test_server_password_encrypted_on_disk(self, tmp_config_dir):
        manager = ConfigurationManager()
        manager.config = AppConfiguration(
            settings=Settings(
                first_run_complete=True,
                server_info=ServerInfo(password="secret123"),
            )
        )
        manager.save()

        # Read raw XML and check password is encrypted
        raw = manager.config_path.read_text(encoding="utf-8")
        assert "secret123" not in raw
        assert "ENC:" in raw

    def test_backups_roundtrip(self, tmp_config_dir, tmp_path):
        backup_file = tmp_path / "backup.sav"
        backup_file.write_bytes(b"fake")

        manager = ConfigurationManager()
        manager.config = AppConfiguration(
            settings=Settings(first_run_complete=True),
            backups=[
                BackupRecord(
                    id="test-backup-001",
                    installation=InstallationType.STEAM,
                    timestamp=datetime(2025, 1, 15, 14, 30, 52),
                    description="Test backup",
                    file_path=backup_file,
                ),
            ],
        )
        manager.save()

        manager2 = ConfigurationManager()
        loaded = manager2.load()
        assert len(loaded.backups) == 1
        b = loaded.backups[0]
        assert b.id == "test-backup-001"
        assert b.installation == InstallationType.STEAM
        assert b.description == "Test backup"


class TestAddRemoveBackup:
    """Tests for add_backup and remove_backup."""

    def test_add_backup(self, tmp_config_dir, tmp_path):
        manager = ConfigurationManager()
        manager.config = AppConfiguration(
            settings=Settings(first_run_complete=True)
        )
        manager.save()

        backup = BackupRecord(
            id="new-backup",
            installation=InstallationType.STEAM,
            timestamp=datetime.now(),
            description="New backup",
            file_path=tmp_path / "save.sav",
        )
        manager.add_backup(backup)
        assert len(manager.config.backups) == 1

        # Verify persisted
        manager2 = ConfigurationManager()
        loaded = manager2.load()
        assert len(loaded.backups) == 1

    def test_remove_backup_by_id(self, tmp_config_dir, tmp_path):
        manager = ConfigurationManager()
        manager.config = AppConfiguration(
            settings=Settings(first_run_complete=True),
            backups=[
                BackupRecord(
                    id="backup-001",
                    installation=InstallationType.STEAM,
                    timestamp=datetime.now(),
                    description="To remove",
                    file_path=tmp_path / "save.sav",
                ),
            ],
        )
        manager.save()

        result = manager.remove_backup("backup-001")
        assert result is True
        assert len(manager.config.backups) == 0

    def test_remove_backup_returns_false_for_unknown(self, tmp_config_dir):
        manager = ConfigurationManager()
        manager.config = AppConfiguration(
            settings=Settings(first_run_complete=True)
        )
        manager.save()
        assert manager.remove_backup("nonexistent") is False

    def test_add_backup_raises_without_config(self, tmp_config_dir, tmp_path):
        manager = ConfigurationManager()
        backup = BackupRecord(
            id="test",
            installation=InstallationType.STEAM,
            timestamp=datetime.now(),
            description="test",
            file_path=tmp_path / "save.sav",
        )
        with pytest.raises(ValueError):
            manager.add_backup(backup)

    def test_remove_backup_raises_without_config(self, tmp_config_dir):
        manager = ConfigurationManager()
        with pytest.raises(ValueError):
            manager.remove_backup("test")


class TestStaticHelpers:
    """Tests for static XML helper methods."""

    def test_get_text_existing_element(self):
        root = ET.fromstring("<root><Name>Test</Name></root>")
        assert ConfigurationManager._get_text(root, "Name") == "Test"

    def test_get_text_missing_element(self):
        root = ET.fromstring("<root></root>")
        assert ConfigurationManager._get_text(root, "Name", "default") == "default"

    def test_get_text_empty_element(self):
        root = ET.fromstring("<root><Name/></root>")
        assert ConfigurationManager._get_text(root, "Name", "default") == "default"

    def test_parse_bool_true(self):
        root = ET.fromstring("<root><Flag>true</Flag></root>")
        assert ConfigurationManager._parse_bool(root, "Flag") is True

    def test_parse_bool_false(self):
        root = ET.fromstring("<root><Flag>false</Flag></root>")
        assert ConfigurationManager._parse_bool(root, "Flag") is False

    def test_parse_bool_missing(self):
        root = ET.fromstring("<root></root>")
        assert ConfigurationManager._parse_bool(root, "Flag", True) is True

    def test_parse_path_valid(self):
        root = ET.fromstring(r"<root><Path>C:\test\path</Path></root>")
        result = ConfigurationManager._parse_path(root, "Path")
        assert result is not None
        assert isinstance(result, Path)

    def test_parse_path_empty(self):
        root = ET.fromstring("<root><Path></Path></root>")
        assert ConfigurationManager._parse_path(root, "Path") is None

    def test_parse_path_missing(self):
        root = ET.fromstring("<root></root>")
        assert ConfigurationManager._parse_path(root, "Path") is None


class TestLoadFromFixture:
    """Tests loading from fixture XML files."""

    def test_load_sample_config(self, tmp_config_dir, sample_config_path):
        # Copy fixture to config location
        shutil.copy2(sample_config_path, tmp_config_dir / "configuration.xml")
        manager = ConfigurationManager()
        config = manager.load()

        assert config.settings.first_run_complete is True
        assert config.settings.enable_deletion is True
        assert len(config.installations) == 2
        assert len(config.backups) == 1

    def test_load_minimal_config(self, tmp_config_dir, minimal_config_path):
        shutil.copy2(minimal_config_path, tmp_config_dir / "configuration.xml")
        manager = ConfigurationManager()
        config = manager.load()

        assert config.settings.first_run_complete is False
        assert len(config.installations) == 0
        assert len(config.backups) == 0

    def test_save_raises_without_config(self, tmp_config_dir):
        manager = ConfigurationManager()
        with pytest.raises(ValueError):
            manager.save()
