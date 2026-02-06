"""Shared test fixtures for Moria Manager test suite."""

from pathlib import Path
from unittest.mock import patch

import pytest

# Exclude manual interactive test scripts from pytest collection
collect_ignore_glob = ["test_ftp.py", "test_sftp*.py"]


@pytest.fixture
def tmp_backup_dir(tmp_path):
    """Fresh temp directory for backup index tests."""
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    return backup_dir


@pytest.fixture
def tmp_config_dir(tmp_path, monkeypatch):
    """Temp directory with patched GamePaths.CONFIG_DIR."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    monkeypatch.setattr(
        "moria_manager.config.paths.GamePaths.CONFIG_DIR", config_dir
    )
    monkeypatch.setattr(
        "moria_manager.config.paths.GamePaths.CONFIG_FILE",
        config_dir / "configuration.xml",
    )
    monkeypatch.setattr(
        "moria_manager.config.paths.GamePaths.WORLDS_INDEX_FILE",
        config_dir / "index_worlds.xml",
    )
    monkeypatch.setattr(
        "moria_manager.config.paths.GamePaths.CHARACTERS_INDEX_FILE",
        config_dir / "index_characters.xml",
    )
    monkeypatch.setattr(
        "moria_manager.config.paths.GamePaths.SERVER_INFO_DIR",
        config_dir / "servers",
    )
    monkeypatch.setattr(
        "moria_manager.config.paths.GamePaths.TRADE_CONFIG_FILE",
        config_dir / "trade_config.xml",
    )
    return config_dir


@pytest.fixture
def sample_config_path():
    """Path to the sample configuration XML fixture."""
    return Path(__file__).parent / "fixtures" / "sample_config.xml"


@pytest.fixture
def minimal_config_path():
    """Path to the minimal configuration XML fixture."""
    return Path(__file__).parent / "fixtures" / "minimal_config.xml"


@pytest.fixture
def mock_save_dir(tmp_path):
    """Temp directory for mock save files."""
    save_dir = tmp_path / "saves"
    save_dir.mkdir()
    return save_dir


@pytest.fixture
def mock_env(monkeypatch):
    """Helper to set environment variables for testing."""
    def _set_env(**kwargs):
        for key, value in kwargs.items():
            monkeypatch.setenv(key, value)
    return _set_env
