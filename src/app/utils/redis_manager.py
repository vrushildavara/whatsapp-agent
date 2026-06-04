import logging

import redis.asyncio as redis
from redis.asyncio import Redis

from app.common.settings import settings

logger = logging.getLogger(__name__)

redis_client: Redis | None = None


async def init_redis() -> None:
    global redis_client

    try:
        redis_client = redis.Redis(
            host=settings.redis_host,
            port=int(settings.redis_port),
            password=settings.redis_password,
            decode_responses=True,
        )
        await redis_client.ping()
        logger.info("✅ Redis connected successfully")
    except Exception as e:
        logger.error(f"❌ Redis connection failed: {e}")
        raise e


def get_redis_client() -> Redis | None:
    if redis_client is None:
        logger.warning("Redis client not initialized. Returning None.")
    return redis_client


async def close_redis() -> None:
    global redis_client

    if redis_client:
        await redis_client.aclose()
        logger.info("Redis connection closed")
