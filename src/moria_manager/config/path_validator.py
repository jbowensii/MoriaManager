"""Path validation utilities to prevent dangerous file operations.

Provides validation for paths used in file operations to prevent:
- Path traversal attacks
- Operations on protected system directories
- Operations outside expected directories
"""

import os
from pathlib import Path
from typing import Optional

from ..logging_config import get_logger

logger = get_logger("path_validator")

# Protected Windows system directories that should never be modified
PROTECTED_DIRECTORIES = [
    "C:\\Windows",
    "C:\\Program Files",
    "C:\\Program Files (x86)",
    "C:\\ProgramData",
    "C:\\Users\\Default",
    "C:\\Users\\Public",
    "C:\\$Recycle.Bin",
    "C:\\System Volume Information",
]

# Additional protected paths based on environment variables
PROTECTED_ENV_PATHS = [
    "WINDIR",
    "SYSTEMROOT",
    "PROGRAMFILES",
    "PROGRAMFILES(X86)",
    "PROGRAMDATA",
]


def _get_protected_paths() -> set[Path]:
    """Build the set of protected paths including environment-based ones."""
    protected = set()

    # Add static protected directories
    for dir_path in PROTECTED_DIRECTORIES:
        try:
            protected.add(Path(dir_path).resolve())
        except (OSError, ValueError):
            pass

    # Add environment-based protected paths
    for env_var in PROTECTED_ENV_PATHS:
        env_value = os.environ.get(env_var)
        if env_value:
            try:
                protected.add(Path(env_value).resolve())
            except (OSError, ValueError):
                pass

    return protected


def is_safe_path(path: Path, allowed_roots: Optional[list[Path]] = None) -> bool:
    """Check if a path is safe for file operations.

    Args:
        path: The path to validate
        allowed_roots: Optional list of allowed root directories. If provided,
                      the path must be under one of these roots.

    Returns:
        True if the path is safe, False otherwise
    """
    try:
        resolved = path.resolve()
    except (OSError, ValueError) as e:
        logger.warning("Failed to resolve path %s: %s", path, e)
        return False

    # Check for protected system directories
    protected = _get_protected_paths()
    for protected_path in protected:
        try:
            if resolved == protected_path or protected_path in resolved.parents:
                logger.warning("Path %s is in protected directory %s", path, protected_path)
                return False
        except (OSError, ValueError):
            pass

    # If allowed_roots is specified, ensure path is under one of them
    if allowed_roots:
        is_under_allowed = False
        for root in allowed_roots:
            try:
                root_resolved = root.resolve()
                if resolved == root_resolved or root_resolved in resolved.parents:
                    is_under_allowed = True
                    break
            except (OSError, ValueError):
                pass

        if not is_under_allowed:
            logger.warning("Path %s is not under any allowed root", path)
            return False

    return True


def is_path_under_root(path: Path, root: Path) -> bool:
    """Check if a path is under a given root directory.

    Args:
        path: The path to check
        root: The root directory

    Returns:
        True if path is under root, False otherwise
    """
    try:
        path_resolved = path.resolve()
        root_resolved = root.resolve()
        return path_resolved == root_resolved or root_resolved in path_resolved.parents
    except (OSError, ValueError) as e:
        logger.warning("Failed to check path relationship: %s", e)
        return False


def validate_backup_path(backup_path: Path, backup_root: Path) -> tuple[bool, str]:
    """Validate a backup path before performing operations.

    Args:
        backup_path: The backup path to validate
        backup_root: The configured backup root directory

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check basic path validity
    if not backup_path:
        return False, "Backup path is empty"

    try:
        backup_path.resolve()  # Validate path can be resolved
    except (OSError, ValueError) as e:
        return False, f"Invalid path: {e}"

    # Ensure path is under backup root
    if not is_path_under_root(backup_path, backup_root):
        return False, f"Path must be under backup directory: {backup_root}"

    # Check for path traversal attempts
    path_str = str(backup_path)
    if ".." in path_str:
        return False, "Path contains directory traversal"

    # Check for protected directories
    if not is_safe_path(backup_path):
        return False, "Path is in a protected system directory"

    return True, ""


def validate_save_path(save_path: Path) -> tuple[bool, str]:
    """Validate a game save path before performing operations.

    Args:
        save_path: The save path to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not save_path:
        return False, "Save path is empty"

    try:
        save_path.resolve()  # Validate path can be resolved
    except (OSError, ValueError) as e:
        return False, f"Invalid path: {e}"

    # Save paths should typically be under LocalAppData
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        local_appdata_path = Path(local_appdata)
        if not is_path_under_root(save_path, local_appdata_path):
            # Also allow paths under user profile
            userprofile = os.environ.get("USERPROFILE")
            if userprofile:
                userprofile_path = Path(userprofile)
                if not is_path_under_root(save_path, userprofile_path):
                    return False, "Save path should be under user's local app data or profile"

    # Check for protected directories
    if not is_safe_path(save_path):
        return False, "Path is in a protected system directory"

    return True, ""


def validate_game_path(game_path: Path) -> tuple[bool, str]:
    """Validate a game installation path.

    Args:
        game_path: The game installation path to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not game_path:
        return False, "Game path is empty"

    try:
        resolved = game_path.resolve()
    except (OSError, ValueError) as e:
        return False, f"Invalid path: {e}"

    if not resolved.exists():
        return False, "Game path does not exist"

    if not resolved.is_dir():
        return False, "Game path is not a directory"

    return True, ""


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename by removing dangerous characters.

    Args:
        filename: The filename to sanitize

    Returns:
        Sanitized filename safe for use in file operations
    """
    # Remove or replace dangerous characters
    dangerous_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*', '\0']
    result = filename

    for char in dangerous_chars:
        result = result.replace(char, '_')

    # Remove leading/trailing dots and spaces
    result = result.strip('. ')

    # Limit length
    if len(result) > 200:
        result = result[:200]

    # Ensure not empty
    if not result:
        result = "unnamed"

    return result
