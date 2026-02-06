"""Tests for moria_manager.config.schema module."""

from datetime import datetime
from pathlib import Path

import pytest

from moria_manager.config.schema import (
    AppConfiguration,
    BackupRecord,
    Installation,
    InstallationType,
    ServerInfo,
    Settings,
)


class TestInstallationType:
    """Tests for InstallationType enum."""

    def test_steam_value(self):
        assert InstallationType.STEAM.value == "steam"

    def test_epic_value(self):
        assert InstallationType.EPIC.value == "epic"

    def test_custom_value(self):
        assert InstallationType.CUSTOM.value == "custom"

    def test_from_string(self):
        assert InstallationType("steam") == InstallationType.STEAM
        assert InstallationType("epic") == InstallationType.EPIC
        assert InstallationType("custom") == InstallationType.CUSTOM

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            InstallationType("unknown")


class TestInstallation:
    """Tests for Installation dataclass."""

    def test_is_valid_with_existing_save_path(self, tmp_path):
        save_path = tmp_path / "saves"
        save_path.mkdir()
        inst = Installation(
            id=InstallationType.STEAM,
            display_name="Steam",
            save_path=save_path,
        )
        assert inst.is_valid() is True

    def test_is_valid_false_with_none_save_path(self):
        inst = Installation(
            id=InstallationType.STEAM,
            display_name="Steam",
            save_path=None,
        )
        assert inst.is_valid() is False

    def test_is_valid_false_with_nonexistent_path(self, tmp_path):
        inst = Installation(
            id=InstallationType.STEAM,
            display_name="Steam",
            save_path=tmp_path / "nonexistent",
        )
        assert inst.is_valid() is False

    def test_default_enabled_false(self):
        inst = Installation(
            id=InstallationType.CUSTOM,
            display_name="Custom",
        )
        assert inst.enabled is False


class TestServerInfo:
    """Tests for ServerInfo dataclass."""

    def test_defaults(self):
        si = ServerInfo()
        assert si.name == ""
        assert si.address == ""
        assert si.password == ""
        assert si.notes == ""

    def test_with_values(self):
        si = ServerInfo(name="My Server", address="1.2.3.4", password="pass", notes="note")
        assert si.name == "My Server"
        assert si.address == "1.2.3.4"


class TestSettings:
    """Tests for Settings dataclass."""

    def test_defaults(self):
        s = Settings()
        assert s.first_run_complete is False
        assert s.backup_location is None
        assert s.auto_backup_on_launch is False
        assert s.enable_deletion is False
        assert s.server_info is None


class TestBackupRecord:
    """Tests for BackupRecord dataclass."""

    def test_exists_true(self, tmp_path):
        file_path = tmp_path / "save.sav"
        file_path.write_bytes(b"data")
        br = BackupRecord(
            id="test",
            installation=InstallationType.STEAM,
            timestamp=datetime.now(),
            description="test",
            file_path=file_path,
        )
        assert br.exists() is True

    def test_exists_false(self, tmp_path):
        br = BackupRecord(
            id="test",
            installation=InstallationType.STEAM,
            timestamp=datetime.now(),
            description="test",
            file_path=tmp_path / "nonexistent.sav",
        )
        assert br.exists() is False

    def test_get_size_mb_existing(self, tmp_path):
        file_path = tmp_path / "save.sav"
        file_path.write_bytes(b"x" * 1048576)  # 1 MB
        br = BackupRecord(
            id="test",
            installation=InstallationType.STEAM,
            timestamp=datetime.now(),
            description="test",
            file_path=file_path,
        )
        assert abs(br.get_size_mb() - 1.0) < 0.01

    def test_get_size_mb_nonexistent(self, tmp_path):
        br = BackupRecord(
            id="test",
            installation=InstallationType.STEAM,
            timestamp=datetime.now(),
            description="test",
            file_path=tmp_path / "nonexistent.sav",
        )
        assert br.get_size_mb() == 0.0


class TestAppConfiguration:
    """Tests for AppConfiguration dataclass."""

    def test_defaults(self):
        config = AppConfiguration()
        assert isinstance(config.settings, Settings)
        assert config.installations == []
        assert config.backups == []

    def test_get_installation_found(self):
        config = AppConfiguration(
            installations=[
                Installation(id=InstallationType.STEAM, display_name="Steam"),
                Installation(id=InstallationType.EPIC, display_name="Epic"),
            ]
        )
        steam = config.get_installation(InstallationType.STEAM)
        assert steam is not None
        assert steam.display_name == "Steam"

    def test_get_installation_not_found(self):
        config = AppConfiguration()
        assert config.get_installation(InstallationType.STEAM) is None

    def test_get_enabled_installations(self):
        config = AppConfiguration(
            installations=[
                Installation(id=InstallationType.STEAM, display_name="Steam", enabled=True),
                Installation(id=InstallationType.EPIC, display_name="Epic", enabled=False),
                Installation(id=InstallationType.CUSTOM, display_name="Custom", enabled=True),
            ]
        )
        enabled = config.get_enabled_installations()
        assert len(enabled) == 2
        names = {inst.display_name for inst in enabled}
        assert names == {"Steam", "Custom"}

    def test_get_backups_for_installation(self, tmp_path):
        config = AppConfiguration(
            backups=[
                BackupRecord(
                    id="b1",
                    installation=InstallationType.STEAM,
                    timestamp=datetime(2025, 1, 10),
                    description="older",
                    file_path=tmp_path / "a.sav",
                ),
                BackupRecord(
                    id="b2",
                    installation=InstallationType.EPIC,
                    timestamp=datetime(2025, 1, 12),
                    description="epic backup",
                    file_path=tmp_path / "b.sav",
                ),
                BackupRecord(
                    id="b3",
                    installation=InstallationType.STEAM,
                    timestamp=datetime(2025, 1, 15),
                    description="newer",
                    file_path=tmp_path / "c.sav",
                ),
            ]
        )
        steam_backups = config.get_backups_for_installation(InstallationType.STEAM)
        assert len(steam_backups) == 2
        # Should be sorted newest first
        assert steam_backups[0].description == "newer"
        assert steam_backups[1].description == "older"

    def test_get_backups_for_installation_empty(self):
        config = AppConfiguration()
        assert config.get_backups_for_installation(InstallationType.STEAM) == []
