from typing import Annotated

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.controller.account_controller import (
    create_account_controller,
    delete_account_controller,
    get_account_controller,
    get_account_stage_flow_controller,
    get_user_accounts_controller,
    toggle_account_active_controller,
    update_account_controller,
)
from app.database.db_handler import get_db
from app.utils.middleware import CurrentUser, get_current_user
from app.validation.account_validation import (
    WhatsAppAccountCreate,
    WhatsAppAccountUpdate,
)

router = APIRouter(prefix="/account", tags=["WhatsApp Accounts"])


@router.post("/create")
async def create_account(
    data: WhatsAppAccountCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    x_workspace_id: str | None = Header(None, alias="x-workspace-id"),
) -> JSONResponse:
    return await create_account_controller(current_user.id, data, db, x_workspace_id or current_user.workspace_id)


@router.get("/{account_id}")
async def get_account(
    account_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    return await get_account_controller(current_user.id, account_id, db, current_user.workspace_id)


@router.get("/stage_flow/{account_id}")
async def get_account_stage_flow(
    account_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    return await get_account_stage_flow_controller(current_user.id, account_id, db, current_user.workspace_id)


@router.get("/user/")
async def get_user_accounts(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    return await get_user_accounts_controller(current_user.id, db, current_user.workspace_id)


@router.put("/{account_id}")
async def update_account(
    account_id: int,
    data: WhatsAppAccountUpdate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    return await update_account_controller(current_user.id, account_id, data, db, current_user.workspace_id)


@router.patch("/{account_id}/toggle")
async def toggle_account_active(
    account_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    x_workspace_id: str | None = Header(None, alias="x-workspace-id"),
) -> JSONResponse:
    return await toggle_account_active_controller(
        current_user.id, account_id, db, x_workspace_id or current_user.workspace_id
    )


@router.delete("/{account_id}")
async def delete_account(
    account_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    return await delete_account_controller(current_user.id, account_id, db, current_user.workspace_id)
