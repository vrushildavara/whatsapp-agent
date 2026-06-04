from typing import AsyncGenerator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.model import (
    AssistantTool,
    Broadcast,
    BroadcastContact,
    BroadcastContactStatus,
    RAGDocument,
    User,
    WhatsAppAccount,
    WhatsAppMessage,
    WhatsAppSession,
)
from app.utils.security import encrypt_api_key, generate_api_key, hash_password

TEST_WORKSPACE_ID = "ws-test-123"
OTHER_WORKSPACE_ID = "ws-other-456"


@pytest_asyncio.fixture
async def seed_user(db_session: AsyncSession) -> AsyncGenerator[User, None]:

    user = User(
        name="Test User",
        email="test@example.com",
        password=hash_password("Password@123"),
        api_key=encrypt_api_key(generate_api_key()),
    )

    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    return user


@pytest_asyncio.fixture
async def seed_account(db_session, seed_user):
    account = WhatsAppAccount(
        name="Primary Account",
        phone_number=1111111111,
        phone_number_id="22222222222",
        waba_id="33333333333",
        token="token1tfroiwmefklmdfbtokkpoekf0w948u5395hgnq93285trgnv958j4ufnu",
        prompt="Prompt 1",
        stage_flow=[{"stage": "anything", "goal": "anything"}],
        user_id=seed_user.id,
        workspace_id=TEST_WORKSPACE_ID,
    )

    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(account)

    placeholder_session = WhatsAppSession(
        account_id=account.id,
        to_number=10000000000,
    )
    db_session.add(placeholder_session)
    await db_session.commit()

    return account


@pytest_asyncio.fixture
async def seed_account2(db_session, seed_user):
    account = WhatsAppAccount(
        name="Primary Account",
        phone_number=2222222222,
        phone_number_id="33333333333",
        token="token1tfroiwmefklmdfbtokkpoekf0w948u5395hgnq93285trgnv958j4ufnu",
        prompt="System prompt",
        stage_flow=[{"stage": "anything", "goal": "anything"}],
        user_id=seed_user.id,
        workspace_id=TEST_WORKSPACE_ID,
    )

    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(account)

    return account


@pytest_asyncio.fixture
async def seed_account3(db_session, seed_user):
    account = WhatsAppAccount(
        name="Primary Account",
        phone_number=3333333333,
        phone_number_id="44444444444",
        waba_id="11111111111",
        token="token1",
        prompt="System prompt",
        stage_flow=[{"stage": "anything", "goal": "anything"}],
        user_id=seed_user.id,
        workspace_id=TEST_WORKSPACE_ID,
    )

    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(account)

    return account


@pytest_asyncio.fixture
async def seed_account_other_workspace(db_session, seed_user):
    account = WhatsAppAccount(
        name="Other Workspace Account",
        phone_number=9876543210,
        phone_number_id="99999999999",
        waba_id="88888888888",
        token="token_other_ws",
        prompt="Other workspace prompt",
        stage_flow=[{"stage": "anything", "goal": "anything"}],
        user_id=seed_user.id,
        workspace_id=OTHER_WORKSPACE_ID,
    )

    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(account)

    placeholder_session = WhatsAppSession(
        account_id=account.id,
        to_number=10000000000,
    )
    db_session.add(placeholder_session)
    await db_session.commit()

    return account


@pytest_asyncio.fixture
async def seed_inactive_account(db_session, seed_user):
    account = WhatsAppAccount(
        name="Inactive Account",
        phone_number=4444444444,
        phone_number_id="55555555555",
        waba_id="66666666666",
        token="token_inactive",
        prompt="Inactive prompt",
        stage_flow=[{"stage": "anything", "goal": "anything"}],
        user_id=seed_user.id,
        workspace_id=TEST_WORKSPACE_ID,
        is_active=False,
    )

    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(account)

    placeholder_session = WhatsAppSession(
        account_id=account.id,
        to_number=10000000000,
    )
    db_session.add(placeholder_session)
    await db_session.commit()

    return account


@pytest_asyncio.fixture
async def seed_tool(db_session, seed_account):
    tool = AssistantTool(
        account_id=seed_account.id,
        name="Test API Tool",
        tool_type="api_request",
        config={
            "url": "https://api.example.com/test",
            "description": "Test tool description",
        },
        is_active=True,
    )

    db_session.add(tool)
    await db_session.commit()
    await db_session.refresh(tool)

    return tool


@pytest_asyncio.fixture
async def seed_tool_knowledge(db_session, seed_account):
    tool = AssistantTool(
        account_id=seed_account.id,
        name="Test Knowledge Tool",
        tool_type="knowledge",
        config={
            "file_ids": ["file-abc123", "file-def456"],
        },
        is_active=True,
    )

    db_session.add(tool)
    await db_session.commit()
    await db_session.refresh(tool)

    return tool


@pytest_asyncio.fixture
async def seed_session(db_session, seed_account):
    session = WhatsAppSession(
        account_id=seed_account.id,
    )

    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    return session


@pytest_asyncio.fixture
async def seed_session_with_history(db_session, seed_account):
    session = WhatsAppSession(
        account_id=seed_account.id,
        current_stage="greeting",
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    msg = WhatsAppMessage(session_id=session.id, role="user", message="hello")
    db_session.add(msg)
    await db_session.commit()
    await db_session.refresh(msg)

    return session


@pytest_asyncio.fixture
async def seed_broadcast(db_session: AsyncSession, seed_account):
    broadcast = Broadcast(
        account_id=seed_account.id,
        name="Test Campaign",
        template_name="test_template",
        template_language="en",
        template_snapshot={"name": "test_template"},
        status="DRAFT",
        total_contacts=0,
    )

    db_session.add(broadcast)
    await db_session.commit()
    await db_session.refresh(broadcast)

    return broadcast


@pytest_asyncio.fixture
async def seed_broadcast_sent(db_session: AsyncSession, seed_account):
    broadcast = Broadcast(
        account_id=seed_account.id,
        name="Test Campaign",
        template_name="test_template2",
        template_language="en",
        template_snapshot={"name": "test_template2"},
        status="FAILED",
        total_contacts=0,
    )

    db_session.add(broadcast)
    await db_session.commit()
    await db_session.refresh(broadcast)

    return broadcast


@pytest_asyncio.fixture
async def seed_rag_document(db_session, seed_user):
    doc = RAGDocument(
        user_id=seed_user.id,
        filename="test_document.pdf",
        collection_name="test_collection_abc123",
        chunks_count=5,
    )

    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    return doc


@pytest_asyncio.fixture
async def seed_broadcast_contacts(db_session, seed_broadcast):
    contacts = [
        BroadcastContact(
            broadcast_id=seed_broadcast.id,
            phone_number="9999999991",
            template_variables=[
                {"type": "body", "parameters": [{"type": "text", "text": "Alice"}]}
            ],
            status=BroadcastContactStatus.PENDING,
        ),
        BroadcastContact(
            broadcast_id=seed_broadcast.id,
            phone_number="9999999992",
            template_variables=[
                {"type": "body", "parameters": [{"type": "text", "text": "Bob"}]}
            ],
            status=BroadcastContactStatus.SENT,
        ),
        BroadcastContact(
            broadcast_id=seed_broadcast.id,
            phone_number="9999999993",
            template_variables=[
                {"type": "body", "parameters": [{"type": "text", "text": "Charlie"}]}
            ],
            status=BroadcastContactStatus.DELIVERED,
        ),
    ]

    db_session.add_all(contacts)
    await db_session.commit()

    return contacts
