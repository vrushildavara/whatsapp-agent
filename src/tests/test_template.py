from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.common.responses import ErrorResponse
from app.models.model import WhatsAppAccount

# -------------------------GET TEMPLATES----------------------------


@pytest.mark.asyncio
@patch(
    "app.service.template_service.template_service.fetch_templates",
    new_callable=AsyncMock,
)
async def test_get_templates_success(
    mock_fetch: AsyncMock,
    client,
    mock_auth,
    seed_account,
    db_session,
) -> None:
    mock_fetch.return_value = {
        "data": [{"name": "test_template", "status": "APPROVED"}]
    }

    response = await client.get(
        f"/templates/account/{seed_account.id}?status=APPROVED?limit=10"
    )

    assert response.status_code == 200
    data = response.json()

    assert data["message"] == "Templates fetched successfully"
    assert len(data["data"]["data"]) == 1

    result = await db_session.execute(select(WhatsAppAccount))
    account = result.scalar_one_or_none()

    assert account is not None
    assert account.id == seed_account.id

    mock_fetch.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_templates_account_not_found(
    client,
    mock_auth,
    db_session,
) -> None:
    response = await client.get("/templates/account/999")

    data = response.json()

    assert response.status_code == 404
    assert data["message"] == "Account not found"

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
async def test_get_templates_account_not_configured(
    client,
    mock_auth,
    seed_account2,
    db_session,
) -> None:
    response = await client.get(
        f"/templates/account/{seed_account2.id}?status=APPROVED?limit=10"
    )

    assert response.status_code == 400
    data = response.json()

    assert data["message"] == "Account not properly configured"

    result = await db_session.execute(
        select(WhatsAppAccount).where(
            WhatsAppAccount.id == seed_account2.id,
            WhatsAppAccount.user_id == mock_auth.id,
            WhatsAppAccount.waba_id.is_(None),
            WhatsAppAccount.deleted_at.is_(None),
        )
    )
    account = result.scalar_one_or_none()

    assert account.waba_id is None


@pytest.mark.asyncio
async def test_get_templates_account_token_invalid(
    client,
    mock_auth,
    seed_account3,
    db_session,
) -> None:
    response = await client.get(
        f"/templates/account/{seed_account3.id}?status=APPROVED?limit=10"
    )

    assert response.status_code == 400
    data = response.json()

    assert (
        data["message"]
        == "Invalid access token format. Please update your WhatsApp account with a valid Meta access token."
    )

    result = await db_session.execute(
        select(WhatsAppAccount).where(
            WhatsAppAccount.id == seed_account3.id,
            WhatsAppAccount.user_id == mock_auth.id,
            WhatsAppAccount.deleted_at.is_(None),
        )
    )
    account = result.scalar_one_or_none()

    assert len(account.token) < 20


@pytest.mark.asyncio
async def test_get_templates_unauthorized(client, seed_account) -> None:
    response = await client.get(
        f"/templates/account/{seed_account.id}?status=APPROVED?limit=10"
    )

    assert response.status_code == 401
    assert (
        response.json()["detail"]
        == "Authentication required: provide JWT token or X-API-Key header"
    )


# -------------------------GET TEMPLATE----------------------------


@pytest.mark.asyncio
@patch(
    "app.service.template_service.template_service.get_template_by_name",
    new_callable=AsyncMock,
)
@patch("app.service.template_service.template_service.parse_template_variables")
async def test_get_template_detail_success(
    mock_parse,
    mock_get_template,
    client,
    mock_auth,
    seed_account,
) -> None:
    template_name = "welcome_template"

    mock_get_template.return_value = {
        "name": template_name,
        "language": "en_US",
        "components": [{"type": "BODY", "text": "Hello {{1}}"}],
    }

    mock_parse.return_value = ["{{1}}"]

    response = await client.get(f"/templates/account/{seed_account.id}/{template_name}")

    assert response.status_code == 200

    data = response.json()

    assert data["message"] == "Template details retrieved successfully"
    assert data["data"]["variables"] == ["{{1}}"]


@pytest.mark.asyncio
async def test_get_template_account_not_found(
    client,
    mock_auth,
    db_session,
) -> None:
    template_name = "welcome_template"
    response = await client.get(f"/templates/account/999/{template_name}")

    data = response.json()

    assert response.status_code == 404
    assert data["message"] == "Account not found"

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
async def test_get_template_account_not_configured(
    client,
    mock_auth,
    seed_account2,
    db_session,
) -> None:
    template_name = "welcome_template"
    response = await client.get(
        f"/templates/account/{seed_account2.id}/{template_name}"
    )

    assert response.status_code == 400
    data = response.json()

    assert data["message"] == "Account not properly configured"

    result = await db_session.execute(
        select(WhatsAppAccount).where(
            WhatsAppAccount.id == seed_account2.id,
            WhatsAppAccount.user_id == mock_auth.id,
            WhatsAppAccount.waba_id.is_(None),
            WhatsAppAccount.deleted_at.is_(None),
        )
    )
    account = result.scalar_one_or_none()

    assert account.waba_id is None


@pytest.mark.asyncio
async def test_get_template_account_token_invalid(
    client,
    mock_auth,
    seed_account3,
    db_session,
) -> None:
    template_name = "welcome_template"
    response = await client.get(
        f"/templates/account/{seed_account3.id}/{template_name}"
    )

    assert response.status_code == 400
    data = response.json()

    assert (
        data["message"]
        == "Invalid access token format. Please update your WhatsApp account with a valid Meta access token."
    )

    result = await db_session.execute(
        select(WhatsAppAccount).where(
            WhatsAppAccount.id == seed_account3.id,
            WhatsAppAccount.user_id == mock_auth.id,
            WhatsAppAccount.deleted_at.is_(None),
        )
    )
    account = result.scalar_one_or_none()

    assert len(account.token) < 20


@pytest.mark.asyncio
@patch(
    "app.service.template_service.template_service.get_template_by_name",
    new_callable=AsyncMock,
)
async def test_get_template_not_found(
    mock_get_template,
    client,
    mock_auth,
    seed_account,
) -> None:
    mock_get_template.return_value = None

    response = await client.get(
        f"/templates/account/{seed_account.id}/unknown_template"
    )

    assert response.status_code == 404
    assert response.json()["message"] == "Template not found"


@pytest.mark.asyncio
@patch(
    "app.service.template_service.template_service.fetch_templates",
    new_callable=AsyncMock,
)
async def test_get_template_meta_api_error(
    mock_fetch_templates,
    client,
    mock_auth,
    seed_account,
) -> None:
    mock_fetch_templates.side_effect = ErrorResponse(500, "Meta API error")

    response = await client.get(
        f"/templates/account/{seed_account.id}/test_template?language=en"
    )

    assert response.status_code == 500

    data = response.json()

    assert "Meta API error" in data["message"]


@pytest.mark.asyncio
async def test_get_template_unauthorized(client, seed_account) -> None:
    template_name = "hello_world"
    response = await client.get(f"/templates/account/{seed_account.id}/{template_name}")

    assert response.status_code == 401
    assert (
        response.json()["detail"]
        == "Authentication required: provide JWT token or X-API-Key header"
    )
