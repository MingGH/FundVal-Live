import datetime
import logging
from typing import List, Dict, Any, Optional
from ..db import get_db_connection, release_db_connection, dict_cursor

logger = logging.getLogger(__name__)

IMPORT_ORDER = ["settings", "ai_prompts", "accounts", "positions", "transactions", "subscriptions"]
SENSITIVE_MASK = "***"


def export_data(modules: List[str], user_id: int = None) -> Dict[str, Any]:
    if not modules:
        raise ValueError("No modules selected for export")

    result = {
        "version": "1.0",
        "exported_at": datetime.datetime.utcnow().isoformat() + "Z",
        "metadata": {},
        "modules": {}
    }

    for module in modules:
        if module == "settings":
            result["modules"]["settings"] = _export_settings()
        elif module == "ai_prompts":
            result["modules"]["ai_prompts"] = _export_ai_prompts(user_id)
        elif module == "accounts":
            result["modules"]["accounts"] = _export_accounts(user_id)
        elif module == "positions":
            result["modules"]["positions"] = _export_positions(user_id)
        elif module == "transactions":
            result["modules"]["transactions"] = _export_transactions(user_id)
        elif module == "subscriptions":
            result["modules"]["subscriptions"] = _export_subscriptions(user_id)

        if module in result["modules"]:
            result["metadata"][f"total_{module}"] = len(result["modules"][module])

    return result


def import_data(data: Dict[str, Any], modules: List[str], mode: str, user_id: int = None) -> Dict[str, Any]:
    if not modules:
        raise ValueError("No modules selected for import")
    if "version" not in data:
        raise ValueError("Missing version field in import data")

    result = {"success": True, "total_records": 0, "imported": 0, "skipped": 0, "failed": 0, "deleted": 0, "details": {}}

    conn = get_db_connection()
    cur = dict_cursor(conn)
    try:
        ordered_modules = [m for m in IMPORT_ORDER if m in modules]
        for module in ordered_modules:
            if module not in data.get("modules", {}):
                continue
            module_data = data["modules"][module]
            if not module_data:
                continue

            if module == "settings":
                module_result = _import_settings(cur, module_data, mode)
            elif module == "ai_prompts":
                module_result = _import_ai_prompts(cur, module_data, mode, user_id)
            elif module == "accounts":
                module_result = _import_accounts(cur, module_data, mode, user_id)
            elif module == "positions":
                module_result = _import_positions(cur, module_data, mode, user_id)
            elif module == "transactions":
                module_result = _import_transactions(cur, module_data, mode, user_id)
            elif module == "subscriptions":
                module_result = _import_subscriptions(cur, module_data, mode, user_id)
            else:
                continue

            result["details"][module] = module_result
            result["total_records"] += module_result.get("total", 0)
            result["imported"] += module_result.get("imported", 0)
            result["skipped"] += module_result.get("skipped", 0)
            result["failed"] += module_result.get("failed", 0)
            result["deleted"] += module_result.get("deleted", 0)

        conn.commit()
    except Exception as e:
        conn.rollback()
        result["success"] = False
        result["error"] = str(e)
        logger.error(f"Import failed: {e}")
        raise
    finally:
        release_db_connection(conn)

    return result


def _export_settings() -> Dict[str, str]:
    conn = get_db_connection()
    cur = dict_cursor(conn)
    try:
        cur.execute("SELECT `key`, value, encrypted FROM settings")
        settings = {}
        for row in cur.fetchall():
            settings[row["key"]] = SENSITIVE_MASK if row["encrypted"] else row["value"]
        return settings
    finally:
        release_db_connection(conn)


def _export_ai_prompts(user_id: int = None) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cur = dict_cursor(conn)
    try:
        cur.execute("""
            SELECT name, system_prompt, user_prompt, is_default, created_at, updated_at
            FROM ai_prompts WHERE user_id IS NULL OR user_id = %s ORDER BY id
        """, (user_id,))
        return [dict(r) for r in cur.fetchall()]
    finally:
        release_db_connection(conn)


def _export_accounts(user_id: int = None) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cur = dict_cursor(conn)
    try:
        cur.execute("SELECT id, name, description, created_at, updated_at FROM accounts WHERE user_id = %s ORDER BY id", (user_id,))
        return [dict(r) for r in cur.fetchall()]
    finally:
        release_db_connection(conn)


def _export_positions(user_id: int = None) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cur = dict_cursor(conn)
    try:
        cur.execute("""
            SELECT p.account_id, p.code, p.cost, p.shares, p.updated_at
            FROM positions p JOIN accounts a ON p.account_id = a.id
            WHERE a.user_id = %s ORDER BY p.account_id, p.code
        """, (user_id,))
        return [dict(r) for r in cur.fetchall()]
    finally:
        release_db_connection(conn)


def _export_transactions(user_id: int = None) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cur = dict_cursor(conn)
    try:
        cur.execute("""
            SELECT t.id, t.account_id, t.code, t.op_type, t.amount_cny, t.shares_redeemed,
                   t.confirm_date, t.confirm_nav, t.shares_added, t.cost_after, t.created_at, t.applied_at
            FROM transactions t JOIN accounts a ON t.account_id = a.id
            WHERE a.user_id = %s ORDER BY t.id
        """, (user_id,))
        rows = cur.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            for k in ("created_at", "applied_at"):
                if d[k]:
                    d[k] = str(d[k])
            result.append(d)
        return result
    finally:
        release_db_connection(conn)


def _export_subscriptions(user_id: int = None) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cur = dict_cursor(conn)
    try:
        cur.execute("""
            SELECT id, code, email, threshold_up, threshold_down, enable_digest, digest_time,
                   enable_volatility, last_notified_at, last_digest_at, created_at
            FROM subscriptions WHERE user_id = %s ORDER BY id
        """, (user_id,))
        return [dict(r) for r in cur.fetchall()]
    finally:
        release_db_connection(conn)


# Import functions

def _import_settings(cur, data: Dict[str, str], mode: str) -> Dict[str, Any]:
    result = {"total": len(data), "imported": 0, "skipped": 0, "failed": 0, "deleted": 0, "errors": []}
    for key, value in data.items():
        if value == SENSITIVE_MASK:
            result["skipped"] += 1
            continue
        try:
            cur.execute("""
                INSERT INTO settings (`key`, value) VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE value = VALUES(value), updated_at = CURRENT_TIMESTAMP
            """, (key, value))
            result["imported"] += 1
        except Exception as e:
            result["failed"] += 1
            result["errors"].append(f"Failed to import setting {key}: {str(e)}")
    return result


def _import_ai_prompts(cur, data: List[Dict[str, Any]], mode: str, user_id: int = None) -> Dict[str, Any]:
    result = {"total": len(data), "imported": 0, "skipped": 0, "failed": 0, "deleted": 0, "errors": []}
    if mode == "replace":
        cur.execute("DELETE FROM ai_prompts WHERE user_id = %s", (user_id,))
        result["deleted"] = cur.rowcount

    for prompt in data:
        try:
            name = prompt.get("name")
            if not name:
                result["skipped"] += 1
                continue
            if mode == "merge":
                cur.execute("SELECT id FROM ai_prompts WHERE (user_id = %s OR user_id IS NULL) AND name = %s", (user_id, name))
                if cur.fetchone():
                    result["skipped"] += 1
                    continue
            cur.execute("""
                INSERT INTO ai_prompts (user_id, name, system_prompt, user_prompt, is_default)
                VALUES (%s, %s, %s, %s, %s)
            """, (user_id, name, prompt.get("system_prompt", ""), prompt.get("user_prompt", ""), prompt.get("is_default", False)))
            result["imported"] += 1
        except Exception as e:
            result["failed"] += 1
            result["errors"].append(str(e))
    return result


def _import_accounts(cur, data: List[Dict[str, Any]], mode: str, user_id: int = None) -> Dict[str, Any]:
    result = {"total": len(data), "imported": 0, "skipped": 0, "failed": 0, "deleted": 0, "errors": []}
    if mode == "replace":
        cur.execute("DELETE FROM accounts WHERE user_id = %s", (user_id,))
        result["deleted"] = cur.rowcount

    for account in data:
        try:
            name = account.get("name")
            if not name:
                result["skipped"] += 1
                continue
            if mode == "merge":
                cur.execute("SELECT id FROM accounts WHERE user_id = %s AND name = %s", (user_id, name))
                if cur.fetchone():
                    result["skipped"] += 1
                    continue
            cur.execute("INSERT INTO accounts (user_id, name, description) VALUES (%s, %s, %s)",
                        (user_id, name, account.get("description", "")))
            result["imported"] += 1
        except Exception as e:
            result["failed"] += 1
            result["errors"].append(str(e))
    return result


def _import_positions(cur, data: List[Dict[str, Any]], mode: str, user_id: int = None) -> Dict[str, Any]:
    result = {"total": len(data), "imported": 0, "skipped": 0, "failed": 0, "deleted": 0, "errors": []}
    if mode == "replace":
        cur.execute("DELETE FROM positions WHERE account_id IN (SELECT id FROM accounts WHERE user_id = %s)", (user_id,))
        result["deleted"] = cur.rowcount

    for position in data:
        try:
            account_id = position.get("account_id")
            code = position.get("code")
            if not account_id or not code:
                result["skipped"] += 1
                continue
            cur.execute("SELECT id FROM accounts WHERE id = %s AND user_id = %s", (account_id, user_id))
            if not cur.fetchone():
                result["skipped"] += 1
                continue
            if mode == "merge":
                cur.execute("SELECT 1 FROM positions WHERE account_id = %s AND code = %s", (account_id, code))
                if cur.fetchone():
                    result["skipped"] += 1
                    continue
            cur.execute("INSERT INTO positions (account_id, code, cost, shares) VALUES (%s, %s, %s, %s)",
                        (account_id, code, position.get("cost", 0.0), position.get("shares", 0.0)))
            result["imported"] += 1
        except Exception as e:
            result["failed"] += 1
            result["errors"].append(str(e))
    return result


def _import_transactions(cur, data: List[Dict[str, Any]], mode: str, user_id: int = None) -> Dict[str, Any]:
    result = {"total": len(data), "imported": 0, "skipped": 0, "failed": 0, "deleted": 0, "errors": []}
    if mode == "replace":
        cur.execute("DELETE FROM transactions WHERE account_id IN (SELECT id FROM accounts WHERE user_id = %s)", (user_id,))
        result["deleted"] = cur.rowcount

    for t in data:
        try:
            account_id = t.get("account_id")
            code = t.get("code")
            if not account_id or not code:
                result["skipped"] += 1
                continue
            cur.execute("SELECT id FROM accounts WHERE id = %s AND user_id = %s", (account_id, user_id))
            if not cur.fetchone():
                result["skipped"] += 1
                continue
            cur.execute("""
                INSERT INTO transactions (account_id, code, op_type, amount_cny, shares_redeemed,
                    confirm_date, confirm_nav, shares_added, cost_after, applied_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (account_id, code, t.get("op_type"), t.get("amount_cny"), t.get("shares_redeemed"),
                  t.get("confirm_date"), t.get("confirm_nav"), t.get("shares_added"), t.get("cost_after"),
                  t.get("applied_at")))
            result["imported"] += 1
        except Exception as e:
            result["failed"] += 1
            result["errors"].append(str(e))
    return result


def _import_subscriptions(cur, data: List[Dict[str, Any]], mode: str, user_id: int = None) -> Dict[str, Any]:
    result = {"total": len(data), "imported": 0, "skipped": 0, "failed": 0, "deleted": 0, "errors": []}
    if mode == "replace":
        cur.execute("DELETE FROM subscriptions WHERE user_id = %s", (user_id,))
        result["deleted"] = cur.rowcount

    for sub in data:
        try:
            code = sub.get("code")
            email = sub.get("email")
            if not code or not email:
                result["skipped"] += 1
                continue
            if mode == "merge":
                cur.execute("SELECT id FROM subscriptions WHERE user_id = %s AND code = %s AND email = %s", (user_id, code, email))
                if cur.fetchone():
                    result["skipped"] += 1
                    continue
            cur.execute("""
                INSERT INTO subscriptions (user_id, code, email, threshold_up, threshold_down,
                    enable_digest, digest_time, enable_volatility)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (user_id, code, email, sub.get("threshold_up"), sub.get("threshold_down"),
                  sub.get("enable_digest", False), sub.get("digest_time", "14:45"),
                  sub.get("enable_volatility", True)))
            result["imported"] += 1
        except Exception as e:
            result["failed"] += 1
            result["errors"].append(str(e))
    return result
