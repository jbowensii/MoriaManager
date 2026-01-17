"""Logging configuration for Moria Manager.

Provides centralized logging setup with file and console handlers.
Log files are stored in the application's config directory.
"""

import logging
import sys
from pathlib import Path

from .config.paths import GamePaths


def setup_logging(debug: bool = False) -> logging.Logger:
    """Configure application-wide logging.

    Sets up logging to both file and console (if debug mode).
    Log file is stored in %APPDATA%/MoriaManager/moria_manager.log

    Args:
        debug: If True, also log to console at DEBUG level

    Returns:
        The root logger for the application
    """
    # Ensure config directory exists for log file
    log_dir = GamePaths.CONFIG_DIR
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "moria_manager.log"

    # Create logger
    logger = logging.getLogger("moria_manager")
    logger.setLevel(logging.DEBUG)

    # Clear any existing handlers
    logger.handlers.clear()

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
