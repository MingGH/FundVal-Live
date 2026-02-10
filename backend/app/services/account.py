from typing import List, Dict, Any
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..db import get_db_connection, release_db_connection, dict_cursor
from .fund import get_combined_valuation, get_fund_type

logger = logging.getLogger(__name__)

def get_all_positions(account_id: int = 1, user_id: int = None) -> Dict[str, Any]:
    """
    Fetch all positions for a specific account, get real-time valuations in parallel,
    and compute portfolio statistics.

    Special case: account_id = 0 returns aggregated data from all accounts for the user.
    """
    conn = get_db_connection()
    cur = dict_cursor(conn)

    if account_id == 0:
        if user_id:
            cur.execute("""
                SELECT p.* FROM positions p
                JOIN accounts a ON p.account_id = a.id
                WHERE a.user_id = %s AND p.shares > 0
            """, (user_id,))
        else:
            cur.execute("SELECT * FROM positions WHERE shares > 0")
    else:
        cur.execute("SELECT * FROM positions WHERE account_id = %s AND shares > 0", (account_id,))

    rows = cur.fetchall()
    release_db_connection(conn)

    positions = []
    total_market_value = 0.0
    total_cost = 0.0
    total_day_income = 0.0

    # For account_id = 0, merge positions with same code
    if account_id == 0:
        code_positions = {}
        for row in rows:
            code = row["code"]
            if code not in code_positions:
                code_positions[code] = {"cost": 0.0, "shares": 0.0, "total_cost_basis": 0.0}
            shares = float(row["shares"])
            cost = float(row["cost"])
            code_positions[code]["shares"] += shares
            code_positions[code]["total_cost_basis"] += shares * cost

        position_map = {}
        for code, data in code_positions.items():
            if data["shares"] > 0:
                weighted_avg_cost = data["total_cost_basis"] / data["shares"]
                position_map[code] = {"code": code, "cost": weighted_avg_cost, "shares": data["shares"]}
    else:
        position_map = {row["code"]: row for row in rows}

    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_code = {
            executor.submit(get_combined_valuation, code): code
            for code in position_map.keys()
        }

        for future in as_completed(future_to_code):
            code = future_to_code[future]
            row = position_map[code]

            try:
                data = future.result() or {}
                name = data.get("name")
                fund_type = None

                if not name:
                    conn_temp = get_db_connection()
                    cur_temp = dict_cursor(conn_temp)
                    cur_temp.execute("SELECT name, type FROM funds WHERE code = %s", (code,))
                    db_row = cur_temp.fetchone()
                    release_db_connection(conn_temp)
                    if db_row:
                        name = db_row["name"]
                        fund_type = db_row["type"]
                    else:
                        name = code

                if not fund_type:
                    fund_type = get_fund_type(code, name)

                from datetime import datetime
                today_str = datetime.now().strftime("%Y-%m-%d")
                conn_temp = get_db_connection()
                cur_temp = dict_cursor(conn_temp)
                cur_temp.execute(
                    "SELECT date FROM fund_history WHERE code = %s ORDER BY date DESC LIMIT 1", (code,)
                )
                latest_nav_row = cur_temp.fetchone()
                release_db_connection(conn_temp)
                nav_updated_today = latest_nav_row and latest_nav_row["date"] == today_str

                nav = float(data.get("nav", 0.0))
                estimate = float(data.get("estimate", 0.0))
                current_price = estimate if estimate > 0 else nav

                cost = float(row["cost"])
                shares = float(row["shares"])

                nav_market_value = nav * shares
                cost_basis = cost * shares

                est_rate = data.get("est_rate", data.get("estRate", 0.0))

                is_est_valid = False
                if estimate > 0 and nav > 0:
                    if abs(est_rate) < 10.0 or "ETF" in (name or "") or "联接" in (name or ""):
                        is_est_valid = True

                accumulated_income = nav_market_value - cost_basis
                accumulated_return_rate = (accumulated_income / cost_basis * 100) if cost_basis > 0 else 0.0

                if is_est_valid:
                    day_income = (estimate - nav) * shares
                    est_market_value = estimate * shares
                else:
                    day_income = 0.0
                    est_market_value = nav_market_value

                total_income = accumulated_income + day_income
                total_return_rate = (total_income / cost_basis * 100) if cost_basis > 0 else 0.0

                positions.append({
                    "code": code, "name": name, "type": fund_type,
                    "cost": cost, "shares": shares,
                    "nav": nav, "nav_date": data.get("navDate", "--"),
                    "nav_updated_today": nav_updated_today,
                    "estimate": estimate, "est_rate": est_rate, "is_est_valid": is_est_valid,
                    "cost_basis": round(cost_basis, 2),
                    "nav_market_value": round(nav_market_value, 2),
                    "est_market_value": round(est_market_value, 2),
                    "accumulated_income": round(accumulated_income, 2),
                    "accumulated_return_rate": round(accumulated_return_rate, 2),
                    "day_income": round(day_income, 2),
                    "total_income": round(total_income, 2),
                    "total_return_rate": round(total_return_rate, 2),
                    "update_time": data.get("time", "--")
                })

                total_market_value += est_market_value
                total_day_income += day_income
                total_cost += cost_basis

            except Exception as e:
                logger.error(f"Error processing position {code}: {e}")
                positions.append({
                    "code": code, "name": "Error",
                    "cost": float(row["cost"]), "shares": float(row["shares"]),
                    "nav": 0.0, "estimate": 0.0, "est_market_value": 0.0,
                    "day_income": 0.0, "total_income": 0.0, "total_return_rate": 0.0,
                    "accumulated_income": 0.0, "est_rate": 0.0, "is_est_valid": False,
                    "update_time": "--"
                })

    total_income = total_market_value - total_cost
    total_return_rate = (total_income / total_cost * 100) if total_cost > 0 else 0.0

    return {
        "summary": {
            "total_market_value": round(total_market_value, 2),
            "total_cost": round(total_cost, 2),
            "total_day_income": round(total_day_income, 2),
            "total_income": round(total_income, 2),
            "total_return_rate": round(total_return_rate, 2)
        },
        "positions": sorted(positions, key=lambda x: x.get("est_market_value", 0), reverse=True)
    }

def upsert_position(account_id: int, code: str, cost: float, shares: float):
    conn = get_db_connection()
    cur = dict_cursor(conn)
    cur.execute("""
        INSERT INTO positions (account_id, code, cost, shares)
        VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            cost = VALUES(cost),
            shares = VALUES(shares),
            updated_at = CURRENT_TIMESTAMP
    """, (account_id, code, cost, shares))
    conn.commit()
    release_db_connection(conn)

def remove_position(account_id: int, code: str):
    conn = get_db_connection()
    cur = dict_cursor(conn)
    cur.execute("DELETE FROM positions WHERE account_id = %s AND code = %s", (account_id, code))
    conn.commit()
    release_db_connection(conn)
