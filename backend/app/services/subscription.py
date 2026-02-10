import logging
from datetime import datetime
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

def get_active_subscriptions():
    conn = get_db_connection()
    cur = dict_cursor(conn)
    cur.execute("SELECT * FROM subscriptions")
    rows = cur.fetchall()
    release_db_connection(conn)
    return rows

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
