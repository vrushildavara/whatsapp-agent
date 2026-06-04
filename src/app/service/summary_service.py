from google import genai
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.settings import settings
from app.models.model import WhatsAppMessage, WhatsAppSessionSummary
from app.prompt.summary_prompt import SUMMARY_PROMPT
from app.service.message_service import MessageService

CHUNK_SIZE = 20


class SummaryService:
    @staticmethod
    async def update_summary_if_chunk_complete(
        db: AsyncSession, session_id: int
    ) -> None:
        # Get current unsummarized chunk
        message_service = MessageService(db)
        messages = await message_service.get_unsummarized_messages(
            session_id=session_id, limit=CHUNK_SIZE
        )

        # Not enough messages yet
        if len(messages) < CHUNK_SIZE:
            return

        conversation_text = "\n".join(
            f"{m['role'].upper()}: {m['content']}" for m in messages if m.get("content")
        )

        # Load existing summary
        result = await db.execute(
            select(WhatsAppSessionSummary)
            .where(WhatsAppSessionSummary.session_id == session_id)
            .with_for_update()
        )
        summary_row = result.scalar_one_or_none()
        existing_summary = summary_row.summary if summary_row else "None"

        # Build prompt
        prompt = SUMMARY_PROMPT.format(
            existing_summary=existing_summary, conversation=conversation_text
        )

        # Call Gemini 2.5 Flash directly
        client = genai.Client(api_key=settings.gemini_api_key)
        response = await client.aio.models.generate_content(
            model="gemini-2.0-flash-lite", contents=prompt
        )

        updated_summary = (
            response.text.replace("**", "").strip()
            if response.text
            else existing_summary
        )

        # Save summary
        if summary_row:
            summary_row.summary = updated_summary
        else:
            db.add(
                WhatsAppSessionSummary(session_id=session_id, summary=updated_summary)
            )

        # Mark messages as summarized
        await db.execute(
            update(WhatsAppMessage)
            .where(
                WhatsAppMessage.session_id == session_id,
                WhatsAppMessage.is_summarized.is_(False),
            )
            .values(is_summarized=True)
            .execution_options(synchronize_session=False)
        )

        await db.commit()

    #  Used by controller
    @staticmethod
    async def get_summary(db: AsyncSession, session_id: int) -> str:
        result = await db.execute(
            select(WhatsAppSessionSummary.summary).where(
                WhatsAppSessionSummary.session_id == session_id
            )
        )
        return result.scalar() or ""
