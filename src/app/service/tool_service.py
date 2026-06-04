import logging
from datetime import datetime, timezone

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import ErrorResponse
from app.models.model import AssistantTool
from app.validation.tool_validation import AssistantToolCreate, AssistantToolUpdate

logger = logging.getLogger(__name__)


class ToolService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.model = AssistantTool

    async def get_tool_by_type(self, account_id: int, tool_type: str) -> dict | None:
        stmt = select(
            self.model.id,
            self.model.account_id,
            self.model.name,
            self.model.tool_type,
            self.model.config,
            self.model.is_active,
            self.model.created_at,
            self.model.updated_at,
        ).where(
            self.model.account_id == account_id,
            self.model.tool_type == tool_type,
            self.model.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        row = result.mappings().one_or_none()
        return dict(row) if row else None

    async def get_tool_by_name(
        self, account_id: int, name: str, exclude_tool_id: int | None = None
    ) -> dict | None:
        stmt = select(self.model.id).where(
            self.model.account_id == account_id,
            self.model.name == name,
            self.model.deleted_at.is_(None),
        )
        if exclude_tool_id is not None:
            stmt = stmt.where(self.model.id != exclude_tool_id)
        result = await self.db.execute(stmt)
        row = result.mappings().one_or_none()
        return dict(row) if row else None

    async def create_tool(self, account_id: int, data: AssistantToolCreate) -> dict:
        config = data.config

        stmt = (
            insert(self.model)
            .values(
                account_id=account_id,
                name=data.name,
                tool_type=data.tool_type,
                config=config,
                is_active=data.is_active,
            )
            .returning(
                self.model.id,
                self.model.account_id,
                self.model.name,
                self.model.tool_type,
                self.model.config,
                self.model.is_active,
                self.model.created_at,
                self.model.updated_at,
            )
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return dict(result.mappings().one())

    async def get_tool(self, account_id: int, tool_id: int) -> dict | None:
        stmt = select(
            self.model.id,
            self.model.account_id,
            self.model.name,
            self.model.tool_type,
            self.model.config,
            self.model.is_active,
            self.model.created_at,
            self.model.updated_at,
        ).where(
            self.model.id == tool_id,
            self.model.account_id == account_id,
            self.model.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        row = result.mappings().one_or_none()
        return dict(row) if row else None

    async def get_account_tools(self, account_id: int) -> list[dict]:
        stmt = select(
            self.model.id,
            self.model.account_id,
            self.model.name,
            self.model.tool_type,
            self.model.config,
            self.model.is_active,
            self.model.created_at,
            self.model.updated_at,
        ).where(
            self.model.account_id == account_id,
            self.model.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        return [dict(row) for row in result.mappings().all()]

    async def update_tool(
        self, account_id: int, tool_id: int, data: AssistantToolUpdate, existing: dict
    ) -> dict | None:
        update_values: dict = {"updated_at": datetime.now(timezone.utc)}

        if data.name is not None:
            update_values["name"] = data.name
        if data.is_active is not None:
            update_values["is_active"] = data.is_active

        if data.config is not None:
            tool_type = existing["tool_type"]
            current_config = dict(existing["config"])

            if tool_type == "api_request":
                merged = dict(current_config)
                for field in ("url", "method", "description", "headers", "body"):
                    if field in data.config:
                        merged[field] = data.config[field]
                update_values["config"] = merged
            elif tool_type == "knowledge":
                new_file_ids = data.config.get("file_ids")
                if not isinstance(new_file_ids, list) or not new_file_ids:
                    raise ErrorResponse(
                        422,
                        "knowledge config update must include a non-empty 'file_ids' list",
                    )
                current_file_ids = list(current_config.get("file_ids", []))
                current_file_ids.extend(new_file_ids)
                update_values["config"] = {**current_config, "file_ids": current_file_ids}

        stmt = (
            update(self.model)
            .where(
                self.model.id == tool_id,
                self.model.account_id == account_id,
                self.model.deleted_at.is_(None),
            )
            .values(**update_values)
        )
        await self.db.execute(stmt)
        await self.db.commit()
        return await self.get_tool(account_id, tool_id)

    async def soft_delete_tool(self, account_id: int, tool_id: int) -> bool:
        stmt = (
            update(self.model)
            .where(
                self.model.id == tool_id,
                self.model.account_id == account_id,
                self.model.deleted_at.is_(None),
            )
            .values(deleted_at=datetime.now(timezone.utc))
            .returning(self.model.id)
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.scalar_one_or_none() is not None
