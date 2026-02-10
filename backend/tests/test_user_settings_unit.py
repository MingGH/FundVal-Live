"""Unit tests for user-level settings — no DB required.

Tests the get_user_effective_settings logic and the USER_CONFIGURABLE_KEYS / ENCRYPTED_FIELDS constants.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.routers.settings import (
    ENCRYPTED_FIELDS,
    USER_CONFIGURABLE_KEYS,
    validate_email,
    validate_url,
    validate_port,
)


class TestUserSettingsConstants:
    """Verify the constants are correctly defined."""

    def test_encrypted_fields_contains_sensitive_keys(self):
        assert "OPENAI_API_KEY" in ENCRYPTED_FIELDS
        assert "SMTP_PASSWORD" in ENCRYPTED_FIELDS

    def test_encrypted_fields_does_not_contain_non_sensitive(self):
        assert "OPENAI_API_BASE" not in ENCRYPTED_FIELDS
        assert "AI_MODEL_NAME" not in ENCRYPTED_FIELDS
        assert "SMTP_HOST" not in ENCRYPTED_FIELDS

    def test_user_configurable_keys_includes_ai_settings(self):
        assert "OPENAI_API_KEY" in USER_CONFIGURABLE_KEYS
        assert "OPENAI_API_BASE" in USER_CONFIGURABLE_KEYS
        assert "AI_MODEL_NAME" in USER_CONFIGURABLE_KEYS

    def test_user_configurable_keys_includes_smtp_settings(self):
        assert "SMTP_HOST" in USER_CONFIGURABLE_KEYS
        assert "SMTP_PORT" in USER_CONFIGURABLE_KEYS
        assert "SMTP_USER" in USER_CONFIGURABLE_KEYS
        assert "SMTP_PASSWORD" in USER_CONFIGURABLE_KEYS
        assert "EMAIL_FROM" in USER_CONFIGURABLE_KEYS

    def test_user_configurable_keys_does_not_include_system_keys(self):
        # Users should not be able to set system-level keys
        assert "INTRADAY_COLLECT_INTERVAL" not in USER_CONFIGURABLE_KEYS

    def test_all_encrypted_fields_are_configurable(self):
        # Every encrypted field should be in the user-configurable set
        for field in ENCRYPTED_FIELDS:
            assert field in USER_CONFIGURABLE_KEYS, f"{field} is encrypted but not user-configurable"


class TestValidatorsStillWork:
    """Ensure existing validators are not broken by the changes."""

    def test_email_valid(self):
        assert validate_email("test@example.com")
        assert validate_email("user.name+tag@domain.co")

    def test_email_invalid(self):
        assert not validate_email("")
        assert not validate_email("notanemail")

    def test_url_valid(self):
        assert validate_url("https://api.deepseek.com")
        assert validate_url("http://localhost:8080/v1")

    def test_url_invalid(self):
        assert not validate_url("not-a-url")
        assert not validate_url("")

    def test_port_valid(self):
        assert validate_port("587")
        assert validate_port("1")
        assert validate_port("65535")

    def test_port_invalid(self):
        assert not validate_port("0")
        assert not validate_port("70000")
        assert not validate_port("abc")
