import pytest
from sqlalchemy import select

from app.models.model import (
    WhatsAppAccount,
    WhatsAppMessage,
    WhatsAppSession,
    WhatsAppSessionSummary,
)
from tests.fixtures import OTHER_WORKSPACE_ID, TEST_WORKSPACE_ID

# -------------------------CREATE ACCOUNT----------------------------


@pytest.mark.asyncio
async def test_create_account(client, mock_auth, db_session) -> None:
    phone = "9999999999"

    response = await client.post(
        "/account/create",
        json={
            "name": "test",
            "phone_number": phone,
            "phone_id": "9517534862",
            "waba_id": "84565795215",
            "token": "token123",
            "prompt": "account prompt",
            "stage_flow": [{"stage": "anything", "goal": "anything"}],
        },
        headers={"x-workspace-id": TEST_WORKSPACE_ID},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "WhatsApp account created successfully"

    result = await db_session.execute(
        select(WhatsAppAccount).where(
            WhatsAppAccount.phone_number == int(phone),
            WhatsAppAccount.deleted_at.is_(None),
        )
    )

    account = result.scalar_one_or_none()

    assert account is not None

    response = await db_session.execute(
        select(
            WhatsAppSession.account_id == account.id,
            WhatsAppSession.deleted_at.is_(None),
        )
    )

    session = response.scalar_one_or_none()

    assert session is not None

    assert account.phone_number == int(phone)
    assert account.user_id == mock_auth.id


@pytest.mark.asyncio
async def test_create_duplicate_account(client, mock_auth, db_session) -> None:
    payload = {
        "name": "dup",
        "phone_number": "1111111111",
        "phone_id": "111111111",
        "waba_id": "15623465235",
        "token": "token123",
        "prompt": "prompt",
        "stage_flow": [{"stage": "anything", "goal": "anything"}],
    }
    ws_headers = {"x-workspace-id": TEST_WORKSPACE_ID}

    await client.post("/account/create", json=payload, headers=ws_headers)
    response = await client.post("/account/create", json=payload, headers=ws_headers)

    assert response.status_code == 409
    assert response.json()["message"] == "WhatsApp account already exists"

    result = await db_session.execute(
        select(WhatsAppAccount).where(
            WhatsAppAccount.phone_number == int(payload["phone_number"]),
            WhatsAppAccount.deleted_at.is_(None),
        )
    )

    accounts = result.scalars().all()
    assert len(accounts) == 1


@pytest.mark.asyncio
async def test_create_account_invalid_phone(client, seed_user, mock_auth) -> None:
    response = await client.post(
        "/account/create",
        json={
            "name": "test",
            "phone_number": "abcd",
            "phone_id": "123",
            "waba_id": "98654765231",
            "token": "token",
            "prompt": "prompt",
            "stage_flow": [{"stage": "anything", "goal": "anything"}],
        },
        headers={"x-workspace-id": TEST_WORKSPACE_ID},
    )

    assert response.status_code == 422
    assert (
        response.json()["detail"][0]["msg"]
        == "Value error, Phone number must contain only digits"
    )


@pytest.mark.asyncio
async def test_create_account_invalid_waba_id(client, seed_user, mock_auth) -> None:
    response = await client.post(
        "/account/create",
        json={
            "name": "test",
            "phone_number": "9999999999",
            "phone_id": "9517534862",
            "waba_id": "invalid_waba",
            "token": "token",
            "prompt": "prompt",
            "stage_flow": [{"stage": "anything", "goal": "anything"}],
        },
        headers={"x-workspace-id": TEST_WORKSPACE_ID},
    )

    assert response.status_code == 422
    assert (
        response.json()["detail"][0]["msg"]
        == "Value error, WABA ID must contain only digits"
    )


@pytest.mark.asyncio
async def test_create_account_invalid_phone_id(client, seed_user, mock_auth) -> None:
    response = await client.post(
        "/account/create",
        json={
            "name": "test",
            "phone_number": "9999999999",
            "phone_id": "invalid_phone_id",
            "waba_id": "84565795215",
            "token": "token",
            "prompt": "prompt",
            "stage_flow": [{"stage": "anything", "goal": "anything"}],
        },
        headers={"x-workspace-id": TEST_WORKSPACE_ID},
    )

    assert response.status_code == 422
    assert (
        response.json()["detail"][0]["msg"]
        == "Value error, Phone ID must contain only digits"
    )


@pytest.mark.asyncio
async def test_create_account_invalid_stage_flow(client, seed_user, mock_auth) -> None:
    response = await client.post(
        "/account/create",
        json={
            "name": "test",
            "phone_number": "9999999999",
            "phone_id": "123456",
            "waba_id": "98654765231",
            "token": "token",
            "prompt": "prompt",
            "stage_flow": [{"goal": "welcome"}],
        },
        headers={"x-workspace-id": TEST_WORKSPACE_ID},
    )

    assert response.status_code == 422
    assert (
        response.json()["detail"][0]["msg"]
        == "Value error, Each stage_flow item must have 'stage' and 'goal'"
    )


@pytest.mark.asyncio
async def test_create_account_missing_fields(client, seed_user, mock_auth) -> None:
    response = await client.post(
        "/account/create",
        json={
            "name": "test",
            "phone_number": "9999999999",
            "phone_id": "123",
            "waba_id": "98654765231",
            "token": "token",
            "stage_flow": [{"stage": "anything", "goal": "anything"}],
        },
        headers={"x-workspace-id": TEST_WORKSPACE_ID},
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["msg"] == "Field required"


@pytest.mark.asyncio
async def test_create_account_extra_fields(client, seed_user, mock_auth) -> None:
    response = await client.post(
        "/account/create",
        json={
            "name": "test",
            "phone_number": "5555555555",
            "phone_id": "123",
            "waba_id": "98654765231",
            "token": "token",
            "prompt": "prompt",
            "stage_flow": [{"stage": "anything", "goal": "anything"}],
            "extra": "field",
        },
        headers={"x-workspace-id": TEST_WORKSPACE_ID},
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["msg"] == "Extra inputs are not permitted"


@pytest.mark.asyncio
async def test_create_account_unauthorized(client) -> None:
    response = await client.post(
        "/account/create",
        json={
            "name": "test",
            "phone_number": "9999999999",
            "phone_id": "123456",
            "waba_id": "98654765231",
            "token": "token",
            "prompt": "prompt",
            "stage_flow": [{"stage": "anything", "goal": "anything"}],
        },
    )

    assert response.status_code == 401
    assert (
        response.json()["detail"]
        == "Authentication required: provide JWT token or X-API-Key header"
    )


# -------------------------GET ACCOUNT----------------------------


@pytest.mark.asyncio
async def test_get_account(client, seed_account, mock_auth, db_session) -> None:
    account_id = seed_account.id

    response = await client.get(f"/account/{account_id}")

    assert response.status_code == 200
    assert response.json()["message"] == "WhatsApp account retrieved successfully"

    result = await db_session.execute(
        select(WhatsAppAccount).where(
            WhatsAppAccount.id == account_id,
            WhatsAppAccount.user_id == mock_auth.id,
            WhatsAppAccount.deleted_at.is_(None),
        )
    )

    account = result.scalar_one_or_none()
    assert account is not None


@pytest.mark.asyncio
async def test_get_account_not_found(client, mock_auth, db_session) -> None:
    response = await client.get("/account/999")

    assert response.status_code == 404
    assert response.json()["message"] == "Account not found"

    result = await db_session.execute(
        select(WhatsAppAccount).where(
            WhatsAppAccount.id == 999,
            WhatsAppAccount.user_id == mock_auth.id,
            WhatsAppAccount.deleted_at.is_(None),
        )
    )
    account = result.scalar_one_or_none()

    assert account is None


@pytest.mark.asyncio
async def test_get_account_unauthorized(client) -> None:
    response = await client.get("/account/1")

    assert response.status_code == 401
    assert (
        response.json()["detail"]
        == "Authentication required: provide JWT token or X-API-Key header"
    )


# -------------------------GET ACCOUNT STAGE FLOW----------------------------


@pytest.mark.asyncio
async def test_get_stage_flow(client, seed_account, mock_auth, db_session) -> None:
    account_id = seed_account.id

    response = await client.get(f"/account/stage_flow/{account_id}")

    assert response.status_code == 200
    assert (
        response.json()["message"]
        == "WhatsApp account stage flow retrieved successfully"
    )

    result = await db_session.execute(
        select(WhatsAppAccount.stage_flow).where(
            WhatsAppAccount.id == account_id,
            WhatsAppAccount.user_id == mock_auth.id,
            WhatsAppAccount.deleted_at.is_(None),
        )
    )

    stage_flow = result.scalar_one_or_none() or []
    assert stage_flow is not None


@pytest.mark.asyncio
async def test_get_stage_flow_account_not_found(client, mock_auth, db_session) -> None:
    response = await client.get("/account/stage_flow/999")

    assert response.status_code == 404
    assert response.json()["message"] == "Account not found"

    result = await db_session.execute(
        select(WhatsAppAccount.stage_flow).where(
            WhatsAppAccount.id == 999,
            WhatsAppAccount.user_id == mock_auth.id,
            WhatsAppAccount.deleted_at.is_(None),
        )
    )

    stage_flow = result.scalar_one_or_none()
    assert stage_flow is None


@pytest.mark.asyncio
async def test_get_stage_flow_unauthorized(client) -> None:
    response = await client.get("/account/stage_flow/1")

    assert response.status_code == 401
    assert (
        response.json()["detail"]
        == "Authentication required: provide JWT token or X-API-Key header"
    )


# -------------------------GET ALL ACCOUNT----------------------------


@pytest.mark.asyncio
async def test_get_user_accounts(client, seed_account, mock_auth, db_session) -> None:
    response = await client.get("/account/user/")

    assert response.status_code == 200
    assert response.json()["message"] == "WhatsApp accounts retrieved successfully"

    result = await db_session.execute(
        select(WhatsAppAccount).where(
            WhatsAppAccount.user_id == mock_auth.id,
            WhatsAppAccount.deleted_at.is_(None),
        )
    )

    accounts = result.scalars().all()

    assert len(accounts) == len(response.json()["data"])


@pytest.mark.asyncio
async def test_get_user_accounts_unauthorized(client) -> None:
    response = await client.get("/account/user/")

    assert response.status_code == 401
    assert (
        response.json()["detail"]
        == "Authentication required: provide JWT token or X-API-Key header"
    )


# -------------------------UPDATE ACCOUNT----------------------------


@pytest.mark.asyncio
async def test_update_account(client, seed_account, mock_auth, db_session) -> None:
    account_id = seed_account.id

    response = await client.put(
        f"/account/{account_id}",
        json={
            "prompt": "Updated prompt",
            "stage_flow": [{"stage": "anything", "goal": "anything"}],
        },
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Prompt updated successfully"

    result = await db_session.execute(
        select(WhatsAppAccount).where(
            WhatsAppAccount.id == account_id,
            WhatsAppAccount.user_id == mock_auth.id,
            WhatsAppAccount.deleted_at.is_(None),
        )
    )

    account = result.scalar_one()
    assert account.prompt == "Updated prompt"


@pytest.mark.asyncio
async def test_update_account_not_found(client, mock_auth, db_session) -> None:
    response = await client.put(
        "/account/999",
        json={
            "prompt": "test",
            "stage_flow": [{"stage": "anything", "goal": "anything"}],
        },
    )

    assert response.status_code == 404
    assert response.json()["message"] == "Account not found"

    result = await db_session.execute(
        select(WhatsAppAccount).where(
            WhatsAppAccount.id == 999,
            WhatsAppAccount.user_id == mock_auth.id,
            WhatsAppAccount.deleted_at.is_(None),
        )
    )
    account = result.scalar_one_or_none()

    assert account is None


@pytest.mark.asyncio
async def test_update_account_stage_missing_stage(
    client, seed_account, mock_auth
) -> None:
    response = await client.put(
        f"/account/{seed_account.id}",
        json={
            "prompt": "Updated",
            "stage_flow": [{"goal": "welcome"}],
        },
    )

    assert response.status_code == 422
    assert (
        response.json()["detail"][0]["msg"]
        == "Value error, Each stage_flow item must have 'stage' and 'goal'"
    )


@pytest.mark.asyncio
async def test_update_account_missing_fields(client, seed_account, mock_auth) -> None:
    response = await client.put(f"/account/{seed_account.id}")

    assert response.status_code == 422
    assert response.json()["detail"][0]["msg"] == "Field required"


@pytest.mark.asyncio
async def test_update_account_extra_fields(client, seed_account, mock_auth) -> None:
    response = await client.put(
        f"/account/{seed_account.id}",
        json={
            "prompt": "test",
            "stage_flow": [{"stage": "anything", "goal": "anything"}],
            "extra": "field",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["msg"] == "Extra inputs are not permitted"


@pytest.mark.asyncio
async def test_update_account_unauthorized(client, seed_account) -> None:
    response = await client.put(
        f"/account/{seed_account.id}",
        json={
            "prompt": "test",
            "stage_flow": [{"stage": "anything", "goal": "anything"}],
        },
    )

    assert response.status_code == 401
    assert (
        response.json()["detail"]
        == "Authentication required: provide JWT token or X-API-Key header"
    )


# -------------------------DELETE ACCOUNT----------------------------


@pytest.mark.asyncio
async def test_delete_account(client, seed_account, mock_auth, db_session) -> None:
    account_id = seed_account.id

    response = await client.delete(f"/account/{account_id}")

    assert response.status_code == 200
    assert response.json()["message"] == "WhatsApp account deleted successfully"

    result = await db_session.execute(
        select(WhatsAppAccount).where(
            WhatsAppAccount.id == account_id,
            WhatsAppAccount.user_id == mock_auth.id,
            WhatsAppAccount.deleted_at.isnot(None),
        )
    )

    account = result.scalar_one()
    assert account.deleted_at is not None

    result = await db_session.execute(
        select(WhatsAppSession)
        .join(WhatsAppAccount, WhatsAppSession.account_id == WhatsAppAccount.id)
        .where(
            WhatsAppSession.account_id == account_id,
            WhatsAppAccount.user_id == mock_auth.id,
            WhatsAppSession.deleted_at.is_(None),
        )
    )
    active_sessions = result.scalars().all()
    assert len(active_sessions) == 0

    result = await db_session.execute(
        select(WhatsAppMessage)
        .join(WhatsAppSession, WhatsAppSession.id == WhatsAppMessage.session_id)
        .join(WhatsAppAccount, WhatsAppSession.account_id == WhatsAppAccount.id)
        .where(
            WhatsAppSession.account_id == account_id,
            WhatsAppAccount.user_id == mock_auth.id,
            WhatsAppMessage.deleted_at.is_(None),
        )
    )
    active_messages = result.scalars().all()
    assert len(active_messages) == 0

    result = await db_session.execute(
        select(WhatsAppSessionSummary)
        .join(WhatsAppSession, WhatsAppSession.id == WhatsAppSessionSummary.session_id)
        .join(WhatsAppAccount, WhatsAppSession.account_id == WhatsAppAccount.id)
        .where(
            WhatsAppSession.account_id == account_id,
            WhatsAppAccount.user_id == mock_auth.id,
        )
    )
    summaries = result.scalars().all()
    assert len(summaries) == 0


@pytest.mark.asyncio
async def test_delete_account_auth(client, seed_account) -> None:
    account_id = seed_account.id

    response = await client.delete(f"/account/{account_id}")

    assert response.status_code == 401
    assert (
        response.json()["detail"]
        == "Authentication required: provide JWT token or X-API-Key header"
    )


@pytest.mark.asyncio
async def test_delete_account_not_found(client, mock_auth, db_session) -> None:
    response = await client.delete("/account/999")

    assert response.status_code == 404
    assert response.json()["message"] == "Account not found"

    result = await db_session.execute(
        select(WhatsAppAccount).where(
            WhatsAppAccount.id == 999,
            WhatsAppAccount.user_id == mock_auth.id,
            WhatsAppAccount.deleted_at.is_(None),
        )
    )
    account = result.scalar_one_or_none()

    assert account is None


# -------------------------TOGGLE ACCOUNT ACTIVE----------------------------


@pytest.mark.asyncio
async def test_toggle_account_active_deactivate(
    client, seed_account, mock_auth, db_session
) -> None:
    account_id = seed_account.id

    response = await client.patch(f"/account/{account_id}/toggle")

    assert response.status_code == 200
    assert response.json()["message"] == "Account deactivated successfully"
    assert response.json()["data"]["is_active"] is False

    result = await db_session.execute(
        select(WhatsAppAccount).where(
            WhatsAppAccount.id == account_id,
            WhatsAppAccount.deleted_at.is_(None),
        )
    )
    account = result.scalar_one()
    assert account.is_active is False


@pytest.mark.asyncio
async def test_toggle_account_active_reactivate(
    client, seed_inactive_account, mock_auth, db_session
) -> None:
    account_id = seed_inactive_account.id

    response = await client.patch(f"/account/{account_id}/toggle")

    assert response.status_code == 200
    assert response.json()["message"] == "Account activated successfully"
    assert response.json()["data"]["is_active"] is True

    result = await db_session.execute(
        select(WhatsAppAccount).where(
            WhatsAppAccount.id == account_id,
            WhatsAppAccount.deleted_at.is_(None),
        )
    )
    account = result.scalar_one()
    assert account.is_active is True


@pytest.mark.asyncio
async def test_toggle_account_active_not_found(client, mock_auth, db_session) -> None:
    response = await client.patch("/account/999/toggle")

    assert response.status_code == 404
    assert response.json()["message"] == "Account not found"

    result = await db_session.execute(
        select(WhatsAppAccount).where(
            WhatsAppAccount.id == 999,
            WhatsAppAccount.deleted_at.is_(None),
        )
    )
    account = result.scalar_one_or_none()
    assert account is None


@pytest.mark.asyncio
async def test_toggle_account_active_unauthorized(client, seed_account) -> None:
    response = await client.patch(f"/account/{seed_account.id}/toggle")

    assert response.status_code == 401
    assert (
        response.json()["detail"]
        == "Authentication required: provide JWT token or X-API-Key header"
    )


@pytest.mark.asyncio
async def test_toggle_account_active_wrong_workspace(
    client, seed_account_other_workspace, mock_auth_workspace
) -> None:
    response = await client.patch(f"/account/{seed_account_other_workspace.id}/toggle")

    assert response.status_code == 404
    assert response.json()["message"] == "Account not found"


# -------------------------WORKSPACE SCOPING TESTS----------------------------


@pytest.mark.asyncio
async def test_create_account_no_workspace_header(
    client, mock_auth, db_session
) -> None:
    phone = "7777777777"

    response = await client.post(
        "/account/create",
        json={
            "name": "test",
            "phone_number": phone,
            "phone_id": "9517534862",
            "waba_id": "84565795215",
            "token": "token123",
            "prompt": "prompt",
            "stage_flow": [{"stage": "anything", "goal": "anything"}],
        },
    )

    assert response.status_code == 200
    assert response.json()["message"] == "WhatsApp account created successfully"
    assert response.json()["data"]["workspace_id"] is None

    result = await db_session.execute(
        select(WhatsAppAccount).where(
            WhatsAppAccount.phone_number == int(phone),
            WhatsAppAccount.workspace_id.is_(None),
            WhatsAppAccount.deleted_at.is_(None),
        )
    )
    account = result.scalar_one_or_none()
    assert account is not None


@pytest.mark.asyncio
async def test_create_duplicate_account_different_workspace(
    client, mock_auth, db_session
) -> None:
    payload = {
        "name": "dup-ws",
        "phone_number": "6543210987",
        "phone_id": "111111111",
        "waba_id": "15623465235",
        "token": "token123",
        "prompt": "prompt",
        "stage_flow": [{"stage": "anything", "goal": "anything"}],
    }

    r1 = await client.post(
        "/account/create", json=payload, headers={"x-workspace-id": TEST_WORKSPACE_ID}
    )
    r2 = await client.post(
        "/account/create", json=payload, headers={"x-workspace-id": OTHER_WORKSPACE_ID}
    )

    assert r1.status_code == 200
    assert r2.status_code == 200

    result = await db_session.execute(
        select(WhatsAppAccount).where(
            WhatsAppAccount.phone_number == int(payload["phone_number"]),
            WhatsAppAccount.deleted_at.is_(None),
        )
    )
    accounts = result.scalars().all()
    assert len(accounts) == 2


@pytest.mark.asyncio
async def test_get_account_workspace_scoped(
    client, seed_account, seed_account_other_workspace, mock_auth_workspace, db_session
) -> None:
    response = await client.get(f"/account/{seed_account.id}")
    assert response.status_code == 200
    assert response.json()["data"]["workspace_id"] == TEST_WORKSPACE_ID


@pytest.mark.asyncio
async def test_get_account_wrong_workspace(
    client, seed_account_other_workspace, mock_auth_workspace, db_session
) -> None:
    response = await client.get(f"/account/{seed_account_other_workspace.id}")

    assert response.status_code == 404
    assert response.json()["message"] == "Account not found"


@pytest.mark.asyncio
async def test_get_user_accounts_workspace_scoped(
    client, seed_account, seed_account_other_workspace, mock_auth_workspace, db_session
) -> None:
    response = await client.get("/account/user/")

    assert response.status_code == 200
    returned_ids = [a["id"] for a in response.json()["data"]]
    assert seed_account.id in returned_ids
    assert seed_account_other_workspace.id not in returned_ids


@pytest.mark.asyncio
async def test_update_account_wrong_workspace(
    client, seed_account_other_workspace, mock_auth_workspace
) -> None:
    response = await client.put(
        f"/account/{seed_account_other_workspace.id}",
        json={
            "prompt": "Should not update",
            "stage_flow": [{"stage": "anything", "goal": "anything"}],
        },
    )

    assert response.status_code == 404
    assert response.json()["message"] == "Account not found"


@pytest.mark.asyncio
async def test_delete_account_wrong_workspace(
    client, seed_account_other_workspace, mock_auth_workspace
) -> None:
    response = await client.delete(f"/account/{seed_account_other_workspace.id}")

    assert response.status_code == 404
    assert response.json()["message"] == "Account not found"
