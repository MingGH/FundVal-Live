"""Unit tests for auth module — no DB required."""
import os
import sys
import time

# Ensure backend is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.auth import (
    hash_password, verify_password,
    create_access_token, decode_token,
    _b64url_encode, _b64url_decode,
)


class TestPasswordHashing:
    def test_hash_and_verify(self):
        pw = "test_password_123"
        h = hash_password(pw)
        assert verify_password(pw, h)

    def test_wrong_password_fails(self):
        h = hash_password("correct")
        assert not verify_password("wrong", h)

    def test_different_hashes_for_same_password(self):
        """Salt should make each hash unique."""
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2
        assert verify_password("same", h1)
        assert verify_password("same", h2)

    def test_empty_password(self):
        h = hash_password("")
        assert verify_password("", h)
        assert not verify_password("x", h)


class TestJWT:
    def test_create_and_decode(self):
        token = create_access_token(42, "alice", "admin")
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == 42
        assert payload["username"] == "alice"
        assert payload["role"] == "admin"

    def test_tampered_token_rejected(self):
        token = create_access_token(1, "bob", "user")
        # Flip a character in the signature
        parts = token.split(".")
        sig = parts[2]
        tampered_sig = sig[:-1] + ("A" if sig[-1] != "A" else "B")
        tampered = f"{parts[0]}.{parts[1]}.{tampered_sig}"
        assert decode_token(tampered) is None

    def test_expired_token_rejected(self):
        """Manually craft an expired token."""
        import json, hmac, hashlib, base64
        from app.auth import JWT_SECRET

        header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
        payload_data = {"sub": 1, "username": "x", "role": "user", "exp": int(time.time()) - 10}
        payload = _b64url_encode(json.dumps(payload_data).encode())
        sig = hmac.new(JWT_SECRET.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
        token = f"{header}.{payload}.{_b64url_encode(sig)}"
        assert decode_token(token) is None

    def test_malformed_token_rejected(self):
        assert decode_token("not.a.valid.token") is None
        assert decode_token("") is None
        assert decode_token("abc") is None

    def test_token_contains_three_parts(self):
        token = create_access_token(1, "u", "user")
        assert len(token.split(".")) == 3


class TestB64Url:
    def test_roundtrip(self):
        data = b"hello world \x00\xff"
        assert _b64url_decode(_b64url_encode(data)) == data

    def test_no_padding(self):
        encoded = _b64url_encode(b"test")
        assert "=" not in encoded
