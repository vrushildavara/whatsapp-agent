# app/service/stage_service.py

import logging
import os
from datetime import datetime, timedelta, timezone

from google import genai
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.model import WhatsAppAccount, WhatsAppMessage, WhatsAppSession
from app.prompt.stage_prompt import STAGE_LABELING_PROMPT

logger = logging.getLogger(__name__)

# Only rule: user inactivity threshold
INACTIVITY_SECONDS = 120  # 2 minutes

# Special test number: 1000000000 - evaluates stage immediately without waiting


class StageService:
    @staticmethod
    async def update_stage_if_user_inactive(
        db: AsyncSession,
        session_id: int,
        update_source: str = "background_job",
    ) -> None:
        """
        Update stage ONLY if:
        - user is inactive for >= 2 minutes
        - session has unlabeled messages

        EXCEPTION: For to_number=1000000000, skip inactivity check and evaluate immediately.

        This function is SAFE to call repeatedly.
        """

        # Load session and check if there are unlabeled messages
        session_result = await db.execute(
            select(
                WhatsAppSession.id,
                WhatsAppSession.to_number,
                WhatsAppSession.current_stage,
                WhatsAppAccount.stage_flow,
            )
            .join(WhatsAppAccount, WhatsAppAccount.id == WhatsAppSession.account_id)
            .where(WhatsAppSession.id == session_id)
        )

        session = session_result.first()

        if not session:
            logger.debug(f"Session not found | session_id={session_id}")
            return

        # Get last user message timestamp
        last_user_msg_result = await db.execute(
            select(
                func.max(WhatsAppMessage.created_at), func.count(WhatsAppMessage.id)
            ).where(
                WhatsAppMessage.session_id == session_id,
                WhatsAppMessage.role == "user",
                WhatsAppMessage.is_labeled.is_(False),
                WhatsAppMessage.deleted_at.is_(None),
            )
        )
        row = last_user_msg_result.first()
        if row is None:
            return

        last_msg_time, unlabeled_count = row

        if not last_msg_time or unlabeled_count == 0:
            return

        # Check if this is the special testing number
        is_test_number = session.to_number == 10000000000

        # Check inactivity condition (skip for test number)
        if not is_test_number:
            now_utc = datetime.now(timezone.utc)
            inactivity_delta = now_utc - last_msg_time

            if inactivity_delta < timedelta(seconds=INACTIVITY_SECONDS):
                # User still active
                return
        else:
            logger.info(
                f"Test number detected, skipping inactivity check | session_id={session_id}"
            )

        # Load ALL unlabeled messages for this session
        messages_result = await db.execute(
            select(WhatsAppMessage)
            .where(
                WhatsAppMessage.session_id == session_id,
                WhatsAppMessage.is_labeled.is_(False),
                WhatsAppMessage.deleted_at.is_(None),
            )
            .order_by(WhatsAppMessage.created_at.asc())
        )
        messages = messages_result.scalars().all()

        if not messages:
            return

        # Build conversation text
        conversation_text = "\n".join(
            f"{m.role.upper()}: {m.message}" for m in messages if m.message
        )

        if not session.stage_flow:
            logger.warning(f"No stage flow configured | session_id={session_id}")
            return

        prompt = STAGE_LABELING_PROMPT.format(
            stage_flow=session.stage_flow,
            conversation=conversation_text,
        )

        # Call Gemini
        try:
            client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
            response = await client.aio.models.generate_content(
                model="gemini-2.0-flash-lite",
                contents=prompt,
            )

            extracted_stage = response.text.strip() if response.text else None
            logger.info(
                f"Stage extracted | session_id={session_id} | stage={extracted_stage} | source={update_source}"
            )

            # Update session stage
            await db.execute(
                update(WhatsAppSession)
                .where(WhatsAppSession.id == session_id)
                .values(current_stage=extracted_stage)
            )

            # Mark messages as labeled
            await db.execute(
                update(WhatsAppMessage)
                .where(
                    WhatsAppMessage.session_id == session_id,
                    WhatsAppMessage.is_labeled.is_(False),
                )
                .values(is_labeled=True)
                .execution_options(synchronize_session=False)
            )

            await db.commit()

            logger.info(
                f"Stage updated successfully | session_id={session_id} | messages={len(messages)}"
            )

        except Exception as e:
            await db.rollback()
            logger.error(f"Stage update failed | session_id={session_id} | error={e}")
