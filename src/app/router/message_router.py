import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.controller.message_controller import (
    save_reaction_controller,
    send_llm_message_controller,
    send_message_controller,
    send_reaction_controller,
    send_template_controller,
    status_update,
)
from app.database.db_handler import get_db
from app.utils.middleware import CurrentUser, get_current_user
from app.validation.message_validation import (
    AssistantMessage,
    MessageCreate,
    ReactionSend,
    TemplateSend,
)

router = APIRouter(
    prefix="/message", tags=["WhatsApp Messages"], include_in_schema=True
)


@router.post("/send", include_in_schema=True)
async def send_message(
    request: Request, db: AsyncSession = Depends(get_db)
) -> JSONResponse:
    body_dict = await request.json()
    sandbox = body_dict.get("sandbox", False)

    # Sandbox mode: accept simple flat payload
    # { "sandbox": true, "from_number": "919999999999", "to_number": "918888888888", "message": "Hello" }
    if sandbox:
        data = MessageCreate(
            from_number=body_dict.get("from_number"),
            to_number=body_dict.get("to_number"),
            message=body_dict.get("message", "[Media]"),
            media_bytes=body_dict.get("media_bytes"),
            media_type=body_dict.get("media_type"),
            sandbox=True,
        )
        return await send_message_controller(data, db)

    # Normal mode: parse Meta webhook payload
    value = body_dict.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {})

    # Ignore status updates (sent/delivered/read receipts)
    if "statuses" in value:
        return await status_update(value.get("statuses", []), db)

    message = value.get("messages", [{}])[0]
    metadata = value.get("metadata", {})

    from_number = message.get("from")  # USER
    to_number = metadata.get("display_phone_number")  # BUSINESS
    # Extract message based on type
    msg_type = message.get("type")
    user_message = None
    media_id = None

    if msg_type == "text":
        user_message = message.get("text", {}).get("body")
    elif msg_type == "image":
        user_message = message.get("image", {}).get("caption", "[Image]")
        media_id = message.get("image", {}).get("id")
    elif msg_type == "video":
        user_message = message.get("video", {}).get("caption", "[Video]")
        media_id = message.get("video", {}).get("id")
    elif msg_type == "audio":
        user_message = "[Audio]"
        media_id = message.get("audio", {}).get("id")
    elif msg_type == "document":
        user_message = message.get("document", {}).get("caption", "[Document]")
        media_id = message.get("document", {}).get("id")
    elif msg_type == "sticker":
        user_message = "[Sticker]"
        media_id = message.get("sticker", {}).get("id")
    elif msg_type == "button":
        # Quick-reply button tap — use the button text so the LLM sees natural language
        user_message = message.get("button", {}).get("text")
    elif msg_type == "reaction":
        reaction = message.get("reaction", {})
        emoji = reaction.get("emoji", "")
        user_message = emoji if emoji else "[Reaction removed]"
        data = MessageCreate(
            from_number=to_number,
            to_number=from_number,
            message=user_message,
            meta_message_id=message.get("id"),
        )
        return await save_reaction_controller(data, db)

    if msg_type is None or user_message is None:
        return JSONResponse(content={"status": "ignored"})

    data = MessageCreate(
        from_number=to_number,
        to_number=from_number,
        message=user_message or "[Media]",
        media=media_id,
        meta_message_id=message.get("id"),
    )
    return await send_message_controller(data, db)


@router.get("/send", include_in_schema=False)
def read_root(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: int = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
):
    logging.info(f"hub.mode = {hub_mode}")
    logging.info(f"hub.verify_token = {hub_verify_token}")
    logging.info(f"hub.challenge = {hub_challenge}")

    return hub_challenge


@router.post("/{from_number}/send-template")
async def send_template(
    from_number: int,
    payload: TemplateSend,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    return await send_template_controller(from_number, payload, db)


@router.post("/assistant/send")
async def send_llm(
    data: AssistantMessage,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    return await send_llm_message_controller(current_user.id, data, db)


@router.post("/react")
async def send_reaction(
    data: ReactionSend,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    return await send_reaction_controller(current_user.id, data, db)
