from datetime import datetime, timezone

from sqlalchemy import delete, exists, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.model import (
    WhatsAppAccount,
    WhatsAppMessage,
    WhatsAppSession,
    WhatsAppSessionSummary,
)
from app.validation.account_validation import (
    WhatsAppAccountCreate,
    WhatsAppAccountUpdate,
)


def _serialize_stage_flow(stage_flow):
    """Ensure stage_flow maintains correct key order: stage, goal"""
    if not stage_flow:
        return None
    return [{"stage": item["stage"], "goal": item["goal"]} for item in stage_flow]


class AccountService:
    def __init__(self, db: AsyncSession) -> None:
        self.model = WhatsAppAccount
        self.db = db

    async def create_account(
        self, user_id: int, data: WhatsAppAccountCreate, workspace_id: str | None = None
    ) -> dict | None:
        # Only check for active (non-deleted) accounts
        conditions = [
            self.model.phone_number == data.phone_number,
            self.model.user_id == user_id,
            self.model.deleted_at.is_(None),
        ]

        if workspace_id:
            conditions.append(self.model.workspace_id == workspace_id)

        stmt = select(self.model.id).where(*conditions)
        result = await self.db.execute(stmt)
        if result.scalar_one_or_none():
            return None  # Active account exists

        stmt = (
            insert(self.model)
            .values(
                workspace_id=workspace_id,
                name=data.name,
                phone_number=data.phone_number,
                phone_number_id=data.phone_id,
                waba_id=data.waba_id,
                token=data.token,
                prompt=data.prompt,
                stage_flow=_serialize_stage_flow(data.stage_flow),
                user_id=user_id,
                is_active=True,
            )
            .returning(
                self.model.id,
                self.model.user_id,
                self.model.workspace_id,
                self.model.name,
                self.model.phone_number,
                self.model.phone_number_id,
                self.model.waba_id,
                self.model.token,
                self.model.prompt,
                self.model.stage_flow,
                self.model.is_active,
            )
        )

        result = await self.db.execute(stmt)
        await self.db.commit()
        account = dict(result.mappings().one())
        account["stage_flow"] = _serialize_stage_flow(account.get("stage_flow"))
        return account

    async def get_account(
        self, user_id: int, account_id: int, workspace_id: str | None = None
    ) -> dict | None:
        conditions = [
            self.model.id == account_id,
            self.model.user_id == user_id,
            self.model.deleted_at.is_(None),
        ]

        if workspace_id:
            conditions.append(self.model.workspace_id == workspace_id)

        stmt = select(
            self.model.id,
            self.model.user_id,
            self.model.workspace_id,
            self.model.name,
            self.model.phone_number,
            self.model.phone_number_id,
            self.model.waba_id,
            self.model.token,
            self.model.prompt,
            self.model.stage_flow,
            self.model.is_active,
        ).where(*conditions)

        result = await self.db.execute(stmt)

        account = result.mappings().one_or_none()
        if not account:
            return None

        account = dict(account)
        account["stage_flow"] = _serialize_stage_flow(account.get("stage_flow"))
        return account

    async def get_account_stage_flow(
        self, user_id: int, account_id: int, workspace_id: str | None = None
    ) -> list[str] | None:
        conditions = [
            self.model.id == account_id,
            self.model.user_id == user_id,
            self.model.deleted_at.is_(None),
        ]

        if workspace_id:
            conditions.append(self.model.workspace_id == workspace_id)

        stmt = select(self.model.stage_flow).where(*conditions)
        result = await self.db.execute(stmt)
        stage_flow = result.scalar_one_or_none()
        if stage_flow is None:
            return None
        return [item["stage"] for item in stage_flow]

    async def get_user_accounts(
        self, user_id: int, workspace_id: str | None = None
    ) -> list[dict]:
        conditions = [
            WhatsAppSession.to_number == int(10000000000),
            self.model.user_id == user_id,
            self.model.deleted_at.is_(None),
        ]

        if workspace_id:
            conditions.append(self.model.workspace_id == workspace_id)

        stmt = (
            select(
                self.model.id,
                self.model.user_id,
                self.model.workspace_id,
                self.model.name,
                self.model.phone_number,
                self.model.phone_number_id,
                self.model.waba_id,
                self.model.token,
                self.model.prompt,
                self.model.stage_flow,
                self.model.is_active,
                WhatsAppSession.id.label("session_id"),
                WhatsAppSession.to_number,
            )
            .join(WhatsAppSession, WhatsAppSession.account_id == self.model.id)
            .where(*conditions)
        )

        result = await self.db.execute(stmt)
        accounts = [dict(row) for row in result.mappings().all()]
        for account in accounts:
            account["stage_flow"] = _serialize_stage_flow(account.get("stage_flow"))
        return accounts

    async def get_account_by_session_id(self, session_id: int) -> dict | None:
        stmt = (
            select(self.model.phone_number_id, self.model.token)
            .join(WhatsAppSession, WhatsAppSession.account_id == self.model.id)
            .where(WhatsAppSession.id == session_id, self.model.deleted_at.is_(None))
        )
        result = await self.db.execute(stmt)
        account = result.mappings().one_or_none()
        if not account:
            return None
        return dict(account)

    async def update_account_prompt(
        self,
        user_id: int,
        account_id: int,
        data: WhatsAppAccountUpdate,
        workspace_id: str | None = None,
    ) -> dict | None:
        update_values = {}
        if data.prompt is not None:
            update_values["prompt"] = data.prompt
        if data.stage_flow is not None:
            update_values["stage_flow"] = _serialize_stage_flow(data.stage_flow)

        if not update_values:
            return await self.get_account(user_id, account_id, workspace_id)

        conditions = [
            self.model.id == account_id,
            self.model.user_id == user_id,
            self.model.deleted_at.is_(None),
        ]

        if workspace_id:
            conditions.append(self.model.workspace_id == workspace_id)

        stmt = update(self.model).where(*conditions).values(**update_values)
        await self.db.execute(stmt)
        await self.db.commit()
        return await self.get_account(user_id, account_id, workspace_id)

    async def soft_delete_account(
        self, user_id: int, account_id: int, workspace_id: str | None = None
    ) -> bool:
        now = datetime.now(timezone.utc)

        conditions = [
            self.model.id == account_id,
            self.model.user_id == user_id,
            self.model.deleted_at.is_(None),
        ]

        if workspace_id:
            conditions.append(self.model.workspace_id == workspace_id)

        stmt = (
            update(self.model)
            .where(*conditions)
            .values(deleted_at=now)
            .returning(self.model.id)
        )
        result = await self.db.execute(stmt)

        await self.db.execute(
            update(WhatsAppSession)
            .where(
                WhatsAppSession.account_id == account_id,
                WhatsAppSession.deleted_at.is_(None),
            )
            .values(deleted_at=now)
        )

        await self.db.execute(
            update(WhatsAppMessage)
            .where(
                exists().where(
                    WhatsAppSession.id == WhatsAppMessage.session_id,
                    WhatsAppSession.account_id == account_id,
                    WhatsAppSession.deleted_at.is_(None),
                ),
                WhatsAppMessage.deleted_at.is_(None),
            )
            .values(deleted_at=now)
        )
        await self.db.execute(
            delete(WhatsAppSessionSummary).where(
                exists().where(
                    WhatsAppSession.id == WhatsAppSessionSummary.session_id,
                    WhatsAppSession.account_id == account_id,
                    WhatsAppSession.deleted_at.is_(None),
                ),
            )
        )

        await self.db.commit()

        return result.scalar_one_or_none() is not None

    async def toggle_account_active(
        self, user_id: int, account_id: int, workspace_id: str | None = None
    ) -> dict | None:
        conditions = [
            self.model.id == account_id,
            self.model.user_id == user_id,
            self.model.deleted_at.is_(None),
        ]

        if workspace_id:
            conditions.append(self.model.workspace_id == workspace_id)

        stmt = (
            update(self.model)
            .where(*conditions)
            .values(is_active=~self.model.is_active)
            .returning(self.model.is_active)
        )
        result = await self.db.execute(stmt)
        await self.db.commit()

        return dict(result.mappings().one())
