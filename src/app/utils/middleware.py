import logging
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.settings import settings
from app.database.db_handler import get_db
from app.service.user_service import UserService

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"
security = HTTPBearer(auto_error=False)


@dataclass
class CurrentUser:
    id: int
    email: str
    workspace_id: str | None = None


def validate_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])


async def _fetch_current_user(token: str, db: AsyncSession) -> CurrentUser:
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = validate_token(token)
    except JWTError as e:
        logger.error(f"JWT Error: {e}")
        raise credentials_exception

    user_id = payload.get("user_id")
    email = payload.get("email")

    if not user_id or not email:
        raise credentials_exception

    user_service = UserService(db)
    user = await user_service.get_user_by_id(user_id)
    if not user:
        logger.error(f"User not found: {user_id}")
        raise credentials_exception

    return CurrentUser(id=user_id, email=email)


async def _fetch_user_by_api_key(api_key: str, db: AsyncSession) -> CurrentUser:
    user_service = UserService(db)
    user = await user_service.get_user_by_api_key(api_key)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return CurrentUser(id=user["id"], email=user["email"])


async def get_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(security)
    ] = None,
    x_api_key: Annotated[str | None, Header()] = None,
    x_workspace_id: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    if x_api_key:
        user = await _fetch_user_by_api_key(x_api_key, db)
        user.workspace_id = x_workspace_id
        return user

    if credentials:
        return await _fetch_current_user(credentials.credentials, db)

    raise HTTPException(
        status_code=401,
        detail="Authentication required: provide JWT token or X-API-Key header",
    )


def get_current_user(
    current_user: Annotated[CurrentUser, Depends(get_user)],
) -> CurrentUser:
    return current_user
