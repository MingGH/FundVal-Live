"""Integration tests for SaaS API — requires running MySQL.

Uses a dedicated test database. Tests auth, admin CRUD, multi-tenant isolation.
"""
import os
import sys
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    "mysql://funduser:fundpass@localhost:3306/fundval_test"
)
os.environ["DATABASE_URL"] = TEST_DB_URL

import pymysql
import httpx
import pytest

# ── DB setup/teardown ──

def _parse_mysql_url(url):
    from urllib.parse import urlparse
    parsed = urlparse(url)
    return {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 3306,
        "user": parsed.username or "root",
        "password": parsed.password or "",
    }

def _setup_db():
    params = _parse_mysql_url(TEST_DB_URL)
    conn = pymysql.connect(**params)
    conn.autocommit(True)
    cur = conn.cursor()
    cur.execute("DROP DATABASE IF EXISTS fundval_test")
    cur.execute("CREATE DATABASE fundval_test CHARACTER SET utf8mb4")
    cur.close()
    conn.close()

    from app.db import init_db, _init_pool
    _init_pool()
    init_db()


def _teardown_db():
    from app.db import _pool
    if _pool:
        _pool.close()
    params = _parse_mysql_url(TEST_DB_URL)
    conn = pymysql.connect(**params)
    conn.autocommit(True)
    cur = conn.cursor()
    cur.execute("DROP DATABASE IF EXISTS fundval_test")
    cur.close()
    conn.close()


# Setup once
_setup_db()

from app.main import app as _app


def auth(token):
    return {"Authorization": f"Bearer {token}"}


async def _req(method, url, **kwargs):
    transport = httpx.ASGITransport(app=_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        return await getattr(c, method)(url, **kwargs)


def req(method, url, **kwargs):
    return asyncio.get_event_loop().run_until_complete(_req(method, url, **kwargs))


# Get admin token once
_admin_pw = os.getenv("ADMIN_PASSWORD", "admin123")
_r = req("post", "/api/auth/login", json={"username": "admin", "password": _admin_pw})
assert _r.status_code == 200, f"Admin login failed: {_r.text}"
ADMIN_TOKEN = _r.json()["token"]


# ── Auth Tests ──

class TestAuth:
    def test_login_success(self):
        r = req("post", "/api/auth/login", json={"username": "admin", "password": _admin_pw})
        assert r.status_code == 200
        assert "token" in r.json()
        assert r.json()["user"]["username"] == "admin"

    def test_login_wrong_password(self):
        r = req("post", "/api/auth/login", json={"username": "admin", "password": "wrong"})
        assert r.status_code == 401

    def test_login_nonexistent_user(self):
        r = req("post", "/api/auth/login", json={"username": "ghost", "password": "x"})
        assert r.status_code == 401

    def test_me_with_token(self):
        r = req("get", "/api/auth/me", headers=auth(ADMIN_TOKEN))
        assert r.status_code == 200
        assert r.json()["user"]["username"] == "admin"

    def test_me_without_token(self):
        r = req("get", "/api/auth/me")
        assert r.status_code == 401

    def test_me_with_bad_token(self):
        r = req("get", "/api/auth/me", headers=auth("invalid.token.here"))
        assert r.status_code == 401


# ── Admin User Management ──

class TestAdminUsers:
    def test_create_user(self):
        r = req("post", "/api/admin/users", json={"username": "testuser1", "password": "pass1234"}, headers=auth(ADMIN_TOKEN))
        assert r.status_code == 200
        assert "id" in r.json()

    def test_create_duplicate_user(self):
        r = req("post", "/api/admin/users", json={"username": "testuser1", "password": "x"}, headers=auth(ADMIN_TOKEN))
        assert r.status_code == 400

    def test_list_users(self):
        r = req("get", "/api/admin/users", headers=auth(ADMIN_TOKEN))
        assert r.status_code == 200
        names = [u["username"] for u in r.json()["users"]]
        assert "admin" in names
        assert "testuser1" in names

    def test_disable_and_reenable_user(self):
        r = req("get", "/api/admin/users", headers=auth(ADMIN_TOKEN))
        uid = [u for u in r.json()["users"] if u["username"] == "testuser1"][0]["id"]

        # Disable
        r = req("put", f"/api/admin/users/{uid}", json={"is_active": False}, headers=auth(ADMIN_TOKEN))
        assert r.status_code == 200

        # Can't login
        r = req("post", "/api/auth/login", json={"username": "testuser1", "password": "pass1234"})
        assert r.status_code == 403

        # Re-enable
        req("put", f"/api/admin/users/{uid}", json={"is_active": True}, headers=auth(ADMIN_TOKEN))

    def test_non_admin_forbidden(self):
        r = req("post", "/api/auth/login", json={"username": "testuser1", "password": "pass1234"})
        user_token = r.json()["token"]
        r = req("get", "/api/admin/users", headers=auth(user_token))
        assert r.status_code == 403

    def test_delete_user(self):
        r = req("post", "/api/admin/users", json={"username": "todelete", "password": "x"}, headers=auth(ADMIN_TOKEN))
        uid = r.json()["id"]
        r = req("delete", f"/api/admin/users/{uid}", headers=auth(ADMIN_TOKEN))
        assert r.status_code == 200


# ── Multi-Tenant Isolation ──

class TestMultiTenant:
    @classmethod
    def setup_class(cls):
        req("post", "/api/admin/users", json={"username": "iso_a", "password": "aaa"}, headers=auth(ADMIN_TOKEN))
        r = req("post", "/api/auth/login", json={"username": "iso_a", "password": "aaa"})
        cls.token_a = r.json()["token"]

        req("post", "/api/admin/users", json={"username": "iso_b", "password": "bbb"}, headers=auth(ADMIN_TOKEN))
        r = req("post", "/api/auth/login", json={"username": "iso_b", "password": "bbb"})
        cls.token_b = r.json()["token"]

    def test_accounts_isolated(self):
        r = req("post", "/api/accounts", json={"name": "A的账户", "description": ""}, headers=auth(self.token_a))
        assert r.status_code == 200

        r = req("get", "/api/accounts", headers=auth(self.token_b))
        names = [a["name"] for a in r.json()["accounts"]]
        assert "A的账户" not in names

    def test_prompts_isolated(self):
        r = req("post", "/api/ai/prompts", json={
            "name": "A的模板", "system_prompt": "sys", "user_prompt": "usr", "is_default": False
        }, headers=auth(self.token_a))
        assert r.status_code == 200
        prompt_id = r.json()["id"]

        r = req("get", "/api/ai/prompts", headers=auth(self.token_b))
        ids = [p["id"] for p in r.json()["prompts"]]
        assert prompt_id not in ids

    def test_preferences_isolated(self):
        req("post", "/api/preferences", json={"watchlist": "[1,2,3]"}, headers=auth(self.token_a))
        r = req("get", "/api/preferences", headers=auth(self.token_b))
        assert r.json()["watchlist"] == "[]"


# ── Protected Endpoints ──

class TestProtectedEndpoints:
    @pytest.mark.parametrize("url", [
        "/api/accounts", "/api/ai/prompts", "/api/preferences",
        "/api/auth/me", "/api/data/export",
    ])
    def test_get_requires_auth(self, url):
        r = req("get", url)
        assert r.status_code == 401, f"{url} got {r.status_code}"

    @pytest.mark.parametrize("url,body", [
        ("/api/accounts", {"name": "x", "description": ""}),
        ("/api/ai/prompts", {"name": "x", "system_prompt": "s", "user_prompt": "u"}),
        ("/api/preferences", {"watchlist": "[]"}),
    ])
    def test_post_requires_auth(self, url, body):
        r = req("post", url, json=body)
        assert r.status_code == 401, f"{url} got {r.status_code}"


# ── Settings (admin-only) ──

class TestSettings:
    def test_requires_auth(self):
        assert req("get", "/api/settings").status_code == 401

    def test_non_admin_forbidden(self):
        req("post", "/api/admin/users", json={"username": "normie", "password": "nnn"}, headers=auth(ADMIN_TOKEN))
        r = req("post", "/api/auth/login", json={"username": "normie", "password": "nnn"})
        assert req("get", "/api/settings", headers=auth(r.json()["token"])).status_code == 403

    def test_admin_can_read(self):
        r = req("get", "/api/settings", headers=auth(ADMIN_TOKEN))
        assert r.status_code == 200
        assert "settings" in r.json()


# ── Public Endpoints ──

class TestPublicEndpoints:
    def test_categories(self):
        assert req("get", "/api/categories").status_code == 200

    def test_info(self):
        assert req("get", "/api/info").status_code == 200


# ── Change Password ──

class TestChangePassword:
    def test_full_flow(self):
        req("post", "/api/admin/users", json={"username": "pwuser", "password": "old123"}, headers=auth(ADMIN_TOKEN))
        r = req("post", "/api/auth/login", json={"username": "pwuser", "password": "old123"})
        token = r.json()["token"]

        r = req("post", "/api/auth/change-password", json={"old_password": "old123", "new_password": "new456"}, headers=auth(token))
        assert r.status_code == 200

        assert req("post", "/api/auth/login", json={"username": "pwuser", "password": "old123"}).status_code == 401
        assert req("post", "/api/auth/login", json={"username": "pwuser", "password": "new456"}).status_code == 200

    def test_wrong_old_password(self):
        req("post", "/api/admin/users", json={"username": "pwuser2", "password": "abc"}, headers=auth(ADMIN_TOKEN))
        r = req("post", "/api/auth/login", json={"username": "pwuser2", "password": "abc"})
        token = r.json()["token"]

        r = req("post", "/api/auth/change-password", json={"old_password": "wrong", "new_password": "new"}, headers=auth(token))
        assert r.status_code == 400
