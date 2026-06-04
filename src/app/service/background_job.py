# app/service/background_job.py

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.common.responses import ErrorResponse
from app.database.db_handler import AsyncSessionLocal
from app.models.model import (
    Broadcast,
    WhatsAppAccount,
    WhatsAppMessage,
    WhatsAppSession,
)
from app.service.broadcast_service import BroadcastService
from app.service.message_service import MessageService
from app.service.stage_service import INACTIVITY_SECONDS, StageService
from app.service.template_service import template_service
from app.service.whatsapp_service import WhatsAppService
from app.utils.redis_manager import get_redis_client

logger = logging.getLogger(__name__)

# Background job runs every 30 seconds
JOB_INTERVAL_SECONDS = 30


async def _process_inactive_sessions() -> None:
    """
    Background job that checks for inactive sessions and updates their stages.
    Runs every 30 seconds.
    """
    while True:
        try:
            async with AsyncSessionLocal() as db:
                # Find sessions with unlabeled user messages that are inactive
                cutoff_time = func.now() - timedelta(seconds=INACTIVITY_SECONDS)

                # Subquery to get last user message time per session
                result = await db.execute(
                    select(WhatsAppMessage.session_id)
                    .join(
                        WhatsAppSession,
                        WhatsAppSession.id == WhatsAppMessage.session_id,
                    )
                    .join(
                        WhatsAppAccount,
                        WhatsAppAccount.id == WhatsAppSession.account_id,
                    )
                    .where(
                        WhatsAppMessage.role == "user",
                        WhatsAppMessage.is_labeled.is_(False),
                        WhatsAppMessage.created_at <= cutoff_time,
                        WhatsAppMessage.deleted_at.is_(None),
                        WhatsAppAccount.stage_flow.isnot(None),
                    )
                    .group_by(WhatsAppMessage.session_id)
                    .limit(50)  # Process max 50 sessions per run
                )

                session_ids = [row[0] for row in result.all()]

                if session_ids:
                    logger.info(f"Processing {len(session_ids)} inactive sessions")

                    for session_id in session_ids:
                        try:
                            await StageService.update_stage_if_user_inactive(
                                db, session_id, update_source="background_job"
                            )
                        except Exception as e:
                            logger.error(
                                f"Failed to process session | session_id={session_id} | error={e}"
                            )
                            continue

        except Exception as e:
            logger.error(f"Background job error: {e}")

        await asyncio.sleep(JOB_INTERVAL_SECONDS)


async def start_background_jobs() -> None:
    """Start all background jobs"""
    logger.info("Starting background jobs...")
    asyncio.create_task(_process_inactive_sessions())
    asyncio.create_task(_process_broadcast_queue())
    asyncio.create_task(_recover_interrupted_broadcasts())


async def _recover_interrupted_broadcasts() -> None:
    """
    On startup, recover any broadcasts stuck in RUNNING status.
    This handles worker crashes mid-broadcast.
    """
    try:
        async with AsyncSessionLocal() as db:
            # Find broadcasts stuck in RUNNING
            result = await db.execute(
                select(Broadcast).where(Broadcast.status == "RUNNING")
            )

            running_broadcasts = result.scalars().all()

            if running_broadcasts:
                logger.info(
                    f"Recovering {len(running_broadcasts)} interrupted broadcasts"
                )

                service = BroadcastService(db)
                redis = get_redis_client()

                for broadcast in running_broadcasts:
                    # Reset to QUEUED
                    await service.update_broadcast_status(broadcast.id, "QUEUED")

                    # Re-queue for processing
                    if redis:
                        await redis.lpush("broadcast_queue", str(broadcast.id))

                    logger.info(f"Recovered broadcast_id={broadcast.id}")

                await db.commit()
    except Exception as e:
        logger.error(f"Failed to recover interrupted broadcasts: {e}", exc_info=True)


async def _process_broadcast_queue() -> None:
    """
    Background job that processes queued broadcast campaigns.
    Uses Redis queue (with fallback to database polling).
    Runs continuously.
    """
    FALLBACK_POLL_INTERVAL = 10  # Fallback to polling every 10 seconds

    while True:
        try:
            redis = get_redis_client()

            if redis:
                # Use Redis queue (blocking pop with timeout)
                try:
                    result = await redis.brpop("broadcast_queue", timeout=10)

                    if result:
                        _, broadcast_id = result
                        async with AsyncSessionLocal() as db:
                            await _process_single_broadcast(db, int(broadcast_id))

                    continue  # Skip fallback polling

                except Exception as redis_error:
                    logger.warning(
                        f"Redis queue error, falling back to polling: {redis_error}"
                    )

            # Fallback: Poll database for QUEUED broadcasts
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(Broadcast)
                    .where(Broadcast.status == "QUEUED")
                    .order_by(Broadcast.created_at.asc())
                    .limit(5)
                )

                broadcasts = result.scalars().all()

                if broadcasts:
                    logger.info(
                        f"Processing {len(broadcasts)} queued broadcasts (polling mode)"
                    )

                    for broadcast in broadcasts:
                        try:
                            await _process_single_broadcast(db, broadcast.id)
                        except Exception as e:
                            logger.error(
                                f"Failed to process broadcast | broadcast_id={broadcast.id} | error={e}",
                                exc_info=True,
                            )
                            # Mark as failed
                            service = BroadcastService(db)
                            await service.update_broadcast_status(
                                broadcast.id,
                                "FAILED",
                                started_at=datetime.now(timezone.utc),
                                completed_at=datetime.now(timezone.utc),
                            )
                            continue

            await asyncio.sleep(FALLBACK_POLL_INTERVAL)

        except Exception as e:
            logger.error(f"Broadcast queue job error: {e}", exc_info=True)
            await asyncio.sleep(FALLBACK_POLL_INTERVAL)


async def _process_single_broadcast(db, broadcast_id: int) -> None:
    """
    Process a single broadcast campaign - send messages to all contacts.
    Includes retry logic and Redis-based rate limiting.

    Args:
        db: Database session
        broadcast_id: Broadcast ID to process
    """
    service = BroadcastService(db)

    # Get broadcast details
    broadcast_result = await db.execute(
        select(Broadcast).where(Broadcast.id == broadcast_id)
    )
    broadcast = broadcast_result.scalars().first()

    if not broadcast:
        logger.error(f"Broadcast not found: {broadcast_id}")
        return

    # Skip if already processing or completed
    if broadcast.status not in ["QUEUED", "RUNNING"]:
        logger.info(
            f"Broadcast {broadcast_id} already in status {broadcast.status}, skipping"
        )
        return

    # Get account details for access token
    account_result = await db.execute(
        select(WhatsAppAccount).where(WhatsAppAccount.id == broadcast.account_id)
    )
    account = account_result.scalars().first()

    if not account:
        raise Exception(f"Account not found: {broadcast.account_id}")

    # Update status to RUNNING
    await service.update_broadcast_status(
        broadcast.id, "RUNNING", started_at=datetime.now(timezone.utc)
    )

    # Get all pending contacts
    contacts = await service.get_pending_contacts(broadcast.id)

    logger.info(
        f"Starting broadcast | broadcast_id={broadcast.id} | contacts={len(contacts)}"
    )

    sent_count = 0
    failed_count = 0

    # Send messages to each contact with retry logic
    for contact in contacts:
        # Check Redis rate limit (13 msg/sec safe limit)
        if not await _check_rate_limit(account.id):
            await asyncio.sleep(0.1)  # Wait if rate limit hit

        success = False
        last_error = None

        # Retry up to 3 times for transient errors
        for attempt in range(3):
            try:
                # Send via WhatsApp API
                # template_variables is now a components list (list[dict]).
                # Fall back to the legacy variables dict path for older rows.
                template_vars = contact.get("template_variables")
                response = await WhatsAppService.send_template_message(
                    phone_number_id=account.phone_number_id,
                    to_number=contact["phone_number"],
                    template_name=broadcast.template_name,
                    language=broadcast.template_language,
                    access_token=account.token,
                    components=template_vars
                    if isinstance(template_vars, list)
                    else None,
                    variables=template_vars
                    if isinstance(template_vars, dict)
                    else None,
                )

                if response and response.get("status") == "failed":
                    raise ErrorResponse(500, response["error"])

                # Update contact status to SENT
                await service.update_contact_status(
                    contact["id"],
                    status="SENT",
                    meta_message_id=response["message_id"],
                    sent_at=datetime.now(timezone.utc),
                )

                # Create session if it doesn't exist, then save the template as a message
                try:
                    template_vars = contact.get("template_variables")
                    rendered = template_service.render_template_message(
                        broadcast.template_snapshot,
                        template_vars if isinstance(template_vars, list) else None,
                    )
                    await MessageService(db).save_template_to_session(
                        account_id=account.id,
                        phone_number=int(contact["phone_number"]),
                        template_name=broadcast.template_name,
                        rendered_message=rendered or f"[Template: {broadcast.template_name}]",
                    )
                except Exception as session_err:
                    logger.warning(
                        f"Session/message save failed | contact_id={contact['id']} | error={session_err}"
                    )

                sent_count += 1
                success = True
                break  # Success, exit retry loop

            except Exception as e:
                last_error = str(e)
                error_str = str(e).lower()

                # Check if it's a transient error (5xx, timeout, network)
                is_transient = (
                    "timeout" in error_str
                    or "connection" in error_str
                    or "500" in error_str
                    or "502" in error_str
                    or "503" in error_str
                    or "504" in error_str
                )

                if is_transient and attempt < 2:
                    # Exponential backoff: 1s, 2s, 4s
                    wait_time = 2**attempt
                    logger.warning(
                        f"Transient error, retrying in {wait_time}s | contact_id={contact['id']} | attempt={attempt + 1} | error={e}"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    # Permanent error or max retries reached
                    logger.error(
                        f"Failed to send to contact | contact_id={contact['id']} | attempts={attempt + 1} | error={e}"
                    )
                    break

        if not success:
            # Mark contact as failed
            await service.update_contact_status(
                contact["id"],
                status="FAILED",
                error_message=last_error[:500] if last_error else "Unknown error",
            )
            failed_count += 1

        # Rate limiting - 13 msg/sec (safe headroom below 80/sec)
        await asyncio.sleep(0.077)  # ~13 msg/sec

    # Update broadcast counts
    await service.update_broadcast_counts(
        broadcast.id,
        sent_count=sent_count,
        delivered_count=0,  # Will be updated by webhooks
        failed_count=failed_count,
    )

    # Mark broadcast as completed
    await service.update_broadcast_status(
        broadcast.id, "COMPLETED", completed_at=datetime.now(timezone.utc)
    )

    logger.info(
        f"Broadcast completed | broadcast_id={broadcast.id} | sent={sent_count} | failed={failed_count}"
    )


async def _check_rate_limit(account_id: int) -> bool:
    """
    Redis-based sliding window rate limiter.
    Limits to 13 messages per second per account (safe headroom below 80/sec).

    Args:
        account_id: WhatsApp account ID

    Returns:
        True if within rate limit, False if limit exceeded
    """
    redis = get_redis_client()

    if not redis:
        return True  # No rate limiting if Redis unavailable

    try:
        key = f"rate_limit:broadcast:{account_id}"
        count = await redis.incr(key)

        if count == 1:
            # First message in window, set 1 second expiry
            await redis.expire(key, 1)

        return count <= 13  # Max 13 msg/sec

    except Exception as e:
        logger.warning(f"Rate limit check failed: {e}")
        return True  # Allow on error
