"""Unit tests for user note feature in admin router — no DB required."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from app.routers.admin import router, CreateUserRequest, UpdateUserRequest
from app.auth import require_admin


# ── Build a test app with admin dependency overridden ──
app = FastAPI()
app.include_router(router)

FAKE_ADMIN = {"id": 1, "user_id": 1, "username": "admin", "role": "admin"}
app.dependency_overrides[require_admin] = lambda: FAKE_ADMIN

client = TestClient(app)


class TestNoteModels:
    """Verify Pydantic models accept the note field."""

    def test_create_request_default_note(self):
        req = CreateUserRequest(username="alice", password="pw123")
        assert req.note == ""

    def test_create_request_with_note(self):
        req = CreateUserRequest(username="alice", password="pw123", note="我的朋友小明")
        assert req.note == "我的朋友小明"

    def test_update_request_note_none_by_default(self):
        req = UpdateUserRequest()
        assert req.note is None

    def test_update_request_with_note(self):
        req = UpdateUserRequest(note="同事老王")
        assert req.note == "同事老王"

    def test_update_request_note_empty_string(self):
        req = UpdateUserRequest(note="")
        assert req.note == ""


class TestListUsersNote:
    """Verify list_users returns note field."""

    @patch("app.routers.admin.release_db_connection")
    @patch("app.routers.admin.get_db_connection")
    def test_list_users_includes_note(self, mock_conn, mock_release):
        mock_cur = MagicMock()
        mock_conn.return_value.cursor.return_value = mock_cur
        mock_cur.fetchall.return_value = [
            {"id": 1, "username": "admin", "role": "admin", "note": "", "is_active": 1, "created_at": "2026-01-01"},
            {"id": 2, "username": "bob", "role": "user", "note": "朋友小李", "is_active": 1, "created_at": "2026-01-02"},
        ]

        with patch("app.routers.admin.dict_cursor", return_value=mock_cur):
            resp = client.get("/admin/users")

        assert resp.status_code == 200
        users = resp.json()["users"]
        assert len(users) == 2
        assert users[0]["note"] == ""
        assert users[1]["note"] == "朋友小李"

    @patch("app.routers.admin.release_db_connection")
    @patch("app.routers.admin.get_db_connection")
    def test_list_users_sql_contains_note(self, mock_conn, mock_release):
        mock_cur = MagicMock()
        mock_conn.return_value.cursor.return_value = mock_cur
        mock_cur.fetchall.return_value = []

        with patch("app.routers.admin.dict_cursor", return_value=mock_cur):
            client.get("/admin/users")

        sql = mock_cur.execute.call_args[0][0]
        assert "note" in sql


class TestCreateUserNote:
    """Verify create_user handles note field."""

    @patch("app.routers.admin.release_db_connection")
    @patch("app.routers.admin.get_db_connection")
    def test_create_user_with_note(self, mock_conn, mock_release):
        mock_cur = MagicMock()
        mock_cur.lastrowid = 10
        mock_conn.return_value.cursor.return_value = mock_cur

        with patch("app.routers.admin.dict_cursor", return_value=mock_cur):
            resp = client.post("/admin/users", json={
                "username": "alice", "password": "pw123", "note": "大学同学"
            })

        assert resp.status_code == 200
        assert resp.json()["username"] == "alice"
        # Check the INSERT SQL includes note
        insert_call = mock_cur.execute.call_args_list[0]
        sql = insert_call[0][0]
        params = insert_call[0][1]
        assert "note" in sql
        assert "大学同学" in params

    @patch("app.routers.admin.release_db_connection")
    @patch("app.routers.admin.get_db_connection")
    def test_create_user_without_note(self, mock_conn, mock_release):
        mock_cur = MagicMock()
        mock_cur.lastrowid = 11
        mock_conn.return_value.cursor.return_value = mock_cur

        with patch("app.routers.admin.dict_cursor", return_value=mock_cur):
            resp = client.post("/admin/users", json={
                "username": "bob", "password": "pw456"
            })

        assert resp.status_code == 200
        insert_call = mock_cur.execute.call_args_list[0]
        params = insert_call[0][1]
        # Default empty note
        assert "" in params


class TestUpdateUserNote:
    """Verify update_user handles note field."""

    @patch("app.routers.admin.release_db_connection")
    @patch("app.routers.admin.get_db_connection")
    def test_update_note_only(self, mock_conn, mock_release):
        mock_cur = MagicMock()
        mock_conn.return_value.cursor.return_value = mock_cur

        with patch("app.routers.admin.dict_cursor", return_value=mock_cur):
            resp = client.put("/admin/users/5", json={"note": "高中同学"})

        assert resp.status_code == 200
        # Should have executed one UPDATE for note
        assert mock_cur.execute.call_count == 1
        sql = mock_cur.execute.call_args[0][0]
        params = mock_cur.execute.call_args[0][1]
        assert "note" in sql
        assert "高中同学" in params

    @patch("app.routers.admin.release_db_connection")
    @patch("app.routers.admin.get_db_connection")
    def test_update_note_with_other_fields(self, mock_conn, mock_release):
        mock_cur = MagicMock()
        mock_conn.return_value.cursor.return_value = mock_cur

        with patch("app.routers.admin.dict_cursor", return_value=mock_cur):
            resp = client.put("/admin/users/5", json={"note": "备注", "is_active": False})

        assert resp.status_code == 200
        # Two UPDATEs: is_active + note
        assert mock_cur.execute.call_count == 2

    @patch("app.routers.admin.release_db_connection")
    @patch("app.routers.admin.get_db_connection")
    def test_update_note_to_empty(self, mock_conn, mock_release):
        mock_cur = MagicMock()
        mock_conn.return_value.cursor.return_value = mock_cur

        with patch("app.routers.admin.dict_cursor", return_value=mock_cur):
            resp = client.put("/admin/users/5", json={"note": ""})

        assert resp.status_code == 200
        sql = mock_cur.execute.call_args[0][0]
        params = mock_cur.execute.call_args[0][1]
        assert "note" in sql
        assert "" in params

    @patch("app.routers.admin.release_db_connection")
    @patch("app.routers.admin.get_db_connection")
    def test_update_without_note_does_not_touch_note(self, mock_conn, mock_release):
        mock_cur = MagicMock()
        mock_conn.return_value.cursor.return_value = mock_cur

        with patch("app.routers.admin.dict_cursor", return_value=mock_cur):
            resp = client.put("/admin/users/5", json={"is_active": True})

        assert resp.status_code == 200
        # Only one UPDATE for is_active, note should not be touched
        assert mock_cur.execute.call_count == 1
        sql = mock_cur.execute.call_args[0][0]
        assert "note" not in sql
