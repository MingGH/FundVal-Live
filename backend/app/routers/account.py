from fastapi import APIRouter, HTTPException, Body, Query, Depends
from pydantic import BaseModel
from typing import Dict, Any, Optional, List

from ..services.account import get_all_positions, upsert_position, remove_position
from ..services.trade import add_position_trade, reduce_position_trade, list_transactions
from ..db import get_db_connection, release_db_connection, dict_cursor
from ..auth import get_current_user

router = APIRouter()

class AccountModel(BaseModel):
    name: str
    description: Optional[str] = ""

class PositionModel(BaseModel):
    code: str
    cost: float
    shares: float

class AddTradeModel(BaseModel):
    amount: float
    trade_time: Optional[str] = None

class ReduceTradeModel(BaseModel):
    shares: float
    trade_time: Optional[str] = None


def _verify_account_ownership(account_id: int, user_id: int):
    """Verify that the account belongs to the user."""
    conn = get_db_connection()
    cur = dict_cursor(conn)
    cur.execute("SELECT id FROM accounts WHERE id = %s AND user_id = %s", (account_id, user_id))
    row = cur.fetchone()
    release_db_connection(conn)
    if not row:
        raise HTTPException(status_code=403, detail="无权访问该账户")


@router.get("/accounts")
def list_accounts(user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cur = dict_cursor(conn)
    try:
        cur.execute("SELECT * FROM accounts WHERE user_id = %s ORDER BY id", (user["id"],))
        return {"accounts": cur.fetchall()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        release_db_connection(conn)

@router.post("/accounts")
def create_account(data: AccountModel, user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cur = dict_cursor(conn)
    try:
        cur.execute(
            "INSERT INTO accounts (user_id, name, description) VALUES (%s, %s, %s)",
            (user["id"], data.name, data.description)
        )
        account_id = cur.lastrowid
        conn.commit()
        return {"id": account_id, "name": data.name}
    except Exception as e:
        conn.rollback()
        if "unique" in str(e).lower():
            raise HTTPException(status_code=400, detail="账户名称已存在")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        release_db_connection(conn)

@router.put("/accounts/{account_id}")
def update_account(account_id: int, data: AccountModel, user: dict = Depends(get_current_user)):
    _verify_account_ownership(account_id, user["id"])
    conn = get_db_connection()
    cur = dict_cursor(conn)
    try:
        cur.execute(
            "UPDATE accounts SET name = %s, description = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s AND user_id = %s",
            (data.name, data.description, account_id, user["id"])
        )
        conn.commit()
        return {"status": "ok"}
    except Exception as e:
        conn.rollback()
        if "unique" in str(e).lower():
            raise HTTPException(status_code=400, detail="账户名称已存在")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        release_db_connection(conn)

@router.delete("/accounts/{account_id}")
def delete_account(account_id: int, user: dict = Depends(get_current_user)):
    _verify_account_ownership(account_id, user["id"])
    conn = get_db_connection()
    cur = dict_cursor(conn)
    try:
        # Check if it's the only account
        cur.execute("SELECT COUNT(*) as cnt FROM accounts WHERE user_id = %s", (user["id"],))
        if cur.fetchone()["cnt"] <= 1:
            raise HTTPException(status_code=400, detail="至少保留一个账户")

        cur.execute("SELECT COUNT(*) as cnt FROM positions WHERE account_id = %s", (account_id,))
        if cur.fetchone()["cnt"] > 0:
            raise HTTPException(status_code=400, detail="账户下有持仓，无法删除")

        cur.execute("DELETE FROM accounts WHERE id = %s AND user_id = %s", (account_id, user["id"]))
        conn.commit()
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        release_db_connection(conn)

@router.get("/account/positions")
def get_positions(account_id: int = Query(1), user: dict = Depends(get_current_user)):
    if account_id != 0:
        _verify_account_ownership(account_id, user["id"])
    try:
        return get_all_positions(account_id, user_id=user["id"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/account/positions/update-nav")
def update_positions_nav(account_id: int = Query(1), user: dict = Depends(get_current_user)):
    import time as _time
    from datetime import datetime
    from ..services.fund import get_fund_history

    if account_id != 0:
        _verify_account_ownership(account_id, user["id"])

    conn = get_db_connection()
    cur = dict_cursor(conn)
    try:
        if account_id == 0:
            cur.execute("""
                SELECT DISTINCT p.code FROM positions p
                JOIN accounts a ON p.account_id = a.id
                WHERE a.user_id = %s AND p.shares > 0
            """, (user["id"],))
        else:
            cur.execute("SELECT DISTINCT code FROM positions WHERE account_id = %s AND shares > 0", (account_id,))
        codes = [row["code"] for row in cur.fetchall()]
    finally:
        release_db_connection(conn)

    if not codes:
        return {"ok": True, "message": "无持仓基金", "updated": 0, "pending": 0, "failed": 0}

    today = datetime.now().strftime("%Y-%m-%d")
    updated = 0
    pending = 0
    failed = []

    for code in codes:
        try:
            history = get_fund_history(code, limit=5)
            if history:
                if history[-1]["date"] == today:
                    updated += 1
                else:
                    pending += 1
            else:
                failed.append({"code": code, "error": "无历史数据"})
            _time.sleep(0.3)
        except Exception as e:
            failed.append({"code": code, "error": str(e)})

    msg_parts = []
    if updated > 0: msg_parts.append(f"{updated} 个已更新当日净值")
    if pending > 0: msg_parts.append(f"{pending} 个净值未公布")
    if failed: msg_parts.append(f"{len(failed)} 个拉取失败")

    return {
        "ok": True, "message": "、".join(msg_parts) if msg_parts else "无数据",
        "updated": updated, "pending": pending,
        "failed_count": len(failed), "total": len(codes),
        "failed": failed if failed else None
    }

@router.post("/account/positions")
def update_position(data: PositionModel, account_id: int = Query(1), user: dict = Depends(get_current_user)):
    _verify_account_ownership(account_id, user["id"])
    try:
        upsert_position(account_id, data.code, data.cost, data.shares)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/account/positions/{code}")
def delete_position(code: str, account_id: int = Query(1), user: dict = Depends(get_current_user)):
    _verify_account_ownership(account_id, user["id"])
    try:
        remove_position(account_id, code)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/account/positions/{code}/add")
def add_trade(code: str, data: AddTradeModel, account_id: int = Query(1), user: dict = Depends(get_current_user)):
    _verify_account_ownership(account_id, user["id"])
    from datetime import datetime
    trade_ts = None
    if data.trade_time:
        try:
            trade_ts = datetime.fromisoformat(data.trade_time.replace("Z", "+00:00"))
            if trade_ts.tzinfo:
                trade_ts = trade_ts.replace(tzinfo=None)
        except: pass
    try:
        result = add_position_trade(account_id, code, data.amount, trade_ts)
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result.get("message", "加仓失败"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/account/positions/{code}/reduce")
def reduce_trade(code: str, data: ReduceTradeModel, account_id: int = Query(1), user: dict = Depends(get_current_user)):
    _verify_account_ownership(account_id, user["id"])
    from datetime import datetime
    trade_ts = None
    if data.trade_time:
        try:
            trade_ts = datetime.fromisoformat(data.trade_time.replace("Z", "+00:00"))
            if trade_ts.tzinfo:
                trade_ts = trade_ts.replace(tzinfo=None)
        except: pass
    try:
        result = reduce_position_trade(account_id, code, data.shares, trade_ts)
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result.get("message", "减仓失败"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/account/transactions")
def get_transactions(account_id: int = Query(1), code: Optional[str] = Query(None),
                     limit: int = Query(100, le=500), user: dict = Depends(get_current_user)):
    if account_id:
        _verify_account_ownership(account_id, user["id"])
    try:
        return {"transactions": list_transactions(account_id, code, limit)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
