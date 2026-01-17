"""Auto-detect installed game versions"""

from typing import Optional

from ..config.paths import GamePaths
from ..config.schema import Installation, InstallationType


class GameDetector:
    """Auto-detect Steam and Epic game installations.

    Checks default installation paths to determine which versions
    of the game are installed on the system.
    """

    def detect_steam_installation(self) -> Optional[Installation]:
        """Check if Steam version is installed at the default location.

        Returns:
            Installation object if found, None otherwise
        """
        # Check if either the game path or save path exists
        game_exists = GamePaths.STEAM_GAME_DEFAULT.exists()
        save_exists = GamePaths.STEAM_SAVE_DEFAULT.exists()

        if game_exists or save_exists:
            return Installation(
                id=InstallationType.STEAM,
                display_name="Steam",
                game_path=GamePaths.STEAM_GAME_DEFAULT if game_exists else None,
                save_path=GamePaths.STEAM_SAVE_DEFAULT if save_exists else None,
                enabled=True,  # Auto-enable if detected
            )
        return None

    def detect_epic_installation(self) -> Optional[Installation]:
        """Check if Epic Games version is installed at the default location.

        Returns:
            Installation object if found, None otherwise
        """
        # Check if either the game path or save path exists
        game_exists = GamePaths.EPIC_GAME_DEFAULT.exists()
        save_exists = GamePaths.EPIC_SAVE_DEFAULT.exists()

        if game_exists or save_exists:
            return Installation(
                id=InstallationType.EPIC,
                display_name="Epic Games",
                game_path=GamePaths.EPIC_GAME_DEFAULT if game_exists else None,
                save_path=GamePaths.EPIC_SAVE_DEFAULT if save_exists else None,
                enabled=True,  # Auto-enable if detected
            )
        return None

    def detect_all(self) -> list[Installation]:
        """Detect all installed versions and create installation list.

        Always includes a Custom installation option (disabled by default).

        Returns:
            List of Installation objects for all detected and custom options
        """
        installations = []

        # Try to detect Steam installation
        steam = self.detect_steam_installation()
        if steam:
            installations.append(steam)
        else:
            # Add Steam as option but disabled
            installations.append(Installation(
                id=InstallationType.STEAM,
                display_name="Steam",
                game_path=GamePaths.STEAM_GAME_DEFAULT,
                save_path=GamePaths.STEAM_SAVE_DEFAULT,
                enabled=False,
            ))

        # Try to detect Epic installation
        epic = self.detect_epic_installation()
        if epic:
            installations.append(epic)
        else:
            # Add Epic as option but disabled
            installations.append(Installation(
                id=InstallationType.EPIC,
                display_name="Epic Games",
                game_path=GamePaths.EPIC_GAME_DEFAULT,
                save_path=GamePaths.EPIC_SAVE_DEFAULT,
                enabled=False,
            ))

        # Always add Custom option (disabled by default)
        installations.append(Installation(
            id=InstallationType.CUSTOM,
            display_name="Custom Installation",
            game_path=None,
            save_path=None,
            enabled=False,
        ))

        return installations

    def verify_installation(self, installation: Installation) -> dict[str, bool]:
        """Verify the paths for an installation exist.

        Args:
            installation: The installation to verify

        Returns:
            Dictionary with 'game_path' and 'save_path' keys indicating existence
        """
        return {
            "game_path": installation.game_path.exists() if installation.game_path else False,
            "save_path": installation.save_path.exists() if installation.save_path else False,
        }
