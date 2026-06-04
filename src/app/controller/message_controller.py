import asyncio
import base64
import json
import logging
import uuid

from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import ErrorResponse, success_response
from app.service.account_service import AccountService
from app.service.broadcast_service import BroadcastService
from app.service.mem0_service import Mem0Service
from app.service.message_service import MessageService
from app.service.s3_service import S3Service
from app.service.template_service import template_service
from app.service.whatsapp_service import WhatsAppService
from app.utils.media_utils import (
    GEMINI_SUPPORTED_MIME_TYPES,
    detect_media_type,
    mime_to_hint_ext,
    to_jpeg_if_needed,
)
from app.utils.redis_manager import get_redis_client
from app.utils.session_processor import enqueue_and_trigger
from app.validation.message_validation import (
    AssistantMessage,
    MessageCreate,
    ReactionSend,
    TemplateSend,
)

logger = logging.getLogger(__name__)


async def send_message_controller(
    data: MessageCreate, db: AsyncSession
) -> JSONResponse:
    service = MessageService(db)
    s3_service = S3Service(db)

    # Early exit: check account status before any media work
    if not await service.check_account_active(data.from_number):
        logger.info("Account is inactive | phone_number=%s", data.from_number)
        raise ErrorResponse(400, "Account is inactive")

    media_urls = []
    first_media_mime: str | None = None

    # Handle media in sandbox mode (media_bytes)
    if data.sandbox and data.media_bytes and len(data.media_bytes) > 0:
        logger.info("Processing sandbox media | count=%d", len(data.media_bytes))
        for idx, media_b64 in enumerate(data.media_bytes):
            try:
                media_content = base64.b64decode(media_b64)

                # Use provided media_type hint or detect from bytes
                if data.media_type:
                    mime_type = data.media_type
                    ext = mime_to_hint_ext(mime_type) or "bin"
                else:
                    # Fallback: try detect_media_type from media_utils
                    try:
                        hint_ext = (
                            mime_to_hint_ext(data.media_type) if data.media_type else ""
                        )
                        _, ext, mime_type, _ = detect_media_type(
                            media_content, hint_ext
                        )
                    except Exception:
                        mime_type, ext = "application/octet-stream", "bin"

                file_name = f"{uuid.uuid4()}.{ext}"
                media_s3_url = await s3_service.upload_media(
                    media_content, file_name, mime_type
                )
                if media_s3_url:
                    media_urls.append(media_s3_url)
                    if first_media_mime is None:
                        first_media_mime = mime_type
                    logger.info(
                        "Sandbox media uploaded | index=%d | mime=%s | url=%s",
                        idx,
                        mime_type,
                        media_s3_url,
                    )
                else:
                    logger.error("S3 upload failed | index=%d", idx)
            except Exception as e:
                logger.error(
                    "Failed to process sandbox media | index=%d | error=%s",
                    idx,
                    e,
                    exc_info=True,
                )

    # Download media from WhatsApp (if exists) — skip in sandbox mode
    elif data.media and not data.sandbox:
        access_token = await service.get_access_token(data.from_number)
        if not access_token:
            logger.error("Access token not found | from_number=%s", data.from_number)
        else:
            result = await WhatsAppService.download_media(data.media, access_token)
            if result:
                media_content, mime_type = result
                ext = mime_to_hint_ext(mime_type) or "bin"
                file_name = f"{uuid.uuid4()}.{ext}"
                media_s3_url = await s3_service.upload_media(
                    media_content, file_name, mime_type
                )
                if media_s3_url:
                    media_urls.append(media_s3_url)
                    first_media_mime = mime_type
                    logger.info(
                        "WhatsApp media uploaded | mime=%s | url=%s",
                        mime_type,
                        media_s3_url,
                    )

    # Save USER message immediately
    logger.info(
        "Saving user message | media_urls_count=%d | media_urls=%s",
        len(media_urls),
        media_urls,
    )
    session_id, message_id, error = await service.save_user_message(data, media_urls)
    if error:
        raise ErrorResponse(404, error)

    # Trigger background metadata extraction for supported media types
    if media_urls and first_media_mime in GEMINI_SUPPORTED_MIME_TYPES:
        asyncio.create_task(
            s3_service.extract_media_metadata(
                media_urls[0], message_id, first_media_mime
            )
        )

    # Add to Mem0 memory
    mem0_service = Mem0Service()
    mem0_service.add_memory([data.message], session_id)

    redis = get_redis_client()
    lock_key = f"s:{session_id}:lock"
    if redis and await redis.exists(lock_key):
        logger.info(
            "Session processor active, skipping enqueue | session_id=%s", session_id
        )
    else:
        await enqueue_and_trigger(
            session_id,
            data.from_number,
            data.to_number,
            media_urls,
            sandbox=data.sandbox,
        )

    return success_response(
        data={"session_id": session_id, "media_urls": media_urls},
        message="Message received",
        status_code=200,
    )


async def send_llm_message_controller(
    user_id: int, data: AssistantMessage, db: AsyncSession
) -> JSONResponse:
    account_service = AccountService(db)
    service = MessageService(db)
    s3_service = S3Service(db)
    account_info = await account_service.get_account(user_id, data.account_id)
    if not account_info:
        raise ErrorResponse(404, "WhatsApp account not found")

    account_active = await service.check_account_active(account_info["phone_number"])
    if not account_active:
        raise ErrorResponse(404, "WhatsApp account inactive")

    phone_number_id = account_info["phone_number_id"]
    token = account_info["token"]

    # --- Template path ---
    if data.template:
        # Serialize components once — used for both API call and history rendering
        serialized_components = (
            [c.model_dump(exclude_none=True) for c in data.template.components]
            if data.template.components
            else None
        )

        # Render template text for message history
        template_display = f"[Template] {data.template.name}"
        waba_id = account_info.get("waba_id")
        if waba_id:
            try:
                template_data = await template_service.get_template_by_name(
                    waba_id=waba_id,
                    access_token=token,
                    template_name=data.template.name,
                    language=data.template.language,
                )
                if template_data:
                    template_display = template_service.render_template_message(
                        template_data, serialized_components
                    )
            except Exception:
                logger.warning(
                    "Could not fetch template for history render | template=%s",
                    data.template.name,
                )

        if not data.sandbox:
            result = await WhatsAppService.send_template_message(
                phone_number_id=phone_number_id,
                to_number=str(data.to_number),
                template_name=data.template.name,
                language=data.template.language,
                access_token=token,
                components=serialized_components,
            )
            if result and result.get("status") == "failed":
                raise ErrorResponse(500, result["error"])
        else:
            logger.info(
                "Sandbox mode | skipping template send | to_number=%s", data.to_number
            )

        # Only create session and save message after successful send
        session = await service.save_template_to_session(
            account_id=data.account_id,
            phone_number=data.to_number,
            template_name=data.template.name,
            rendered_message=template_display,
        )
        if not session:
            raise ErrorResponse(500, "Failed to save template to session")

        return success_response(
            data={"session_id": session["id"]},
            message="Template dispatched",
            status_code=200,
        )

    # --- Message path ---
    session = await service.get_or_create_session(data.account_id, data.to_number)
    session_id = session["id"]

    media_urls = []
    document_urls = []
    audio_urls = []
    if data.media_bytes:
        for idx, media_b64 in enumerate(data.media_bytes):
            try:
                media_content = base64.b64decode(media_b64)
                size_mb = len(media_content) / (1024 * 1024)

                hint_name = (
                    (data.media_names or [])[idx]
                    if data.media_names and idx < len(data.media_names)
                    else ""
                )
                hint_ext = (
                    hint_name.rsplit(".", 1)[-1].lower() if "." in hint_name else ""
                )

                media_content, hint_ext = to_jpeg_if_needed(media_content, hint_ext)

                file_type, ext, content_type, size_limit_mb = detect_media_type(
                    media_content, hint_ext
                )

                if size_mb > size_limit_mb:
                    raise ErrorResponse(
                        400,
                        f"File size exceeds {size_limit_mb}MB limit for {file_type} "
                        f"(current: {size_mb:.2f}MB)",
                    )

                file_name = f"{uuid.uuid4()}.{ext}"
                s3_url = await s3_service.upload_media(
                    media_content, file_name, content_type
                )

                if s3_url:
                    if file_type == "document":
                        document_urls.append(s3_url)
                    elif file_type == "audio":
                        audio_urls.append(s3_url)
                    else:
                        media_urls.append(s3_url)
                    logger.info(
                        "Media uploaded to S3 | type=%s | index=%d | size=%.2fMB | url=%s",
                        file_type,
                        idx,
                        size_mb,
                        s3_url,
                    )
                else:
                    logger.error("Failed to upload media to S3 | index=%d", idx)

            except ErrorResponse:
                raise
            except Exception as e:
                logger.error(
                    "Failed to process media bytes | index=%d | error=%s",
                    idx,
                    e,
                    exc_info=True,
                )
                raise ErrorResponse(400, f"Failed to process media: {str(e)}")

    if media_urls or document_urls or audio_urls:
        payload_obj: dict = {}
        if data.message:
            payload_obj["message"] = data.message
        if media_urls:
            payload_obj["media"] = media_urls
        if document_urls:
            payload_obj["documents"] = [
                {"link": url, "filename": url.split("/")[-1]} for url in document_urls
            ]
        if audio_urls:
            payload_obj["audio"] = audio_urls
        send_payload = json.dumps(payload_obj)
    else:
        send_payload = data.message or ""

    all_media = media_urls + document_urls + audio_urls

    if not data.sandbox:
        sent = await WhatsAppService.send_message(
            phone_number_id=phone_number_id,
            to_number=str(data.to_number),
            message=send_payload,
            access_token=token,
        )
        if not sent:
            logger.error(
                "Failed to send message | session_id=%s | to=%s",
                session_id,
                data.to_number,
            )
            raise ErrorResponse(500, "WhatsApp send failed")
    else:
        logger.info("Sandbox mode | skipping WhatsApp send | session_id=%s", session_id)

    await service.save_assistant_message(
        session_id=session_id, message=send_payload, media_urls=all_media
    )

    return success_response(
        data={
            "session_id": session_id,
            "media_urls": media_urls,
            "document_urls": document_urls,
            "audio_urls": audio_urls,
        },
        message="Message dispatched",
        status_code=200,
    )


async def send_template_controller(
    from_number: int, payload: TemplateSend, db: AsyncSession
) -> JSONResponse:
    service = MessageService(db)
    account_details = await service.get_account_details(from_number)
    if not account_details:
        raise ErrorResponse(404, "Account not found")

    token, phone_number_id = account_details

    # Serialize components if provided
    serialized_components = (
        [c.model_dump(exclude_none=True) for c in payload.components]
        if payload.components
        else None
    )

    result = await WhatsAppService.send_template_message(
        phone_number_id=phone_number_id,
        to_number=payload.to_number,
        template_name=payload.template_name,
        language=payload.language,
        access_token=token,
        components=serialized_components,
    )

    if result and result.get("status") == "failed":
        raise ErrorResponse(500, result.get("error", "Template send failed"))

    return success_response(
        data=result,
        message="Template sent successfully",
        status_code=200,
    )


async def save_reaction_controller(
    data: MessageCreate, db: AsyncSession
) -> JSONResponse:
    service = MessageService(db)
    if not await service.check_account_active(data.from_number):
        logger.info("Account inactive | phone_number=%s", data.from_number)
        raise ErrorResponse(400, "Account is inactive")
    session_id, _, error = await service.save_user_message(data, [])
    if error:
        raise ErrorResponse(404, error)
    return success_response(
        data={"session_id": session_id}, message="Reaction stored", status_code=200
    )


async def send_reaction_controller(
    user_id: int, data: ReactionSend, db: AsyncSession
) -> JSONResponse:
    account_service = AccountService(db)
    service = MessageService(db)
    account_info = await account_service.get_account(user_id, data.account_id)
    if not account_info:
        raise ErrorResponse(404, "WhatsApp account not found")
    if not await service.check_account_active(account_info["phone_number"]):
        raise ErrorResponse(404, "WhatsApp account inactive")

    if not data.sandbox:
        success = await WhatsAppService.send_reaction(
            phone_number_id=account_info["phone_number_id"],
            to_number=str(data.to_number),
            message_id=data.message_id,
            emoji=data.emoji,
            access_token=account_info["token"],
        )
        if not success:
            raise ErrorResponse(500, "WhatsApp reaction send failed")
    else:
        logger.info("Sandbox mode | skipping reaction send | to=%s", data.to_number)

    return success_response(data={}, message="Reaction sent", status_code=200)


async def status_update(statuses: list, db: AsyncSession) -> JSONResponse:
    broadcast = BroadcastService(db)
    # Handle broadcast delivery status updates

    asyncio.create_task(broadcast.handle_broadcast_status_update(statuses))
    return JSONResponse(content={"status": "ignored"})
