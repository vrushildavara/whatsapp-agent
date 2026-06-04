from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.main import app
from app.models.model import User
from app.utils.middleware import get_current_user
from app.utils.security import verify_password
from tests.conftest import FakeUser

# -------------------------REGISTER USER----------------------------


@pytest.mark.asyncio
async def test_register_user(client, db_session) -> None:
    email = "newuser@example.com"
    response = await client.post(
        "/users/register",
        json={
            "email": email,
            "password": "Password@123",
            "name": "Test",
        },
    )

    assert response.status_code == 200
    assert response.json()["message"] == "User registered successfully"

    result = await db_session.execute(select(User).where(User.email == email))

    user = result.scalar_one_or_none()

    assert user is not None
    assert user.email == email
    assert user.name == "Test"


@pytest.mark.asyncio
async def test_register_validation_error(client) -> None:
    response = await client.post(
        "/users/register",
        json={"email": "invalid-email", "password": "Password@123", "name": "test"},
    )

    assert response.status_code == 422
    assert (
        response.json()["detail"][0]["msg"]
        == "value is not a valid email address: An email address must have an @-sign."
    )


@pytest.mark.asyncio
async def test_register_missing_fields(client) -> None:
    response = await client.post(
        "/users/register",
        json={"email": "missing@example.com"},
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["msg"] == "Field required"


@pytest.mark.asyncio
async def test_register_extra_fields(client) -> None:
    response = await client.post(
        "/users/register",
        json={
            "email": "missing@example.com",
            "password": "Password@123",
            "name": "Test",
            "extra": "field",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["msg"] == "Extra inputs are not permitted"


@pytest.mark.asyncio
async def test_already_exists(client, seed_user, db_session) -> None:
    email = seed_user.email
    response = await client.post(
        "/users/register",
        json={
            "email": email,
            "password": "Password@123",
            "name": "test",
        },
    )

    assert response.status_code == 400
    assert response.json()["message"] == "User already registered"

    result = await db_session.execute(select(User).where(User.email == email))

    user = result.scalar_one_or_none()

    assert user is not None
    assert user.email == email


# -------------------------LOGIN USER----------------------------


@pytest.mark.asyncio
async def test_login_user(client, seed_user, db_session) -> None:
    email = seed_user.email
    response = await client.post(
        "/users/login",
        json={"email": email, "password": "Password@123"},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Login successfully"

    result = await db_session.execute(select(User).where(User.email == email))

    user = result.scalar_one_or_none()

    assert user is not None
    assert verify_password("Password@123", user.password)


@pytest.mark.asyncio
async def test_validate_login(client, seed_user) -> None:
    response = await client.post(
        "/users/login", json={"email": seed_user.email, "password": "password123"}
    )

    assert response.status_code == 401
    assert response.json()["message"] == "Invalid email or password"


@pytest.mark.asyncio
async def test_login_validation_error(client) -> None:
    response = await client.post(
        "/users/login",
        json={"email": "invalid-email", "password": "Password@123"},
    )

    assert response.status_code == 422
    assert (
        response.json()["detail"][0]["msg"]
        == "value is not a valid email address: An email address must have an @-sign."
    )


@pytest.mark.asyncio
async def test_login_missing_fields(client, seed_user) -> None:
    response = await client.post(
        "/users/login",
        json={
            "email": seed_user.email,
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["msg"] == "Field required"


@pytest.mark.asyncio
async def test_login_extra_fields(client, seed_user) -> None:
    response = await client.post(
        "/users/login",
        json={
            "email": seed_user.email,
            "password": "Password@123",
            "extra": "field",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["msg"] == "Extra inputs are not permitted"


# -------------------------GET USER----------------------------


@pytest.mark.asyncio
async def test_get_user(client, mock_auth, db_session) -> None:
    response = await client.get(
        "/users/get",
    )

    assert response.status_code == 200
    assert response.json()["message"] == "User retrieved successfully"

    result = await db_session.execute(select(User).where(User.id == mock_auth.id))

    user = result.scalar_one_or_none()

    assert user is not None


@pytest.mark.asyncio
async def test_get_user_unauthorized(client) -> None:
    response = await client.get("/users/get")

    assert response.status_code == 401
    assert (
        response.json()["detail"]
        == "Authentication required: provide JWT token or X-API-Key header"
    )


@pytest.mark.asyncio
async def test_get_user_not_found(client, db_session) -> None:
    app.dependency_overrides[get_current_user] = lambda: FakeUser()

    response = await client.get("/users/get")

    assert response.status_code == 404
    assert response.json()["message"] == "User not found"

    result = await db_session.execute(
        select(User).where(User.email == "fakeuser@example.com")
    )

    user = result.scalar_one_or_none()

    assert user is None

    app.dependency_overrides.pop(get_current_user, None)


# -------------------------FORGOT PASSWORD----------------------------


@pytest.mark.asyncio
@patch("app.controller.user_controller.send_email", new_callable=AsyncMock)
async def test_forgot_password(mock_send_email, client, seed_user, db_session) -> None:
    email = seed_user.email
    response = await client.post(
        "/users/forgot-password",
        json={"email": email},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Password reset code sent to email"

    result = await db_session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    assert user.reset_code is not None
    assert user.reset_code_expires_at is not None

    mock_send_email.assert_called_once()


@pytest.mark.asyncio
async def test_forgot_password_user_not_found(client, db_session) -> None:
    email = "nouser@example.com"
    response = await client.post(
        "/users/forgot-password",
        json={"email": email},
    )

    assert response.status_code == 404
    assert response.json()["message"] == "User not found"

    result = await db_session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    assert user is None


@pytest.mark.asyncio
async def test_forgot_password_validation(client) -> None:
    response = await client.post(
        "/users/forgot-password",
        json={"email": "invalid-email"},
    )

    assert response.status_code == 422
    assert (
        response.json()["detail"][0]["msg"]
        == "value is not a valid email address: An email address must have an @-sign."
    )


@pytest.mark.asyncio
async def test_forgot_password_missing_fields(client) -> None:
    response = await client.post("/users/forgot-password")

    assert response.status_code == 422
    assert response.json()["detail"][0]["msg"] == "Field required"


@pytest.mark.asyncio
async def test_forgot_password_extra_fields(client, seed_user) -> None:
    response = await client.post(
        "/users/forgot-password",
        json={"email": seed_user.email, "extra": "field"},
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["msg"] == "Extra inputs are not permitted"


# -------------------------RESET PASSWORD----------------------------


@pytest.mark.asyncio
@patch("app.controller.user_controller.send_email", new_callable=AsyncMock)
async def test_reset_password(mock_send_email, client, seed_user, db_session) -> None:
    email = seed_user.email

    await client.post(
        "/users/forgot-password",
        json={"email": email},
    )

    mock_send_email.assert_called_once()

    result = await db_session.execute(select(User).where(User.email == email))
    user = result.scalar_one()
    code = user.reset_code

    response = await client.post(
        "/users/reset-password",
        json={
            "email": email,
            "code": str(code),
            "new_password": "NewPassword@123",
        },
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Password reset successfully"

    await db_session.refresh(user)

    result = await db_session.execute(select(User).where(User.email == email))
    updated_user = result.scalar_one()

    assert verify_password("NewPassword@123", updated_user.password)


@pytest.mark.asyncio
async def test_reset_password_user_not_found(client, db_session) -> None:
    email = "nouser@example.com"
    response = await client.post(
        "/users/reset-password",
        json={
            "email": email,
            "code": "123456",
            "new_password": "NewPassword@123",
        },
    )

    assert response.status_code == 400
    assert response.json()["message"] == "We couldn’t find an account with this email"

    result = await db_session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    assert user is None


@pytest.mark.asyncio
async def test_reset_password_invalid_code(client, seed_user, db_session) -> None:
    email = seed_user.email
    response = await client.post(
        "/users/reset-password",
        json={
            "email": email,
            "code": "wrongcode",
            "new_password": "Password@123",
        },
    )

    assert response.status_code == 400
    assert response.json()["message"] == "The reset code you entered is incorrect"

    result = await db_session.execute(select(User).where(User.email == email))
    user = result.scalar_one()
    code = user.reset_code

    assert code != "wrongcode"


@pytest.mark.asyncio
async def test_reset_password_validation(client) -> None:
    response = await client.post(
        "/users/reset-password",
        json={
            "email": "invalid",
            "code": "",
            "new_password": "short",
        },
    )

    assert response.status_code == 422
    assert (
        response.json()["detail"][0]["msg"]
        == "value is not a valid email address: An email address must have an @-sign."
    )


@pytest.mark.asyncio
async def test_reset_password_missing_fields(client, seed_user) -> None:
    response = await client.post(
        "/users/reset-password",
        json={
            "email": seed_user.email,
            "new_password": "Password@123",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["msg"] == "Field required"


@pytest.mark.asyncio
async def test_reset_password_extra_fields(client, seed_user) -> None:
    response = await client.post(
        "/users/reset-password",
        json={
            "email": seed_user.email,
            "code": "159874",
            "new_password": "Password@123",
            "extra": "field",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["msg"] == "Extra inputs are not permitted"


# -------------------------REGENERATE API KEY----------------------------


@pytest.mark.asyncio
async def test_regenerate_api_key(client, seed_user, db_session) -> None:
    email = seed_user.email
    old_api_key = seed_user.api_key

    response = await client.post(
        "/users/api-key/regenerate",
        json={"email": email, "password": "Password@123"},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "API key regenerated successfully"

    result = await db_session.execute(select(User).where(User.email == email))
    user = result.scalar_one()

    assert user.api_key != old_api_key


@pytest.mark.asyncio
async def test_regenerate_api_key_invalid_credentials(client, seed_user) -> None:
    response = await client.post(
        "/users/api-key/regenerate",
        json={"email": seed_user.email, "password": "WrongPassword@123"},
    )

    assert response.status_code == 401
    assert response.json()["message"] == "Invalid email or password"


@pytest.mark.asyncio
async def test_regenerate_api_key_missing_fields(client, seed_user) -> None:
    response = await client.post(
        "/users/api-key/regenerate",
        json={"email": seed_user.email},
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["msg"] == "Field required"


@pytest.mark.asyncio
async def test_regenerate_api_key_extra_fields(client, seed_user) -> None:
    response = await client.post(
        "/users/api-key/regenerate",
        json={
            "email": seed_user.email,
            "password": "Password@123",
            "extra": "field",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["msg"] == "Extra inputs are not permitted"


@pytest.mark.asyncio
async def test_regenerate_api_key_invalid_email(client) -> None:
    response = await client.post(
        "/users/api-key/regenerate",
        json={"email": "invalid-email", "password": "Password@123"},
    )

    assert response.status_code == 422
    assert (
        response.json()["detail"][0]["msg"]
        == "value is not a valid email address: An email address must have an @-sign."
    )
