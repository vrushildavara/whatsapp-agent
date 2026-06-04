import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from app.common.settings import settings
from app.utils.redis_manager import close_redis, init_redis

logger = logging.getLogger(__name__)

engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
            logger.info("✅ Database connected successfully")
    except Exception as exc:
        logger.error("❌ Error connecting to database | error=%s", exc)
        raise exc

    await init_redis()

    yield

    await engine.dispose()
    logger.info("🔌 Database connection closed")

    await close_redis()
    logger.info("🔌 Redis connection closed")
