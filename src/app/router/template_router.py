from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.controller.template_controller import (
    get_template_detail_controller,
    get_templates_controller,
)
from app.database.db_handler import get_db
from app.utils.middleware import CurrentUser, get_current_user

router = APIRouter(prefix="/templates", tags=["Templates"])


@router.get("/account/{account_id}")
async def get_templates(
    account_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    status: Annotated[str, Query()] = "APPROVED",
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> JSONResponse:
    """
    Fetch all message templates for a WhatsApp Business Account.
    """
    return await get_templates_controller(
        current_user.id, account_id, status, limit, db
    )


@router.get("/account/{account_id}/{template_name}")
async def get_template_detail(
    account_id: int,
    template_name: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    language: Annotated[str, Query()] = "en_US",
) -> JSONResponse:
    """
    Get details of a specific template including variable placeholders.
    """
    return await get_template_detail_controller(
        current_user.id, account_id, template_name, language, db
    )
