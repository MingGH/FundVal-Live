"""Unit tests for settings validators — no DB required."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.routers.settings import validate_email, validate_url, validate_port


class TestValidators:
    def test_valid_emails(self):
        assert validate_email("user@example.com")
        assert validate_email("a.b+c@d.co")

    def test_invalid_emails(self):
        assert not validate_email("")
        assert not validate_email("noat")
        assert not validate_email("@no-local.com")

    def test_valid_urls(self):
        assert validate_url("https://api.openai.com/v1")
        assert validate_url("http://localhost:8080")

    def test_invalid_urls(self):
        assert not validate_url("ftp://bad")
        assert not validate_url("not a url")

    def test_valid_ports(self):
        assert validate_port("80")
        assert validate_port("443")
        assert validate_port("65535")

    def test_invalid_ports(self):
        assert not validate_port("0")
        assert not validate_port("99999")
        assert not validate_port("abc")
