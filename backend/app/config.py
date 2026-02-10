import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# 判断是否为打包后的应用
if getattr(sys, 'frozen', False):
    BASE_DIR = Path.home() / '.fundval-live'
    BASE_DIR.mkdir(parents=True, exist_ok=True)
else:
    BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env from project root
if not getattr(sys, 'frozen', False):
    load_dotenv(BASE_DIR.parent / ".env")


def _load_settings_from_db():
    """从数据库读取配置，解密加密字段"""
    try:
        from .db import get_db_connection, release_db_connection, dict_cursor
        from .crypto import decrypt_value

        conn = get_db_connection()
        cur = dict_cursor(conn)
        cur.execute("SELECT `key`, value, encrypted FROM settings")
        rows = cur.fetchall()
        release_db_connection(conn)

        settings = {}
        for row in rows:
            key, value, encrypted = row["key"], row["value"], row["encrypted"]
            if encrypted and value:
                value = decrypt_value(value)
            settings[key] = value
        return settings
    except Exception:
        return {}


def _get_setting(key: str, default: str = "") -> str:
    """获取配置，优先级：环境变量 > 数据库 > 默认值"""
    env_val = os.getenv(key)
    if env_val:
        return env_val
    db_settings = _load_settings_from_db()
    if key in db_settings and db_settings[key]:
        return db_settings[key]
    return default


class Config:
    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", "mysql://funduser:fundpass@localhost:3306/fundval")

    # Data Sources
    DEFAULT_DATA_SOURCE = "eastmoney"

    # External APIs (Eastmoney)
    EASTMONEY_API_URL = "http://fundgz.1234567.com.cn/js/{code}.js"
    EASTMONEY_DETAILED_API_URL = "http://fund.eastmoney.com/pingzhongdata/{code}.js"
    EASTMONEY_ALL_FUNDS_API_URL = "http://fund.eastmoney.com/js/fundcode_search.js"

    # Update Intervals
    FUND_LIST_UPDATE_INTERVAL = 86400  # 24 hours
    STOCK_SPOT_CACHE_DURATION = 60     # 1 minute

    # AI Configuration - 延迟读取，避免模块导入时连接数据库
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
    AI_MODEL_NAME = os.getenv("AI_MODEL_NAME", "gpt-3.5-turbo")

    # Email / Subscription Configuration
    SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    EMAIL_FROM = os.getenv("EMAIL_FROM", "noreply@fundval.live")

    _initialized = False

    @classmethod
    def _ensure_loaded(cls):
        """首次访问时从数据库加载配置"""
        if cls._initialized:
            return
        cls._initialized = True
        cls.reload()

    @classmethod
    def reload(cls):
        """重新加载配置（在设置更新后调用）"""
        cls.OPENAI_API_KEY = _get_setting("OPENAI_API_KEY", "")
        cls.OPENAI_API_BASE = _get_setting("OPENAI_API_BASE", "https://api.openai.com/v1")
        cls.AI_MODEL_NAME = _get_setting("AI_MODEL_NAME", "gpt-3.5-turbo")
        cls.SMTP_HOST = _get_setting("SMTP_HOST", "smtp.gmail.com")
        cls.SMTP_PORT = int(_get_setting("SMTP_PORT", "587"))
        cls.SMTP_USER = _get_setting("SMTP_USER", "")
        cls.SMTP_PASSWORD = _get_setting("SMTP_PASSWORD", "")
        cls.EMAIL_FROM = _get_setting("EMAIL_FROM", "noreply@fundval.live")
