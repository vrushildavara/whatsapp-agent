import json
import logging
import os
from datetime import datetime, timezone
from urllib.parse import urlparse

from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.model import (
    AssistantTool,
    WhatsAppAccount,
    WhatsAppMessage,
    WhatsAppSession,
)
from app.validation.message_validation import MessageCreate

logger = logging.getLogger(__name__)


class MessageService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.model = WhatsAppMessage

    async def check_account_active(self, from_number: int) -> bool:
        stmt = select(WhatsAppAccount.is_active).where(
            WhatsAppAccount.phone_number == from_number,
            WhatsAppAccount.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        row = result.scalar_one_or_none()
        return bool(row)

    # Save USER message
    async def save_user_message(
        self, data: MessageCreate, media_urls: list[str] | None = None
    ) -> tuple:
        logger.debug(
            "Saving user message | from=%s | to=%s", data.from_number, data.to_number
        )

        # rejected by the controller before this method is called
        stmt = select(WhatsAppAccount.id).where(
            WhatsAppAccount.phone_number == data.from_number,
            WhatsAppAccount.deleted_at.is_(None),
            WhatsAppAccount.is_active.is_(True),
        )

        result = await self.db.execute(stmt)
        account_id = result.scalar_one_or_none()

        if not account_id:
            logger.warning(
                "Rejected WhatsApp number (account not found or deleted) | phone_number=%s",
                data.from_number,
            )
            return None, None, "WhatsApp account is not registered"

        # Get or create session (only active sessions)
        stmt = (
            update(WhatsAppSession)
            .where(
                WhatsAppSession.account_id == account_id,
                WhatsAppSession.to_number == data.to_number,
                WhatsAppSession.deleted_at.is_(None),
            )
            .values(updated_at=datetime.now(timezone.utc))
            .returning(WhatsAppSession.id)
        )

        result = await self.db.execute(stmt)
        session_id = result.scalar_one_or_none()

        if not session_id:
            logger.info(
                "Session not found, creating new | account_id=%s | to=%s",
                account_id,
                data.to_number,
            )

            stmt = (
                insert(WhatsAppSession)
                .values(account_id=account_id, to_number=data.to_number)
                .returning(WhatsAppSession.id)
            )

            result = await self.db.execute(stmt)
            session_id = result.scalar_one()

        normalized_media = media_urls or None

        # Insert USER message with JSONB media
        stmt = (
            insert(self.model)
            .values(
                session_id=session_id,
                role="user",
                message=data.message,
                media=normalized_media,
                meta_message_id=data.meta_message_id,
            )
            .returning(self.model.id)
        )

        result = await self.db.execute(stmt)
        message_id = result.scalar_one()
        await self.db.commit()

        logger.info(
            "User message saved | session_id=%s | message_id=%s | media_count=%s",
            session_id,
            message_id,
            len(normalized_media) if normalized_media else 0,
        )

        return session_id, message_id, None

    #  Fetch pending user messages
    async def get_pending_user_messages(self, session_id: int) -> list[WhatsAppMessage]:
        logger.debug("Fetching pending user messages | session_id=%s", session_id)

        last_assistant_id_subquery = (
            select(func.coalesce(func.max(self.model.id), 0))
            .where(
                self.model.session_id == session_id,
                self.model.role == "assistant",
                self.model.deleted_at.is_(None),
            )
            .scalar_subquery()
        )

        stmt = (
            select(self.model)
            .where(
                self.model.session_id == session_id,
                self.model.role == "user",
                self.model.id > last_assistant_id_subquery,
                self.model.deleted_at.is_(None),
            )
            .order_by(self.model.created_at.asc())
        )

        result = await self.db.execute(stmt)
        messages = result.scalars().all()

        logger.debug(
            "Pending user messages fetched | session_id=%s | count=%s",
            session_id,
            len(messages),
        )

        return list(messages)

    #  Save ASSISTANT message
    async def save_assistant_message(
        self,
        session_id: int,
        message: str,
        media_urls: list[str] | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        meta_message_id: str | None = None,
    ) -> None:
        # Parse JSON if message contains structured data
        try:
            parsed = json.loads(message)
            if isinstance(parsed, dict) and any(k in parsed for k in ("message", "media", "audio", "documents")):
                text_message = parsed.get("message", "")
                media_from_llm = parsed.get("media", [])
                documents_from_llm = parsed.get("documents", [])
                audio_from_llm = parsed.get("audio", [])

                # Combine all media types into media field
                combined_media = []
                combined_media.extend(media_from_llm)
                combined_media.extend(
                    link for doc in documents_from_llm
                    if isinstance(doc, dict) and (link := doc.get("link"))
                )
                combined_media.extend(audio_from_llm)

                if combined_media:
                    media_urls = combined_media

                # Build tags based on media types present
                tags = []
                if audio_from_llm:
                    tags.append("[Audio]")
                if documents_from_llm:
                    tags.append("[Document]")
                if media_from_llm:
                    video_exts = {".mp4", ".webm", ".avi", ".mov", ".mkv"}
                    image_exts = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
                    has_video = any(
                        _get_url_ext(url) in video_exts for url in media_from_llm
                    )
                    has_image = any(
                        _get_url_ext(url) in image_exts for url in media_from_llm
                    )
                    if has_video:
                        tags.append("[Video]")
                    if has_image:
                        tags.append("[Image]")
                    if not has_video and not has_image:
                        tags.append("[Media]")

                if tags:
                    tag_prefix = "".join(tags)
                    message = f"{tag_prefix} {text_message}" if text_message else tag_prefix
                else:
                    message = text_message
        except (json.JSONDecodeError, AttributeError):
            pass

        normalized_media = media_urls or None

        logger.info(
            "Saving assistant message | session_id=%s | media_count=%s",
            session_id,
            len(normalized_media) if normalized_media else 0,
        )

        stmt = insert(self.model).values(
            session_id=session_id,
            role="assistant",
            message=message,
            media=normalized_media,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            meta_message_id=meta_message_id,
        )

        await self.db.execute(stmt)
        await self.db.commit()

    async def get_or_create_session(self, account_id: int, phone_number: int) -> dict:
        """Return existing session for phone_number, or create one if it doesn't exist."""
        from app.service.session_service import SessionService

        session_service = SessionService(self.db)
        session = await session_service.get_session_by_to_number(account_id, phone_number)
        if not session:
            session = await session_service.create_session_for_number(account_id, phone_number)
        assert session is not None
        return session

    async def save_template_to_session(
        self,
        account_id: int,
        phone_number: int,
        template_name: str,
        rendered_message: str,
    ) -> dict:
        """Get-or-create session for phone_number and save the sent template as an assistant message."""
        session = await self.get_or_create_session(account_id, phone_number)
        await self.save_assistant_message(
            session_id=session["id"],
            message=rendered_message or f"[Template: {template_name}]",
        )
        return session

    async def get_last_25_messages(self, session_id: int) -> list[WhatsAppMessage]:
        logger.debug("Fetching last 25 messages | session_id=%s", session_id)

        result = await self.db.execute(
            select(self.model)
            .where(
                self.model.session_id == session_id,
                self.model.role.in_(["user", "assistant"]),
                self.model.deleted_at.is_(None),
            )
            .order_by(self.model.created_at.desc())
            .limit(25)
        )

        messages = list(reversed(result.scalars().all()))

        logger.debug(
            "Fetched messages | session_id=%s | count=%s", session_id, len(messages)
        )

        return messages

    # Split messages into older + recent
    async def get_messages_for_context(
        self, session_id: int, window_size: int = 5
    ) -> tuple:
        logger.debug(
            "Building context window | session_id=%s | window_size=%s",
            session_id,
            window_size,
        )

        total_count = await self.db.scalar(
            select(func.count())
            .select_from(self.model)
            .where(
                self.model.session_id == session_id,
                self.model.role.in_(["user", "assistant"]),
                self.model.deleted_at.is_(None),
            )
        )

        recent_result = await self.db.execute(
            select(self.model)
            .where(
                self.model.session_id == session_id,
                self.model.role.in_(["user", "assistant"]),
                self.model.deleted_at.is_(None),
            )
            .order_by(self.model.created_at.desc())
            .limit(window_size)
        )
        recent_messages = list(reversed(recent_result.scalars().all()))

        older_messages = []
        if total_count and total_count > window_size:
            older_result = await self.db.execute(
                select(self.model)
                .where(
                    self.model.session_id == session_id,
                    self.model.role.in_(["user", "assistant"]),
                    self.model.deleted_at.is_(None),
                )
                .order_by(self.model.created_at.asc())
                .limit(total_count - window_size)
            )
            older_messages = older_result.scalars().all()

        logger.debug(
            "Context built | session_id=%s | older=%s | recent=%s",
            session_id,
            len(older_messages),
            len(recent_messages),
        )

        return older_messages, recent_messages

    # Get unsummarized messages
    async def get_unsummarized_messages(
        self, session_id: int, limit: int = 20
    ) -> list[dict]:
        logger.debug(
            "Fetching unsummarized messages | session_id=%s | limit=%s",
            session_id,
            limit,
        )

        result = await self.db.execute(
            select(
                self.model.role,
                self.model.message,
                self.model.media_text,
            )
            .where(
                self.model.session_id == session_id,
                self.model.role.in_(["user", "assistant"]),
                self.model.is_summarized.is_(False),
                self.model.deleted_at.is_(None),
            )
            .order_by(self.model.created_at.asc())
            .limit(limit)
        )

        rows = result.all()

        messages: list[dict] = []

        for role, message, media_text in rows:
            content = message or media_text
            if not content:
                continue

            messages.append(
                {
                    "role": role,
                    "content": content,
                }
            )

        logger.debug(
            "Unsummarized messages fetched | session_id=%s | count=%s",
            session_id,
            len(messages),
        )

        return messages

    async def get_account_details(self, from_number: int) -> tuple | None:
        logger.debug("Fetching account details | from_number=%s", from_number)

        stmt = select(WhatsAppAccount.token, WhatsAppAccount.phone_number_id).where(
            WhatsAppAccount.phone_number == from_number,
            WhatsAppAccount.deleted_at.is_(None),
        )

        result = await self.db.execute(stmt)
        row = result.one_or_none()

        if not row:
            logger.warning("Account details not found | from_number=%s", from_number)
            return None

        return row[0], row[1]

    async def get_access_token(self, from_number: int) -> str | None:
        logger.debug("Fetching access token | from_number=%s", from_number)

        stmt = select(WhatsAppAccount.token).where(
            WhatsAppAccount.phone_number == from_number,
            WhatsAppAccount.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_account_prompt(self, from_number: int) -> str | None:
        logger.debug("Fetching account prompt | from_number=%s", from_number)

        stmt = select(WhatsAppAccount.prompt).where(
            WhatsAppAccount.phone_number == from_number,
            WhatsAppAccount.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        prompt = result.scalar_one_or_none()
        if prompt is None:
            return None
        prompt = str(prompt).strip()
        return prompt or None

    async def get_active_tools(self, from_number: int, to_number: str, media_urls: list[str] | None = None) -> list[dict] | None:
        logger.debug("Fetching active tools | from_number=%s", from_number)

        stmt = (
            select(
                AssistantTool.name,
                AssistantTool.tool_type,
                AssistantTool.config,
                WhatsAppAccount.id.label("account_id"),
            )
            .join(WhatsAppAccount, WhatsAppAccount.id == AssistantTool.account_id)
            .where(
                WhatsAppAccount.phone_number == from_number,
                WhatsAppAccount.deleted_at.is_(None),
                AssistantTool.is_active.is_(True),
                AssistantTool.deleted_at.is_(None),
            )
        )
        result = await self.db.execute(stmt)
        rows = result.all()

        if not rows:
            return None

        tools = []
        for name, tool_type, config, account_id in rows:
            if not config:
                continue
            fn_name = name.lower().replace(" ", "_")
            if fn_name == "initiate_call":
                payload = _build_initiate_call_payload(config, to_number)
            elif fn_name == "send_reaction":
                payload = _build_send_reaction_payload(config, to_number, str(account_id))
            else:
                payload = _build_tool_payload(name, tool_type, config, to_number, media_urls)
            if payload:
                tools.append(payload)

        return tools or None


def _get_url_ext(url: str) -> str:
    """Return lowercase file extension from a URL, ignoring query strings."""
    return os.path.splitext(urlparse(url).path)[1].lower()


def _normalize_tool_schema(value: dict | list | str | int | bool | None) -> dict | list | str | int | bool | None:
    """Convert stored tool field config into Gemini-compatible JSON Schema."""
    if isinstance(value, list):
        return [_normalize_tool_schema(item) for item in value]

    if not isinstance(value, dict):
        return value

    schema: dict = {}
    for key, item in value.items():
        if key in {"name", "value"}:
            continue
        if key == "properties" and isinstance(item, list):
            schema[key] = {
                prop["name"]: _convert_field_to_property(prop)
                for prop in item
                if isinstance(prop, dict) and prop.get("name")
            }
            continue
        schema[key] = _normalize_tool_schema(item)
    return schema


def _convert_field_to_property(field: dict) -> dict:
    """Strip config-only keys and return a JSON Schema property object."""
    result = _normalize_tool_schema(field)
    return result if isinstance(result, dict) else {}


SESSION_PHONE_PLACEHOLDERS = {
    "{{session.to_number}}",
    "{{session.phone_number}}",
    "{{to_number}}",
}

SESSION_MEDIA_URL_PLACEHOLDERS = {
    "{{session.media_url}}",
    "{{media_url}}",
}


def _resolve_static_tool_value(value: str | int | bool | None, to_number: str, media_url: str | None = None) -> str | int | bool | None:
    if not isinstance(value, str):
        return value
    if value.strip() in SESSION_PHONE_PLACEHOLDERS:
        return str(to_number)
    for placeholder in SESSION_PHONE_PLACEHOLDERS:
        if placeholder in value:
            value = value.replace(placeholder, str(to_number))
    if media_url:
        if value.strip() in SESSION_MEDIA_URL_PLACEHOLDERS:
            return media_url
        for placeholder in SESSION_MEDIA_URL_PLACEHOLDERS:
            if placeholder in value:
                value = value.replace(placeholder, media_url)
    return value


def _build_tool_payload(
    name: str, tool_type: str, config: dict, to_number: str,
    media_urls: list[str] | None = None,
) -> dict | None:
    """Builds a structured tool payload with definition and execution sections."""
    media_url = media_urls[0] if media_urls else None
    url_value = _resolve_static_tool_value(config.get("url", ""), to_number, media_url)
    url: str = str(url_value) if url_value else ""
    description: str = config.get("description", "")
    method: str = config.get("method", "POST").upper()
    if not url:
        return None

    # Sanitize name for function declaration (lowercase, spaces → underscores)
    fn_name: str = name.lower().replace(" ", "_")

    # Build flat headers dict for execution (name → value)
    headers_config: dict = config.get("headers") or {}
    header_fields: list[dict] = headers_config.get("properties", [])
    execution_headers: dict = {
        f["name"]: f.get("value", "")
        for f in header_fields
        if isinstance(f, dict) and f.get("name")
    }

    # Build parameters from body config
    if tool_type == "knowledge":
        parameters: dict = {
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language query to search the knowledge base",
                }
            },
        }
        execution_body: list[dict] = []
    else:
        body_config: dict = config.get("body") or {}
        body_fields: list[dict] = body_config.get("properties", [])

        # Static fields (have a 'value') go into execution body; dynamic fields go to LLM params
        static_fields = [f for f in body_fields if isinstance(f, dict) and f.get("value") is not None]
        dynamic_fields = [f for f in body_fields if isinstance(f, dict) and f.get("value") is None]

        execution_body = [
            {
                "name": f["name"],
                "value": _resolve_static_tool_value(f["value"], to_number, media_url),
            }
            for f in static_fields
            if f.get("name")
        ]

        dynamic_names = {f["name"] for f in dynamic_fields if f.get("name")}
        required = [r for r in body_config.get("required", []) if r in dynamic_names]

        parameters = {
            "type": "object",
            "required": required,
            "properties": {
                f["name"]: _convert_field_to_property(f)
                for f in dynamic_fields
                if f.get("name")
            },
        }

    execution: dict = {
        "type": "http",
        "url": url,
        "method": method,
        "headers": execution_headers,
    }
    if execution_body:
        execution["body"] = execution_body

    return {
        "name": fn_name,
        "definition": {
            "functionDeclarations": [
                {
                    "name": fn_name,
                    "description": description,
                    "parameters": parameters,
                }
            ]
        },
        "execution": execution,
    }


def _build_initiate_call_payload(config: dict, to_number: str) -> dict | None:
    """Hardcoded builder for the initiate_call tool.

    Injects to_number from the session (not AI-generated) and reads all credentials
    from the tool config stored in DB.
    """
    url: str = config.get("url", "")
    if not url:
        return None

    description: str = config.get("description", "Places an outbound voice call to the user.")

    # Static headers from config
    headers_config: dict = config.get("headers") or {}
    header_fields: list[dict] = headers_config.get("properties", [])
    execution_headers: dict = {
        f["name"]: f.get("value", "")
        for f in header_fields
        if isinstance(f, dict) and f.get("name")
    }

    # Body: phoneNumber always injected from session; static fields from config; dynamic fields for LLM
    body_config: dict = config.get("body") or {}
    body_fields: list[dict] = body_config.get("properties", [])

    static_fields = [f for f in body_fields if isinstance(f, dict) and f.get("value") is not None]
    dynamic_fields = [f for f in body_fields if isinstance(f, dict) and f.get("value") is None]

    execution_body: list[dict] = [{"name": "phoneNumber", "value": to_number}]
    for f in static_fields:
        if f.get("name"):
            execution_body.append({"name": f["name"], "value": f["value"]})

    dynamic_names = {f["name"] for f in dynamic_fields if f.get("name")}
    required = [r for r in body_config.get("required", []) if r in dynamic_names]
    parameters = {
        "type": "object",
        "required": required,
        "properties": {
            f["name"]: _convert_field_to_property(f)
            for f in dynamic_fields
            if f.get("name")
        },
    }

    return {
        "name": "initiate_call",
        "definition": {
            "functionDeclarations": [
                {
                    "name": "initiate_call",
                    "description": description,
                    "parameters": parameters,
                }
            ]
        },
        "execution": {
            "type": "http",
            "url": url,
            "method": "POST",
            "headers": execution_headers,
            "body": execution_body,
        },
    }


def _build_send_reaction_payload(config: dict, to_number: str, account_id: str) -> dict | None:
    """Hardcoded builder for the send_reaction tool.

    Injects account_id and to_number from session context; LLM provides message_id and emoji.
    """
    url: str = config.get("url", "")
    if not url:
        return None

    description: str = config.get("description", "Send an emoji reaction to the user's WhatsApp message.")

    headers_config: dict = config.get("headers") or {}
    header_fields: list[dict] = headers_config.get("properties", [])
    execution_headers: dict = {
        f["name"]: f.get("value", "")
        for f in header_fields
        if isinstance(f, dict) and f.get("name")
    }

    return {
        "name": "send_reaction",
        "definition": {
            "functionDeclarations": [
                {
                    "name": "send_reaction",
                    "description": description,
                    "parameters": {
                        "type": "object",
                        "required": ["message_id", "emoji"],
                        "properties": {
                            "message_id": {
                                "type": "string",
                                "description": "The wamid of the WhatsApp message to react to.",
                            },
                            "emoji": {
                                "type": "string",
                                "description": "Unicode emoji to send as reaction. Pass empty string to remove a reaction.",
                            },
                        },
                    },
                }
            ]
        },
        "execution": {
            "type": "http",
            "url": url,
            "method": "POST",
            "headers": execution_headers,
            "body": [
                {"name": "account_id", "value": account_id},
                {"name": "to_number", "value": to_number},
            ],
        },
    }
