from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.models.model import (
    Broadcast,
    BroadcastContact,
    BroadcastStatus,
    WhatsAppAccount,
)
from tests.helpers import create_csv_file

# -------------------------CREATE BROADCAST----------------------------


@pytest.mark.asyncio
@patch(
    "app.service.template_service.template_service.get_template_by_name",
    new_callable=AsyncMock,
)
async def test_create_broadcast_success(
    mock_template,
    client,
    mock_auth,
    seed_account,
    db_session,
):
    mock_template.return_value = {"name": "test_template"}

    payload = {
        "name": "Test Campaign",
        "template_name": "test_template",
        "template_language": "en",
    }

    response = await client.post(
        f"/broadcasts/account/{seed_account.id}",
        json=payload,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["message"] == "Broadcast campaign created successfully"

    result = await db_session.execute(
        select(Broadcast).where(
            Broadcast.account_id == seed_account.id,
            Broadcast.name == "Test Campaign",
        )
    )
    broadcast = result.scalar_one_or_none()

    assert broadcast is not None
    assert broadcast.status.name == "DRAFT"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload, expected_error",
    [
        (
            {
                "name": "",
                "template_name": "test_template",
                "template_language": "en",
            },
            "Value error, Campaign name must be between 1 and 255 characters",
        ),
        (
            {
                "name": "Test Campaign",
                "template_name": "test_template",
                "template_language": "",
            },
            "Value error, Template language must be a valid BCP-47 code",
        ),
    ],
)
async def test_create_broadcast_validation_fields(
    client,
    mock_auth,
    seed_account,
    payload,
    expected_error,
):
    response = await client.post(
        f"/broadcasts/account/{seed_account.id}",
        json=payload,
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["msg"] == expected_error


@pytest.mark.asyncio
async def test_create_broadcast_extra_fields(
    client,
    mock_auth,
    seed_account,
):
    payload = {
        "name": "Test Campaign",
        "template_name": "test_template",
        "template_language": "en",
        "extra": "field",
    }

    response = await client.post(
        f"/broadcasts/account/{seed_account.id}",
        json=payload,
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["msg"] == "Extra inputs are not permitted"


@pytest.mark.asyncio
async def test_create_broadcast_missing_fields(
    client,
    mock_auth,
    seed_account,
):
    response = await client.post(
        f"/broadcasts/account/{seed_account.id}",
        json={
            "name": "Test Campaign",
            "template_language": "en",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["msg"] == "Field required"


@pytest.mark.asyncio
async def test_create_broadcast_account_not_found(
    client,
    mock_auth,
    db_session,
):
    payload = {
        "name": "Test Campaign",
        "template_name": "test_template",
        "template_language": "en",
    }

    response = await client.post(
        "/broadcasts/account/999",
        json=payload,
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
@patch(
    "app.service.template_service.template_service.get_template_by_name",
    new_callable=AsyncMock,
)
async def test_create_broadcast_template_not_found(
    mock_template,
    client,
    mock_auth,
    seed_account,
    db_session,
):
    template_name = "invalid_template"
    mock_template.return_value = None

    payload = {
        "name": "Test Campaign",
        "template_name": template_name,
        "template_language": "en",
    }

    response = await client.post(
        f"/broadcasts/account/{seed_account.id}",
        json=payload,
    )

    assert response.status_code == 400
    assert (
        response.json()["message"]
        == f"Template '{template_name}' not found or not approved"
    )

    result = await db_session.execute(select(Broadcast))
    broadcast = result.scalar_one_or_none()

    assert broadcast is None


@pytest.mark.asyncio
async def test_create_broadcast_missing_credentials(
    client,
    mock_auth,
    seed_account2,
    db_session,
):
    payload = {
        "name": "Test Campaign",
        "template_name": "test_template",
        "template_language": "en",
    }

    response = await client.post(
        f"/broadcasts/account/{seed_account2.id}",
        json=payload,
    )

    assert response.status_code == 400
    assert response.json()["message"] == "Missing WhatsApp account credentials"

    result = await db_session.execute(select(Broadcast))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_create_broadcast_inactive_account(
    client,
    mock_auth,
    seed_inactive_account,
    db_session,
):
    payload = {
        "name": "Test Campaign",
        "template_name": "test_template",
        "template_language": "en",
    }

    response = await client.post(
        f"/broadcasts/account/{seed_inactive_account.id}",
        json=payload,
    )

    assert response.status_code == 403
    assert response.json()["message"] == "Account is inactive"

    result = await db_session.execute(
        select(WhatsAppAccount).where(WhatsAppAccount.id == seed_inactive_account.id)
    )
    account = result.scalar_one_or_none()
    assert account is not None
    assert account.is_active is False


@pytest.mark.asyncio
async def test_create_broadcast_unauthorized(client, seed_account):
    payload = {
        "name": "Test Campaign",
        "template_name": "test_template",
        "template_language": "en",
    }

    response = await client.post(
        f"/broadcasts/account/{seed_account.id}",
        json=payload,
    )

    assert response.status_code == 401
    assert (
        response.json()["detail"]
        == "Authentication required: provide JWT token or X-API-Key header"
    )


# -------------------------GET BROADCASTS----------------------------


@pytest.mark.asyncio
async def test_get_broadcasts_success(
    client,
    mock_auth,
    seed_account,
    seed_broadcast,
    db_session,
):
    response = await client.get(
        f"/broadcasts/account/{seed_account.id}?page=1&page_size=2"
    )

    assert response.status_code == 200

    data = response.json()
    assert data["message"] == "Broadcast campaigns retrieved successfully"

    result = await db_session.execute(
        select(Broadcast).where(Broadcast.account_id == seed_account.id)
    )
    broadcasts = result.scalars().all()

    assert broadcasts is not None


@pytest.mark.asyncio
async def test_get_broadcasts_account_not_found(
    client,
    mock_auth,
    db_session,
):
    response = await client.get("/broadcasts/account/999")

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
async def test_get_broadcasts_inactive_account(
    client,
    mock_auth,
    seed_inactive_account,
    db_session,
):
    response = await client.get(f"/broadcasts/account/{seed_inactive_account.id}")

    assert response.status_code == 403
    assert response.json()["message"] == "Account is inactive"

    result = await db_session.execute(
        select(WhatsAppAccount).where(WhatsAppAccount.id == seed_inactive_account.id)
    )
    account = result.scalar_one_or_none()
    assert account is not None
    assert account.is_active is False


@pytest.mark.asyncio
async def test_get_broadcasts_unauthorized(
    client,
    seed_account,
):
    response = await client.get(f"/broadcasts/account/{seed_account.id}")

    assert response.status_code == 401
    assert (
        response.json()["detail"]
        == "Authentication required: provide JWT token or X-API-Key header"
    )


# -------------------------GET BROADCAST----------------------------


@pytest.mark.asyncio
async def test_get_broadcast_success(
    client,
    mock_auth,
    seed_account,
    seed_broadcast,
    db_session,
):
    response = await client.get(
        f"/broadcasts/account/{seed_account.id}/{seed_broadcast.id}"
    )

    assert response.status_code == 200

    data = response.json()
    assert data["message"] == "Broadcast campaign retrieved successfully"

    result = await db_session.execute(
        select(Broadcast).where(Broadcast.id == seed_broadcast.id)
    )
    db_broadcast = result.scalar_one_or_none()

    assert db_broadcast is not None


@pytest.mark.asyncio
async def test_get_broadcast_account_not_found(
    client,
    mock_auth,
    seed_broadcast,
    db_session,
):
    response = await client.get(f"/broadcasts/account/999/{seed_broadcast.id}")

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
async def test_get_broadcast_not_found(
    client,
    mock_auth,
    seed_account,
    db_session,
):
    response = await client.get(f"/broadcasts/account/{seed_account.id}/999")

    assert response.status_code == 404
    assert response.json()["message"] == "Broadcast campaign not found"

    result = await db_session.execute(select(Broadcast).where(Broadcast.id == 999))
    broadcast = result.scalar_one_or_none()

    assert broadcast is None


@pytest.mark.asyncio
async def test_get_broadcast_inactive_account(
    client,
    mock_auth,
    seed_inactive_account,
    seed_broadcast,
    db_session,
):
    response = await client.get(
        f"/broadcasts/account/{seed_inactive_account.id}/{seed_broadcast.id}"
    )

    assert response.status_code == 403
    assert response.json()["message"] == "Account is inactive"

    result = await db_session.execute(
        select(WhatsAppAccount).where(WhatsAppAccount.id == seed_inactive_account.id)
    )
    account = result.scalar_one_or_none()
    assert account is not None
    assert account.is_active is False


@pytest.mark.asyncio
async def test_get_broadcast_unauthorized(
    client,
    seed_account,
    seed_broadcast,
):
    response = await client.get(
        f"/broadcasts/account/{seed_account.id}/{seed_broadcast.id}"
    )

    assert response.status_code == 401
    assert (
        response.json()["detail"]
        == "Authentication required: provide JWT token or X-API-Key header"
    )


# -------------------------GET BROADCAST CONTACTS----------------------------


@pytest.mark.asyncio
async def test_get_broadcast_contacts_success(
    client,
    mock_auth,
    seed_account,
    seed_broadcast_contacts,
    seed_broadcast,
    db_session,
):
    response = await client.get(
        f"/broadcasts/account/{seed_account.id}/{seed_broadcast.id}/contacts?status=PENDING"
    )

    assert response.status_code == 200

    data = response.json()
    assert data["message"] == "Broadcast contacts retrieved successfully"

    result = await db_session.execute(
        select(BroadcastContact).where(
            BroadcastContact.broadcast_id == seed_broadcast.id,
            BroadcastContact.status == "PENDING",
        )
    )
    contacts = result.scalars().all()

    api_data = data["data"]

    assert api_data["total"] == len(contacts)


@pytest.mark.asyncio
async def test_get_broadcast_contacts_account_not_found(
    client,
    mock_auth,
    seed_broadcast_contacts,
    seed_broadcast,
    db_session,
):
    response = await client.get(f"/broadcasts/account/999/{seed_broadcast.id}/contacts")

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
async def test_get_broadcast_contacts_broadcast_not_found(
    client,
    mock_auth,
    seed_account,
    db_session,
):
    response = await client.get(
        f"/broadcasts/account/{seed_account.id}/999999/contacts"
    )

    assert response.status_code == 404
    assert response.json()["message"] == "Broadcast campaign not found"

    result = await db_session.execute(select(Broadcast).where(Broadcast.id == 999))
    broadcast = result.scalar_one_or_none()

    assert broadcast is None


@pytest.mark.asyncio
async def test_get_broadcast_contacts_invalid_status(
    client,
    mock_auth,
    seed_account,
    seed_broadcast_contacts,
    seed_broadcast,
):
    response = await client.get(
        f"/broadcasts/account/{seed_account.id}/{seed_broadcast.id}/contacts?status=INVALID"
    )

    assert response.status_code == 400

    data = response.json()
    assert "Status must be one of" in data["message"]


@pytest.mark.asyncio
async def test_get_broadcast_contacts_inactive_account(
    client,
    mock_auth,
    seed_inactive_account,
    seed_broadcast,
    db_session,
):
    response = await client.get(
        f"/broadcasts/account/{seed_inactive_account.id}/{seed_broadcast.id}/contacts"
    )

    assert response.status_code == 403
    assert response.json()["message"] == "Account is inactive"

    result = await db_session.execute(
        select(WhatsAppAccount).where(WhatsAppAccount.id == seed_inactive_account.id)
    )
    account = result.scalar_one_or_none()
    assert account is not None
    assert account.is_active is False


@pytest.mark.asyncio
async def test_get_broadcast_contacts_unauthorized(
    client,
    seed_account,
    seed_broadcast_contacts,
    seed_broadcast,
):
    response = await client.get(
        f"/broadcasts/account/{seed_account.id}/{seed_broadcast.id}/contacts"
    )

    assert response.status_code == 401
    assert (
        response.json()["detail"]
        == "Authentication required: provide JWT token or X-API-Key header"
    )


# -------------------------DELETE BROADCAST----------------------------


@pytest.mark.asyncio
async def test_delete_broadcast_success(
    client,
    mock_auth,
    seed_account,
    seed_broadcast,
    db_session,
):
    response = await client.delete(
        f"/broadcasts/account/{seed_account.id}/{seed_broadcast.id}"
    )

    assert response.status_code == 200

    data = response.json()
    assert data["message"] == "Broadcast campaign deleted successfully"
    assert data["data"]["broadcast_id"] == seed_broadcast.id

    result = await db_session.execute(
        select(Broadcast).where(Broadcast.id == seed_broadcast.id)
    )
    broadcast = result.scalar_one_or_none()

    assert broadcast is None


@pytest.mark.asyncio
async def test_delete_broadcast_account_not_found(
    client,
    mock_auth,
    seed_broadcast,
    db_session,
):
    response = await client.delete(f"/broadcasts/account/999/{seed_broadcast.id}")

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
async def test_delete_broadcast_not_found(
    client,
    mock_auth,
    seed_account,
    db_session,
):
    response = await client.delete(f"/broadcasts/account/{seed_account.id}/999999")

    assert response.status_code == 404
    assert response.json()["message"] == "Broadcast campaign not found"

    result = await db_session.execute(select(Broadcast).where(Broadcast.id == 999999))
    broadcast = result.scalar_one_or_none()

    assert broadcast is None


@pytest.mark.asyncio
async def test_delete_broadcast_inactive_account(
    client,
    mock_auth,
    seed_inactive_account,
    seed_broadcast,
    db_session,
):
    response = await client.delete(
        f"/broadcasts/account/{seed_inactive_account.id}/{seed_broadcast.id}"
    )

    assert response.status_code == 403
    assert response.json()["message"] == "Account is inactive"

    result = await db_session.execute(
        select(WhatsAppAccount).where(WhatsAppAccount.id == seed_inactive_account.id)
    )
    account = result.scalar_one_or_none()
    assert account is not None
    assert account.is_active is False


@pytest.mark.asyncio
async def test_delete_broadcast_unauthorized(
    client,
    seed_account,
    seed_broadcast,
):
    response = await client.delete(
        f"/broadcasts/account/{seed_account.id}/{seed_broadcast.id}"
    )

    assert response.status_code == 401
    assert (
        response.json()["detail"]
        == "Authentication required: provide JWT token or X-API-Key header"
    )


# -------------------------UPLOAD CONTACTS----------------------------


@pytest.mark.asyncio
async def test_upload_contacts_success(
    client,
    mock_auth,
    seed_account,
    seed_broadcast,
    db_session,
):
    csv_content = "phone_number\n9999999991\n9999999992"

    response = await client.post(
        f"/broadcasts/account/{seed_account.id}/{seed_broadcast.id}/contacts/upload",
        files=[create_csv_file(csv_content)],
    )

    assert response.status_code == 201

    data = response.json()
    assert data["message"] == "Contacts uploaded successfully"

    api_data = data["data"]

    result = await db_session.execute(
        select(BroadcastContact).where(
            BroadcastContact.broadcast_id == seed_broadcast.id
        )
    )
    contacts = result.scalars().all()

    assert len(contacts) == api_data["contacts_uploaded"]

    result = await db_session.execute(
        select(Broadcast).where(Broadcast.id == seed_broadcast.id)
    )
    broadcast = result.scalar_one()

    assert broadcast.total_contacts == len(contacts)


@pytest.mark.asyncio
async def test_upload_contacts_account_not_found(
    client,
    mock_auth,
    seed_broadcast,
    db_session,
):
    response = await client.post(
        f"/broadcasts/account/999/{seed_broadcast.id}/contacts/upload",
        files=[create_csv_file("phone_number\n9999999991")],
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
async def test_upload_contacts_broadcast_not_found(
    client,
    mock_auth,
    seed_account,
    db_session,
):
    response = await client.post(
        f"/broadcasts/account/{seed_account.id}/999/contacts/upload",
        files=[create_csv_file("phone_number\n9999999991")],
    )

    assert response.status_code == 404
    assert response.json()["message"] == "Broadcast not found"

    result = await db_session.execute(select(Broadcast).where(Broadcast.id == 999))
    broadcast = result.scalar_one_or_none()

    assert broadcast is None


@pytest.mark.asyncio
async def test_upload_contacts_invalid_status(
    client,
    mock_auth,
    seed_account,
    seed_broadcast_sent,
):
    response = await client.post(
        f"/broadcasts/account/{seed_account.id}/{seed_broadcast_sent.id}/contacts/upload",
        files=[create_csv_file("phone_number\n9999999991")],
    )

    assert response.status_code == 400
    assert "Cannot upload contacts" in response.json()["message"]


@pytest.mark.asyncio
async def test_upload_contacts_no_file(
    client,
    mock_auth,
    seed_account,
    seed_broadcast,
):
    response = await client.post(
        f"/broadcasts/account/{seed_account.id}/{seed_broadcast.id}/contacts/upload"
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["msg"] == "Field required"


@pytest.mark.asyncio
async def test_upload_contacts_invalid_file_type(
    client,
    mock_auth,
    seed_account,
    seed_broadcast,
):
    response = await client.post(
        f"/broadcasts/account/{seed_account.id}/{seed_broadcast.id}/contacts/upload",
        files=[create_csv_file("data", filename="test.txt")],
    )

    assert response.status_code == 400
    assert response.json()["message"] == "File must be a CSV file"


@pytest.mark.asyncio
async def test_upload_contacts_with_component_variables(
    client,
    mock_auth,
    seed_account,
    seed_broadcast,
    db_session,
):
    """CSV with typed component headers stores a components list in template_variables."""
    csv_content = (
        "phone_number,header_1,body_1,body_2\n9999999991,Hello,Order #123,₹499"
    )

    response = await client.post(
        f"/broadcasts/account/{seed_account.id}/{seed_broadcast.id}/contacts/upload",
        files=[create_csv_file(csv_content)],
    )

    assert response.status_code == 201
    assert response.json()["data"]["contacts_uploaded"] == 1

    result = await db_session.execute(
        select(BroadcastContact).where(
            BroadcastContact.broadcast_id == seed_broadcast.id
        )
    )
    contact = result.scalars().first()

    assert isinstance(contact.template_variables, list)
    types = {c["type"] for c in contact.template_variables}
    assert "header" in types
    assert "body" in types

    header = next(c for c in contact.template_variables if c["type"] == "header")
    assert header["parameters"][0] == {"type": "text", "text": "Hello"}

    body = next(c for c in contact.template_variables if c["type"] == "body")
    assert body["parameters"][0] == {"type": "text", "text": "Order #123"}
    assert body["parameters"][1] == {"type": "text", "text": "₹499"}


@pytest.mark.asyncio
async def test_upload_contacts_without_variables_stored_as_none(
    client,
    mock_auth,
    seed_account,
    seed_broadcast,
    db_session,
):
    """CSV with only phone numbers stores None in template_variables."""
    csv_content = "phone_number\n9999999991\n9999999992"

    response = await client.post(
        f"/broadcasts/account/{seed_account.id}/{seed_broadcast.id}/contacts/upload",
        files=[create_csv_file(csv_content)],
    )

    assert response.status_code == 201
    assert response.json()["data"]["contacts_uploaded"] == 2

    result = await db_session.execute(
        select(BroadcastContact).where(
            BroadcastContact.broadcast_id == seed_broadcast.id
        )
    )
    contacts = result.scalars().all()

    assert all(c.template_variables is None for c in contacts)


@pytest.mark.asyncio
async def test_upload_contacts_button_variables(
    client,
    mock_auth,
    seed_account,
    seed_broadcast,
    db_session,
):
    """CSV with button column stores a quick_reply button component."""
    csv_content = "phone_number,body_1,button_0\n9999999991,John,CONFIRM_YES"

    response = await client.post(
        f"/broadcasts/account/{seed_account.id}/{seed_broadcast.id}/contacts/upload",
        files=[create_csv_file(csv_content)],
    )

    assert response.status_code == 201

    result = await db_session.execute(
        select(BroadcastContact).where(
            BroadcastContact.broadcast_id == seed_broadcast.id
        )
    )
    contact = result.scalars().first()

    assert isinstance(contact.template_variables, list)
    button = next(c for c in contact.template_variables if c["type"] == "button")
    assert button["sub_type"] == "quick_reply"
    assert button["index"] == 0
    assert button["parameters"][0] == {"type": "payload", "payload": "CONFIRM_YES"}


@pytest.mark.asyncio
@patch("app.controller.broadcast_controller.parse_csv_file", new_callable=AsyncMock)
async def test_upload_contacts_no_valid_contacts(
    mock_parse,
    client,
    mock_auth,
    seed_account,
    seed_broadcast,
):
    mock_parse.return_value = ([], [])

    response = await client.post(
        f"/broadcasts/account/{seed_account.id}/{seed_broadcast.id}/contacts/upload",
        files=[create_csv_file("invalid")],
    )

    assert response.status_code == 400
    assert "no valid contacts" in response.json()["message"].lower()


@pytest.mark.asyncio
async def test_upload_contacts_inactive_account(
    client,
    mock_auth,
    seed_inactive_account,
    seed_broadcast,
    db_session,
):
    response = await client.post(
        f"/broadcasts/account/{seed_inactive_account.id}/{seed_broadcast.id}/contacts/upload",
        files=[create_csv_file("phone_number\n9999999991")],
    )

    assert response.status_code == 403
    assert response.json()["message"] == "Account is inactive"

    result = await db_session.execute(
        select(WhatsAppAccount).where(WhatsAppAccount.id == seed_inactive_account.id)
    )
    account = result.scalar_one_or_none()
    assert account is not None
    assert account.is_active is False


@pytest.mark.asyncio
async def test_upload_contacts_unauthorized(
    client,
    seed_account,
    seed_broadcast,
):
    response = await client.post(
        f"/broadcasts/account/{seed_account.id}/{seed_broadcast.id}/contacts/upload"
    )

    assert response.status_code == 401
    assert (
        response.json()["detail"]
        == "Authentication required: provide JWT token or X-API-Key header"
    )


# -------------------------TRIGGER BROADCAST----------------------------


@pytest.mark.asyncio
async def test_trigger_broadcast_success(
    client,
    mock_auth,
    seed_account,
    seed_broadcast,
    db_session,
):
    seed_broadcast.total_contacts = 2
    seed_broadcast.status = BroadcastStatus.DRAFT
    await db_session.commit()

    response = await client.post(
        f"/broadcasts/account/{seed_account.id}/{seed_broadcast.id}/trigger"
    )

    assert response.status_code == 200

    data = response.json()
    assert data["message"].startswith("Broadcast triggered successfully")

    result = await db_session.execute(
        select(Broadcast).where(Broadcast.id == seed_broadcast.id)
    )
    broadcast = result.scalar_one()

    assert broadcast.status == "QUEUED"


@pytest.mark.asyncio
async def test_trigger_broadcast_account_not_found(
    client,
    mock_auth,
    seed_broadcast,
    db_session,
):
    response = await client.post(f"/broadcasts/account/999/{seed_broadcast.id}/trigger")

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
async def test_trigger_broadcast_not_found(
    client,
    mock_auth,
    seed_account,
    db_session,
):
    response = await client.post(f"/broadcasts/account/{seed_account.id}/999/trigger")

    assert response.status_code == 400
    assert response.json()["message"] == "Broadcast not found"

    result = await db_session.execute(select(Broadcast).where(Broadcast.id == 999))
    broadcast = result.scalar_one_or_none()

    assert broadcast is None


@pytest.mark.asyncio
async def test_trigger_broadcast_no_contacts(
    client,
    mock_auth,
    seed_account,
    seed_broadcast,
    db_session,
):
    seed_broadcast.total_contacts = 0
    await db_session.commit()

    response = await client.post(
        f"/broadcasts/account/{seed_account.id}/{seed_broadcast.id}/trigger"
    )

    assert response.status_code == 400
    assert "no contacts" in response.json()["message"].lower()


@pytest.mark.asyncio
async def test_trigger_broadcast_invalid_status(
    client,
    mock_auth,
    seed_account,
    seed_broadcast,
    db_session,
):
    seed_broadcast.total_contacts = 2
    seed_broadcast.status = BroadcastStatus.QUEUED
    await db_session.commit()

    response = await client.post(
        f"/broadcasts/account/{seed_account.id}/{seed_broadcast.id}/trigger"
    )

    assert response.status_code == 400
    assert "Cannot trigger broadcast" in response.json()["message"]


@patch(
    "app.service.broadcast_service.BroadcastService.trigger_broadcast",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_trigger_broadcast_failure(
    mock_trigger,
    client,
    mock_auth,
    seed_account,
    seed_broadcast,
):
    mock_trigger.return_value = False

    response = await client.post(
        f"/broadcasts/account/{seed_account.id}/{seed_broadcast.id}/trigger"
    )

    assert response.status_code == 400
    assert "Failed to trigger broadcast:" in response.json()["message"]


@pytest.mark.asyncio
async def test_trigger_broadcast_inactive_account(
    client,
    mock_auth,
    seed_inactive_account,
    seed_broadcast,
    db_session,
):
    response = await client.post(
        f"/broadcasts/account/{seed_inactive_account.id}/{seed_broadcast.id}/trigger"
    )

    assert response.status_code == 403
    assert response.json()["message"] == "Account is inactive"

    result = await db_session.execute(
        select(WhatsAppAccount).where(WhatsAppAccount.id == seed_inactive_account.id)
    )
    account = result.scalar_one_or_none()
    assert account is not None
    assert account.is_active is False


@pytest.mark.asyncio
async def test_trigger_broadcast_unauthorized(
    client,
    seed_account,
    seed_broadcast,
):
    response = await client.post(
        f"/broadcasts/account/{seed_account.id}/{seed_broadcast.id}/trigger"
    )

    assert response.status_code == 401
    assert (
        response.json()["detail"]
        == "Authentication required: provide JWT token or X-API-Key header"
    )
