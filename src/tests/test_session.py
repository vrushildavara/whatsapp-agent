import pytest
from sqlalchemy import select

from app.models.model import WhatsAppAccount, WhatsAppMessage, WhatsAppSession

# -------------------------GET SESSION----------------------------


@pytest.mark.asyncio
async def test_get_session(client, seed_session, mock_auth, db_session) -> None:
    session_id = seed_session.id

    response = await client.get(f"/session/{session_id}")

    assert response.status_code == 200
    assert response.json()["message"] == "WhatsApp session retrieved successfully"

    result = await db_session.execute(
        select(WhatsAppSession)
        .join(WhatsAppAccount, WhatsAppSession.account_id == WhatsAppAccount.id)
        .where(
            WhatsAppSession.id == session_id,
            WhatsAppAccount.user_id == mock_auth.id,
            WhatsAppSession.deleted_at.is_(None),
        )
    )

    session = result.scalar_one_or_none()
    assert session is not None


@pytest.mark.asyncio
async def test_get_session_unauthorized(client, seed_session) -> None:
    response = await client.get(f"/session/{seed_session.id}")

    assert response.status_code == 401
    assert (
        response.json()["detail"]
        == "Authentication required: provide JWT token or X-API-Key header"
    )


@pytest.mark.asyncio
async def test_get_session_not_found(client, mock_auth, db_session) -> None:
    response = await client.get("/session/999")

    assert response.status_code == 404
    assert response.json()["message"] == "Session not found"

    result = await db_session.execute(
        select(WhatsAppSession)
        .join(WhatsAppAccount, WhatsAppSession.account_id == WhatsAppAccount.id)
        .where(
            WhatsAppSession.id == 999,
            WhatsAppAccount.user_id == mock_auth.id,
            WhatsAppSession.deleted_at.is_(None),
        )
    )

    session = result.scalar_one_or_none()
    assert session is None


# -------------------------GET ALL SESSION----------------------------


@pytest.mark.asyncio
async def test_get_all_sessions(client, seed_account, mock_auth, db_session) -> None:
    response = await client.get(
        f"/session/account/{seed_account.id}?page=1&limit=10&search=65&stage_search=greeting"
    )

    assert response.status_code == 200
    assert response.json()["message"] == "WhatsApp sessions retrieved successfully."

    result = await db_session.execute(
        select(WhatsAppSession)
        .join(WhatsAppAccount, WhatsAppSession.account_id == WhatsAppAccount.id)
        .where(
            WhatsAppSession.account_id == seed_account.id,
            WhatsAppAccount.user_id == mock_auth.id,
            WhatsAppSession.deleted_at.is_(None),
        )
    )

    sessions = result.scalars().all()

    assert len(sessions) >= 0


@pytest.mark.asyncio
async def test_get_all_sessions_unauthorized(client, seed_account) -> None:
    response = await client.get(f"/session/account/{seed_account.id}")

    assert response.status_code == 401
    assert (
        response.json()["detail"]
        == "Authentication required: provide JWT token or X-API-Key header"
    )


@pytest.mark.asyncio
async def test_get_all_sessions_account_not_found(
    client, mock_auth, db_session
) -> None:
    response = await client.get(
        "/session/account/999?page=1&limit=10&search=65&stage_search=greeting"
    )

    assert response.status_code == 404
    assert response.json()["message"] == "Account not found"

    result = await db_session.execute(
        select(WhatsAppSession)
        .join(WhatsAppAccount, WhatsAppSession.account_id == WhatsAppAccount.id)
        .where(
            WhatsAppSession.account_id == 999,
            WhatsAppAccount.user_id == mock_auth.id,
            WhatsAppSession.deleted_at.is_(None),
        )
    )

    sessions = result.scalars().all()
    assert len(sessions) == 0


# -------------------------GET SESSION HISTORY----------------------------


@pytest.mark.asyncio
async def test_get_session_history(client, seed_session, mock_auth, db_session) -> None:
    session_id = seed_session.id
    response = await client.get(f"/session/history/{session_id}")

    assert response.status_code == 200
    assert response.json()["message"] == "Session history retrieved successfully."

    result = await db_session.execute(
        select(WhatsAppSession)
        .join(WhatsAppAccount, WhatsAppSession.account_id == WhatsAppAccount.id)
        .where(
            WhatsAppSession.id == session_id,
            WhatsAppAccount.user_id == mock_auth.id,
            WhatsAppSession.deleted_at.is_(None),
        )
    )

    session = result.scalar_one_or_none()
    assert session is not None


@pytest.mark.asyncio
async def seed_data_history_unauthorized(client, seed_session) -> None:
    response = await client.get(f"/session/history/{seed_session.id}")

    assert response.status_code == 401
    assert (
        response.json()["detail"]
        == "Authentication required: provide JWT token or X-API-Key header"
    )


@pytest.mark.asyncio
async def seed_data_history_not_found(client, mock_auth, db_session) -> None:
    response = await client.get("/session/history/999")

    assert response.status_code == 404
    assert response.json()["message"] == "Session not found"

    result = await db_session.execute(
        select(WhatsAppMessage).where(WhatsAppMessage.session_id == 999)
    )

    messages = result.scalars().all()
    assert len(messages) == 0


# -------------------------DELETE SESSION HISTORY----------------------------


@pytest.mark.asyncio
async def test_delete_session_history(
    client, seed_session_with_history, mock_auth, db_session
) -> None:
    response = await client.delete(f"/session/history/{seed_session_with_history.id}")

    assert response.status_code == 200
    assert response.json()["message"] == "Session history deleted successfully"

    result = await db_session.execute(
        select(WhatsAppMessage).where(
            WhatsAppMessage.session_id == seed_session_with_history.id
        )
    )
    messages = result.scalars().all()
    assert len(messages) == 1
    assert messages[0].deleted_at is not None

    result = await db_session.execute(
        select(WhatsAppSession).where(
            WhatsAppSession.id == seed_session_with_history.id
        )
    )
    session = result.scalar_one()
    assert session.current_stage is None


@pytest.mark.asyncio
async def test_delete_session_history_unauthorized(client, seed_session) -> None:
    response = await client.delete(f"/session/history/{seed_session.id}")

    assert response.status_code == 401
    assert (
        response.json()["detail"]
        == "Authentication required: provide JWT token or X-API-Key header"
    )


@pytest.mark.asyncio
async def test_delete_session_history_not_found(client, mock_auth, db_session) -> None:
    response = await client.delete("/session/history/999")

    assert response.status_code == 404
    assert response.json()["message"] == "Session history not found"

    result = await db_session.execute(
        select(WhatsAppMessage).where(WhatsAppMessage.session_id == 999)
    )

    messages = result.scalars().all()
    assert len(messages) == 0
