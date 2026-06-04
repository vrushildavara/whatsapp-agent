import pytest
from sqlalchemy import select

from app.models.model import AssistantTool, WhatsAppAccount

# -------------------------CREATE TOOL----------------------------


@pytest.mark.asyncio
async def test_create_tool_knowledge(
    client, seed_account, mock_auth, db_session
) -> None:
    account_id = seed_account.id

    response = await client.post(
        f"/tools/account/{account_id}",
        json={
            "name": "Knowledge Base",
            "tool_type": "knowledge",
            "config": {
                "file_ids": ["file-abc123", "file-def456"],
            },
        },
    )

    assert response.status_code == 201
    assert response.json()["message"] == "Knowledge tool created successfully"

    result = await db_session.execute(
        select(AssistantTool).where(
            AssistantTool.account_id == account_id,
            AssistantTool.name == "Knowledge Base",
            AssistantTool.deleted_at.is_(None),
        )
    )
    tool = result.scalar_one_or_none()

    assert tool is not None
    assert tool.tool_type.value == "knowledge"
    assert tool.config["file_ids"] == ["file-abc123", "file-def456"]


@pytest.mark.asyncio
async def test_create_tool_api_request_with_headers_and_body(
    client, seed_account, mock_auth, db_session
) -> None:
    account_id = seed_account.id

    response = await client.post(
        f"/tools/account/{account_id}",
        json={
            "name": "Full Config Tool",
            "tool_type": "api_request",
            "config": {
                "url": "https://api.example.com/data",
                "description": "Full config",
                "headers": {
                    "properties": [
                        {"name": "Authorization", "value": "Bearer token123"},
                    ]
                },
                "body": {
                    "required": ["query"],
                    "properties": [
                        {
                            "name": "query",
                            "type": "string",
                            "description": "Search query",
                        },
                    ],
                },
            },
        },
    )

    assert response.status_code == 201
    assert response.json()["message"] == "Knowledge tool created successfully"

    result = await db_session.execute(
        select(AssistantTool).where(
            AssistantTool.account_id == account_id,
            AssistantTool.name == "Full Config Tool",
            AssistantTool.deleted_at.is_(None),
        )
    )
    tool = result.scalar_one_or_none()
    assert tool is not None
    assert tool.config["url"] == "https://api.example.com/data"
    assert isinstance(tool.config["headers"]["properties"], list)
    assert isinstance(tool.config["body"]["properties"], list)


@pytest.mark.asyncio
async def test_create_tool_api_request_with_method(
    client, seed_account, mock_auth, db_session
) -> None:
    account_id = seed_account.id

    response = await client.post(
        f"/tools/account/{account_id}",
        json={
            "name": "GET Weather Tool",
            "tool_type": "api_request",
            "config": {
                "url": "https://api.open-meteo.com/v1/forecast",
                "description": "Get current weather data.",
                "method": "GET",
            },
        },
    )

    assert response.status_code == 201
    assert response.json()["message"] == "Knowledge tool created successfully"

    result = await db_session.execute(
        select(AssistantTool).where(
            AssistantTool.account_id == account_id,
            AssistantTool.name == "GET Weather Tool",
            AssistantTool.deleted_at.is_(None),
        )
    )
    tool = result.scalar_one_or_none()
    assert tool is not None
    assert tool.config["method"] == "GET"
    assert tool.config["description"] == "Get current weather data."


@pytest.mark.asyncio
async def test_create_tool_account_not_found(client, mock_auth, db_session) -> None:
    response = await client.post(
        "/tools/account/999",
        json={
            "name": "Tool",
            "tool_type": "api_request",
            "config": {"url": "https://api.example.com"},
        },
    )

    result = await db_session.execute(
        select(WhatsAppAccount).where(
            WhatsAppAccount.id == 999,
            WhatsAppAccount.user_id == mock_auth.id,
            WhatsAppAccount.deleted_at.is_(None),
        )
    )
    account = result.scalar_one_or_none()

    assert account is None

    assert response.status_code == 404
    assert response.json()["message"] == "Account not found"


@pytest.mark.asyncio
async def test_create_tool_invalid_tool_type(client, seed_account, mock_auth) -> None:
    response = await client.post(
        f"/tools/account/{seed_account.id}",
        json={
            "name": "Tool",
            "tool_type": "invalid_type",
            "config": {"url": "https://api.example.com"},
        },
    )

    assert response.status_code == 422
    assert (
        "Value error, tool_type must be one of: " in response.json()["detail"][0]["msg"]
    )


@pytest.mark.asyncio
async def test_create_tool_empty_name(client, seed_account, mock_auth) -> None:
    response = await client.post(
        f"/tools/account/{seed_account.id}",
        json={
            "name": "   ",
            "tool_type": "api_request",
            "config": {"url": "https://api.example.com"},
        },
    )

    assert response.status_code == 422
    assert (
        response.json()["detail"][0]["msg"]
        == "Value error, Tool name must be between 1 and 255 characters"
    )


@pytest.mark.asyncio
async def test_create_tool_empty_config(client, seed_account, mock_auth) -> None:
    response = await client.post(
        f"/tools/account/{seed_account.id}",
        json={
            "name": "Tool",
            "tool_type": "api_request",
            "config": {},
        },
    )

    assert response.status_code == 422
    assert (
        response.json()["detail"][0]["msg"] == "Value error, config must not be empty"
    )


@pytest.mark.asyncio
async def test_create_tool_api_request_missing_url(
    client, seed_account, mock_auth
) -> None:
    response = await client.post(
        f"/tools/account/{seed_account.id}",
        json={
            "name": "Tool",
            "tool_type": "api_request",
            "config": {"description": "no url"},
        },
    )

    assert response.status_code == 422
    assert (
        response.json()["detail"][0]["msg"]
        == "Value error, api_request config must include a non-empty 'url' string"
    )


@pytest.mark.asyncio
async def test_create_tool_api_request_empty_url(
    client, seed_account, mock_auth
) -> None:
    response = await client.post(
        f"/tools/account/{seed_account.id}",
        json={
            "name": "Tool",
            "tool_type": "api_request",
            "config": {"url": "   "},
        },
    )

    assert response.status_code == 422
    assert (
        response.json()["detail"][0]["msg"]
        == "Value error, api_request config must include a non-empty 'url' string"
    )


@pytest.mark.asyncio
async def test_create_tool_api_request_invalid_headers(
    client, seed_account, mock_auth
) -> None:
    response = await client.post(
        f"/tools/account/{seed_account.id}",
        json={
            "name": "Tool",
            "tool_type": "api_request",
            "config": {
                "url": "https://api.example.com",
                "headers": {"not_properties": "wrong"},
            },
        },
    )

    assert response.status_code == 422
    assert (
        response.json()["detail"][0]["msg"]
        == "Value error, api_request config 'headers' must be an object with a 'properties' list"
    )


@pytest.mark.asyncio
async def test_create_tool_api_request_invalid_body(
    client, seed_account, mock_auth
) -> None:
    response = await client.post(
        f"/tools/account/{seed_account.id}",
        json={
            "name": "Tool",
            "tool_type": "api_request",
            "config": {
                "url": "https://api.example.com",
                "body": {"not_properties": "wrong"},
            },
        },
    )

    assert response.status_code == 422
    assert (
        response.json()["detail"][0]["msg"]
        == "Value error, api_request config 'body' must be an object with a 'properties' list"
    )


@pytest.mark.asyncio
async def test_create_tool_api_request_invalid_method(
    client, seed_account, mock_auth
) -> None:
    response = await client.post(
        f"/tools/account/{seed_account.id}",
        json={
            "name": "Tool",
            "tool_type": "api_request",
            "config": {"url": "https://api.example.com", "method": "INVALID"},
        },
    )

    assert response.status_code == 422
    assert (
        "api_request config 'method' must be one of"
        in response.json()["detail"][0]["msg"]
    )


@pytest.mark.asyncio
async def test_create_tool_api_request_empty_description(
    client, seed_account, mock_auth
) -> None:
    response = await client.post(
        f"/tools/account/{seed_account.id}",
        json={
            "name": "Tool",
            "tool_type": "api_request",
            "config": {"url": "https://api.example.com", "description": "   "},
        },
    )

    assert response.status_code == 422
    assert (
        response.json()["detail"][0]["msg"]
        == "Value error, api_request config 'description' must be a non-empty string"
    )


@pytest.mark.asyncio
async def test_create_tool_api_request_extra_config_field(
    client, seed_account, mock_auth
) -> None:
    response = await client.post(
        f"/tools/account/{seed_account.id}",
        json={
            "name": "Tool",
            "tool_type": "api_request",
            "config": {"url": "https://api.example.com", "unknown_field": "value"},
        },
    )

    assert response.status_code == 422
    assert (
        "api_request config contains unknown fields"
        in response.json()["detail"][0]["msg"]
    )


@pytest.mark.asyncio
async def test_create_tool_knowledge_extra_config_field(
    client, seed_account, mock_auth
) -> None:
    response = await client.post(
        f"/tools/account/{seed_account.id}",
        json={
            "name": "Tool",
            "tool_type": "knowledge",
            "config": {"file_ids": ["file-abc"], "extra_field": "value"},
        },
    )

    assert response.status_code == 422
    assert (
        "knowledge config contains unknown fields"
        in response.json()["detail"][0]["msg"]
    )


@pytest.mark.asyncio
async def test_create_tool_knowledge_missing_file_ids(
    client, seed_account, mock_auth
) -> None:
    response = await client.post(
        f"/tools/account/{seed_account.id}",
        json={
            "name": "Tool",
            "tool_type": "knowledge",
            "config": {"unknown_field": "no file_ids"},
        },
    )

    assert response.status_code == 422
    assert (
        "knowledge config contains unknown fields"
        in response.json()["detail"][0]["msg"]
    )


@pytest.mark.asyncio
async def test_create_tool_knowledge_empty_file_ids(
    client, seed_account, mock_auth
) -> None:
    response = await client.post(
        f"/tools/account/{seed_account.id}",
        json={
            "name": "Tool",
            "tool_type": "knowledge",
            "config": {"file_ids": []},
        },
    )

    assert response.status_code == 422
    assert (
        response.json()["detail"][0]["msg"]
        == "Value error, knowledge config must include a non-empty 'file_ids' list"
    )


@pytest.mark.asyncio
async def test_create_tool_extra_fields(client, seed_account, mock_auth) -> None:
    response = await client.post(
        f"/tools/account/{seed_account.id}",
        json={
            "name": "Tool",
            "tool_type": "api_request",
            "config": {"url": "https://api.example.com"},
            "extra": "field",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["msg"] == "Extra inputs are not permitted"


@pytest.mark.asyncio
async def test_create_tool_duplicate_knowledge(
    client, seed_tool_knowledge, mock_auth
) -> None:
    response = await client.post(
        f"/tools/account/{seed_tool_knowledge.account_id}",
        json={
            "name": "Another Knowledge Tool",
            "tool_type": "knowledge",
            "config": {"file_ids": ["file-new123"]},
        },
    )

    assert response.status_code == 409
    assert (
        response.json()["message"] == "A knowledge tool already exists for this account"
    )


@pytest.mark.asyncio
async def test_create_tool_multiple_api_request(
    client, seed_tool, mock_auth, db_session
) -> None:
    """Multiple api_request tools are allowed for the same account as long as names differ."""
    response = await client.post(
        f"/tools/account/{seed_tool.account_id}",
        json={
            "name": "Another API Tool",
            "tool_type": "api_request",
            "config": {"url": "https://api.example.com/v2"},
        },
    )

    assert response.status_code == 201
    assert response.json()["message"] == "Knowledge tool created successfully"
    assert response.json()["data"]["config"]["url"] == "https://api.example.com/v2"


@pytest.mark.asyncio
async def test_create_tool_duplicate_name(client, seed_tool, mock_auth) -> None:
    """Creating a tool with a name already used in the account is rejected."""
    response = await client.post(
        f"/tools/account/{seed_tool.account_id}",
        json={
            "name": seed_tool.name,
            "tool_type": "api_request",
            "config": {"url": "https://api.example.com/v2"},
        },
    )

    assert response.status_code == 409
    assert (
        f"A tool named '{seed_tool.name}' already exists for this account"
        in response.json()["message"]
    )


@pytest.mark.asyncio
async def test_create_tool_unauthorized(client, seed_account) -> None:
    response = await client.post(
        f"/tools/account/{seed_account.id}",
        json={
            "name": "Tool",
            "tool_type": "api_request",
            "config": {"url": "https://api.example.com"},
        },
    )

    assert response.status_code == 401
    assert (
        response.json()["detail"]
        == "Authentication required: provide JWT token or X-API-Key header"
    )


@pytest.mark.asyncio
async def test_create_tool_inactive_account(
    client, seed_inactive_account, mock_auth, db_session
) -> None:
    result = await db_session.execute(
        select(WhatsAppAccount).where(
            WhatsAppAccount.id == seed_inactive_account.id,
            WhatsAppAccount.is_active.is_(False),
            WhatsAppAccount.deleted_at.is_(None),
        )
    )
    assert result.scalar_one_or_none() is not None

    response = await client.post(
        f"/tools/account/{seed_inactive_account.id}",
        json={
            "name": "Tool",
            "tool_type": "api_request",
            "config": {"url": "https://api.example.com"},
        },
    )

    assert response.status_code == 403
    assert response.json()["message"] == "Account is inactive"


# -------------------------GET TOOL----------------------------


@pytest.mark.asyncio
async def test_get_tool(client, seed_tool, mock_auth, db_session) -> None:
    account_id = seed_tool.account_id
    tool_id = seed_tool.id

    response = await client.get(f"/tools/account/{account_id}/{tool_id}")

    assert response.status_code == 200
    assert response.json()["message"] == "Knowledge tool retrieved successfully"

    result = await db_session.execute(
        select(AssistantTool).where(
            AssistantTool.id == tool_id,
            AssistantTool.account_id == account_id,
            AssistantTool.deleted_at.is_(None),
        )
    )
    tool = result.scalar_one_or_none()
    assert tool is not None


@pytest.mark.asyncio
async def test_get_tool_not_found(client, seed_account, mock_auth, db_session) -> None:
    response = await client.get(f"/tools/account/{seed_account.id}/999")

    assert response.status_code == 404
    assert response.json()["message"] == "Tool not found"

    result = await db_session.execute(
        select(AssistantTool).where(
            AssistantTool.id == 999,
            AssistantTool.account_id == seed_account.id,
            AssistantTool.deleted_at.is_(None),
        )
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_get_tool_account_not_found(client, mock_auth, db_session) -> None:
    response = await client.get("/tools/account/999/1")

    assert response.status_code == 404
    assert response.json()["message"] == "Account not found"

    result = await db_session.execute(
        select(WhatsAppAccount).where(
            WhatsAppAccount.id == 999,
            WhatsAppAccount.user_id == mock_auth.id,
            WhatsAppAccount.deleted_at.is_(None),
        )
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_get_tool_unauthorized(client, seed_tool) -> None:
    response = await client.get(f"/tools/account/{seed_tool.account_id}/{seed_tool.id}")

    assert response.status_code == 401
    assert (
        response.json()["detail"]
        == "Authentication required: provide JWT token or X-API-Key header"
    )


@pytest.mark.asyncio
async def test_get_tool_inactive_account(
    client, seed_inactive_account, mock_auth, db_session
) -> None:
    result = await db_session.execute(
        select(WhatsAppAccount).where(
            WhatsAppAccount.id == seed_inactive_account.id,
            WhatsAppAccount.is_active.is_(False),
            WhatsAppAccount.deleted_at.is_(None),
        )
    )
    assert result.scalar_one_or_none() is not None

    response = await client.get(f"/tools/account/{seed_inactive_account.id}/1")

    assert response.status_code == 403
    assert response.json()["message"] == "Account is inactive"


# -------------------------GET ACCOUNT TOOLS----------------------------


@pytest.mark.asyncio
async def test_get_account_tools(client, seed_tool, mock_auth, db_session) -> None:
    account_id = seed_tool.account_id

    response = await client.get(f"/tools/account/{account_id}")

    assert response.status_code == 200
    assert response.json()["message"] == "Knowledge tools retrieved successfully"

    tools = response.json()["data"]
    assert len(tools) > 0
    assert any(t["id"] == seed_tool.id for t in tools)

    result = await db_session.execute(
        select(AssistantTool).where(
            AssistantTool.account_id == account_id,
            AssistantTool.deleted_at.is_(None),
        )
    )
    db_tools = result.scalars().all()
    assert len(db_tools) == len(tools)


@pytest.mark.asyncio
async def test_get_account_tools_multiple(
    client, seed_tool, seed_tool_knowledge, mock_auth, db_session
) -> None:
    account_id = seed_tool.account_id

    response = await client.get(f"/tools/account/{account_id}")

    assert response.status_code == 200
    assert response.json()["message"] == "Knowledge tools retrieved successfully"

    tools = response.json()["data"]

    returned_ids = [t["id"] for t in tools]
    assert seed_tool.id in returned_ids
    assert seed_tool_knowledge.id in returned_ids

    result = await db_session.execute(
        select(AssistantTool).where(
            AssistantTool.account_id == account_id,
            AssistantTool.deleted_at.is_(None),
        )
    )
    db_tools = result.scalars().all()
    assert len(db_tools) == 2


@pytest.mark.asyncio
async def test_get_account_tools_account_not_found(
    client, mock_auth, db_session
) -> None:
    response = await client.get("/tools/account/999")

    assert response.status_code == 404
    assert response.json()["message"] == "Account not found"

    result = await db_session.execute(
        select(WhatsAppAccount).where(
            WhatsAppAccount.id == 999,
            WhatsAppAccount.user_id == mock_auth.id,
            WhatsAppAccount.deleted_at.is_(None),
        )
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_get_account_tools_unauthorized(client, seed_account) -> None:
    response = await client.get(f"/tools/account/{seed_account.id}")

    assert response.status_code == 401
    assert (
        response.json()["detail"]
        == "Authentication required: provide JWT token or X-API-Key header"
    )


@pytest.mark.asyncio
async def test_get_account_tools_inactive_account(
    client, seed_inactive_account, mock_auth, db_session
) -> None:
    result = await db_session.execute(
        select(WhatsAppAccount).where(
            WhatsAppAccount.id == seed_inactive_account.id,
            WhatsAppAccount.is_active.is_(False),
            WhatsAppAccount.deleted_at.is_(None),
        )
    )
    assert result.scalar_one_or_none() is not None

    response = await client.get(f"/tools/account/{seed_inactive_account.id}")

    assert response.status_code == 403
    assert response.json()["message"] == "Account is inactive"


# -------------------------UPDATE TOOL----------------------------


@pytest.mark.asyncio
async def test_update_tool_name_and_active(
    client, seed_tool, mock_auth, db_session
) -> None:
    account_id = seed_tool.account_id
    tool_id = seed_tool.id

    response = await client.put(
        f"/tools/account/{account_id}/{tool_id}",
        json={"name": "Renamed Tool", "is_active": False},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Knowledge tool updated successfully"

    result = await db_session.execute(
        select(AssistantTool).where(
            AssistantTool.id == tool_id,
            AssistantTool.account_id == account_id,
            AssistantTool.deleted_at.is_(None),
        )
    )
    tool = result.scalar_one_or_none()
    assert tool is not None
    assert tool.name == "Renamed Tool"
    assert tool.is_active is False


@pytest.mark.asyncio
async def test_update_tool_api_request_update_url(
    client, seed_tool, mock_auth, db_session
) -> None:
    account_id = seed_tool.account_id
    tool_id = seed_tool.id

    response = await client.put(
        f"/tools/account/{account_id}/{tool_id}",
        json={"config": {"url": "https://api.example.com/v2"}},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Knowledge tool updated successfully"

    result = await db_session.execute(
        select(AssistantTool).where(
            AssistantTool.id == tool_id,
            AssistantTool.account_id == account_id,
            AssistantTool.deleted_at.is_(None),
        )
    )
    tool = result.scalar_one_or_none()
    assert tool is not None
    assert tool.config["url"] == "https://api.example.com/v2"


@pytest.mark.asyncio
async def test_update_tool_api_request_update_headers_and_body(
    client, seed_tool, mock_auth, db_session
) -> None:
    account_id = seed_tool.account_id
    tool_id = seed_tool.id

    response = await client.put(
        f"/tools/account/{account_id}/{tool_id}",
        json={
            "config": {
                "headers": {
                    "properties": [
                        {"name": "Authorization", "value": "Bearer new-token"}
                    ]
                },
                "body": {
                    "required": ["query"],
                    "properties": [{"name": "query", "type": "string"}],
                },
            }
        },
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Knowledge tool updated successfully"

    result = await db_session.execute(
        select(AssistantTool).where(
            AssistantTool.id == tool_id,
            AssistantTool.account_id == account_id,
            AssistantTool.deleted_at.is_(None),
        )
    )
    tool = result.scalar_one_or_none()
    assert tool is not None
    assert tool.config["url"] == "https://api.example.com/test"
    assert tool.config["headers"]["properties"][0]["name"] == "Authorization"
    assert tool.config["body"]["properties"][0]["name"] == "query"


@pytest.mark.asyncio
async def test_update_tool_knowledge_extend_file_ids(
    client, seed_tool_knowledge, mock_auth, db_session
) -> None:
    account_id = seed_tool_knowledge.account_id
    tool_id = seed_tool_knowledge.id

    response = await client.put(
        f"/tools/account/{account_id}/{tool_id}",
        json={"config": {"file_ids": ["file-new123", "file-new456"]}},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Knowledge tool updated successfully"

    result = await db_session.execute(
        select(AssistantTool).where(
            AssistantTool.id == tool_id,
            AssistantTool.account_id == account_id,
            AssistantTool.deleted_at.is_(None),
        )
    )
    tool = result.scalar_one_or_none()
    assert tool is not None
    assert "file-abc123" in tool.config["file_ids"]
    assert "file-def456" in tool.config["file_ids"]
    assert "file-new123" in tool.config["file_ids"]
    assert "file-new456" in tool.config["file_ids"]


@pytest.mark.asyncio
async def test_update_tool_api_request_update_description(
    client, seed_tool, mock_auth, db_session
) -> None:
    """Updating description saves it and leaves other config fields unchanged."""
    original_url = seed_tool.config["url"]

    response = await client.put(
        f"/tools/account/{seed_tool.account_id}/{seed_tool.id}",
        json={"config": {"description": "updated description"}},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Knowledge tool updated successfully"

    result = await db_session.execute(
        select(AssistantTool).where(
            AssistantTool.id == seed_tool.id,
            AssistantTool.account_id == seed_tool.account_id,
            AssistantTool.deleted_at.is_(None),
        )
    )
    tool = result.scalar_one_or_none()
    assert tool is not None
    assert tool.config["url"] == original_url
    assert tool.config["description"] == "updated description"


@pytest.mark.asyncio
async def test_update_tool_api_request_update_method(
    client, seed_tool, mock_auth, db_session
) -> None:
    """Updating method saves it and leaves other config fields unchanged."""
    original_url = seed_tool.config["url"]

    response = await client.put(
        f"/tools/account/{seed_tool.account_id}/{seed_tool.id}",
        json={"config": {"method": "GET"}},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Knowledge tool updated successfully"

    result = await db_session.execute(
        select(AssistantTool).where(
            AssistantTool.id == seed_tool.id,
            AssistantTool.account_id == seed_tool.account_id,
            AssistantTool.deleted_at.is_(None),
        )
    )
    tool = result.scalar_one_or_none()
    assert tool is not None
    assert tool.config["method"] == "GET"
    assert tool.config["url"] == original_url


@pytest.mark.asyncio
async def test_update_tool_knowledge_config_missing_file_ids(
    client, seed_tool_knowledge, mock_auth
) -> None:
    response = await client.put(
        f"/tools/account/{seed_tool_knowledge.account_id}/{seed_tool_knowledge.id}",
        json={"config": {"url": "https://example.com"}},
    )

    assert response.status_code == 422
    assert (
        response.json()["message"]
        == "knowledge config update must include a non-empty 'file_ids' list"
    )


@pytest.mark.asyncio
async def test_update_tool_duplicate_name(
    client, seed_tool, seed_tool_knowledge, mock_auth
) -> None:
    """Renaming a tool to a name already taken in the account is rejected."""
    response = await client.put(
        f"/tools/account/{seed_tool.account_id}/{seed_tool.id}",
        json={"name": seed_tool_knowledge.name},
    )

    assert response.status_code == 409
    assert (
        f"A tool named '{seed_tool_knowledge.name}' already exists for this account"
        in response.json()["message"]
    )


@pytest.mark.asyncio
async def test_update_tool_not_found(
    client, seed_account, mock_auth, db_session
) -> None:
    response = await client.put(
        f"/tools/account/{seed_account.id}/999",
        json={"name": "Updated"},
    )

    assert response.status_code == 404
    assert response.json()["message"] == "Tool not found"

    result = await db_session.execute(
        select(AssistantTool).where(
            AssistantTool.id == 999,
            AssistantTool.account_id == seed_account.id,
            AssistantTool.deleted_at.is_(None),
        )
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_update_tool_account_not_found(client, mock_auth, db_session) -> None:
    response = await client.put(
        "/tools/account/999/1",
        json={"name": "Updated"},
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
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_update_tool_empty_config(client, seed_tool, mock_auth) -> None:
    response = await client.put(
        f"/tools/account/{seed_tool.account_id}/{seed_tool.id}",
        json={"config": {}},
    )

    assert response.status_code == 422
    assert (
        response.json()["detail"][0]["msg"] == "Value error, config must not be empty"
    )


@pytest.mark.asyncio
async def test_update_tool_empty_name(client, seed_tool, mock_auth) -> None:
    response = await client.put(
        f"/tools/account/{seed_tool.account_id}/{seed_tool.id}",
        json={"name": "   "},
    )

    assert response.status_code == 422
    assert (
        response.json()["detail"][0]["msg"]
        == "Value error, Tool name must be between 1 and 255 characters"
    )


@pytest.mark.asyncio
async def test_update_tool_extra_fields(client, seed_tool, mock_auth) -> None:
    response = await client.put(
        f"/tools/account/{seed_tool.account_id}/{seed_tool.id}",
        json={"name": "Updated", "extra": "field"},
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["msg"] == "Extra inputs are not permitted"


@pytest.mark.asyncio
async def test_update_tool_config_extra_unknown_field(
    client, seed_tool, mock_auth
) -> None:
    response = await client.put(
        f"/tools/account/{seed_tool.account_id}/{seed_tool.id}",
        json={"config": {"url": "https://api.example.com", "unknown_field": "value"}},
    )

    assert response.status_code == 422
    assert "config contains unknown fields" in response.json()["detail"][0]["msg"]


@pytest.mark.asyncio
async def test_update_tool_api_request_config_invalid_method(
    client, seed_tool, mock_auth
) -> None:
    response = await client.put(
        f"/tools/account/{seed_tool.account_id}/{seed_tool.id}",
        json={"config": {"method": "INVALID"}},
    )

    assert response.status_code == 422
    assert (
        "api_request config 'method' must be one of"
        in response.json()["detail"][0]["msg"]
    )


@pytest.mark.asyncio
async def test_update_tool_api_request_config_empty_description(
    client, seed_tool, mock_auth
) -> None:
    response = await client.put(
        f"/tools/account/{seed_tool.account_id}/{seed_tool.id}",
        json={"config": {"description": "   "}},
    )

    assert response.status_code == 422
    assert (
        response.json()["detail"][0]["msg"]
        == "Value error, api_request config 'description' must be a non-empty string"
    )


@pytest.mark.asyncio
async def test_update_tool_api_request_config_empty_url(
    client, seed_tool, mock_auth
) -> None:
    response = await client.put(
        f"/tools/account/{seed_tool.account_id}/{seed_tool.id}",
        json={"config": {"url": "   "}},
    )

    assert response.status_code == 422
    assert (
        response.json()["detail"][0]["msg"]
        == "Value error, api_request config 'url' must be a non-empty string"
    )


@pytest.mark.asyncio
async def test_update_tool_unauthorized(client, seed_tool) -> None:
    response = await client.put(
        f"/tools/account/{seed_tool.account_id}/{seed_tool.id}",
        json={"name": "Updated"},
    )

    assert response.status_code == 401
    assert (
        response.json()["detail"]
        == "Authentication required: provide JWT token or X-API-Key header"
    )


@pytest.mark.asyncio
async def test_update_tool_inactive_account(
    client, seed_inactive_account, mock_auth, db_session
) -> None:
    result = await db_session.execute(
        select(WhatsAppAccount).where(
            WhatsAppAccount.id == seed_inactive_account.id,
            WhatsAppAccount.is_active.is_(False),
            WhatsAppAccount.deleted_at.is_(None),
        )
    )
    assert result.scalar_one_or_none() is not None

    response = await client.put(
        f"/tools/account/{seed_inactive_account.id}/1",
        json={"name": "Updated"},
    )

    assert response.status_code == 403
    assert response.json()["message"] == "Account is inactive"


# -------------------------DELETE TOOL----------------------------


@pytest.mark.asyncio
async def test_delete_tool(client, seed_tool, mock_auth, db_session) -> None:
    account_id = seed_tool.account_id
    tool_id = seed_tool.id

    response = await client.delete(f"/tools/account/{account_id}/{tool_id}")

    assert response.status_code == 200
    assert response.json()["message"] == "Knowledge tool deleted successfully"

    result = await db_session.execute(
        select(AssistantTool).where(
            AssistantTool.id == tool_id,
            AssistantTool.deleted_at.isnot(None),
        )
    )
    tool = result.scalar_one_or_none()
    assert tool is not None
    assert tool.deleted_at is not None


@pytest.mark.asyncio
async def test_delete_tool_not_found(
    client, seed_account, mock_auth, db_session
) -> None:
    response = await client.delete(f"/tools/account/{seed_account.id}/999")

    assert response.status_code == 404
    assert response.json()["message"] == "Tool not found"

    result = await db_session.execute(
        select(AssistantTool).where(
            AssistantTool.id == 999,
            AssistantTool.account_id == seed_account.id,
            AssistantTool.deleted_at.is_(None),
        )
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_delete_tool_account_not_found(client, mock_auth, db_session) -> None:
    response = await client.delete("/tools/account/999/1")

    assert response.status_code == 404
    assert response.json()["message"] == "Account not found"

    result = await db_session.execute(
        select(WhatsAppAccount).where(
            WhatsAppAccount.id == 999,
            WhatsAppAccount.user_id == mock_auth.id,
            WhatsAppAccount.deleted_at.is_(None),
        )
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_delete_tool_unauthorized(client, seed_tool) -> None:
    response = await client.delete(
        f"/tools/account/{seed_tool.account_id}/{seed_tool.id}"
    )

    assert response.status_code == 401
    assert (
        response.json()["detail"]
        == "Authentication required: provide JWT token or X-API-Key header"
    )


@pytest.mark.asyncio
async def test_delete_tool_inactive_account(
    client, seed_inactive_account, mock_auth, db_session
) -> None:
    result = await db_session.execute(
        select(WhatsAppAccount).where(
            WhatsAppAccount.id == seed_inactive_account.id,
            WhatsAppAccount.is_active.is_(False),
            WhatsAppAccount.deleted_at.is_(None),
        )
    )
    assert result.scalar_one_or_none() is not None

    response = await client.delete(f"/tools/account/{seed_inactive_account.id}/1")

    assert response.status_code == 403
    assert response.json()["message"] == "Account is inactive"
