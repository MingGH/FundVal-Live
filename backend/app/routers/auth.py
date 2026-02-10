"""Auth router: login + current user info."""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from ..db import get_db_connection, release_db_connection, dict_cursor
from ..auth import verify_password, create_access_token, get_current_user

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/auth/login")
def login(req: LoginRequest):
    conn = get_db_connection()
    try:
        cur = dict_cursor(conn)
        cur.execute("SELECT id, username, password_hash, role, is_active FROM users WHERE username = %s", (req.username,))
        user = cur.fetchone()
        if not user or not verify_password(req.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        if not user["is_active"]:
            raise HTTPException(status_code=403, detail="账号已被禁用")
        token = create_access_token(user["id"], user["username"], user["role"])
        return {"token": token, "user": {"id": user["id"], "username": user["username"], "role": user["role"]}}
    finally:
        release_db_connection(conn)


@router.get("/auth/me")
def get_me(user: dict = Depends(get_current_user)):
    return {"user": user}


@router.post("/auth/change-password")
def change_password(data: dict, user: dict = Depends(get_current_user)):
    old_pw = data.get("old_password", "")
    new_pw = data.get("new_password", "")
    if not new_pw or len(new_pw) < 4:
        raise HTTPException(status_code=400, detail="新密码至少4位")
    conn = get_db_connection()
    try:
        cur = dict_cursor(conn)
        cur.execute("SELECT password_hash FROM users WHERE id = %s", (user["id"],))
        row = cur.fetchone()
        if not row or not verify_password(old_pw, row["password_hash"]):
            raise HTTPException(status_code=400, detail="原密码错误")
        from ..auth import hash_password
        cur.execute("UPDATE users SET password_hash = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                     (hash_password(new_pw), user["id"]))
        conn.commit()
        return {"message": "密码已修改"}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        release_db_connection(conn)
