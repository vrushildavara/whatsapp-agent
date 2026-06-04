from typing import Any

from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import ErrorResponse, success_response
from app.service.account_service import AccountService
from app.service.template_service import template_service


async def _get_account_fatch(
    user_id: int, account_id: int, db: AsyncSession
) -> dict[str, Any]:
    """Helper function to fetch account details and validate access token"""
    account_service = AccountService(db)
    account = await account_service.get_account(user_id, account_id)

    if not account:
        raise ErrorResponse(404, "Account not found")

    if not account.get("waba_id") or not account.get("token"):
        raise ErrorResponse(400, "Account not properly configured")

    # Validate token format
    token = account["token"].strip()
    if not token or len(token) < 20:
        raise ErrorResponse(
            400,
            "Invalid access token format. Please update your WhatsApp account with a valid Meta access token.",
        )

    return account


async def get_templates_controller(
    user_id: int,
    account_id: int,
    status: str,
    limit: int,
    db: AsyncSession,
) -> JSONResponse:
    """
    Fetch all message templates for a WhatsApp Business Account.
    Results are cached in Redis for 5 minutes.
    """
    # Get account details
    account = await _get_account_fatch(user_id, account_id, db)

    # Fetch templates from Meta API (with Redis caching)
    templates = await template_service.fetch_templates(
        waba_id=account["waba_id"],
        access_token=account["token"],
        status=status,
        limit=limit,
    )

    return success_response(
        data=templates,
        message="Templates fetched successfully",
        status_code=200,
    )


async def get_template_detail_controller(
    user_id: int,
    account_id: int,
    template_name: str,
    language: str,
    db: AsyncSession,
) -> JSONResponse:
    """
    Get details of a specific template including variable placeholders.
    """
    # Get account details
    account = await _get_account_fatch(user_id, account_id, db)

    # Fetch specific template
    template = await template_service.get_template_by_name(
        waba_id=account["waba_id"],
        access_token=account["token"],
        template_name=template_name,
        language=language,
    )

    if not template:
        raise ErrorResponse(404, "Template not found")

    # Parse variables from template components
    variables = template_service.parse_template_variables(template)

    return success_response(
        data={
            "template": template,
            "variables": variables,
        },
        message="Template details retrieved successfully",
        status_code=200,
    )
