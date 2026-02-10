"""Unit tests for SaaS multi-tenancy fixes — no DB required.

Covers:
1. Per-user key derivation in crypto.py
2. Per-user SMTP in email.py
3. Tenant-aware subscription grouping in subscription.py
4. Tenant-aware scheduler in scheduler.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch, MagicMock


# ═══════════════════════════════════════════════════════════════
# 1. Per-user key derivation (crypto.py)
# ═══════════════════════════════════════════════════════════════

class TestPerUserKeyDerivation:
    """Verify that per-user encryption keys are derived correctly."""

    def test_different_users_get_different_keys(self):
        from app.crypto import _derive_user_key
        key1 = _derive_user_key(1)
        key2 = _derive_user_key(2)
        assert key1 != key2, "Different users must have different derived keys"

    def test_same_user_gets_same_key(self):
        from app.crypto import _derive_user_key
        key1 = _derive_user_key(42)
        key2 = _derive_user_key(42)
        assert key1 == key2, "Same user must always get the same derived key"

    def test_derived_key_is_valid_fernet_key(self):
        """Derived key must be a valid 32-byte url-safe base64 Fernet key."""
        import base64
        from app.crypto import _derive_user_key
        key = _derive_user_key(1)
        decoded = base64.urlsafe_b64decode(key)
        assert len(decoded) == 32

    def test_encrypt_decrypt_with_user_id(self):
        from app.crypto import encrypt_value, decrypt_value
        plaintext = "sk-secret-api-key-12345"
        encrypted = encrypt_value(plaintext, user_id=10)
        assert encrypted != ""
        assert encrypted != plaintext
        decrypted = decrypt_value(encrypted, user_id=10)
        assert decrypted == plaintext

    def test_cross_user_decrypt_fails(self):
        """User A's encrypted data cannot be decrypted by user B's key."""
        from app.crypto import encrypt_value, decrypt_value
        encrypted = encrypt_value("my-secret", user_id=1)
        # Decrypting with a different user_id should fail (return empty)
        decrypted = decrypt_value(encrypted, user_id=2)
        assert decrypted == "", "Cross-user decryption must fail"

    def test_global_key_still_works(self):
        """encrypt/decrypt without user_id should still use global key."""
        from app.crypto import encrypt_value, decrypt_value
        plaintext = "global-secret"
        encrypted = encrypt_value(plaintext)
        assert encrypted != ""
        decrypted = decrypt_value(encrypted)
        assert decrypted == plaintext

    def test_global_and_user_keys_are_incompatible(self):
        """Global-encrypted data cannot be decrypted with a user key."""
        from app.crypto import encrypt_value, decrypt_value
        encrypted_global = encrypt_value("test", user_id=None)
        decrypted_with_user = decrypt_value(encrypted_global, user_id=1)
        assert decrypted_with_user == "", "Global-encrypted data must not be decryptable with user key"

    def test_empty_string_handling(self):
        from app.crypto import encrypt_value, decrypt_value
        assert encrypt_value("", user_id=1) == ""
        assert decrypt_value("", user_id=1) == ""
        assert encrypt_value("") == ""
        assert decrypt_value("") == ""


# ═══════════════════════════════════════════════════════════════
# 2. Per-user SMTP in email.py
# ═══════════════════════════════════════════════════════════════

class TestPerUserEmail:
    """Verify that send_email uses per-user SMTP settings when user_id is provided."""

    @patch("app.services.email.smtplib.SMTP")
    @patch("app.routers.settings.get_user_effective_settings")
    def test_send_email_with_user_id_uses_user_settings(self, mock_get_settings, mock_smtp):
        """When user_id is provided, should load that user's SMTP config."""
        mock_get_settings.return_value = {
            "SMTP_HOST": "user-smtp.example.com",
            "SMTP_PORT": 465,
            "SMTP_USER": "user@example.com",
            "SMTP_PASSWORD": "user-pass",
            "EMAIL_FROM": "user@example.com",
        }
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server

        from app.services.email import send_email
        result = send_email("to@example.com", "Test", "Body", user_id=42)

        mock_get_settings.assert_called_once_with(42)
        mock_smtp.assert_called_once_with("user-smtp.example.com", 465)
        assert result is True

    @patch("app.services.email.smtplib.SMTP")
    def test_send_email_without_user_id_uses_global_config(self, mock_smtp):
        """When no user_id, should fall back to global Config."""
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server

        from app.services.email import send_email, Config
        original_host = Config.SMTP_HOST
        original_user = Config.SMTP_USER
        original_password = Config.SMTP_PASSWORD
        original_port = Config.SMTP_PORT

        try:
            Config.SMTP_HOST = "global-smtp.example.com"
            Config.SMTP_PORT = 587
            Config.SMTP_USER = "global@example.com"
            Config.SMTP_PASSWORD = "global-pass"
            Config.EMAIL_FROM = "noreply@example.com"

            result = send_email("to@example.com", "Test", "Body")

            mock_smtp.assert_called_once_with("global-smtp.example.com", 587)
            assert result is True
        finally:
            Config.SMTP_HOST = original_host
            Config.SMTP_USER = original_user
            Config.SMTP_PASSWORD = original_password
            Config.SMTP_PORT = original_port

    @patch("app.routers.settings.get_user_effective_settings")
    def test_send_email_skips_when_no_smtp_configured(self, mock_get_settings):
        """When user has no SMTP config and global is empty, should skip."""
        mock_get_settings.return_value = {
            "SMTP_HOST": "",
            "SMTP_USER": "",
        }
        from app.services.email import send_email, Config
        original_host = Config.SMTP_HOST
        original_user = Config.SMTP_USER
        try:
            Config.SMTP_HOST = ""
            Config.SMTP_USER = ""
            result = send_email("to@example.com", "Test", "Body", user_id=1)
            assert result is False
        finally:
            Config.SMTP_HOST = original_host
            Config.SMTP_USER = original_user

    @patch("app.services.email.smtplib.SMTP")
    @patch("app.routers.settings.get_user_effective_settings")
    def test_send_email_falls_back_on_user_settings_error(self, mock_get_settings, mock_smtp):
        """If loading user settings fails, should fall back to global."""
        mock_get_settings.side_effect = Exception("DB error")
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server

        from app.services.email import send_email, Config
        original_host = Config.SMTP_HOST
        original_user = Config.SMTP_USER
        original_password = Config.SMTP_PASSWORD
        original_port = Config.SMTP_PORT
        try:
            Config.SMTP_HOST = "fallback-smtp.example.com"
            Config.SMTP_PORT = 587
            Config.SMTP_USER = "fallback@example.com"
            Config.SMTP_PASSWORD = "fallback-pass"
            Config.EMAIL_FROM = "noreply@example.com"

            result = send_email("to@example.com", "Test", "Body", user_id=99)

            mock_smtp.assert_called_once_with("fallback-smtp.example.com", 587)
            assert result is True
        finally:
            Config.SMTP_HOST = original_host
            Config.SMTP_USER = original_user
            Config.SMTP_PASSWORD = original_password
            Config.SMTP_PORT = original_port


# ═══════════════════════════════════════════════════════════════
# 3. Tenant-aware subscription grouping (subscription.py)
# ═══════════════════════════════════════════════════════════════

class TestSubscriptionGrouping:
    """Verify subscription queries support user_id filtering and grouping."""

    @patch("app.services.subscription.get_db_connection")
    @patch("app.services.subscription.release_db_connection")
    @patch("app.services.subscription.dict_cursor")
    def test_get_active_subscriptions_with_user_id(self, mock_cursor, mock_release, mock_conn):
        """When user_id is provided, should filter by that user."""
        mock_cur = MagicMock()
        mock_cursor.return_value = mock_cur
        mock_cur.fetchall.return_value = [
            {"id": 1, "user_id": 10, "code": "000001", "email": "a@test.com"}
        ]

        from app.services.subscription import get_active_subscriptions
        result = get_active_subscriptions(user_id=10)

        # Verify the SQL used user_id filter
        call_args = mock_cur.execute.call_args
        assert "user_id" in call_args[0][0]
        assert call_args[0][1] == (10,)
        assert len(result) == 1

    @patch("app.services.subscription.get_db_connection")
    @patch("app.services.subscription.release_db_connection")
    @patch("app.services.subscription.dict_cursor")
    def test_get_active_subscriptions_without_user_id(self, mock_cursor, mock_release, mock_conn):
        """When no user_id, should return all subscriptions."""
        mock_cur = MagicMock()
        mock_cursor.return_value = mock_cur
        mock_cur.fetchall.return_value = [
            {"id": 1, "user_id": 10, "code": "000001"},
            {"id": 2, "user_id": 20, "code": "000002"},
        ]

        from app.services.subscription import get_active_subscriptions
        result = get_active_subscriptions()

        call_args = mock_cur.execute.call_args
        assert "WHERE" not in call_args[0][0]
        assert len(result) == 2

    @patch("app.services.subscription.get_db_connection")
    @patch("app.services.subscription.release_db_connection")
    @patch("app.services.subscription.dict_cursor")
    def test_get_subscriptions_grouped_by_user(self, mock_cursor, mock_release, mock_conn):
        """Should group subscriptions by user_id."""
        mock_cur = MagicMock()
        mock_cursor.return_value = mock_cur
        mock_cur.fetchall.return_value = [
            {"id": 1, "user_id": 10, "code": "000001"},
            {"id": 2, "user_id": 10, "code": "000002"},
            {"id": 3, "user_id": 20, "code": "000003"},
        ]

        from app.services.subscription import get_subscriptions_grouped_by_user
        grouped = get_subscriptions_grouped_by_user()

        assert 10 in grouped
        assert 20 in grouped
        assert len(grouped[10]) == 2
        assert len(grouped[20]) == 1

    @patch("app.services.subscription.get_db_connection")
    @patch("app.services.subscription.release_db_connection")
    @patch("app.services.subscription.dict_cursor")
    def test_get_subscriptions_grouped_empty(self, mock_cursor, mock_release, mock_conn):
        """Empty subscriptions should return empty dict."""
        mock_cur = MagicMock()
        mock_cursor.return_value = mock_cur
        mock_cur.fetchall.return_value = []

        from app.services.subscription import get_subscriptions_grouped_by_user
        grouped = get_subscriptions_grouped_by_user()

        assert grouped == {}


# ═══════════════════════════════════════════════════════════════
# 4. Tenant-aware scheduler (scheduler.py)
# ═══════════════════════════════════════════════════════════════

class TestSchedulerTenantAwareness:
    """Verify scheduler processes data per-user with error isolation."""

    @patch("app.services.scheduler.send_email")
    @patch("app.services.scheduler.update_notification_time")
    @patch("app.services.scheduler.get_combined_valuation")
    def test_process_user_subscriptions_sends_with_user_id(self, mock_valuation, mock_update, mock_send):
        """_process_user_subscriptions should pass user_id to send_email."""
        mock_valuation.return_value = {
            "name": "Test Fund",
            "estRate": 5.0,
            "estimate": 1.5,
            "time": "14:30",
        }
        mock_send.return_value = True

        subs = [{
            "id": 1,
            "code": "000001",
            "email": "user@test.com",
            "enable_volatility": True,
            "threshold_up": 3.0,
            "threshold_down": -3.0,
            "last_notified_at": None,
            "enable_digest": False,
        }]

        from app.services.scheduler import _process_user_subscriptions
        _process_user_subscriptions(
            user_id=42, subs=subs, valuations={},
            today_str="2026-02-10", current_time_str="14:30", now_cst=None
        )

        # Verify send_email was called with user_id=42
        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args
        assert call_kwargs[1]["user_id"] == 42

    @patch("app.services.scheduler.send_email")
    @patch("app.services.scheduler.update_digest_time")
    @patch("app.services.scheduler.get_combined_valuation")
    def test_process_user_subscriptions_digest_with_user_id(self, mock_valuation, mock_update, mock_send):
        """Digest emails should also use per-user SMTP."""
        from datetime import datetime, timezone, timedelta
        CST = timezone(timedelta(hours=8))
        now = datetime.now(CST)

        mock_valuation.return_value = {
            "name": "Test Fund",
            "estRate": 1.0,
            "estimate": 1.5,
            "time": "14:30",
        }
        mock_send.return_value = True

        subs = [{
            "id": 1,
            "code": "000001",
            "email": "user@test.com",
            "enable_volatility": False,
            "enable_digest": True,
            "digest_time": "14:00",
            "last_digest_at": None,
            "last_notified_at": None,
        }]

        from app.services.scheduler import _process_user_subscriptions
        _process_user_subscriptions(
            user_id=99, subs=subs, valuations={},
            today_str="2026-02-10", current_time_str="15:00", now_cst=now
        )

        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args
        assert call_kwargs[1]["user_id"] == 99

    @patch("app.services.scheduler._process_user_subscriptions")
    @patch("app.services.scheduler.get_subscriptions_grouped_by_user")
    def test_check_subscriptions_isolates_user_errors(self, mock_grouped, mock_process):
        """If one user's processing fails, others should still be processed."""
        mock_grouped.return_value = {
            1: [{"id": 1}],
            2: [{"id": 2}],
            3: [{"id": 3}],
        }
        # User 2 raises an exception
        def side_effect(user_id, *args, **kwargs):
            if user_id == 2:
                raise Exception("User 2 DB error")
        mock_process.side_effect = side_effect

        from app.services.scheduler import check_subscriptions
        # Should not raise
        check_subscriptions()

        # All 3 users should have been attempted
        assert mock_process.call_count == 3

    @patch("app.services.scheduler.get_subscriptions_grouped_by_user")
    def test_check_subscriptions_empty(self, mock_grouped):
        """Empty subscriptions should return without error."""
        mock_grouped.return_value = {}

        from app.services.scheduler import check_subscriptions
        check_subscriptions()  # Should not raise

    @patch("app.services.scheduler.send_email")
    @patch("app.services.scheduler.get_combined_valuation")
    def test_no_notification_when_threshold_not_reached(self, mock_valuation, mock_send):
        """Should not send email when threshold is not reached."""
        mock_valuation.return_value = {
            "name": "Test Fund",
            "estRate": 1.0,
            "estimate": 1.5,
            "time": "14:30",
        }

        subs = [{
            "id": 1,
            "code": "000001",
            "email": "user@test.com",
            "enable_volatility": True,
            "threshold_up": 3.0,
            "threshold_down": -3.0,
            "last_notified_at": None,
            "enable_digest": False,
        }]

        from app.services.scheduler import _process_user_subscriptions
        _process_user_subscriptions(
            user_id=1, subs=subs, valuations={},
            today_str="2026-02-10", current_time_str="14:30", now_cst=None
        )

        mock_send.assert_not_called()

    @patch("app.services.scheduler.send_email")
    @patch("app.services.scheduler.get_combined_valuation")
    def test_no_duplicate_notification_same_day(self, mock_valuation, mock_send):
        """Should not send notification if already notified today."""
        mock_valuation.return_value = {
            "name": "Test Fund",
            "estRate": 5.0,
            "estimate": 1.5,
            "time": "14:30",
        }

        subs = [{
            "id": 1,
            "code": "000001",
            "email": "user@test.com",
            "enable_volatility": True,
            "threshold_up": 3.0,
            "threshold_down": -3.0,
            "last_notified_at": "2026-02-10 10:00:00",
            "enable_digest": False,
        }]

        from app.services.scheduler import _process_user_subscriptions
        _process_user_subscriptions(
            user_id=1, subs=subs, valuations={},
            today_str="2026-02-10", current_time_str="14:30", now_cst=None
        )

        mock_send.assert_not_called()
