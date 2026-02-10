# -*- coding: utf-8 -*-
"""加仓/减仓：T+1 确认后用真实净值更新持仓，并写入操作记录。"""
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from ..db import get_db_connection, release_db_connection, dict_cursor
from .fund import get_nav_on_date
from .account import upsert_position, remove_position
from .trading_calendar import get_confirm_date, confirm_date_to_str

logger = logging.getLogger(__name__)


def _get_position(account_id: int, code: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cur = dict_cursor(conn)
    cur.execute("SELECT code, cost, shares FROM positions WHERE account_id = %s AND code = %s", (account_id, code))
    row = cur.fetchone()
    release_db_connection(conn)
    if not row:
        return None
    return {"code": row["code"], "cost": float(row["cost"]), "shares": float(row["shares"])}


def add_position_trade(account_id: int, code: str, amount_cny: float, trade_ts: Optional[datetime] = None) -> Dict[str, Any]:
    if amount_cny <= 0:
        return {"ok": False, "message": "加仓金额必须大于 0"}
    confirm_d = get_confirm_date(trade_ts)
    confirm_date_str = confirm_date_to_str(confirm_d)
    nav = get_nav_on_date(code, confirm_date_str)

    conn = get_db_connection()
    cur = dict_cursor(conn)

    if nav and nav > 0:
        shares_added = round(amount_cny / nav, 4)
        pos = _get_position(account_id, code)
        if pos:
            old_cost, old_shares = pos["cost"], pos["shares"]
            new_shares = old_shares + shares_added
            new_cost = round((old_cost * old_shares + nav * shares_added) / new_shares, 4)
        else:
            new_shares = shares_added
            new_cost = nav
        upsert_position(account_id, code, new_cost, new_shares)
        cur.execute(
            """INSERT INTO transactions (account_id, code, op_type, amount_cny, confirm_date, confirm_nav, shares_added, cost_after, applied_at)
            VALUES (%s, %s, 'add', %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)""",
            (account_id, code, amount_cny, confirm_date_str, nav, shares_added, new_cost),
        )
        conn.commit()
        release_db_connection(conn)
        return {"ok": True, "confirm_date": confirm_date_str, "confirm_nav": nav,
                "shares_added": shares_added, "cost_after": new_cost, "shares_after": new_shares}
    else:
        cur.execute(
            """INSERT INTO transactions (account_id, code, op_type, amount_cny, confirm_date)
            VALUES (%s, %s, 'add', %s, %s)""",
            (account_id, code, amount_cny, confirm_date_str),
        )
        conn.commit()
        release_db_connection(conn)
        return {"ok": True, "pending": True,
                "message": f"已记录加仓，确认日为 {confirm_date_str}，待净值公布后自动更新持仓",
                "confirm_date": confirm_date_str}


def reduce_position_trade(account_id: int, code: str, shares_redeemed: float, trade_ts: Optional[datetime] = None) -> Dict[str, Any]:
    if shares_redeemed <= 0:
        return {"ok": False, "message": "减仓份额必须大于 0"}
    pos = _get_position(account_id, code)
    if not pos or pos["shares"] <= 0:
        return {"ok": False, "message": "该基金无持仓或份额为 0"}
    if shares_redeemed > pos["shares"]:
        return {"ok": False, "message": f"减仓份额不能大于当前持仓 {pos['shares']}"}

    confirm_d = get_confirm_date(trade_ts)
    confirm_date_str = confirm_date_to_str(confirm_d)
    nav = get_nav_on_date(code, confirm_date_str)

    conn = get_db_connection()
    cur = dict_cursor(conn)

    if nav and nav > 0:
        amount_cny = round(shares_redeemed * nav, 2)
        new_shares = round(pos["shares"] - shares_redeemed, 4)
        new_cost = pos["cost"]
        if new_shares <= 0:
            remove_position(account_id, code)
            cost_after = 0.0
        else:
            upsert_position(account_id, code, new_cost, new_shares)
            cost_after = new_cost
        cur.execute(
            """INSERT INTO transactions (account_id, code, op_type, amount_cny, shares_redeemed, confirm_date, confirm_nav, cost_after, applied_at)
            VALUES (%s, %s, 'reduce', %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)""",
            (account_id, code, amount_cny, shares_redeemed, confirm_date_str, nav, cost_after),
        )
        conn.commit()
        release_db_connection(conn)
        return {"ok": True, "confirm_date": confirm_date_str, "confirm_nav": nav,
                "amount_cny": amount_cny, "shares_after": new_shares}
    else:
        cur.execute(
            """INSERT INTO transactions (account_id, code, op_type, shares_redeemed, confirm_date)
            VALUES (%s, %s, 'reduce', %s, %s)""",
            (account_id, code, shares_redeemed, confirm_date_str),
        )
        conn.commit()
        release_db_connection(conn)
        return {"ok": True, "pending": True,
                "message": f"已记录减仓，确认日为 {confirm_date_str}，待净值公布后自动更新持仓",
                "confirm_date": confirm_date_str}


def list_transactions(account_id: int = None, code: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cur = dict_cursor(conn)

    conditions = []
    params = []
    if account_id:
        conditions.append("account_id = %s")
        params.append(account_id)
    if code:
        conditions.append("code = %s")
        params.append(code)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params.append(limit)

    cur.execute(f"""
        SELECT id, code, op_type, amount_cny, shares_redeemed, confirm_date, confirm_nav,
               shares_added, cost_after, created_at, applied_at
        FROM transactions {where} ORDER BY id DESC LIMIT %s
    """, params)
    rows = cur.fetchall()
    release_db_connection(conn)

    out = []
    for r in rows:
        out.append({
            "id": r["id"], "code": r["code"], "op_type": r["op_type"],
            "amount_cny": r["amount_cny"], "shares_redeemed": r["shares_redeemed"],
            "confirm_date": r["confirm_date"], "confirm_nav": r["confirm_nav"],
            "shares_added": r["shares_added"], "cost_after": r["cost_after"],
            "created_at": str(r["created_at"]) if r["created_at"] else None,
            "applied_at": str(r["applied_at"]) if r["applied_at"] else None,
        })
    return out


def process_pending_transactions() -> int:
    """处理待确认流水：对 confirm_nav 为空的记录拉取确认日净值并更新持仓。"""
    conn = get_db_connection()
    cur = dict_cursor(conn)
    cur.execute(
        "SELECT id, account_id, code, op_type, amount_cny, shares_redeemed, confirm_date FROM transactions WHERE applied_at IS NULL AND confirm_nav IS NULL"
    )
    pending = cur.fetchall()
    release_db_connection(conn)

    applied = 0
    for row in pending:
        tid, account_id, code, op_type = row["id"], row["account_id"], row["code"], row["op_type"]
        amount_cny, shares_redeemed, confirm_date = row["amount_cny"], row["shares_redeemed"], row["confirm_date"]
        nav = get_nav_on_date(code, confirm_date) if confirm_date else None
        if not nav or nav <= 0:
            continue
        conn = get_db_connection()
        cur = dict_cursor(conn)
        if op_type == "add" and amount_cny:
            shares_added = round(amount_cny / nav, 4)
            pos = _get_position(account_id, code)
            if pos:
                new_shares = pos["shares"] + shares_added
                new_cost = round((pos["cost"] * pos["shares"] + nav * shares_added) / new_shares, 4)
            else:
                new_shares = shares_added
                new_cost = nav
            upsert_position(account_id, code, new_cost, new_shares)
            cur.execute(
                "UPDATE transactions SET confirm_nav = %s, shares_added = %s, cost_after = %s, applied_at = CURRENT_TIMESTAMP WHERE id = %s",
                (nav, shares_added, new_cost, tid),
            )
        elif op_type == "reduce" and shares_redeemed:
            pos = _get_position(account_id, code)
            if not pos:
                release_db_connection(conn)
                continue
            amount_cny = round(shares_redeemed * nav, 2)
            new_shares = round(pos["shares"] - shares_redeemed, 4)
            cost_after = pos["cost"] if new_shares > 0 else 0.0
            if new_shares <= 0:
                remove_position(account_id, code)
            else:
                upsert_position(account_id, code, pos["cost"], new_shares)
            cur.execute(
                "UPDATE transactions SET confirm_nav = %s, amount_cny = %s, cost_after = %s, applied_at = CURRENT_TIMESTAMP WHERE id = %s",
                (nav, amount_cny, cost_after, tid),
            )
        else:
            release_db_connection(conn)
            continue
        conn.commit()
        release_db_connection(conn)
        applied += 1
    return applied
