from datetime import datetime, timezone

from sqlalchemy import String, cast, delete, exists, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.model import (
    WhatsAppAccount,
    WhatsAppMessage,
    WhatsAppSession,
    WhatsAppSessionSummary,
)
from app.service.mem0_service import Mem0Service


class SessionService:
    def __init__(self, db: AsyncSession) -> None:
        self.model = WhatsAppSession
        self.db = db
        self.mem0_service = Mem0Service()

    DUMMY_NUMBER = 10000000000

    async def create_session(self, account_id: int, user_id: int) -> dict | None:
        # Check account exists and is active (not deleted)
        stmt = select(WhatsAppAccount.id).where(
            WhatsAppAccount.id == account_id,
            WhatsAppAccount.user_id == user_id,
            WhatsAppAccount.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        if not result.scalar_one_or_none():
            return None

        # Return existing dummy session if one already exists for this account
        existing_stmt = select(
            self.model.id,
            self.model.account_id,
            self.model.to_number,
        ).where(
            self.model.account_id == account_id,
            self.model.to_number == self.DUMMY_NUMBER,
            self.model.deleted_at.is_(None),
        )
        existing = await self.db.execute(existing_stmt)
        existing_session = existing.mappings().one_or_none()
        if existing_session:
            return dict(existing_session)

        stmt = (
            insert(self.model)
            .values(account_id=account_id, to_number=self.DUMMY_NUMBER)
            .returning(
                self.model.id,
                self.model.account_id,
                self.model.to_number,
            )
        )

        result = await self.db.execute(stmt)
        await self.db.commit()

        return dict(result.mappings().one())

    async def create_session_for_number(
        self, account_id: int, to_number: int
    ) -> dict | None:
        """Create (or return existing) session for a real `to_number`."""
        stmt = (
            insert(self.model)
            .values(account_id=account_id, to_number=to_number)
            .returning(
                self.model.id,
                self.model.account_id,
                self.model.to_number,
            )
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return dict(result.mappings().one())

    async def get_session(self, user_id: int, session_id: int) -> dict | None:
        stmt = (
            select(
                self.model.id,
                self.model.account_id,
                self.model.to_number,
                self.model.current_stage,
            )
            .join(WhatsAppAccount, self.model.account_id == WhatsAppAccount.id)
            .where(
                self.model.id == session_id,
                WhatsAppAccount.user_id == user_id,
                self.model.deleted_at.is_(None),
            )
        )
        result = await self.db.execute(stmt)

        session = result.mappings().one_or_none()
        if not session:
            return None

        return dict(session)

    async def get_session_by_to_number(
        self, account_id: int, to_number: int
    ) -> dict | None:
        stmt = select(
            self.model.id,
            self.model.account_id,
            self.model.to_number,
            self.model.current_stage,
        ).where(
            self.model.account_id == account_id,
            self.model.to_number == to_number,
            self.model.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        session = result.mappings().one_or_none()
        if not session:
            return None
        return dict(session)

    async def get_all_sessions(
        self,
        user_id: int,
        account_id: int,
        page: int,
        limit: int,
        search: str | None = None,
        stage_search: str | None = None,
    ) -> dict:
        # Base where conditions
        where_conditions = [
            self.model.account_id == account_id,
            self.model.deleted_at.is_(None),
            self.model.to_number != self.DUMMY_NUMBER,  # Exclude dummy sessions
            WhatsAppAccount.user_id == user_id,
        ]

        # Add search filter if provided
        if search:
            where_conditions.append(
                cast(self.model.to_number, String).ilike(f"%{search}%")
            )

        # Add stage search filter if provided
        if stage_search:
            where_conditions.append(self.model.current_stage.ilike(f"%{stage_search}%"))

        # Get total count
        count_stmt = (
            select(func.count(self.model.id))
            .join(WhatsAppAccount, self.model.account_id == WhatsAppAccount.id)
            .where(*where_conditions)
        )
        total_results = (await self.db.scalar(count_stmt)) or 0

        # Calculate pagination
        skip = (page - 1) * limit
        total_pages = (total_results + limit - 1) // limit

        # Get sessions
        stmt = (
            select(
                self.model.id,
                self.model.to_number,
                self.model.created_at,
                self.model.current_stage,
                self.model.updated_at,
            )
            .join(WhatsAppAccount, self.model.account_id == WhatsAppAccount.id)
            .where(*where_conditions)
            .order_by(self.model.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(stmt)

        results = [
            {
                "_id": str(row["id"]),
                "toNumber": row["to_number"],
                "currentStage": row["current_stage"] or "",
                "createdAt": row["created_at"].isoformat(),
                "updatedAt": row["updated_at"].isoformat(),
            }
            for row in result.mappings().all()
        ]

        return {
            "results": results,
            "page": page,
            "limit": limit,
            "totalPages": total_pages,
            "totalResults": total_results,
        }

    async def get_session_history(
        self, user_id: int, session_id: int
    ) -> list[dict] | None:
        stmt = (
            select(
                WhatsAppMessage.role,
                WhatsAppMessage.message,
                WhatsAppMessage.media,
                WhatsAppMessage.created_at,
            )
            .join(WhatsAppMessage.session)
            .join(WhatsAppAccount, WhatsAppSession.account_id == WhatsAppAccount.id)
            .where(
                WhatsAppMessage.session_id == session_id,
                WhatsAppAccount.user_id == user_id,
                WhatsAppSession.deleted_at.is_(None),
                WhatsAppMessage.deleted_at.is_(None),
            )
            .order_by(WhatsAppMessage.created_at.asc())
        )

        result = await self.db.execute(stmt)
        return [
            {**dict(row), "created_at": row["created_at"].isoformat()}
            for row in result.mappings().all()
        ]

    async def delete_session_history(self, user_id: int, session_id: int) -> bool:
        now = datetime.now(timezone.utc)
        stmt = (
            update(WhatsAppMessage)
            .where(
                WhatsAppMessage.session_id == session_id,
                WhatsAppMessage.deleted_at.is_(None),
                exists().where(
                    WhatsAppSession.id == session_id,
                    WhatsAppSession.deleted_at.is_(None),
                    exists().where(
                        WhatsAppAccount.id == WhatsAppSession.account_id,
                        WhatsAppAccount.user_id == user_id,
                    ),
                ),
            )
            .values(deleted_at=now)
            .returning(WhatsAppMessage.session_id)
        )
        result = await self.db.execute(stmt)
        deleted = result.first() is not None

        await self.db.execute(
            delete(WhatsAppSessionSummary).where(
                WhatsAppSessionSummary.session_id == session_id
            )
        )

        # reset current stage for the session
        await self.db.execute(
            update(WhatsAppSession)
            .where(WhatsAppSession.id == session_id)
            .values(current_stage=None)
        )

        await self.db.commit()

        # Delete Mem0 session memories
        self.mem0_service.delete_memories(session_id)

        return deleted
