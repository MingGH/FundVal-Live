"""Authentication module: JWT + bcrypt password hashing."""
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import hashlib
import hmac
import json
import base64

security = HTTPBearer(auto_error=False)

JWT_SECRET = os.getenv("JWT_SECRET", "fundval-live-jwt-secret-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 72


def hash_password(password: str) -> str:
    """Hash password with salt using SHA-256 (no extra deps)."""
    salt = os.urandom(16)
    pw_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)
    return base64.b64encode(salt + pw_hash).decode()


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify password against stored hash."""
    decoded = base64.b64decode(stored_hash.encode())
    salt = decoded[:16]
    stored_pw_hash = decoded[16:]
    pw_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)
    return hmac.compare_digest(pw_hash, stored_pw_hash)


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    s += "=" * (4 - len(s) % 4)
    return base64.urlsafe_b64decode(s)


def create_access_token(user_id: int, username: str, role: str) -> str:
    """Create a JWT token."""
    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload_data = {
        "sub": user_id,
        "username": username,
        "role": role,
        "exp": int((datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS)).timestamp()),
    }
    payload = _b64url_encode(json.dumps(payload_data).encode())
    signature = hmac.new(JWT_SECRET.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
    sig = _b64url_encode(signature)
    return f"{header}.{payload}.{sig}"


def decode_token(token: str) -> Optional[dict]:
    """Decode and verify a JWT token."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header, payload, sig = parts
        expected_sig = hmac.new(JWT_SECRET.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(_b64url_decode(sig), expected_sig):
            return None
        payload_data = json.loads(_b64url_decode(payload))
        if payload_data.get("exp", 0) < datetime.now(timezone.utc).timestamp():
            return None
        return payload_data
    except Exception:
        return None


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """FastAPI dependency to get current authenticated user."""
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")
    payload = decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 无效或已过期")
    return {"id": payload["sub"], "user_id": payload["sub"], "username": payload["username"], "role": payload["role"]}


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """FastAPI dependency to require admin role."""
    if user["role"] != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return user
