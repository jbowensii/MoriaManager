"""Logging configuration for Moria Manager.

Provides centralized logging setup with file and console handlers.
Log files are stored in the application's config directory.
Logging can be enabled/disabled via the settings.ini file.
"""

import configparser
import logging
import sys

from .config.paths import GamePaths

# Module-level flag to track if logging is enabled (mutable, not a constant)
_logging_enabled: bool = False  # pylint: disable=invalid-name

# Valid theme values
THEME_LIGHT = "light"
THEME_DARK = "dark"
THEME_SYSTEM = "system"
VALID_THEMES = (THEME_LIGHT, THEME_DARK, THEME_SYSTEM)


def _read_logging_flag() -> bool:
    """Read the logging flag from settings.ini.

    Creates the settings.ini file with defaults if it doesn't exist.

    Returns:
        True if logging is enabled, False otherwise
    """
    ini_path = GamePaths.SETTINGS_INI_FILE

    # Ensure config directory exists
    GamePaths.CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    config = configparser.ConfigParser()

    if ini_path.exists():
        try:
            config.read(ini_path, encoding="utf-8")
            return config.getboolean("General", "logging", fallback=False)
        except (configparser.Error, ValueError):
            # If there's an error reading, return default and don't overwrite
            return False

    # Create default settings.ini if it doesn't exist
    config["General"] = {
        "logging": "false",
        "theme": "system",
    }
    try:
        with open(ini_path, "w", encoding="utf-8") as f:
            f.write("; Moria Manager Settings\n")
            f.write("; Set logging = true to enable detailed logging to file\n")
            f.write("; theme = light, dark, or system (match Windows)\n\n")
            config.write(f)
    except OSError:
        pass  # Silently fail if we can't write the file

    return False


def is_logging_enabled() -> bool:
    """Check if logging is currently enabled.

    Returns:
        True if logging is enabled via settings.ini
    """
    return _logging_enabled


def setup_logging(debug: bool = False) -> logging.Logger:
    """Configure application-wide logging.

    Sets up logging to both file and console (if debug mode).
    Log file is stored in %APPDATA%/MoriaManager/moria_manager.log
    Logging only activates if enabled in settings.ini.

    Args:
        debug: If True, also log to console at DEBUG level

    Returns:
        The root logger for the application
    """
    global _logging_enabled  # pylint: disable=global-statement
    _logging_enabled = _read_logging_flag()

    # Create logger
    logger = logging.getLogger("moria_manager")

    # Clear any existing handlers
    logger.handlers.clear()

    if not _logging_enabled:
        # Disable logging - set to highest level and add null handler
        logger.setLevel(logging.CRITICAL + 1)
        logger.addHandler(logging.NullHandler())
        return logger

    # Logging is enabled - configure normally
    logger.setLevel(logging.DEBUG)

    # Ensure config directory exists for log file
    log_dir = GamePaths.CONFIG_DIR
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "moria_manager.log"

    # File handler - always logs DEBUG and above
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # Console handler - only in debug mode
    if debug:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        console_formatter = logging.Formatter(
            "%(levelname)s - %(name)s - %(message)s"
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a child logger for a specific module.

    Args:
        name: Module name (e.g., 'save_parser', 'backup_service')

    Returns:
        A logger instance for the module
    """
    return logging.getLogger(f"moria_manager.{name}")


def get_theme_setting() -> str:
    """Read the theme setting from settings.ini.

    Returns:
        'light', 'dark', or 'system' (default)
    """
    ini_path = GamePaths.SETTINGS_INI_FILE

    if not ini_path.exists():
        return THEME_SYSTEM

    config = configparser.ConfigParser()
    try:
        config.read(ini_path, encoding="utf-8")
        theme = config.get("General", "theme", fallback=THEME_SYSTEM).lower().strip()
        if theme in VALID_THEMES:
            return theme
    except (configparser.Error, ValueError):
        pass

    return THEME_SYSTEM


def set_theme_setting(theme: str) -> None:
    """Write the theme setting to settings.ini.

    Args:
        theme: 'light', 'dark', or 'system'
    """
    if theme not in VALID_THEMES:
        theme = THEME_SYSTEM

    ini_path = GamePaths.SETTINGS_INI_FILE
    GamePaths.CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    config = configparser.ConfigParser()

    # Read existing settings
    if ini_path.exists():
        try:
            config.read(ini_path, encoding="utf-8")
        except configparser.Error:
            pass

    # Ensure General section exists
    if "General" not in config:
        config["General"] = {}

    # Update theme
    config["General"]["theme"] = theme

    # Preserve logging setting if not present
    if "logging" not in config["General"]:
        config["General"]["logging"] = "false"

    try:
        with open(ini_path, "w", encoding="utf-8") as f:
            f.write("; Moria Manager Settings\n")
            f.write("; Set logging = true to enable detailed logging to file\n")
            f.write("; theme = light, dark, or system (match Windows)\n\n")
            config.write(f)
    except OSError:
        pass
