"""Admin router: user management (admin only)."""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

from ..db import get_db_connection, release_db_connection, dict_cursor
from ..auth import require_admin, hash_password

router = APIRouter()


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str = "user"


class UpdateUserRequest(BaseModel):
    is_active: Optional[bool] = None
    role: Optional[str] = None
    password: Optional[str] = None


@router.get("/admin/users")
def list_users(admin: dict = Depends(require_admin)):
    conn = get_db_connection()
    try:
        cur = dict_cursor(conn)
        cur.execute("SELECT id, username, role, is_active, created_at FROM users ORDER BY id")
        return {"users": cur.fetchall()}
    finally:
        release_db_connection(conn)


@router.post("/admin/users")
def create_user(req: CreateUserRequest, admin: dict = Depends(require_admin)):
    if not req.username or not req.password:
        raise HTTPException(status_code=400, detail="用户名和密码不能为空")
    conn = get_db_connection()
    try:
        cur = dict_cursor(conn)
        cur.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)",
            (req.username, hash_password(req.password), req.role)
        )
        user_id = cur.lastrowid
        # Create default account for new user
        cur.execute(
            "INSERT INTO accounts (user_id, name, description) VALUES (%s, %s, %s)",
            (user_id, "默认账户", "系统默认账户")
        )
        conn.commit()
        return {"id": user_id, "username": req.username}
    except Exception as e:
        conn.rollback()
        if "unique" in str(e).lower():
            raise HTTPException(status_code=400, detail="用户名已存在")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        release_db_connection(conn)


@router.put("/admin/users/{user_id}")
def update_user(user_id: int, req: UpdateUserRequest, admin: dict = Depends(require_admin)):
    conn = get_db_connection()
    try:
        cur = dict_cursor(conn)
        if req.is_active is not None:
            cur.execute("UPDATE users SET is_active = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (req.is_active, user_id))
        if req.role is not None:
            cur.execute("UPDATE users SET role = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (req.role, user_id))
        if req.password:
            cur.execute("UPDATE users SET password_hash = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (hash_password(req.password), user_id))
        conn.commit()
        return {"status": "ok"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        release_db_connection(conn)


@router.delete("/admin/users/{user_id}")
def delete_user(user_id: int, admin: dict = Depends(require_admin)):
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="不能删除自己")
    conn = get_db_connection()
    try:
        cur = dict_cursor(conn)
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
        return {"status": "ok"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        release_db_connection(conn)
