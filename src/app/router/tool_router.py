from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.controller.tool_controller import (
    create_tool_controller,
    delete_tool_controller,
    get_account_tools_controller,
    get_tool_controller,
    update_tool_controller,
)
from app.database.db_handler import get_db
from app.utils.middleware import CurrentUser, get_current_user
from app.validation.tool_validation import AssistantToolCreate, AssistantToolUpdate

router = APIRouter(prefix="/tools", tags=["Knowledge Tools"])


@router.post("/account/{account_id}", status_code=201)
async def create_tool(
    account_id: int,
    data: AssistantToolCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Create a knowledge tool for an account with a list of file IDs."""
    return await create_tool_controller(current_user.id, account_id, data, db)


@router.get("/account/{account_id}")
async def get_account_tools(
    account_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """List all knowledge tools for an account."""
    return await get_account_tools_controller(current_user.id, account_id, db)


@router.get("/account/{account_id}/{tool_id}")
async def get_tool(
    account_id: int,
    tool_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Get a specific knowledge tool."""
    return await get_tool_controller(current_user.id, account_id, tool_id, db)


@router.put("/account/{account_id}/{tool_id}")
async def update_tool(
    account_id: int,
    tool_id: int,
    data: AssistantToolUpdate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Update a knowledge tool's name, file_ids, or active status."""
    return await update_tool_controller(current_user.id, account_id, tool_id, data, db)


@router.delete("/account/{account_id}/{tool_id}")
async def delete_tool(
    account_id: int,
    tool_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Soft-delete a knowledge tool."""
    return await delete_tool_controller(current_user.id, account_id, tool_id, db)
