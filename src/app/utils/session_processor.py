import asyncio
import logging
import uuid

from redis.asyncio import Redis

from app.database.db_handler import get_db
from app.service.assistant_service import generate_assistant_response
from app.utils.redis_manager import get_redis_client

DEBOUNCE_SECONDS = 0
LOCK_TTL = 300

logger = logging.getLogger(__name__)


async def enqueue_and_trigger(
    session_id: int,
    from_number: int,
    to_number: int,
    media: list[str] | None = None,
    sandbox: bool = False,
) -> None:
    redis_client = get_redis_client()
    if redis_client is None:
        async for db in get_db():
            await generate_assistant_response(
                session_id, db, from_number, str(to_number), media, sandbox=sandbox
            )
            break
        return

    lock_key = f"s:{session_id}:lock"
    job_key = f"s:{session_id}:job"
    buffer_key = f"s:{session_id}:buffer"

    # Restart if LLM is processing
    if await redis_client.exists(lock_key):
        logger.info("Cancelling activate job | session=%s", session_id)
        await redis_client.delete(lock_key)

    # Buffer media URLs
    if media:
        for url in media:
            await redis_client.rpush(buffer_key, url)

    # Replace debounce job
    job_id = f"{session_id}:{uuid.uuid4()}"
    await redis_client.set(job_key, job_id, ex=DEBOUNCE_SECONDS + 5)

    asyncio.create_task(
        _process_session(
            session_id, job_id, from_number, str(to_number), sandbox=sandbox
        )
    )


async def _process_session(
    session_id: int,
    job_id: str,
    from_number: int,
    to_number: str,
    sandbox: bool = False,
) -> None:
    redis_client: Redis | None = get_redis_client()
    if redis_client is None:
        async for db in get_db():
            await generate_assistant_response(
                session_id, db, from_number, to_number, None, sandbox=sandbox
            )
            break
        return

    lock_key = f"s:{session_id}:lock"
    job_key = f"s:{session_id}:job"
    buffer_key = f"s:{session_id}:buffer"

    await asyncio.sleep(DEBOUNCE_SECONDS)

    current_job = await redis_client.get(job_key)
    if current_job != job_id:
        return

    locked = await redis_client.set(lock_key, "1", nx=True, ex=LOCK_TTL)
    if not locked:
        return

    try:
        messages = await redis_client.lrange(buffer_key, 0, -1)

        await redis_client.delete(buffer_key)
        await redis_client.delete(job_key)

        media_urls = [msg for msg in messages if msg]

        async for db in get_db():
            await generate_assistant_response(
                session_id,
                db,
                from_number,
                to_number,
                media_urls,
                redis_client,
                sandbox=sandbox,
            )
            break

    except Exception:
        logger.exception("Session processing failed | session_id=%s", session_id)

    finally:
        await redis_client.delete(lock_key)
