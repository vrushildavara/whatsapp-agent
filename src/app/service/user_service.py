from datetime import datetime, timedelta, timezone

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.model import User
from app.utils.jwt import create_access_token
from app.utils.security import (
    decrypt_api_key,
    encrypt_api_key,
    generate_api_key,
    generate_email_code,
    hash_password,
    verify_password,
)
from app.validation.user_validation import (
    ForgotPasswordRequest,
    ResetPasswordRequest,
    UserCreate,
    UserLogin,
)


class UserService:
    def __init__(self, db: AsyncSession):
        self.model = User
        self.db = db

    async def create_user(self, user: UserCreate) -> dict | None:
        try:
            stmt = select(self.model).where(self.model.email == user.email)
            result = await self.db.execute(stmt)
            if result.scalar_one_or_none():
                return None

            api_key = generate_api_key()
            encrypted_api_key = encrypt_api_key(api_key)

            stmt = (
                insert(self.model)
                .values(
                    name=user.name,
                    email=user.email,
                    password=hash_password(user.password),
                    api_key=encrypted_api_key,
                    created_at=datetime.now(timezone.utc),
                )
                .returning(
                    self.model.id,
                    self.model.name,
                    self.model.email,
                    self.model.api_key,
                )
            )

            result = await self.db.execute(stmt)
            await self.db.commit()

            user_data = dict(result.mappings().one())
            user_data["api_key"] = api_key  # Return plain API key to user
            return user_data
        except Exception:
            await self.db.rollback()
            return None

    async def get_user_by_api_key(self, api_key: str) -> dict | None:
        # Get all users and decrypt to find match
        stmt = select(
            self.model.id, self.model.name, self.model.email, self.model.api_key
        )
        result = await self.db.execute(stmt)
        users = result.mappings().all()

        for user in users:
            try:
                decrypted_key = decrypt_api_key(user["api_key"])
                if decrypted_key == api_key:
                    return {
                        "id": user["id"],
                        "name": user["name"],
                        "email": user["email"],
                    }
            except Exception:
                continue

        return None

    async def regenerate_api_key(self, user_id: int) -> str | None:
        new_api_key = generate_api_key()
        encrypted_api_key = encrypt_api_key(new_api_key)

        stmt = (
            update(self.model)
            .where(self.model.id == user_id)
            .values(api_key=encrypted_api_key)
            .returning(self.model.api_key)
        )

        result = await self.db.execute(stmt)
        await self.db.commit()

        row = result.one_or_none()
        return new_api_key if row else None

    async def regenerate_api_key_with_credentials(
        self, email: str, password: str
    ) -> dict | None:
        stmt = select(self.model.id, self.model.email, self.model.password).where(
            self.model.email == email
        )
        result = await self.db.execute(stmt)
        user = result.mappings().one_or_none()

        if not user or not verify_password(password, user["password"]):
            return None

        new_api_key = generate_api_key()
        encrypted_api_key = encrypt_api_key(new_api_key)

        stmt = (
            update(self.model)
            .where(self.model.id == user["id"])
            .values(api_key=encrypted_api_key)
            .returning(self.model.api_key)
        )

        result = await self.db.execute(stmt)
        await self.db.commit()

        row = result.one_or_none()
        return {"api_key": new_api_key} if row else None

    async def login_user(self, data: UserLogin) -> dict | None:
        stmt = select(
            self.model.id,
            self.model.name,
            self.model.email,
            self.model.password,
            self.model.created_at,
        ).where(self.model.email == data.email)
        result = await self.db.execute(stmt)
        user = result.mappings().one_or_none()

        if not user or not verify_password(data.password, user["password"]):
            return None

        access_token = create_access_token({"user_id": user["id"], "email": user["email"]})
        
        created_at = user["created_at"] if user["created_at"] else datetime.now(timezone.utc)
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user["id"],
                "name": user["name"],
                "email": user["email"],
                "created_at": created_at.isoformat() if isinstance(created_at, datetime) else created_at,
            }
        }

    async def get_user_by_id(self, user_id: int) -> dict | None:
        stmt = select(self.model.id, self.model.name, self.model.email).where(
            self.model.id == user_id
        )
        result = await self.db.execute(stmt)
        user = result.mappings().one_or_none()
        if not user:
            return None

        return dict(user)

    async def forgot_password(self, data: ForgotPasswordRequest) -> dict | None:
        stmt = select(self.model).where(self.model.email == data.email)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            return None

        code = generate_email_code()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

        stmt = (
            update(self.model)
            .where(self.model.email == data.email)
            .values(reset_code=str(code), reset_code_expires_at=expires_at)
        )
        await self.db.execute(stmt)
        await self.db.commit()

        return {"email": data.email, "code": code}

    async def reset_password(self, data: ResetPasswordRequest) -> str | bool:
        # Check if user exists
        stmt = select(self.model).where(self.model.email == data.email)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            return "We couldn’t find an account with this email"

        # Check reset code
        if not user.reset_code or user.reset_code != str(data.code):
            return "The reset code you entered is incorrect"

        # Check expiry
        if not user.reset_code_expires_at or user.reset_code_expires_at < datetime.now(
            timezone.utc
        ):
            return "This reset code has expired. Please request a new one"

        # Update password
        stmt = (
            update(self.model)
            .where(self.model.email == data.email)
            .values(
                password=hash_password(data.new_password),
                reset_code=None,
                reset_code_expires_at=None,
            )
        )

        await self.db.execute(stmt)
        await self.db.commit()
        return True
