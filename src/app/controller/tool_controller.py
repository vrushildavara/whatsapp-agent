from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import ErrorResponse, success_response
from app.service.account_service import AccountService
from app.service.tool_service import ToolService
from app.validation.tool_validation import AssistantToolCreate, AssistantToolUpdate


async def create_tool_controller(
    user_id: int, account_id: int, data: AssistantToolCreate, db: AsyncSession
) -> JSONResponse:
    account_service = AccountService(db)
    account = await account_service.get_account(user_id, account_id)
    if not account:
        raise ErrorResponse(404, "Account not found")
    if not account["is_active"]:
        raise ErrorResponse(403, "Account is inactive")

    service = ToolService(db)
    if data.tool_type != "api_request":
        existing = await service.get_tool_by_type(account_id, data.tool_type)
        if existing:
            raise ErrorResponse(
                409, f"A {data.tool_type} tool already exists for this account"
            )

    if await service.get_tool_by_name(account_id, data.name):
        raise ErrorResponse(409, f"A tool named '{data.name}' already exists for this account")

    tool = await service.create_tool(account_id, data)

    return success_response(
        data=tool,
        message="Knowledge tool created successfully",
        status_code=201,
    )


async def get_tool_controller(
    user_id: int, account_id: int, tool_id: int, db: AsyncSession
) -> JSONResponse:
    account_service = AccountService(db)
    account = await account_service.get_account(user_id, account_id)
    if not account:
        raise ErrorResponse(404, "Account not found")
    if not account["is_active"]:
        raise ErrorResponse(403, "Account is inactive")

    service = ToolService(db)
    tool = await service.get_tool(account_id, tool_id)
    if not tool:
        raise ErrorResponse(404, "Tool not found")

    return success_response(
        data=tool,
        message="Knowledge tool retrieved successfully",
        status_code=200,
    )


async def get_account_tools_controller(
    user_id: int, account_id: int, db: AsyncSession
) -> JSONResponse:
    account_service = AccountService(db)
    account = await account_service.get_account(user_id, account_id)
    if not account:
        raise ErrorResponse(404, "Account not found")
    if not account["is_active"]:
        raise ErrorResponse(403, "Account is inactive")

    service = ToolService(db)
    tools = await service.get_account_tools(account_id)

    return success_response(
        data=tools,
        message="Knowledge tools retrieved successfully",
        status_code=200,
    )


async def update_tool_controller(
    user_id: int,
    account_id: int,
    tool_id: int,
    data: AssistantToolUpdate,
    db: AsyncSession,
) -> JSONResponse:
    account_service = AccountService(db)
    account = await account_service.get_account(user_id, account_id)
    if not account:
        raise ErrorResponse(404, "Account not found")
    if not account["is_active"]:
        raise ErrorResponse(403, "Account is inactive")

    service = ToolService(db)
    existing = await service.get_tool(account_id, tool_id)
    if not existing:
        raise ErrorResponse(404, "Tool not found")

    if data.name is not None and await service.get_tool_by_name(account_id, data.name, exclude_tool_id=tool_id):
        raise ErrorResponse(409, f"A tool named '{data.name}' already exists for this account")

    updated_tool = await service.update_tool(account_id, tool_id, data, existing)

    return success_response(
        data=updated_tool,
        message="Knowledge tool updated successfully",
        status_code=200,
    )


async def delete_tool_controller(
    user_id: int, account_id: int, tool_id: int, db: AsyncSession
) -> JSONResponse:
    account_service = AccountService(db)
    account = await account_service.get_account(user_id, account_id)
    if not account:
        raise ErrorResponse(404, "Account not found")
    if not account["is_active"]:
        raise ErrorResponse(403, "Account is inactive")

    service = ToolService(db)
    existing = await service.get_tool(account_id, tool_id)
    if not existing:
        raise ErrorResponse(404, "Tool not found")

    await service.soft_delete_tool(account_id, tool_id)

    return success_response(
        data=None,
        message="Knowledge tool deleted successfully",
        status_code=200,
    )
