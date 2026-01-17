"""Security utilities for encrypting sensitive configuration data.

Uses Fernet symmetric encryption with a machine-specific key derived from
the Windows username, machine name, and a static salt. This provides basic
protection against casual file access while keeping data recoverable on
the same machine.
"""

import base64
import hashlib
import os
from typing import Optional

from ..logging_config import get_logger

logger = get_logger("security")

# Static salt - not secret, just adds entropy
_SALT = b"MoriaManager_v1_salt_2024"


def _get_machine_key() -> bytes:
    """Generate a machine-specific encryption key.

    Derives a key from the current Windows username and computer name.
    This means encrypted data can only be decrypted on the same machine
    by the same user.

    Returns:
        32-byte key suitable for Fernet encryption
    """
    # Combine machine-specific identifiers
    username = os.environ.get("USERNAME", "default_user")
    computername = os.environ.get("COMPUTERNAME", "default_machine")

    # Create a deterministic key from these values
    key_material = f"{username}:{computername}".encode('utf-8')

    # Use PBKDF2 to derive a proper key
    key = hashlib.pbkdf2_hmac(
        'sha256',
        key_material,
        _SALT,
        iterations=100000,
        dklen=32
    )

    return base64.urlsafe_b64encode(key)


def _get_cipher():
    """Get the Fernet cipher instance.

    Returns:
        Fernet cipher or None if cryptography is not available
    """
    try:
        from cryptography.fernet import Fernet
        return Fernet(_get_machine_key())
    except ImportError:
        logger.warning("cryptography package not installed - passwords will be stored in plain text")
        return None


def encrypt_password(plain_text: str) -> str:
    """Encrypt a password for storage.

    Args:
        plain_text: The plain text password to encrypt

    Returns:
        Base64-encoded encrypted string, or the original string if
        encryption is not available. Encrypted strings are prefixed
        with 'ENC:' to identify them.
    """
    if not plain_text:
        return ""

    cipher = _get_cipher()
    if cipher is None:
        return plain_text

    try:
        encrypted = cipher.encrypt(plain_text.encode('utf-8'))
        return f"ENC:{encrypted.decode('utf-8')}"
    except (TypeError, ValueError, UnicodeError) as e:
        logger.error(f"Failed to encrypt password: {e}")
        return plain_text


def decrypt_password(encrypted_text: str) -> str:
    """Decrypt a stored password.

    Args:
        encrypted_text: The encrypted password string (prefixed with 'ENC:')

    Returns:
        The decrypted plain text password, or the original string if
        decryption fails or the string is not encrypted.
    """
    if not encrypted_text:
        return ""

    # Check if this is an encrypted password
    if not encrypted_text.startswith("ENC:"):
        # Not encrypted, return as-is (legacy plain text)
        return encrypted_text

    cipher = _get_cipher()
    if cipher is None:
        # Can't decrypt without cryptography - return empty for security
        logger.warning("Cannot decrypt password: cryptography package not installed")
        return ""

    try:
        encrypted_data = encrypted_text[4:].encode('utf-8')  # Remove 'ENC:' prefix
        decrypted = cipher.decrypt(encrypted_data)
        return decrypted.decode('utf-8')
    except (TypeError, ValueError, UnicodeError) as e:
        logger.error(f"Failed to decrypt password: {e}")
        # Return empty string for security rather than the encrypted data
        return ""


def is_encrypted(text: str) -> bool:
    """Check if a string is encrypted.

    Args:
        text: The string to check

    Returns:
        True if the string appears to be encrypted
    """
    return text.startswith("ENC:") if text else False
