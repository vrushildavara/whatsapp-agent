from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import ErrorResponse, success_response
from app.service.account_service import AccountService
from app.service.session_service import SessionService
from app.validation.account_validation import (
    WhatsAppAccountCreate,
    WhatsAppAccountUpdate,
)


async def create_account_controller(
    user_id: int, data: WhatsAppAccountCreate, db: AsyncSession, workspace_id: str | None = None
) -> JSONResponse:
    service = AccountService(db)
    account = await service.create_account(user_id, data, workspace_id)

    if not account:
        raise ErrorResponse(409, "WhatsApp account already exists")

    service = SessionService(db)
    await service.create_session(account["id"], account["user_id"])

    return success_response(
        data=account,
        message="WhatsApp account created successfully",
        status_code=200,
    )


async def get_account_controller(
    user_id: int, account_id: int, db: AsyncSession, workspace_id: str | None = None
) -> JSONResponse:
    service = AccountService(db)
    account = await service.get_account(user_id, account_id, workspace_id)

    if not account:
        raise ErrorResponse(404, "Account not found")

    return success_response(
        data=account,
        message="WhatsApp account retrieved successfully",
        status_code=200,
    )


async def get_user_accounts_controller(user_id: int, db: AsyncSession, workspace_id: str | None = None) -> JSONResponse:
    service = AccountService(db)
    accounts = await service.get_user_accounts(user_id, workspace_id)

    return success_response(
        data=accounts,
        message="WhatsApp accounts retrieved successfully",
        status_code=200,
    )


async def get_account_stage_flow_controller(
    user_id: int, account_id: int, db: AsyncSession, workspace_id: str | None = None
) -> JSONResponse:
    service = AccountService(db)

    account = await service.get_account(user_id, account_id, workspace_id)

    if not account:
        raise ErrorResponse(404, "Account not found")

    stage_flow = await service.get_account_stage_flow(user_id, account_id, workspace_id)

    return success_response(
        data=stage_flow or [],
        message="WhatsApp account stage flow retrieved successfully",
        status_code=200,
    )


async def update_account_controller(
    user_id: int, account_id: int, data: WhatsAppAccountUpdate, db: AsyncSession, workspace_id: str | None = None
) -> JSONResponse:
    service = AccountService(db)
    account = await service.get_account(user_id, account_id, workspace_id)

    if not account:
        raise ErrorResponse(404, "Account not found")

    updated_data = await service.update_account_prompt(user_id, account_id, data, workspace_id)

    return success_response(
        data=updated_data, message="Prompt updated successfully", status_code=200
    )


async def toggle_account_active_controller(
    user_id: int, account_id: int, db: AsyncSession, workspace_id: str | None = None
) -> JSONResponse:
    service = AccountService(db)
    account = await service.get_account(user_id, account_id, workspace_id)

    if not account:
        raise ErrorResponse(404, "Account not found")

    updated = await service.toggle_account_active(user_id, account_id, workspace_id)
    
    if not updated:
        raise ErrorResponse(500, "Failed to toggle account status")
    
    status = "activated" if updated["is_active"] else "deactivated"

    return success_response(
        data=updated,
        message=f"Account {status} successfully",
        status_code=200,
    )


async def delete_account_controller(
    user_id: int, account_id: int, db: AsyncSession, workspace_id: str | None = None
) -> JSONResponse:
    service = AccountService(db)
    account = await service.get_account(user_id, account_id, workspace_id)

    if not account:
        raise ErrorResponse(404, "Account not found")

    await service.soft_delete_account(user_id, account_id, workspace_id)

    return success_response(
        data=None,
        message="WhatsApp account deleted successfully",
        status_code=200,
    )
