from datetime import datetime, timedelta, timezone

from jose import jwt

from app.common.settings import settings

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120


def create_access_token(
    payload: dict, expires_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES
) -> str:
    data = payload.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    data.update({"exp": expire})

    return jwt.encode(data, settings.secret_key, algorithm=ALGORITHM)
