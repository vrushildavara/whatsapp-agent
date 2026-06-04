from fastapi import BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import ErrorResponse, success_response
from app.common.send_mail import send_email
from app.service.user_service import UserService
from app.validation.user_validation import (
    ForgotPasswordRequest,
    ResetPasswordRequest,
    RegenerateApiKeyRequest,
    UserCreate,
    UserLogin,
)


async def register_user_controller(data: UserCreate, db: AsyncSession) -> JSONResponse:
    service = UserService(db)
    user = await service.create_user(data)

    if not user:
        raise ErrorResponse(400, "User already registered")

    return success_response(
        data=user,
        message="User registered successfully",
        status_code=200,
    )


async def login_user_controller(data: UserLogin, db: AsyncSession) -> JSONResponse:
    service = UserService(db)
    result = await service.login_user(data)

    if not result:
        raise ErrorResponse(401, "Invalid email or password")

    return success_response(
        data=result,
        message="Login successfully",
        status_code=200,
    )


async def get_user_controller(user_id: int, db: AsyncSession) -> JSONResponse:
    service = UserService(db)
    user = await service.get_user_by_id(user_id)

    if not user:
        raise ErrorResponse(404, "User not found")

    return success_response(
        data=user,
        message="User retrieved successfully",
        status_code=200,
    )


async def forgot_password_controller(
    data: ForgotPasswordRequest, db: AsyncSession, background_tasks: BackgroundTasks
) -> JSONResponse:
    service = UserService(db)
    result = await service.forgot_password(data)

    if result is None:
        raise ErrorResponse(404, "User not found")

    # Send email in background - doesn't block response
    background_tasks.add_task(send_email, result["email"], result["code"])

    return success_response(
        message="Password reset code sent to email",
        status_code=200,
    )

async def regenerate_api_key_controller(
    data: RegenerateApiKeyRequest, db: AsyncSession
) -> JSONResponse:
    service = UserService(db)
    result = await service.regenerate_api_key_with_credentials(
        data.email, data.password
    )

    if not result:
        raise ErrorResponse(401, "Invalid email or password")

    return success_response(
        data=result,
        message="API key regenerated successfully",
        status_code=200,
    )


async def reset_password_controller(
    data: ResetPasswordRequest, db: AsyncSession
) -> JSONResponse:
    service = UserService(db)
    reset = await service.reset_password(data)

    if isinstance(reset, str):
        raise ErrorResponse(400, reset)

    return success_response(
        message="Password reset successfully",
        status_code=200,
    )
