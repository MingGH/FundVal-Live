import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from ..db import get_db_connection, release_db_connection, dict_cursor

logger = logging.getLogger(__name__)

def add_subscription(user_id: int, code: str, email: str, up: float, down: float,
                     enable_digest: bool = False, digest_time: str = "14:45", enable_volatility: bool = True):
    conn = get_db_connection()
    cur = dict_cursor(conn)
    cur.execute("""
        INSERT INTO subscriptions (user_id, code, email, threshold_up, threshold_down, enable_digest, digest_time, enable_volatility)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            threshold_up = VALUES(threshold_up),
            threshold_down = VALUES(threshold_down),
            enable_digest = VALUES(enable_digest),
            digest_time = VALUES(digest_time),
            enable_volatility = VALUES(enable_volatility)
    """, (user_id, code, email, up, down, enable_digest, digest_time, enable_volatility))
    conn.commit()
    release_db_connection(conn)
    logger.info(f"Subscription updated: {email} -> {code}")

def get_active_subscriptions(user_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """获取活跃订阅。如果指定 user_id 则只返回该用户的订阅。"""
    conn = get_db_connection()
    cur = dict_cursor(conn)
    if user_id is not None:
        cur.execute("SELECT * FROM subscriptions WHERE user_id = %s", (user_id,))
    else:
        cur.execute("SELECT * FROM subscriptions")
    rows = cur.fetchall()
    release_db_connection(conn)
    return rows

def get_subscriptions_grouped_by_user() -> Dict[int, List[Dict[str, Any]]]:
    """获取所有订阅，按 user_id 分组返回。用于 scheduler 按用户隔离处理。"""
    conn = get_db_connection()
    cur = dict_cursor(conn)
    cur.execute("SELECT * FROM subscriptions ORDER BY user_id")
    rows = cur.fetchall()
    release_db_connection(conn)

    grouped = {}
    for row in rows:
        uid = row["user_id"]
        if uid not in grouped:
            grouped[uid] = []
        grouped[uid].append(row)
    return grouped

def update_notification_time(sub_id: int):
    conn = get_db_connection()
    cur = dict_cursor(conn)
    cur.execute("UPDATE subscriptions SET last_notified_at = CURRENT_TIMESTAMP WHERE id = %s", (sub_id,))
    conn.commit()
    release_db_connection(conn)

def update_digest_time(sub_id: int):
    conn = get_db_connection()
    cur = dict_cursor(conn)
    cur.execute("UPDATE subscriptions SET last_digest_at = CURRENT_TIMESTAMP WHERE id = %s", (sub_id,))
    conn.commit()
    release_db_connection(conn)
