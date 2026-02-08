import logging
from fastapi import APIRouter, HTTPException, Query, Body
from ..services.fund import search_funds, get_fund_intraday, get_fund_history
from ..config import Config

from ..services.subscription import add_subscription

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/categories")
def get_fund_categories():
    """
    Get all unique fund categories from database.
    Returns major categories (simplified) sorted by frequency.
    """
    from ..db import get_db_connection

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get all unique types with their counts
    cursor.execute("""
        SELECT type, COUNT(*) as count
        FROM funds
        WHERE type IS NOT NULL AND type != ''
        GROUP BY type
        ORDER BY count DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    # Map to major categories
    major_categories = {}
    for row in rows:
        fund_type = row["type"]
        count = row["count"]

        # Simplify to major categories
        if "股票" in fund_type or "偏股" in fund_type:
            major = "股票型"
        elif "混合" in fund_type:
            major = "混合型"
        elif "债" in fund_type:
            major = "债券型"
        elif "指数" in fund_type:
            major = "指数型"
        elif "QDII" in fund_type:
            major = "QDII"
        elif "货币" in fund_type:
            major = "货币型"
        elif "FOF" in fund_type:
            major = "FOF"
        elif "REITs" in fund_type or "Reits" in fund_type:
            major = "REITs"
        else:
            major = "其他"

        major_categories[major] = major_categories.get(major, 0) + count

    # Sort by count
    categories = sorted(major_categories.keys(), key=lambda x: major_categories[x], reverse=True)

    return {"categories": categories}

@router.get("/search")
def search(q: str = Query(..., min_length=1)):
    try:
        return search_funds(q)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/fund/{fund_id}")
def fund_detail(fund_id: str):
    try:
        return get_fund_intraday(fund_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/fund/{fund_id}/history")
def fund_history(fund_id: str, limit: int = 30, account_id: int = Query(None)):
    """
    Get historical NAV data for charts.
    Optionally include transaction markers if account_id is provided.
    """
    try:
        history = get_fund_history(fund_id, limit=limit)

        # If account_id is provided, fetch transactions for this fund
        transactions = []
        if account_id:
            from ..db import get_db_connection
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT confirm_date, op_type, confirm_nav, amount_cny, shares_redeemed
                FROM transactions
                WHERE code = ? AND account_id = ? AND confirm_nav IS NOT NULL
                ORDER BY confirm_date ASC
            """, (fund_id, account_id))

            for row in cursor.fetchall():
                # Map op_type: "add" -> "buy", "reduce" -> "sell"
                op_type = row["op_type"]
                transaction_type = "buy" if op_type == "add" else "sell"

                transactions.append({
                    "date": row["confirm_date"],
                    "type": transaction_type,
                    "nav": float(row["confirm_nav"]),
                    "amount": float(row["amount_cny"]) if row["amount_cny"] else None,
                    "shares": float(row["shares_redeemed"]) if row["shares_redeemed"] else None
                })
            conn.close()

        return {
            "history": history,
            "transactions": transactions
        }
    except Exception as e:
        # Don't break UI if history fails
        print(f"History error: {e}")
        return {"history": [], "transactions": []}

@router.get("/fund/{fund_id}/intraday")
def fund_intraday(fund_id: str, date: str = None):
    """
    Get intraday valuation snapshots for charts.
    Returns today's data by default.
    """
    from datetime import datetime
    from ..db import get_db_connection

    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    conn = get_db_connection()
    cursor = conn.cursor()

    # 0. Check if fund exists
    cursor.execute("SELECT 1 FROM funds WHERE code = ?", (fund_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Fund not found")

    # 1. Get previous day NAV
    cursor.execute("""
        SELECT nav FROM fund_history
        WHERE code = ? AND date < ?
        ORDER BY date DESC
        LIMIT 1
    """, (fund_id, date))
    row = cursor.fetchone()
    prev_nav = float(row["nav"]) if row else None

    # 2. Get intraday snapshots
    cursor.execute("""
        SELECT time, estimate FROM fund_intraday_snapshots
        WHERE fund_code = ? AND date = ?
        ORDER BY time ASC
    """, (fund_id, date))
    snapshots = [{"time": r["time"], "estimate": float(r["estimate"])} for r in cursor.fetchall()]

    conn.close()

    return {
        "date": date,
        "prevNav": prev_nav,
        "snapshots": snapshots,
        "lastCollectedAt": snapshots[-1]["time"] if snapshots else None
    }

@router.post("/fund/{fund_id}/subscribe")
def subscribe_fund(fund_id: str, data: dict = Body(...)):
    """
    Subscribe to fund alerts.
    """
    email = data.get("email")
    up = data.get("thresholdUp")
    down = data.get("thresholdDown")
    enable_digest = data.get("enableDailyDigest", False)
    digest_time = data.get("digestTime", "14:45")
    enable_volatility = data.get("enableVolatility", True)
    
    if not email:
        raise HTTPException(status_code=400, detail="Email required")
    
    try:
        add_subscription(
            fund_id, 
            email, 
            float(up or 0), 
            float(down or 0),
            enable_digest=enable_digest,
            digest_time=digest_time,
            enable_volatility=enable_volatility
        )
        return {"status": "ok", "message": "Subscription active"}
    except Exception as e:
        logger.error(f"Subscription failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to save subscription")
