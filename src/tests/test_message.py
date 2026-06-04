import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from app.models.model import WhatsAppAccount, WhatsAppMessage

# -------------------------MESSAGE SEND----------------------------


@pytest.mark.asyncio
@patch("app.controller.message_controller.enqueue_and_trigger", new_callable=AsyncMock)
@patch(
    "app.service.whatsapp_service.WhatsAppService.download_media",
    new_callable=AsyncMock,
)
@patch(
    "app.controller.message_controller.S3Service.upload_media", new_callable=AsyncMock
)
async def test_send_message_api(
    mock_s3,
    mock_download,
    mock_enqueue,
    client,
    seed_account,
    db_session,
) -> None:
    mock_download.return_value = b"fake-image-bytes"
    mock_s3.return_value = "https://s3.fake/test.jpg"

    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": "wamid.inbound123",
                                    "from": str(seed_account.phone_number),
                                    "type": "text",
                                    "text": {"body": "Hello"},
                                }
                            ],
                            "metadata": {"display_phone_number": "1111111111"},
                        }
                    }
                ]
            }
        ]
    }

    response = await client.post("/message/send", json=payload)

    assert response.status_code == 200
    assert response.json()["message"] == "Message received"

    result = await db_session.execute(select(WhatsAppMessage))
    message = result.scalar_one_or_none()

    assert message is not None
    assert message.message == "Hello"
    assert message.meta_message_id == "wamid.inbound123"


@pytest.mark.asyncio
@patch(
    "app.controller.message_controller.enqueue_and_trigger",
    new_callable=AsyncMock,
)
async def test_send_message_sandbox(
    mock_enqueue,
    client,
    seed_account,
    db_session,
) -> None:

    payload = {
        "from_number": seed_account.phone_number,
        "to_number": 918888888888,
        "message": "Sandbox message test",
        "media_bytes": [
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO5WQ1sAAAAASUVORK5CYII="
        ],
        "sandbox": True,
    }

    response = await client.post("/message/send", json=payload)

    assert response.status_code == 200
    assert response.json()["message"] == "Message received"

    result = await db_session.execute(select(WhatsAppMessage))
    message = result.scalar_one_or_none()

    assert message is not None
    assert message.message == "Sandbox message test"


@pytest.mark.asyncio
@patch("app.controller.message_controller.enqueue_and_trigger", new_callable=AsyncMock)
@patch(
    "app.controller.message_controller.S3Service.upload_media", new_callable=AsyncMock
)
async def test_send_message_sandbox_with_media_type(
    mock_s3,
    mock_enqueue,
    client,
    seed_account,
) -> None:
    mock_s3.return_value = "https://s3.fake/test.jpg"

    payload = {
        "from_number": seed_account.phone_number,
        "to_number": 918888888888,
        "message": "Sandbox message with media type",
        "media_bytes": [
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO5WQ1sAAAAASUVORK5CYII="
        ],
        "media_type": "image/png",
        "sandbox": True,
    }

    response = await client.post("/message/send", json=payload)

    assert response.status_code == 200
    assert response.json()["message"] == "Message received"
    assert response.json()["data"]["media_urls"] == ["https://s3.fake/test.jpg"]

    upload_call_args = mock_s3.call_args
    assert upload_call_args[0][1].endswith(".png")
    assert upload_call_args[0][2] == "image/png"


@pytest.mark.asyncio
async def test_send_message_inactive_account(
    client,
    seed_inactive_account,
    db_session,
) -> None:
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": "9876543210",
                                    "type": "text",
                                    "text": {"body": "Hello"},
                                }
                            ],
                            "metadata": {
                                "display_phone_number": str(
                                    seed_inactive_account.phone_number
                                )
                            },
                        }
                    }
                ]
            }
        ]
    }

    response = await client.post("/message/send", json=payload)

    assert response.status_code == 400
    assert "Account is inactive" in response.json()["message"]

    result = await db_session.execute(
        select(WhatsAppAccount).where(
            WhatsAppAccount.id == seed_inactive_account.id,
            WhatsAppAccount.deleted_at.is_(None),
        )
    )
    account = result.scalar_one()
    assert account.is_active is False

    result = await db_session.execute(select(WhatsAppMessage))
    message = result.scalar_one_or_none()
    assert message is None


# -------------------------ASSISTANT SEND----------------------------


@pytest.mark.asyncio
@patch("PIL.Image.open")
@patch(
    "app.controller.message_controller.S3Service.upload_media", new_callable=AsyncMock
)
@patch(
    "app.controller.message_controller.WhatsAppService.send_message",
    new_callable=AsyncMock,
)
@patch(
    "app.service.session_service.SessionService.create_session_for_number",
    new_callable=AsyncMock,
)
@patch(
    "app.service.account_service.AccountService.get_account",
    new_callable=AsyncMock,
)
async def test_send_llm_message(
    mock_get_account,
    mock_create_session_for_number,
    mock_send,
    mock_s3,
    mock_image_open,
    mock_auth,
    client,
    seed_account,
    seed_session,
    db_session,
) -> None:
    fake_image_bytes = b"fake-image-binary-content-here"
    media_b64 = base64.b64encode(fake_image_bytes).decode("utf-8")

    payload = {
        "account_id": seed_account.id,
        "to_number": 919999999999,
        "message": "Here's your image",
        "media_bytes": [media_b64],
    }

    mock_image = MagicMock()
    mock_image.format = "jpeg"
    mock_image_open.return_value = mock_image

    mock_s3.return_value = "https://s3.bucket/uploaded-image.jpg"
    mock_get_account.return_value = {
        "phone_number_id": seed_account.phone_number_id,
        "token": seed_account.token,
        "phone_number": seed_account.phone_number,
    }
    mock_create_session_for_number.return_value = {
        "id": seed_session.id,
        "account_id": seed_account.id,
        "to_number": 919999999999,
    }
    mock_send.return_value = True

    response = await client.post("/message/assistant/send", json=payload)

    assert response.status_code == 200
    assert response.json()["message"] == "Message dispatched"
    assert response.json()["data"]["session_id"] == seed_session.id
    assert response.json()["data"]["media_urls"] == [
        "https://s3.bucket/uploaded-image.jpg"
    ]

    assert mock_s3.call_count == 1
    assert mock_send.call_count == 1
    assert "https://s3.bucket/uploaded-image.jpg" in mock_send.call_args[1]["message"]

    result = await db_session.execute(select(WhatsAppMessage))
    message = result.scalar_one_or_none()
    assert message is not None
    assert message.role == "assistant"
    assert "Here's your image" in message.message
    assert message.input_tokens is None
    assert message.output_tokens is None


@pytest.mark.asyncio
@patch("PIL.Image.open")
@patch(
    "app.controller.message_controller.S3Service.upload_media", new_callable=AsyncMock
)
@patch(
    "app.controller.message_controller.WhatsAppService.send_message",
    new_callable=AsyncMock,
)
@patch(
    "app.service.session_service.SessionService.create_session_for_number",
    new_callable=AsyncMock,
)
@patch(
    "app.service.account_service.AccountService.get_account",
    new_callable=AsyncMock,
)
async def test_send_llm_message_invalid_media_format(
    mock_get_account,
    mock_create_session_for_number,
    mock_send,
    mock_s3,
    mock_image_open,
    mock_auth,
    client,
    seed_account,
    seed_session,
) -> None:
    mock_image = MagicMock()
    mock_image.format = "abc"
    mock_image_open.return_value = mock_image

    fake_image_bytes = b"fake-gif-binary-content-here"
    media_b64 = base64.b64encode(fake_image_bytes).decode("utf-8")

    payload = {
        "account_id": seed_account.id,
        "to_number": 919999999999,
        "message": "Here's your gif",
        "media_bytes": [media_b64],
    }

    mock_get_account.return_value = {
        "phone_number_id": seed_account.phone_number_id,
        "token": seed_account.token,
        "phone_number": seed_account.phone_number,
    }
    mock_create_session_for_number.return_value = {
        "id": seed_session.id,
        "account_id": seed_account.id,
        "to_number": 919999999999,
    }

    response = await client.post("/message/assistant/send", json=payload)

    assert response.status_code == 400
    assert "Unsupported file format." in response.json()["message"]


@pytest.mark.asyncio
@patch(
    "app.service.account_service.AccountService.get_account",
    new_callable=AsyncMock,
)
async def test_send_llm_account_not_found(
    mock_get_account,
    mock_auth,
    client,
    seed_account,
) -> None:
    mock_get_account.return_value = None

    payload = {
        "account_id": 9999,
        "to_number": 919999999999,
        "message": "Hello",
    }

    response = await client.post("/message/assistant/send", json=payload)

    assert response.status_code == 404
    assert "WhatsApp account not found" in response.json()["message"]


@pytest.mark.asyncio
@patch(
    "app.service.message_service.MessageService.check_account_active",
    new_callable=AsyncMock,
    return_value=False,
)
@patch(
    "app.service.account_service.AccountService.get_account",
    new_callable=AsyncMock,
)
async def test_send_llm_inactive_account(
    mock_get_account,
    _mock_check_active,
    mock_auth,
    client,
    seed_account,
) -> None:
    mock_get_account.return_value = {
        "phone_number_id": seed_account.phone_number_id,
        "token": seed_account.token,
        "phone_number": seed_account.phone_number,
    }

    payload = {
        "account_id": seed_account.id,
        "to_number": 919999999999,
        "message": "Hello",
    }

    response = await client.post("/message/assistant/send", json=payload)

    assert response.status_code == 404
    assert "inactive" in response.json()["message"].lower()


@pytest.mark.asyncio
@patch(
    "app.controller.message_controller.WhatsAppService.send_message",
    new_callable=AsyncMock,
)
@patch(
    "app.service.session_service.SessionService.create_session_for_number",
    new_callable=AsyncMock,
)
@patch(
    "app.service.account_service.AccountService.get_account",
    new_callable=AsyncMock,
)
async def test_send_llm_message_sandbox_skips_whatsapp(
    mock_get_account,
    mock_create_session_for_number,
    mock_send,
    mock_auth,
    client,
    seed_account,
    seed_session,
) -> None:
    mock_get_account.return_value = {
        "phone_number_id": seed_account.phone_number_id,
        "token": seed_account.token,
        "phone_number": seed_account.phone_number,
    }
    mock_create_session_for_number.return_value = {
        "id": seed_session.id,
        "account_id": seed_account.id,
        "to_number": 919999999999,
    }

    payload = {
        "account_id": seed_account.id,
        "to_number": 919999999999,
        "message": "Sandbox test message",
        "sandbox": True,
    }

    response = await client.post("/message/assistant/send", json=payload)

    assert response.status_code == 200
    assert response.json()["message"] == "Message dispatched"
    mock_send.assert_not_called()


@pytest.mark.asyncio
@patch(
    "app.controller.message_controller.WhatsAppService.send_message",
    new_callable=AsyncMock,
)
@patch(
    "app.service.session_service.SessionService.create_session_for_number",
    new_callable=AsyncMock,
)
@patch(
    "app.service.account_service.AccountService.get_account",
    new_callable=AsyncMock,
)
async def test_send_llm_creates_new_session_when_none_found(
    mock_get_account,
    mock_create_session_for_number,
    mock_send,
    mock_auth,
    client,
    seed_account,
    seed_session,
    db_session,
) -> None:
    mock_get_account.return_value = {
        "phone_number_id": seed_account.phone_number_id,
        "token": seed_account.token,
        "phone_number": seed_account.phone_number,
    }
    mock_create_session_for_number.return_value = {
        "id": seed_session.id,
        "account_id": seed_account.id,
        "to_number": 919111111111,
    }
    mock_send.return_value = True

    payload = {
        "account_id": seed_account.id,
        "to_number": 919111111111,
        "message": "First message to new contact",
    }

    response = await client.post("/message/assistant/send", json=payload)

    assert response.status_code == 200
    assert response.json()["data"]["session_id"] == seed_session.id

    mock_create_session_for_number.assert_called_once_with(
        seed_account.id, 919111111111
    )

    result = await db_session.execute(select(WhatsAppMessage))
    message = result.scalar_one_or_none()
    assert message is not None
    assert message.role == "assistant"


@pytest.mark.asyncio
@patch(
    "app.controller.message_controller.WhatsAppService.send_template_message",
    new_callable=AsyncMock,
)
@patch(
    "app.service.session_service.SessionService.create_session_for_number",
    new_callable=AsyncMock,
)
@patch(
    "app.service.account_service.AccountService.get_account",
    new_callable=AsyncMock,
)
async def test_send_llm_template(
    mock_get_account,
    mock_create_session_for_number,
    mock_send_template,
    mock_auth,
    client,
    seed_account,
    seed_session,
    db_session,
) -> None:
    mock_get_account.return_value = {
        "phone_number_id": seed_account.phone_number_id,
        "token": seed_account.token,
        "phone_number": seed_account.phone_number,
    }
    mock_create_session_for_number.return_value = {
        "id": seed_session.id,
        "account_id": seed_account.id,
        "to_number": 919999999999,
    }
    mock_send_template.return_value = {"message_id": "wamid.test123", "status": "sent"}

    payload = {
        "account_id": seed_account.id,
        "to_number": 919999999999,
        "template": {
            "name": "welcome_message",
            "language": "en_US",
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": "John"},
                        {"type": "text", "text": "Premium"},
                    ],
                }
            ],
        },
    }

    response = await client.post("/message/assistant/send", json=payload)

    assert response.status_code == 200
    assert response.json()["message"] == "Template dispatched"
    assert response.json()["data"]["session_id"] == seed_session.id

    mock_send_template.assert_called_once_with(
        phone_number_id=seed_account.phone_number_id,
        to_number="919999999999",
        template_name="welcome_message",
        language="en_US",
        access_token=seed_account.token,
        components=[
            {
                "type": "body",
                "parameters": [
                    {"type": "text", "text": "John"},
                    {"type": "text", "text": "Premium"},
                ],
            }
        ],
    )

    result = await db_session.execute(select(WhatsAppMessage))
    message = result.scalar_one_or_none()
    assert message is not None
    assert message.role == "assistant"
    assert "welcome_message" in message.message


@pytest.mark.asyncio
@patch(
    "app.controller.message_controller.WhatsAppService.send_template_message",
    new_callable=AsyncMock,
)
@patch(
    "app.service.session_service.SessionService.create_session_for_number",
    new_callable=AsyncMock,
)
@patch(
    "app.service.account_service.AccountService.get_account",
    new_callable=AsyncMock,
)
async def test_send_llm_template_with_header_image(
    mock_get_account,
    mock_create_session_for_number,
    mock_send_template,
    mock_auth,
    client,
    seed_account,
    seed_session,
) -> None:
    mock_get_account.return_value = {
        "phone_number_id": seed_account.phone_number_id,
        "token": seed_account.token,
        "phone_number": seed_account.phone_number,
    }
    mock_create_session_for_number.return_value = {
        "id": seed_session.id,
        "account_id": seed_account.id,
        "to_number": 919999999999,
    }
    mock_send_template.return_value = {"message_id": "wamid.img123", "status": "sent"}

    payload = {
        "account_id": seed_account.id,
        "to_number": 919999999999,
        "template": {
            "name": "promo_with_banner",
            "language": "en_US",
            "components": [
                {
                    "type": "header",
                    "parameters": [
                        {"type": "image", "link": "https://cdn.example.com/banner.jpg"}
                    ],
                },
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": "Raj"}],
                },
            ],
        },
    }

    response = await client.post("/message/assistant/send", json=payload)

    assert response.status_code == 200
    assert response.json()["message"] == "Template dispatched"

    call_kwargs = mock_send_template.call_args[1]
    header = call_kwargs["components"][0]
    assert header["type"] == "header"
    # model_serializer re-wraps flat link → {"image": {"link": ...}}
    assert header["parameters"][0]["type"] == "image"
    assert (
        header["parameters"][0]["image"]["link"] == "https://cdn.example.com/banner.jpg"
    )


@pytest.mark.asyncio
@patch(
    "app.controller.message_controller.WhatsAppService.send_template_message",
    new_callable=AsyncMock,
)
@patch(
    "app.service.session_service.SessionService.create_session_for_number",
    new_callable=AsyncMock,
)
@patch(
    "app.service.account_service.AccountService.get_account",
    new_callable=AsyncMock,
)
async def test_send_llm_template_with_header_document(
    mock_get_account,
    mock_create_session_for_number,
    mock_send_template,
    mock_auth,
    client,
    seed_account,
    seed_session,
) -> None:
    mock_get_account.return_value = {
        "phone_number_id": seed_account.phone_number_id,
        "token": seed_account.token,
        "phone_number": seed_account.phone_number,
    }
    mock_create_session_for_number.return_value = {
        "id": seed_session.id,
        "account_id": seed_account.id,
        "to_number": 919999999999,
    }
    mock_send_template.return_value = {"message_id": "wamid.doc123", "status": "sent"}

    payload = {
        "account_id": seed_account.id,
        "to_number": 919999999999,
        "template": {
            "name": "invoice_template",
            "language": "en_US",
            "components": [
                {
                    "type": "header",
                    "parameters": [
                        {
                            "type": "document",
                            "link": "https://cdn.example.com/invoice.pdf",
                            "filename": "Invoice_4521.pdf",
                        }
                    ],
                },
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": "4521"}],
                },
            ],
        },
    }

    response = await client.post("/message/assistant/send", json=payload)

    assert response.status_code == 200
    call_kwargs = mock_send_template.call_args[1]
    header_param = call_kwargs["components"][0]["parameters"][0]
    assert header_param["type"] == "document"
    assert header_param["document"]["link"] == "https://cdn.example.com/invoice.pdf"
    assert header_param["document"]["filename"] == "Invoice_4521.pdf"


@pytest.mark.asyncio
@patch(
    "app.controller.message_controller.WhatsAppService.send_template_message",
    new_callable=AsyncMock,
)
@patch(
    "app.service.session_service.SessionService.create_session_for_number",
    new_callable=AsyncMock,
)
@patch(
    "app.service.account_service.AccountService.get_account",
    new_callable=AsyncMock,
)
async def test_send_llm_template_with_quick_reply_button(
    mock_get_account,
    mock_create_session_for_number,
    mock_send_template,
    mock_auth,
    client,
    seed_account,
    seed_session,
) -> None:
    mock_get_account.return_value = {
        "phone_number_id": seed_account.phone_number_id,
        "token": seed_account.token,
        "phone_number": seed_account.phone_number,
    }
    mock_create_session_for_number.return_value = {
        "id": seed_session.id,
        "account_id": seed_account.id,
        "to_number": 919999999999,
    }
    mock_send_template.return_value = {"message_id": "wamid.btn123", "status": "sent"}

    payload = {
        "account_id": seed_account.id,
        "to_number": 919999999999,
        "template": {
            "name": "confirm_order",
            "language": "en_US",
            "components": [
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": "Raj"}],
                },
                {
                    "type": "button",
                    "sub_type": "quick_reply",
                    "index": 0,
                    "parameters": [{"type": "payload", "payload": "CONFIRM_YES"}],
                },
            ],
        },
    }

    response = await client.post("/message/assistant/send", json=payload)

    assert response.status_code == 200
    call_kwargs = mock_send_template.call_args[1]
    button = call_kwargs["components"][1]
    assert button["type"] == "button"
    assert button["sub_type"] == "quick_reply"
    assert button["index"] == 0
    assert button["parameters"][0]["payload"] == "CONFIRM_YES"


@pytest.mark.asyncio
@patch(
    "app.controller.message_controller.WhatsAppService.send_template_message",
    new_callable=AsyncMock,
)
@patch(
    "app.service.session_service.SessionService.create_session_for_number",
    new_callable=AsyncMock,
)
@patch(
    "app.service.account_service.AccountService.get_account",
    new_callable=AsyncMock,
)
async def test_send_llm_template_without_components(
    mock_get_account,
    mock_create_session_for_number,
    mock_send_template,
    mock_auth,
    client,
    seed_account,
    seed_session,
) -> None:
    mock_get_account.return_value = {
        "phone_number_id": seed_account.phone_number_id,
        "token": seed_account.token,
        "phone_number": seed_account.phone_number,
    }
    mock_create_session_for_number.return_value = {
        "id": seed_session.id,
        "account_id": seed_account.id,
        "to_number": 919999999999,
    }
    mock_send_template.return_value = {"message_id": "wamid.test456", "status": "sent"}

    payload = {
        "account_id": seed_account.id,
        "to_number": 919999999999,
        "template": {
            "name": "static_template",
            "language": "hi",
        },
    }

    response = await client.post("/message/assistant/send", json=payload)

    assert response.status_code == 200
    assert response.json()["message"] == "Template dispatched"

    mock_send_template.assert_called_once_with(
        phone_number_id=seed_account.phone_number_id,
        to_number="919999999999",
        template_name="static_template",
        language="hi",
        access_token=seed_account.token,
        components=None,
    )


@pytest.mark.asyncio
@patch(
    "app.controller.message_controller.WhatsAppService.send_template_message",
    new_callable=AsyncMock,
)
@patch(
    "app.service.session_service.SessionService.create_session_for_number",
    new_callable=AsyncMock,
)
@patch(
    "app.service.account_service.AccountService.get_account",
    new_callable=AsyncMock,
)
async def test_send_llm_template_sandbox_skips_whatsapp(
    mock_get_account,
    mock_create_session_for_number,
    mock_send_template,
    mock_auth,
    client,
    seed_account,
    seed_session,
) -> None:
    mock_get_account.return_value = {
        "phone_number_id": seed_account.phone_number_id,
        "token": seed_account.token,
        "phone_number": seed_account.phone_number,
    }
    mock_create_session_for_number.return_value = {
        "id": seed_session.id,
        "account_id": seed_account.id,
        "to_number": 919999999999,
    }

    payload = {
        "account_id": seed_account.id,
        "to_number": 919999999999,
        "template": {"name": "welcome_message", "language": "en_US"},
        "sandbox": True,
    }

    response = await client.post("/message/assistant/send", json=payload)

    assert response.status_code == 200
    assert response.json()["message"] == "Template dispatched"
    mock_send_template.assert_not_called()


@pytest.mark.asyncio
@patch(
    "app.controller.message_controller.WhatsAppService.send_template_message",
    new_callable=AsyncMock,
    return_value={
        "status": "failed",
        "error": "WhatsApp API error: template not approved",
    },
)
@patch(
    "app.service.session_service.SessionService.create_session_for_number",
    new_callable=AsyncMock,
)
@patch(
    "app.service.account_service.AccountService.get_account",
    new_callable=AsyncMock,
)
async def test_send_llm_template_whatsapp_failure(
    mock_get_account,
    mock_create_session_for_number,
    mock_send_template,
    mock_auth,
    client,
    seed_account,
    seed_session,
) -> None:
    mock_get_account.return_value = {
        "phone_number_id": seed_account.phone_number_id,
        "token": seed_account.token,
        "phone_number": seed_account.phone_number,
    }
    mock_create_session_for_number.return_value = {
        "id": seed_session.id,
        "account_id": seed_account.id,
        "to_number": 919999999999,
    }

    payload = {
        "account_id": seed_account.id,
        "to_number": 919999999999,
        "template": {"name": "bad_template", "language": "en_US"},
    }

    response = await client.post("/message/assistant/send", json=payload)

    assert response.status_code == 500
    assert "template not approved" in response.json()["message"]


@pytest.mark.asyncio
@patch(
    "app.service.message_service.MessageService.save_template_to_session",
    new_callable=AsyncMock,
    return_value=None,
)
@patch(
    "app.controller.message_controller.WhatsAppService.send_template_message",
    new_callable=AsyncMock,
)
@patch(
    "app.service.session_service.SessionService.create_session_for_number",
    new_callable=AsyncMock,
)
@patch(
    "app.service.account_service.AccountService.get_account",
    new_callable=AsyncMock,
)
async def test_send_llm_template_save_to_session_fails(
    mock_get_account,
    mock_create_session_for_number,
    mock_send_template,
    mock_save_template,
    mock_auth,
    client,
    seed_account,
    seed_session,
    db_session,
) -> None:
    mock_get_account.return_value = {
        "phone_number_id": seed_account.phone_number_id,
        "token": seed_account.token,
        "phone_number": seed_account.phone_number,
    }
    mock_send_template.return_value = {"message_id": "wamid.test123", "status": "sent"}
    mock_save_template.return_value = None  # Simulate save failure

    payload = {
        "account_id": seed_account.id,
        "to_number": 919999999999,
        "template": {"name": "welcome_template", "language": "en_US"},
    }

    response = await client.post("/message/assistant/send", json=payload)

    assert response.status_code == 500
    assert response.json()["message"] == "Failed to save template to session"

    # Verify that no message was saved to the database
    result = await db_session.execute(select(WhatsAppMessage))
    messages = result.scalars().all()
    assert len(messages) == 0


@pytest.mark.asyncio
@patch(
    "app.controller.message_controller.template_service.get_template_by_name",
    new_callable=AsyncMock,
)
@patch(
    "app.controller.message_controller.WhatsAppService.send_template_message",
    new_callable=AsyncMock,
)
@patch(
    "app.service.session_service.SessionService.create_session_for_number",
    new_callable=AsyncMock,
)
@patch(
    "app.service.account_service.AccountService.get_account",
    new_callable=AsyncMock,
)
async def test_send_llm_template_renders_body_in_history(
    mock_get_account,
    mock_create_session_for_number,
    mock_send_template,
    mock_get_template,
    mock_auth,
    client,
    seed_account,
    seed_session,
    db_session,
) -> None:
    """Template body text (with variables filled) is saved to message history."""
    mock_get_account.return_value = {
        "phone_number_id": seed_account.phone_number_id,
        "token": seed_account.token,
        "phone_number": seed_account.phone_number,
        "waba_id": seed_account.waba_id,
    }
    mock_create_session_for_number.return_value = {
        "id": seed_session.id,
        "account_id": seed_account.id,
        "to_number": 919999999999,
    }
    mock_send_template.return_value = {
        "message_id": "wamid.render123",
        "status": "sent",
    }
    mock_get_template.return_value = {
        "name": "welcome_message",
        "language": "en_US",
        "components": [
            {"type": "BODY", "text": "Hello {{1}}, your plan is {{2}}."},
        ],
    }

    payload = {
        "account_id": seed_account.id,
        "to_number": 919999999999,
        "template": {
            "name": "welcome_message",
            "language": "en_US",
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": "John"},
                        {"type": "text", "text": "Premium"},
                    ],
                }
            ],
        },
    }

    response = await client.post("/message/assistant/send", json=payload)

    assert response.status_code == 200
    assert response.json()["message"] == "Template dispatched"

    result = await db_session.execute(select(WhatsAppMessage))
    message = result.scalar_one_or_none()
    assert message is not None
    assert message.role == "assistant"
    # Should store rendered body, not the raw "[Template] name" label
    assert message.message == "Hello John, your plan is Premium."


@pytest.mark.asyncio
@patch(
    "app.controller.message_controller.template_service.get_template_by_name",
    new_callable=AsyncMock,
    return_value=None,
)
@patch(
    "app.controller.message_controller.WhatsAppService.send_template_message",
    new_callable=AsyncMock,
)
@patch(
    "app.service.session_service.SessionService.create_session_for_number",
    new_callable=AsyncMock,
)
@patch(
    "app.service.account_service.AccountService.get_account",
    new_callable=AsyncMock,
)
async def test_send_llm_template_falls_back_to_label_when_not_found(
    mock_get_account,
    mock_create_session_for_number,
    mock_send_template,
    _mock_get_template,
    mock_auth,
    client,
    seed_account,
    seed_session,
    db_session,
) -> None:
    """Falls back to '[Template] name' when the template cannot be fetched."""
    mock_get_account.return_value = {
        "phone_number_id": seed_account.phone_number_id,
        "token": seed_account.token,
        "phone_number": seed_account.phone_number,
        "waba_id": seed_account.waba_id,
    }
    mock_create_session_for_number.return_value = {
        "id": seed_session.id,
        "account_id": seed_account.id,
        "to_number": 919999999999,
    }
    mock_send_template.return_value = {"message_id": "wamid.fb123", "status": "sent"}

    payload = {
        "account_id": seed_account.id,
        "to_number": 919999999999,
        "template": {"name": "missing_template", "language": "en_US"},
    }

    response = await client.post("/message/assistant/send", json=payload)

    assert response.status_code == 200
    result = await db_session.execute(select(WhatsAppMessage))
    message = result.scalar_one_or_none()
    assert message is not None
    assert message.message == "[Template] missing_template"


@pytest.mark.asyncio
async def test_send_llm_missing_required_fields(client, mock_auth) -> None:
    payload = {"message": "Hello"}

    response = await client.post("message/assistant/send", json=payload)

    assert response.status_code == 422
    assert response.json()["detail"][0]["msg"] == "Field required"


@pytest.mark.asyncio
async def test_send_llm_no_message_no_template(client, mock_auth, seed_account) -> None:
    payload = {
        "account_id": seed_account.id,
        "to_number": 919999999999,
    }

    response = await client.post("message/assistant/send", json=payload)

    assert response.status_code == 422
    assert "Either message, template, or media must be provided" in str(response.json())


@pytest.mark.asyncio
@patch(
    "app.controller.message_controller.S3Service.upload_media", new_callable=AsyncMock
)
@patch(
    "app.controller.message_controller.WhatsAppService.send_message",
    new_callable=AsyncMock,
)
@patch(
    "app.service.session_service.SessionService.create_session_for_number",
    new_callable=AsyncMock,
)
@patch(
    "app.service.account_service.AccountService.get_account",
    new_callable=AsyncMock,
)
async def test_send_llm_media_only_allowed(
    mock_get_account,
    mock_create_session_for_number,
    mock_send,
    mock_s3,
    mock_auth,
    client,
    seed_account,
    seed_session,
    db_session,
) -> None:
    """Media-only payload (no message, no template) should be accepted."""
    txt_b64 = base64.b64encode(b"How long does Seltycas Tadalafil last?").decode()

    mock_s3.return_value = "https://s3.bucket/uploaded-doc.txt"
    mock_get_account.return_value = {
        "phone_number_id": seed_account.phone_number_id,
        "token": seed_account.token,
        "phone_number": seed_account.phone_number,
    }
    mock_create_session_for_number.return_value = {
        "id": seed_session.id,
        "account_id": seed_account.id,
        "to_number": 919081057445,
    }
    mock_send.return_value = True

    payload = {
        "account_id": seed_account.id,
        "to_number": 919081057445,
        "media_bytes": [txt_b64],
        "media_names": ["report.txt"],
        "sandbox": False,
    }

    response = await client.post("/message/assistant/send", json=payload)

    assert response.status_code == 200
    assert response.json()["message"] == "Message dispatched"


@pytest.mark.asyncio
async def test_send_llm_message_and_template_together(
    client, mock_auth, seed_account
) -> None:
    payload = {
        "account_id": seed_account.id,
        "to_number": 919999999999,
        "message": "Hello",
        "template": {"name": "welcome_message", "language": "en_US"},
    }

    response = await client.post("message/assistant/send", json=payload)

    assert response.status_code == 422
    assert "Only one of message or template can be provided" in str(response.json())


@pytest.mark.asyncio
async def test_send_llm_template_with_media_rejected(
    client, mock_auth, seed_account
) -> None:
    payload = {
        "account_id": seed_account.id,
        "to_number": 919999999999,
        "template": {"name": "welcome_message", "language": "en_US"},
        "media_bytes": [
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO5WQ1sAAAAASUVORK5CYII="
        ],
    }

    response = await client.post("message/assistant/send", json=payload)

    assert response.status_code == 422
    assert "Media is not supported with templates" in str(response.json())


@pytest.mark.asyncio
async def test_send_llm_template_empty_text_param_rejected(
    client, mock_auth, seed_account
) -> None:
    """Empty string in a text parameter must be rejected before hitting WhatsApp."""
    payload = {
        "account_id": seed_account.id,
        "to_number": 919999999999,
        "template": {
            "name": "some_template",
            "language": "en_US",
            "components": [
                {
                    "type": "header",
                    "parameters": [{"type": "text", "text": ""}],
                }
            ],
        },
    }

    response = await client.post("message/assistant/send", json=payload)

    assert response.status_code == 422
    assert "text parameter must not be empty" in str(response.json())


@pytest.mark.asyncio
async def test_send_llm_template_whitespace_text_param_rejected(
    client, mock_auth, seed_account
) -> None:
    """Whitespace-only text is also rejected."""
    payload = {
        "account_id": seed_account.id,
        "to_number": 919999999999,
        "template": {
            "name": "some_template",
            "language": "en_US",
            "components": [
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": "   "}],
                }
            ],
        },
    }

    response = await client.post("message/assistant/send", json=payload)

    assert response.status_code == 422
    assert "text parameter must not be empty" in str(response.json())


@pytest.mark.asyncio
async def test_send_llm_extra_field(client, mock_auth, seed_account) -> None:
    payload = {
        "account_id": seed_account.id,
        "to_number": 919999999999,
        "message": "Hello",
        "extra": "field",
    }

    response = await client.post("message/assistant/send", json=payload)

    assert response.status_code == 422
    assert response.json()["detail"][0]["msg"] == "Extra inputs are not permitted"


@pytest.mark.asyncio
async def test_send_llm_unauthorized(client) -> None:
    payload = {
        "account_id": 1,
        "to_number": 919999999999,
        "message": "Hello",
    }

    response = await client.post("message/assistant/send", json=payload)

    assert response.status_code == 401
    assert (
        response.json()["detail"]
        == "Authentication required: provide JWT token or X-API-Key header"
    )


# -------------------------REACTION MESSAGES----------------------------


@pytest.mark.asyncio
@patch("app.controller.message_controller.enqueue_and_trigger", new_callable=AsyncMock)
async def test_incoming_reaction_webhook(
    mock_enqueue,
    client,
    seed_account,
    db_session,
) -> None:
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": "wamid.reaction001",
                                    "from": "919876543210",
                                    "type": "reaction",
                                    "reaction": {
                                        "message_id": "wamid.original001",
                                        "emoji": "👍",
                                    },
                                }
                            ],
                            "metadata": {
                                "display_phone_number": str(seed_account.phone_number)
                            },
                        }
                    }
                ]
            }
        ]
    }

    response = await client.post("/message/send", json=payload)

    assert response.status_code == 200
    assert response.json()["message"] == "Reaction stored"

    result = await db_session.execute(select(WhatsAppMessage))
    message = result.scalar_one_or_none()
    assert message is not None
    assert message.message == "👍"
    assert message.meta_message_id == "wamid.reaction001"
    mock_enqueue.assert_not_called()


@pytest.mark.asyncio
@patch("app.controller.message_controller.enqueue_and_trigger", new_callable=AsyncMock)
async def test_incoming_reaction_removed_webhook(
    mock_enqueue,
    client,
    seed_account,
    db_session,
) -> None:
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": "wamid.reaction002",
                                    "from": "919876543210",
                                    "type": "reaction",
                                    "reaction": {
                                        "message_id": "wamid.original001",
                                        "emoji": "",
                                    },
                                }
                            ],
                            "metadata": {
                                "display_phone_number": str(seed_account.phone_number)
                            },
                        }
                    }
                ]
            }
        ]
    }

    response = await client.post("/message/send", json=payload)

    assert response.status_code == 200
    assert response.json()["message"] == "Reaction stored"

    result = await db_session.execute(select(WhatsAppMessage))
    message = result.scalar_one_or_none()
    assert message is not None
    assert message.message == "[Reaction removed]"
    mock_enqueue.assert_not_called()


@pytest.mark.asyncio
@patch(
    "app.controller.message_controller.WhatsAppService.send_reaction",
    new_callable=AsyncMock,
)
@patch(
    "app.service.account_service.AccountService.get_account",
    new_callable=AsyncMock,
)
async def test_send_reaction_endpoint(
    mock_get_account,
    mock_send_reaction,
    mock_auth,
    client,
    seed_account,
) -> None:
    mock_get_account.return_value = {
        "phone_number_id": seed_account.phone_number_id,
        "token": seed_account.token,
        "phone_number": seed_account.phone_number,
    }
    mock_send_reaction.return_value = True

    payload = {
        "account_id": seed_account.id,
        "to_number": 919876543210,
        "message_id": "wamid.original001",
        "emoji": "👍",
    }

    response = await client.post("/message/react", json=payload)

    assert response.status_code == 200
    assert response.json()["message"] == "Reaction sent"

    mock_send_reaction.assert_called_once_with(
        phone_number_id=seed_account.phone_number_id,
        to_number="919876543210",
        message_id="wamid.original001",
        emoji="👍",
        access_token=seed_account.token,
    )


@pytest.mark.asyncio
@patch(
    "app.controller.message_controller.WhatsAppService.send_reaction",
    new_callable=AsyncMock,
)
@patch(
    "app.service.account_service.AccountService.get_account",
    new_callable=AsyncMock,
)
async def test_send_reaction_sandbox(
    mock_get_account,
    mock_send_reaction,
    mock_auth,
    client,
    seed_account,
) -> None:
    mock_get_account.return_value = {
        "phone_number_id": seed_account.phone_number_id,
        "token": seed_account.token,
        "phone_number": seed_account.phone_number,
    }

    payload = {
        "account_id": seed_account.id,
        "to_number": 919876543210,
        "message_id": "wamid.original001",
        "emoji": "🎉",
        "sandbox": True,
    }

    response = await client.post("/message/react", json=payload)

    assert response.status_code == 200
    assert response.json()["message"] == "Reaction sent"
    mock_send_reaction.assert_not_called()


@pytest.mark.asyncio
@patch(
    "app.service.assistant_service._summarize_in_background",
    new_callable=AsyncMock,
)
@patch(
    "app.service.assistant_service._label_stage_in_background",
    new_callable=AsyncMock,
)
@patch("app.service.mem0_service.Mem0Service.add_memory")
@patch(
    "app.service.mem0_service.Mem0Service.search_memories",
    return_value=[],
)
@patch(
    "app.service.summary_service.SummaryService.get_summary",
    new_callable=AsyncMock,
    return_value=None,
)
@patch(
    "app.service.llm_service.LLMService.generate_response",
    new_callable=AsyncMock,
)
async def test_generate_assistant_response_saves_tokens(
    mock_generate,
    mock_get_summary,
    mock_search_memories,
    mock_add_memory,
    mock_label_stage,
    mock_summarize,
    seed_account,
    seed_session_with_history,
    db_session,
) -> None:
    from app.service.assistant_service import generate_assistant_response

    mock_generate.return_value = ("LLM response text", 120, 45)

    await generate_assistant_response(
        session_id=seed_session_with_history.id,
        db=db_session,
        from_number=seed_account.phone_number,
        to_number="918888888888",
        sandbox=True,
    )

    result = await db_session.execute(
        select(WhatsAppMessage).where(WhatsAppMessage.role == "assistant")
    )
    message = result.scalar_one_or_none()
    assert message is not None
    assert message.input_tokens == 120
    assert message.output_tokens == 45
