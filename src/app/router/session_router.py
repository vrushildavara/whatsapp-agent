from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.controller.session_controller import (
    delete_session_history_controller,
    get_all_sessions_controller,
    get_session_controller,
    get_session_history_controller,
)
from app.database.db_handler import get_db
from app.utils.middleware import CurrentUser, get_current_user

router = APIRouter(prefix="/session", tags=["WhatsApp Sessions"])


@router.get("/{session_id}")
async def get_whatsapp_session(
    session_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    return await get_session_controller(current_user.id, session_id, db)


@router.get("/account/{account_id}")
async def get_all_whatsapp_sessions(
    account_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1),
    search: str = Query(None),
    stage_search: str = Query(None),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    return await get_all_sessions_controller(
        current_user.id, account_id, page, limit, search, stage_search, db
    )


@router.get("/history/{session_id}")
async def get_session_history(
    session_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    return await get_session_history_controller(current_user.id, session_id, db)


@router.delete("/history/{session_id}")
async def delete_session_history(
    session_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    return await delete_session_history_controller(current_user.id, session_id, db)
