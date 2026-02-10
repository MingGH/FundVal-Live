import logging
import re
from fastapi import APIRouter, HTTPException, Body, Depends
from ..db import get_db_connection, release_db_connection, dict_cursor
from ..crypto import encrypt_value, decrypt_value
from ..config import Config
from ..auth import get_current_user, require_admin

logger = logging.getLogger(__name__)
router = APIRouter()

ENCRYPTED_FIELDS = {"OPENAI_API_KEY", "SMTP_PASSWORD"}

def validate_email(email: str) -> bool:
    return re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email) is not None

def validate_url(url: str) -> bool:
    return re.match(r'^https?://[^\s]+$', url) is not None

def validate_port(port: str) -> bool:
    try:
        return 1 <= int(port) <= 65535
    except:
        return False

# ── Global settings (admin only) ──

@router.get("/settings")
def get_settings(admin: dict = Depends(require_admin)):
    conn = get_db_connection()
    try:
        cur = dict_cursor(conn)
        cur.execute("SELECT `key`, value, encrypted FROM settings")
        rows = cur.fetchall()
        settings = {}
        for row in rows:
            key, value, encrypted = row["key"], row["value"], row["encrypted"]
            settings[key] = "***" if encrypted and value else value
        if not settings:
            settings = {
                "OPENAI_API_KEY": "***" if Config.OPENAI_API_KEY else "",
                "OPENAI_API_BASE": Config.OPENAI_API_BASE,
                "AI_MODEL_NAME": Config.AI_MODEL_NAME,
                "SMTP_HOST": Config.SMTP_HOST,
                "SMTP_PORT": str(Config.SMTP_PORT),
                "SMTP_USER": Config.SMTP_USER,
                "SMTP_PASSWORD": "***" if Config.SMTP_PASSWORD else "",
                "EMAIL_FROM": Config.EMAIL_FROM,
            }
        return {"settings": settings}
    except Exception as e:
        logger.error(f"Failed to get settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        release_db_connection(conn)

@router.post("/settings")
def update_settings(data: dict = Body(...), admin: dict = Depends(require_admin)):
    conn = get_db_connection()
    try:
        settings = data.get("settings", {})
        errors = {}
        if "SMTP_PORT" in settings and not validate_port(settings["SMTP_PORT"]):
            errors["SMTP_PORT"] = "端口必须在 1-65535 之间"
        if "SMTP_USER" in settings and settings["SMTP_USER"] and not validate_email(settings["SMTP_USER"]):
            errors["SMTP_USER"] = "邮箱格式不正确"
        if "EMAIL_FROM" in settings and settings["EMAIL_FROM"] and not validate_email(settings["EMAIL_FROM"]):
            errors["EMAIL_FROM"] = "邮箱格式不正确"
        if "OPENAI_API_BASE" in settings and settings["OPENAI_API_BASE"] and not validate_url(settings["OPENAI_API_BASE"]):
            errors["OPENAI_API_BASE"] = "URL 格式不正确"
        if errors:
            raise HTTPException(status_code=400, detail={"errors": errors})

        cur = dict_cursor(conn)
        for key, value in settings.items():
            if value == "***":
                continue
            encrypted = key in ENCRYPTED_FIELDS
            if encrypted and value:
                value = encrypt_value(value)
            cur.execute("""
                INSERT INTO settings (`key`, value, encrypted, updated_at)
                VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                ON DUPLICATE KEY UPDATE value = VALUES(value), encrypted = VALUES(encrypted), updated_at = CURRENT_TIMESTAMP
            """, (key, value, encrypted))
        conn.commit()
        Config.reload()
        return {"message": "设置已保存"}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to update settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        release_db_connection(conn)

# ── User preferences (per-user) ──

@router.get("/preferences")
def get_preferences(user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    try:
        cur = dict_cursor(conn)
        cur.execute("SELECT `key`, value FROM user_preferences WHERE user_id = %s", (user["user_id"],))
        prefs = {row["key"]: row["value"] for row in cur.fetchall()}
        return {
            "watchlist": prefs.get("watchlist", "[]"),
            "currentAccount": int(prefs.get("current_account", "1")),
            "sortOption": prefs.get("sort_option")
        }
    except Exception as e:
        logger.error(f"Failed to get preferences: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        release_db_connection(conn)

@router.post("/preferences")
def update_preferences(data: dict = Body(...), user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    try:
        cur = dict_cursor(conn)
        mapping = {"watchlist": "watchlist", "currentAccount": "current_account", "sortOption": "sort_option"}
        for frontend_key, db_key in mapping.items():
            if frontend_key in data:
                cur.execute("""
                    INSERT INTO user_preferences (user_id, `key`, value, updated_at)
                    VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                    ON DUPLICATE KEY UPDATE value = VALUES(value), updated_at = CURRENT_TIMESTAMP
                """, (user["user_id"], db_key, str(data[frontend_key])))
        conn.commit()
        return {"message": "偏好已保存"}
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to update preferences: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        release_db_connection(conn)
