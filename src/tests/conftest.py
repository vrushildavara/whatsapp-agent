import os
from typing import AsyncGenerator

import pytest_asyncio
from asgi_lifespan import LifespanManager
from dotenv import load_dotenv
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.database.db_handler import Base, get_db
from app.main import app
from app.utils.middleware import CurrentUser, get_current_user
from tests.fixtures import *  # noqa: F403


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "no_db_reset: skip database reset for tests that do not use the database",
    )

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))

load_dotenv(os.path.join(BASE_DIR, ".env.test"))
TEST_DB_URL = os.getenv("TEST_DB_URL")

if not TEST_DB_URL:
    raise RuntimeError("TEST_DB_URL missing in .env.test")


engine = create_async_engine(
    TEST_DB_URL,
    echo=False,
    poolclass=NullPool,
)

TestingSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
)


@pytest_asyncio.fixture(scope="function", autouse=True)
async def reset_database(request):
    if request.node.get_closest_marker("no_db_reset"):
        yield
        return

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


@pytest_asyncio.fixture(scope="function")
async def db_session():
    async with TestingSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session):
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    # triggers lifespan
    async with LifespanManager(app):
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    app.dependency_overrides.clear()


class FakeUser:
    id = 999
    email = "fakeuser@example.com"
    workspace_id = None


@pytest_asyncio.fixture
async def mock_auth(seed_user) -> AsyncGenerator[CurrentUser, None]:
    current_user = CurrentUser(
        id=seed_user.id, email=seed_user.email, workspace_id=None
    )
    app.dependency_overrides[get_current_user] = lambda: current_user
    yield current_user
    app.dependency_overrides.pop(get_current_user, None)


@pytest_asyncio.fixture
async def mock_auth_workspace(seed_user) -> AsyncGenerator[CurrentUser, None]:
    current_user = CurrentUser(
        id=seed_user.id, email=seed_user.email, workspace_id=TEST_WORKSPACE_ID
    )
    app.dependency_overrides[get_current_user] = lambda: current_user
    yield current_user
    app.dependency_overrides.pop(get_current_user, None)
