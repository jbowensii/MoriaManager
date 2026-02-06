"""Tests for moria_manager.logging_config module."""

import logging
from pathlib import Path

import pytest

from moria_manager.config.paths import GamePaths
from moria_manager.logging_config import get_logger, setup_logging


class TestSetupLogging:
    """Tests for setup_logging()."""

    def test_returns_logger(self, tmp_path, monkeypatch):
        monkeypatch.setattr(GamePaths, "CONFIG_DIR", tmp_path)
        logger = setup_logging()
        assert isinstance(logger, logging.Logger)

    def test_logger_name(self, tmp_path, monkeypatch):
        monkeypatch.setattr(GamePaths, "CONFIG_DIR", tmp_path)
        logger = setup_logging()
        assert logger.name == "moria_manager"

    def test_creates_log_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(GamePaths, "CONFIG_DIR", tmp_path)
        setup_logging()
        log_file = tmp_path / "moria_manager.log"
        assert log_file.exists()

    def test_debug_mode_adds_console_handler(self, tmp_path, monkeypatch):
        monkeypatch.setattr(GamePaths, "CONFIG_DIR", tmp_path)
        logger = setup_logging(debug=True)
        handler_types = [type(h).__name__ for h in logger.handlers]
        assert "StreamHandler" in handler_types

    def test_non_debug_mode_no_console_handler(self, tmp_path, monkeypatch):
        monkeypatch.setattr(GamePaths, "CONFIG_DIR", tmp_path)
        logger = setup_logging(debug=False)
        handler_types = [type(h).__name__ for h in logger.handlers]
        assert "StreamHandler" not in handler_types

    def test_has_file_handler(self, tmp_path, monkeypatch):
        monkeypatch.setattr(GamePaths, "CONFIG_DIR", tmp_path)
        logger = setup_logging()
        handler_types = [type(h).__name__ for h in logger.handlers]
        assert "FileHandler" in handler_types


class TestGetLogger:
    """Tests for get_logger()."""

    def test_returns_logger(self):
        logger = get_logger("test_module")
        assert isinstance(logger, logging.Logger)

    def test_correct_name(self):
        logger = get_logger("test_module")
        assert logger.name == "moria_manager.test_module"

    def test_is_child_of_root(self):
        logger = get_logger("child")
        assert logger.parent.name == "moria_manager"
