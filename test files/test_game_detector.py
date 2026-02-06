"""Tests for moria_manager.core.game_detector module."""

from pathlib import Path
from unittest.mock import PropertyMock, patch

import pytest

from moria_manager.config.paths import GamePaths
from moria_manager.config.schema import Installation, InstallationType
from moria_manager.core.game_detector import GameDetector


class TestDetectSteamInstallation:
    """Tests for GameDetector.detect_steam_installation()."""

    def test_returns_none_when_no_paths_exist(self, monkeypatch):
        monkeypatch.setattr(GamePaths, "STEAM_GAME_DEFAULT", Path("C:/nonexistent/steam/game"))
        monkeypatch.setattr(GamePaths, "STEAM_SAVE_DEFAULT", Path("C:/nonexistent/steam/save"))
        detector = GameDetector()
        result = detector.detect_steam_installation()
        assert result is None

    def test_returns_installation_when_game_path_exists(self, tmp_path, monkeypatch):
        game_dir = tmp_path / "steam_game"
        game_dir.mkdir()
        monkeypatch.setattr(GamePaths, "STEAM_GAME_DEFAULT", game_dir)
        monkeypatch.setattr(GamePaths, "STEAM_SAVE_DEFAULT", Path("C:/nonexistent/save"))
        detector = GameDetector()
        result = detector.detect_steam_installation()
        assert result is not None
        assert result.id == InstallationType.STEAM
        assert result.enabled is True
        assert result.game_path == game_dir

    def test_returns_installation_when_save_path_exists(self, tmp_path, monkeypatch):
        save_dir = tmp_path / "steam_save"
        save_dir.mkdir()
        monkeypatch.setattr(GamePaths, "STEAM_GAME_DEFAULT", Path("C:/nonexistent/game"))
        monkeypatch.setattr(GamePaths, "STEAM_SAVE_DEFAULT", save_dir)
        detector = GameDetector()
        result = detector.detect_steam_installation()
        assert result is not None
        assert result.save_path == save_dir

    def test_returns_installation_when_both_exist(self, tmp_path, monkeypatch):
        game_dir = tmp_path / "game"
        save_dir = tmp_path / "save"
        game_dir.mkdir()
        save_dir.mkdir()
        monkeypatch.setattr(GamePaths, "STEAM_GAME_DEFAULT", game_dir)
        monkeypatch.setattr(GamePaths, "STEAM_SAVE_DEFAULT", save_dir)
        detector = GameDetector()
        result = detector.detect_steam_installation()
        assert result is not None
        assert result.game_path == game_dir
        assert result.save_path == save_dir


class TestDetectEpicInstallation:
    """Tests for GameDetector.detect_epic_installation()."""

    def test_returns_none_when_no_paths_exist(self, monkeypatch):
        monkeypatch.setattr(GamePaths, "EPIC_GAME_DEFAULT", Path("C:/nonexistent/epic/game"))
        monkeypatch.setattr(GamePaths, "EPIC_SAVE_DEFAULT", Path("C:/nonexistent/epic/save"))
        detector = GameDetector()
        result = detector.detect_epic_installation()
        assert result is None

    def test_returns_installation_when_paths_exist(self, tmp_path, monkeypatch):
        game_dir = tmp_path / "epic_game"
        game_dir.mkdir()
        monkeypatch.setattr(GamePaths, "EPIC_GAME_DEFAULT", game_dir)
        monkeypatch.setattr(GamePaths, "EPIC_SAVE_DEFAULT", Path("C:/nonexistent/save"))
        detector = GameDetector()
        result = detector.detect_epic_installation()
        assert result is not None
        assert result.id == InstallationType.EPIC
        assert result.display_name == "Epic Games"


class TestDetectAll:
    """Tests for GameDetector.detect_all()."""

    def test_always_includes_custom(self, monkeypatch):
        monkeypatch.setattr(GamePaths, "STEAM_GAME_DEFAULT", Path("C:/nonexistent/steam"))
        monkeypatch.setattr(GamePaths, "STEAM_SAVE_DEFAULT", Path("C:/nonexistent/steam_save"))
        monkeypatch.setattr(GamePaths, "EPIC_GAME_DEFAULT", Path("C:/nonexistent/epic"))
        monkeypatch.setattr(GamePaths, "EPIC_SAVE_DEFAULT", Path("C:/nonexistent/epic_save"))
        detector = GameDetector()
        installations = detector.detect_all()
        custom = [i for i in installations if i.id == InstallationType.CUSTOM]
        assert len(custom) == 1
        assert custom[0].enabled is False

    def test_returns_three_entries(self, monkeypatch):
        monkeypatch.setattr(GamePaths, "STEAM_GAME_DEFAULT", Path("C:/nonexistent/steam"))
        monkeypatch.setattr(GamePaths, "STEAM_SAVE_DEFAULT", Path("C:/nonexistent/steam_save"))
        monkeypatch.setattr(GamePaths, "EPIC_GAME_DEFAULT", Path("C:/nonexistent/epic"))
        monkeypatch.setattr(GamePaths, "EPIC_SAVE_DEFAULT", Path("C:/nonexistent/epic_save"))
        detector = GameDetector()
        installations = detector.detect_all()
        # Always has Steam + Epic + Custom
        assert len(installations) == 3

    def test_detected_installations_enabled(self, tmp_path, monkeypatch):
        steam_game = tmp_path / "steam"
        steam_game.mkdir()
        monkeypatch.setattr(GamePaths, "STEAM_GAME_DEFAULT", steam_game)
        monkeypatch.setattr(GamePaths, "STEAM_SAVE_DEFAULT", Path("C:/nonexistent/save"))
        monkeypatch.setattr(GamePaths, "EPIC_GAME_DEFAULT", Path("C:/nonexistent/epic"))
        monkeypatch.setattr(GamePaths, "EPIC_SAVE_DEFAULT", Path("C:/nonexistent/epic_save"))
        detector = GameDetector()
        installations = detector.detect_all()
        steam = [i for i in installations if i.id == InstallationType.STEAM][0]
        assert steam.enabled is True


class TestVerifyInstallation:
    """Tests for GameDetector.verify_installation()."""

    def test_both_exist(self, tmp_path):
        game_dir = tmp_path / "game"
        save_dir = tmp_path / "save"
        game_dir.mkdir()
        save_dir.mkdir()
        inst = Installation(
            id=InstallationType.STEAM,
            display_name="Steam",
            game_path=game_dir,
            save_path=save_dir,
        )
        detector = GameDetector()
        result = detector.verify_installation(inst)
        assert result["game_path"] is True
        assert result["save_path"] is True

    def test_neither_exist(self):
        inst = Installation(
            id=InstallationType.STEAM,
            display_name="Steam",
            game_path=Path("C:/nonexistent/game"),
            save_path=Path("C:/nonexistent/save"),
        )
        detector = GameDetector()
        result = detector.verify_installation(inst)
        assert result["game_path"] is False
        assert result["save_path"] is False

    def test_none_paths(self):
        inst = Installation(
            id=InstallationType.CUSTOM,
            display_name="Custom",
            game_path=None,
            save_path=None,
        )
        detector = GameDetector()
        result = detector.verify_installation(inst)
        assert result["game_path"] is False
        assert result["save_path"] is False
