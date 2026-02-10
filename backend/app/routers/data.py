from fastapi import APIRouter, HTTPException, Body, Depends
from fastapi.responses import StreamingResponse
from typing import List, Optional
from pydantic import BaseModel
import json
import io
import datetime

from ..services.data_io import export_data, import_data
from ..auth import get_current_user

router = APIRouter()

VALID_MODULES = ["accounts", "positions", "transactions", "ai_prompts", "subscriptions", "settings"]


class ImportRequest(BaseModel):
    data: dict
    modules: List[str]
    mode: str = "merge"


@router.get("/data/export")
def export_data_endpoint(modules: Optional[str] = None, user: dict = Depends(get_current_user)):
    try:
        module_list = [m.strip() for m in modules.split(",")] if modules else VALID_MODULES
        invalid = [m for m in module_list if m not in VALID_MODULES]
        if invalid:
            raise HTTPException(status_code=400, detail=f"Invalid modules: {', '.join(invalid)}")

        data = export_data(module_list, user_id=user["user_id"])
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"fundval_export_{timestamp}.json"
        json_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")

        return StreamingResponse(
            io.BytesIO(json_bytes),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/data/import")
def import_data_endpoint(request: ImportRequest = Body(...), user: dict = Depends(get_current_user)):
    try:
        if request.mode not in ["merge", "replace"]:
            raise HTTPException(status_code=400, detail="Invalid mode. Must be 'merge' or 'replace'")
        invalid = [m for m in request.modules if m not in VALID_MODULES]
        if invalid:
            raise HTTPException(status_code=400, detail=f"Invalid modules: {', '.join(invalid)}")
        return import_data(request.data, request.modules, request.mode, user_id=user["user_id"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
