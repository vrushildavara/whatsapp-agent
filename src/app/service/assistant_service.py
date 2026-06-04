import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db_handler import get_db
from app.prompt.system_prompt import get_system_prompt
from app.service.llm_service import LLMService
from app.service.mem0_service import Mem0Service
from app.service.message_service import MessageService
from app.service.summary_service import SummaryService
from app.service.whatsapp_service import WhatsAppService

logger = logging.getLogger(__name__)


def _build_llm_input(messages, exclude_last_user: bool = False) -> str:
    """
    Build short-term context from unsummarized messages (≤20)
    If exclude_last_user=True, skip the last user message to avoid duplication
    Includes media_text if available
    """
    if exclude_last_user and messages:
        # Find last user message and exclude it
        for i in range(len(messages) - 1, -1, -1):
            role = (
                messages[i].get("role")
                if isinstance(messages[i], dict)
                else messages[i].role
            )
            if role == "user":
                messages = messages[:i] + messages[i + 1 :]
                break

    result = []
    for msg in messages:
        # Handle both dict and object formats
        if isinstance(msg, dict):
            role = msg.get("role", "")
            content = msg.get("content", "")
            if content:
                result.append(f"{role.upper()}: {content}")
        else:
            if msg.message:
                text = f"{msg.role.upper()}: {msg.message}"
                if msg.media_text:
                    text += f" [Image: {msg.media_text}]"
                result.append(text)

    return "\n".join(result)


async def generate_assistant_response(
    session_id: int,
    db: AsyncSession,
    from_number: int,
    to_number: str,
    media_urls: list[str] | None = None,
    redis_client=None,
    sandbox: bool = False,
) -> None:
    """
    Actual assistant generation logic.
    Called ONLY after debounce settles.
    """
    service = MessageService(db)
    mem0_service = Mem0Service()

    # Try summarizing completed chunk (background)
    asyncio.create_task(_summarize_in_background(session_id))

    # Try stage labeling (background)
    asyncio.create_task(_label_stage_in_background(session_id))

    # Fetch CURRENT unsummarized messages (≤20)
    recent_messages = await service.get_unsummarized_messages(
        session_id=session_id, limit=20
    )

    if not recent_messages:
        logger.debug("No recent messages found for session_id=%s", session_id)
        return

    # Get pending user messages (not yet responded to)
    pending_messages = await service.get_pending_user_messages(session_id)

    if not pending_messages:
        logger.debug("No pending messages for session_id=%s", session_id)
        return

    # Combine all pending messages as current user input
    current_user_message = "\n".join(
        msg.message for msg in pending_messages if msg.message
    )

    # Build context excluding the current message(s)
    short_term_context = _build_llm_input(recent_messages, exclude_last_user=True)

    # Use current message as query if context is empty
    query = short_term_context if short_term_context.strip() else current_user_message
    memories = mem0_service.search_memories(session_id=session_id, query=query)

    summary = await SummaryService.get_summary(db, session_id)

    account_prompt = await service.get_account_prompt(from_number)
    active_tools = await service.get_active_tools(from_number, to_number, media_urls)

    if active_tools:
        tool_names = [t.get("name") for t in active_tools]
        logger.info("Tools loaded | session_id=%s | tools=%s", session_id, tool_names)

    system_prompt = get_system_prompt(
        short_term_context=short_term_context,
        summary=summary,
        memories=memories,
        account_prompt=account_prompt,
    )
    if media_urls:
        logger.info(
            "Sending %d image(s) to LLM | session_id=%s",
            len(media_urls),
            session_id,
        )
    account_details = await service.get_account_details(from_number)

    if not account_details:
        logger.error("Account details not found | from_number=%s", from_number)
        return

    token, phone_number_id = account_details

    if not sandbox and (not token or not phone_number_id):
        logger.error(
            "Missing WhatsApp credentials | token=%s | phone_number_id=%s",
            bool(token),
            phone_number_id,
        )
        return

    if not sandbox:
        last_wamid = next(
            (
                m.meta_message_id
                for m in reversed(pending_messages)
                if m.meta_message_id
            ),
            None,
        )
        if last_wamid:
            await WhatsAppService.send_typing_indicator(
                phone_number_id=phone_number_id,
                message_id=last_wamid,
                access_token=token,
            )
    # Generate assistant response
    llm_response, input_tokens, output_tokens = await LLMService.generate_response(
        system_prompt=system_prompt,
        user_message=current_user_message,
        media_urls=media_urls,
        tools=active_tools,
    )

    # ignoring llm response if lock key exists.
    lock_key = f"s:{session_id}:lock"
    if redis_client and not await redis_client.exists(lock_key):
        logger.info("Cancelled after LLM call | session=%s", session_id)
        return

    # Send response to WhatsApp — skip in sandbox mode
    meta_message_id: str | None = None
    if not sandbox:
        logger.info(
            "Attempting to send WhatsApp message | phone_number_id=%s | to_number=%s | message_length=%s",
            phone_number_id,
            to_number,
            len(llm_response),
        )

        meta_message_id = await WhatsAppService.send_message(
            phone_number_id=phone_number_id,
            to_number=to_number,
            message=llm_response,
            access_token=token,
        )
        if meta_message_id:
            logger.info(
                "WhatsApp message sent successfully | session_id=%s | meta_message_id=%s",
                session_id,
                meta_message_id,
            )
        else:
            logger.error(
                "Failed to send WhatsApp message | session_id=%s | to_number=%s",
                session_id,
                to_number,
            )
    else:
        logger.info(
            "Sandbox mode | LLM reply saved, WhatsApp send skipped | session_id=%s",
            session_id,
        )

    # Save ASSISTANT message with meta_message_id from Meta API
    await service.save_assistant_message(
        session_id=session_id,
        message=llm_response,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        meta_message_id=meta_message_id,
    )

    # Try summarizing again (background)
    asyncio.create_task(_summarize_in_background(session_id))

    # Try stage labeling again (background)
    asyncio.create_task(_label_stage_in_background(session_id))


async def _summarize_in_background(session_id: int) -> None:
    """Run summarization in background without blocking response"""
    try:
        async for db in get_db():
            await SummaryService.update_summary_if_chunk_complete(
                db=db, session_id=session_id
            )
            break
    except Exception as e:
        logger.error(
            "Background summarization failed | session_id=%s | error=%s", session_id, e
        )


async def _label_stage_in_background(session_id: int) -> None:
    """Run stage labeling in background without blocking response"""
    try:
        from app.service.stage_service import StageService

        async for db in get_db():
            await StageService.update_stage_if_user_inactive(
                db=db, session_id=session_id
            )
            break
    except Exception as e:
        logger.error(
            "Background stage labeling failed | session_id=%s | error=%s", session_id, e
        )
