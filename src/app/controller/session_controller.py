from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import ErrorResponse, success_response
from app.service.account_service import AccountService
from app.service.session_service import SessionService


async def get_session_controller(
    user_id: int, session_id: int, db: AsyncSession
) -> JSONResponse:
    service = SessionService(db)
    session = await service.get_session(user_id, session_id)

    if not session:
        raise ErrorResponse(404, "Session not found")

    return success_response(
        data=session,
        message="WhatsApp session retrieved successfully",
        status_code=200,
    )


async def get_all_sessions_controller(
    user_id: int,
    account_id: int,
    page: int,
    limit: int,
    search: str,
    stage_search: str,
    db: AsyncSession,
):
    account_service = AccountService(db)
    account = await account_service.get_account(user_id, account_id)
    if not account:
        raise ErrorResponse(404, "Account not found")

    service = SessionService(db)
    result = await service.get_all_sessions(
        user_id, account_id, page, limit, search, stage_search
    )

    return success_response(
        data=result,
        message="WhatsApp sessions retrieved successfully.",
        status_code=200,
    )


async def get_session_history_controller(
    user_id: int, session_id: int, db: AsyncSession
) -> JSONResponse:
    service = SessionService(db)

    session = await service.get_session(user_id, session_id)
    if not session:
        raise ErrorResponse(404, "Session not found")

    history = await service.get_session_history(user_id, session_id)

    return success_response(
        data=history, message="Session history retrieved successfully.", status_code=200
    )


async def delete_session_history_controller(
    user_id: int, session_id: int, db: AsyncSession
) -> JSONResponse:
    service = SessionService(db)
    deleted = await service.delete_session_history(user_id, session_id)
    if not deleted:
        raise ErrorResponse(404, "Session history not found")

    return success_response(
        data=None, message="Session history deleted successfully", status_code=200
    )
