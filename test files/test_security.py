"""Tests for moria_manager.config.security module."""

import os

import pytest

from moria_manager.config.security import (
    _get_machine_key,
    decrypt_password,
    encrypt_password,
    is_encrypted,
)


class TestGetMachineKey:
    """Tests for _get_machine_key()."""

    def test_returns_bytes(self):
        key = _get_machine_key()
        assert isinstance(key, bytes)

    def test_deterministic_on_same_machine(self):
        key1 = _get_machine_key()
        key2 = _get_machine_key()
        assert key1 == key2

    def test_key_length_valid_for_fernet(self):
        key = _get_machine_key()
        # Fernet requires 32 bytes url-safe base64 encoded = 44 bytes
        assert len(key) == 44


class TestEncryptPassword:
    """Tests for encrypt_password()."""

    def test_empty_string_returns_empty(self):
        assert encrypt_password("") == ""

    def test_encrypted_has_enc_prefix(self):
        result = encrypt_password("mypassword")
        assert result.startswith("ENC:")

    def test_roundtrip_normal_string(self):
        original = "mypassword123"
        encrypted = encrypt_password(original)
        decrypted = decrypt_password(encrypted)
        assert decrypted == original

    def test_roundtrip_unicode(self):
        original = "p\u00e4ssw\u00f6rd\u00fc"
        encrypted = encrypt_password(original)
        decrypted = decrypt_password(encrypted)
        assert decrypted == original

    def test_roundtrip_special_chars(self):
        original = "p@ss!w#rd$%^&*()"
        encrypted = encrypt_password(original)
        decrypted = decrypt_password(encrypted)
        assert decrypted == original

    def test_roundtrip_very_long_string(self):
        original = "a" * 10000
        encrypted = encrypt_password(original)
        decrypted = decrypt_password(encrypted)
        assert decrypted == original

    def test_roundtrip_string_with_newlines(self):
        original = "line1\nline2\r\nline3"
        encrypted = encrypt_password(original)
        decrypted = decrypt_password(encrypted)
        assert decrypted == original

    def test_consistency(self):
        """Encrypting same string twice yields same prefix but different ciphertext (Fernet uses random IV)."""
        result1 = encrypt_password("test")
        result2 = encrypt_password("test")
        assert result1.startswith("ENC:")
        assert result2.startswith("ENC:")
        # Both should decrypt to same value
        assert decrypt_password(result1) == decrypt_password(result2) == "test"


class TestDecryptPassword:
    """Tests for decrypt_password()."""

    def test_empty_string_returns_empty(self):
        assert decrypt_password("") == ""

    def test_non_encrypted_returns_as_is(self):
        assert decrypt_password("plaintext") == "plaintext"

    def test_garbage_encrypted_data_returns_empty(self):
        result = decrypt_password("ENC:not_valid_base64_data!!!")
        assert result == ""

    def test_corrupted_ciphertext_returns_empty(self):
        # Valid base64 but not valid Fernet token
        result = decrypt_password("ENC:dGVzdA==")
        assert result == ""


class TestIsEncrypted:
    """Tests for is_encrypted()."""

    def test_encrypted_text(self):
        encrypted = encrypt_password("test")
        assert is_encrypted(encrypted) is True

    def test_plain_text(self):
        assert is_encrypted("plaintext") is False

    def test_empty_string(self):
        assert is_encrypted("") is False

    def test_enc_prefix_only(self):
        assert is_encrypted("ENC:") is True

    def test_partial_prefix(self):
        assert is_encrypted("ENC") is False
        assert is_encrypted("EN") is False
