from fastapi import APIRouter, Body, HTTPException, Depends
from typing import Dict, Any
from pydantic import BaseModel, Field
from ..services.ai import ai_service
from ..db import get_db_connection, release_db_connection, dict_cursor
from ..auth import get_current_user

router = APIRouter()

class PromptModel(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    system_prompt: str = Field(..., min_length=1, max_length=10000)
    user_prompt: str = Field(..., min_length=1, max_length=10000)
    is_default: bool = False

@router.post("/ai/analyze_fund")
async def analyze_fund(fund_info: Dict[str, Any] = Body(...), prompt_id: int = Body(None), user: dict = Depends(get_current_user)):
    return await ai_service.analyze_fund(fund_info, prompt_id=prompt_id, user_id=user["user_id"])

@router.get("/ai/prompts")
def get_prompts(user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    try:
        cur = dict_cursor(conn)
        cur.execute("""
            SELECT id, name, system_prompt, user_prompt, is_default, created_at, updated_at
            FROM ai_prompts WHERE user_id = %s OR user_id IS NULL
            ORDER BY is_default DESC, id ASC
        """, (user["user_id"],))
        return {"prompts": cur.fetchall()}
    finally:
        release_db_connection(conn)

@router.post("/ai/prompts")
def create_prompt(data: PromptModel, user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    try:
        cur = dict_cursor(conn)
        if data.is_default:
            cur.execute("UPDATE ai_prompts SET is_default = FALSE WHERE user_id = %s", (user["user_id"],))
        cur.execute("""
            INSERT INTO ai_prompts (name, system_prompt, user_prompt, is_default, user_id)
            VALUES (%s, %s, %s, %s, %s)
        """, (data.name, data.system_prompt, data.user_prompt, data.is_default, user["user_id"]))
        prompt_id = cur.lastrowid
        conn.commit()
        return {"ok": True, "id": prompt_id}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        release_db_connection(conn)

@router.put("/ai/prompts/{prompt_id}")
def update_prompt(prompt_id: int, data: PromptModel, user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    try:
        cur = dict_cursor(conn)
        if data.is_default:
            cur.execute("UPDATE ai_prompts SET is_default = FALSE WHERE user_id = %s AND id != %s", (user["user_id"], prompt_id))
        cur.execute("""
            UPDATE ai_prompts SET name = %s, system_prompt = %s, user_prompt = %s, is_default = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND (user_id = %s OR user_id IS NULL)
        """, (data.name, data.system_prompt, data.user_prompt, data.is_default, prompt_id, user["user_id"]))
        conn.commit()
        return {"ok": True}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        release_db_connection(conn)

@router.delete("/ai/prompts/{prompt_id}")
def delete_prompt(prompt_id: int, user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    try:
        cur = dict_cursor(conn)
        cur.execute("SELECT is_default FROM ai_prompts WHERE id = %s AND user_id = %s", (prompt_id, user["user_id"]))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="模板不存在")
        if row["is_default"]:
            raise HTTPException(status_code=400, detail="不能删除默认模板")
        cur.execute("DELETE FROM ai_prompts WHERE id = %s AND user_id = %s", (prompt_id, user["user_id"]))
        conn.commit()
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        release_db_connection(conn)
