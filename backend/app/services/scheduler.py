import logging
import threading
import time
from datetime import datetime, timedelta, timezone
import akshare as ak
import pandas as pd
from ..db import get_db_connection, release_db_connection, dict_cursor
from ..config import Config
from ..services.fund import get_combined_valuation
from ..services.subscription import get_active_subscriptions, update_notification_time
from ..services.email import send_email
from ..services.trade import process_pending_transactions

logger = logging.getLogger(__name__)

CST = timezone(timedelta(hours=8))

def fetch_and_update_funds():
    logger.info("Starting fund list update...")
    try:
        df = ak.fund_name_em()
        if df is None or df.empty:
            logger.warning("Fetched empty fund list from AkShare.")
            return

        df = df.rename(columns={"基金代码": "code", "基金简称": "name", "基金类型": "type"})
        data_to_insert = df[["code", "name", "type"]].to_dict(orient="records")

        conn = get_db_connection()
        cur = dict_cursor(conn)

        for row in data_to_insert:
            cur.execute("""
                INSERT INTO funds (code, name, type, updated_at)
                VALUES (%(code)s, %(name)s, %(type)s, CURRENT_TIMESTAMP)
                ON DUPLICATE KEY UPDATE
                    name = VALUES(name), type = VALUES(type), updated_at = CURRENT_TIMESTAMP
            """, row)

        conn.commit()
        release_db_connection(conn)
        logger.info(f"Fund list updated. Total funds: {len(data_to_insert)}")
    except Exception as e:
        logger.error(f"Failed to update fund list: {e}")

from ..services.subscription import get_active_subscriptions, update_notification_time, update_digest_time
from ..services.trading_calendar import is_trading_day

def collect_intraday_snapshots():
    now_cst = datetime.now(CST)
    today = now_cst.date()

    if not is_trading_day(today):
        return

    current_time = now_cst.strftime("%H:%M")
    if current_time < "09:35" or current_time > "15:05":
        return

    conn = get_db_connection()
    cur = dict_cursor(conn)
    cur.execute("SELECT DISTINCT code FROM positions WHERE shares > 0")
    codes = [row["code"] for row in cur.fetchall()]

    if not codes:
        release_db_connection(conn)
        return

    date_str = today.strftime("%Y-%m-%d")
    time_str = now_cst.strftime("%H:%M")

    collected = 0
    for code in codes:
        try:
            data = get_combined_valuation(code)
            if data and data.get("estimate"):
                cur.execute("""
                    INSERT INTO fund_intraday_snapshots (fund_code, date, time, estimate)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE fund_code = fund_code
                """, (code, date_str, time_str, float(data["estimate"])))
                collected += 1
            time.sleep(0.2)
        except Exception as e:
            logger.error(f"Intraday collect failed for {code}: {e}")

    conn.commit()
    release_db_connection(conn)

    if collected > 0:
        logger.info(f"Collected {collected} intraday snapshots at {time_str}")

def cleanup_old_intraday_data():
    now_cst = datetime.now(CST)
    cutoff = (now_cst - timedelta(days=30)).strftime("%Y-%m-%d")

    conn = get_db_connection()
    cur = dict_cursor(conn)
    cur.execute("DELETE FROM fund_intraday_snapshots WHERE date < %s", (cutoff,))
    deleted = cur.rowcount
    conn.commit()
    release_db_connection(conn)

    if deleted > 0:
        logger.info(f"Cleaned up {deleted} old intraday records (before {cutoff})")

def update_holdings_nav():
    from .fund import get_fund_history
    from .trading_calendar import is_trading_day

    now_cst = datetime.now(CST)
    today = now_cst.date()
    today_str = today.strftime("%Y-%m-%d")

    if not is_trading_day(today):
        return
    if now_cst.hour < 16:
        return

    conn = get_db_connection()
    cur = dict_cursor(conn)
    cur.execute("SELECT DISTINCT code FROM positions WHERE shares > 0")
    codes = [row["code"] for row in cur.fetchall()]
    release_db_connection(conn)

    if not codes:
        return

    updated = 0
    pending = 0
    for code in codes:
        try:
            history = get_fund_history(code, limit=5)
            if history:
                latest_date = history[-1]["date"]
                if latest_date == today_str:
                    updated += 1
                else:
                    pending += 1
            time.sleep(0.3)
        except Exception as e:
            logger.error(f"Failed to update NAV for {code}: {e}")

    if updated > 0 or pending > 0:
        logger.info(f"NAV update: {updated} updated, {pending} pending (total {len(codes)})")

def check_subscriptions():
    logger.info("Checking subscriptions...")
    subs = get_active_subscriptions()
    if not subs:
        return

    now_cst = datetime.now(CST)
    today_str = now_cst.strftime("%Y-%m-%d")
    current_time_str = now_cst.strftime("%H:%M")

    valuations = {}

    for sub in subs:
        code = sub["code"]
        sub_id = sub["id"]
        email = sub["email"]

        if code not in valuations:
            valuations[code] = get_combined_valuation(code)

        data = valuations[code]
        if not data: continue

        est_rate = data.get("estRate", 0.0)
        fund_name = data.get("name", code)

        if sub["enable_volatility"]:
            last_notified = str(sub["last_notified_at"]) if sub["last_notified_at"] else None
            if not (last_notified and last_notified.startswith(today_str)):
                triggered = False
                reason = ""
                if sub["threshold_up"] and sub["threshold_up"] > 0 and est_rate >= sub["threshold_up"]:
                    triggered = True
                    reason = f"上涨已达到 {est_rate}% (阈值: {sub['threshold_up']}%)"
                elif sub["threshold_down"] and sub["threshold_down"] < 0 and est_rate <= sub["threshold_down"]:
                    triggered = True
                    reason = f"下跌已达到 {est_rate}% (阈值: {sub['threshold_down']}%)"

                if triggered:
                    subject = f"【异动提醒】{fund_name} ({code}) 预估 {est_rate}%"
                    content = f"""<h3>基金异动提醒</h3>
                    <p>基金: {fund_name} ({code})</p>
                    <p>当前预估涨跌幅: <b>{est_rate}%</b></p>
                    <p>触发原因: {reason}</p>
                    <p>估值时间: {data.get('time')}</p>
                    <hr/><p>此邮件由 FundVal Live 自动发送。</p>"""
                    if send_email(email, subject, content, is_html=True):
                        update_notification_time(sub_id)

        if sub["enable_digest"]:
            last_digest = str(sub["last_digest_at"]) if sub["last_digest_at"] else None
            if not (last_digest and last_digest.startswith(today_str)):
                if current_time_str >= sub["digest_time"]:
                    subject = f"【每日总结】{fund_name} ({code}) 今日估值汇总"
                    content = f"""<h3>每日基金总结</h3>
                    <p>基金: {fund_name} ({code})</p>
                    <p>今日收盘/最新估值: {data.get('estimate', 'N/A')}</p>
                    <p>今日涨跌幅: <b>{est_rate}%</b></p>
                    <p>总结时间: {now_cst.strftime('%Y-%m-%d %H:%M:%S')}</p>
                    <hr/><p>祝您投资愉快！</p>"""
                    if send_email(email, subject, content, is_html=True):
                        update_digest_time(sub_id)

def start_scheduler():
    def _run():
        conn = get_db_connection()
        cur = dict_cursor(conn)
        cur.execute("SELECT count(*) as cnt FROM funds")
        count = cur.fetchone()["cnt"]
        release_db_connection(conn)

        if count == 0:
            logger.info("DB is empty. Performing initial fetch.")
            fetch_and_update_funds()

        last_cleanup_date = None
        last_nav_update_hour = None

        while True:
            try:
                now_cst = datetime.now(CST)
                today_str = now_cst.strftime("%Y-%m-%d")

                conn = get_db_connection()
                cur = dict_cursor(conn)
                cur.execute("SELECT value FROM settings WHERE `key` = 'INTRADAY_COLLECT_INTERVAL'")
                row = cur.fetchone()
                interval_minutes = int(row["value"]) if row and row["value"] else 5
                release_db_connection(conn)

                check_subscriptions()
                collect_intraday_snapshots()

                n = process_pending_transactions()
                if n:
                    logger.info(f"Applied {n} pending add/reduce transactions.")

                if last_cleanup_date != today_str and now_cst.hour == 0:
                    cleanup_old_intraday_data()
                    last_cleanup_date = today_str

                if 16 <= now_cst.hour <= 23 and last_nav_update_hour != now_cst.hour:
                    update_holdings_nav()
                    last_nav_update_hour = now_cst.hour

            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")

            time.sleep(interval_minutes * 60)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
