from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.controller.user_controller import (
    forgot_password_controller,
    get_user_controller,
    login_user_controller,
    regenerate_api_key_controller,
    register_user_controller,
    reset_password_controller,
)
from app.database.db_handler import get_db
from app.utils.middleware import CurrentUser, get_current_user
from app.validation.user_validation import (
    ForgotPasswordRequest,
    ResetPasswordRequest,
    RegenerateApiKeyRequest,
    UserCreate,
    UserLogin,
)

router = APIRouter(
    prefix="/users",
    tags=["Users"],
)


@router.post("/register")
async def register_user(
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    return await register_user_controller(data, db)


@router.post("/login")
async def login_user(
    data: UserLogin,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    return await login_user_controller(data, db)


@router.get("/get")
async def get_user(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    return await get_user_controller(current_user.id, db)


@router.post("/forgot-password")
async def forgot_password(
    data: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    return await forgot_password_controller(data, db, background_tasks)


@router.post("/reset-password")
async def reset_password(
    data: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    return await reset_password_controller(data, db)


@router.post("/api-key/regenerate")
async def regenerate_api_key(
    data: RegenerateApiKeyRequest,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    return await regenerate_api_key_controller(data, db)
