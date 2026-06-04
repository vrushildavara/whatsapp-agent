from fastapi import UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import ErrorResponse, success_response
from app.service.account_service import AccountService
from app.service.broadcast_service import BroadcastService
from app.utils.csv_parser import parse_csv_file
from app.utils.redis_manager import get_redis_client
from app.validation.broadcast_validation import BroadcastCreate, InvalidContactRow


async def create_broadcast_controller(
    user_id: int, account_id: int, data: BroadcastCreate, db: AsyncSession
) -> JSONResponse:
    """Create a new broadcast campaign in DRAFT status"""
    service = BroadcastService(db)

    # Verify account exists and belongs to user
    account_service = AccountService(db)
    account = await account_service.get_account(user_id, account_id)
    if not account:
        raise ErrorResponse(404, "Account not found")
    if not account.get("is_active"):
        raise ErrorResponse(403, "Account is inactive")

    broadcast = await service.create_broadcast(account, data)

    if not broadcast:
        raise ErrorResponse(400, "Failed to create broadcast")
    return success_response(
        data={
            "broadcast": broadcast,
        },
        message="Broadcast campaign created successfully",
        status_code=201,
    )


async def get_broadcast_controller(
    user_id: int, account_id: int, broadcast_id: int, db: AsyncSession
) -> JSONResponse:
    """Get a specific broadcast campaign with details"""
    service = BroadcastService(db)

    # Verify account exists and belongs to user
    account_service = AccountService(db)
    account = await account_service.get_account(user_id, account_id)
    if not account:
        raise ErrorResponse(404, "Account not found")
    if not account.get("is_active"):
        raise ErrorResponse(403, "Account is inactive")

    broadcast = await service.get_broadcast(account_id, broadcast_id)

    if not broadcast:
        raise ErrorResponse(404, "Broadcast campaign not found")

    return success_response(
        data=broadcast,
        message="Broadcast campaign retrieved successfully",
        status_code=200,
    )


async def get_broadcasts_controller(
    user_id: int,
    db: AsyncSession,
    account_id: int,
    page: int = 1,
    page_size: int = 50,
) -> JSONResponse:
    """Get paginated list of broadcast campaigns for an account"""
    service = BroadcastService(db)

    # Verify account exists and belongs to user
    account_service = AccountService(db)
    account = await account_service.get_account(user_id, account_id)
    if not account:
        raise ErrorResponse(404, "Account not found")
    if not account.get("is_active"):
        raise ErrorResponse(403, "Account is inactive")

    if page < 1:
        raise ErrorResponse(400, "Page must be >= 1")
    if page_size < 1 or page_size > 100:
        raise ErrorResponse(400, "Page size must be between 1 and 100")

    result = await service.get_user_broadcasts(account_id, page, page_size)

    return success_response(
        data=result,
        message="Broadcast campaigns retrieved successfully",
        status_code=200,
    )


async def get_broadcast_contacts_controller(
    user_id: int,
    db: AsyncSession,
    account_id: int,
    broadcast_id: int,
    page: int = 1,
    page_size: int = 50,
    status: str | None = None,
) -> JSONResponse:
    """Get paginated list of contacts for a specific broadcast"""
    service = BroadcastService(db)
    account_service = AccountService(db)
    account = await account_service.get_account(user_id, account_id)
    if not account:
        raise ErrorResponse(404, "Account not found")
    if not account.get("is_active"):
        raise ErrorResponse(403, "Account is inactive")

    # Verify broadcast belongs to account
    broadcast = await service.get_broadcast(account_id, broadcast_id)
    if not broadcast:
        raise ErrorResponse(404, "Broadcast campaign not found")

    if page < 1:
        raise ErrorResponse(400, "Page must be >= 1")
    if page_size < 1 or page_size > 100:
        raise ErrorResponse(400, "Page size must be between 1 and 100")

    # Validate status filter if provided
    valid_statuses = ["PENDING", "SENT", "DELIVERED", "FAILED"]
    if status and status not in valid_statuses:
        raise ErrorResponse(400, f"Status must be one of: {', '.join(valid_statuses)}")

    result = await service.get_broadcast_contacts(broadcast_id, page, page_size, status)

    return success_response(
        data=result,
        message="Broadcast contacts retrieved successfully",
        status_code=200,
    )


async def delete_broadcast_controller(
    user_id: int, account_id: int, broadcast_id: int, db: AsyncSession
) -> JSONResponse:
    """Delete a broadcast campaign"""
    service = BroadcastService(db)

    # Verify account exists and belongs to user
    account_service = AccountService(db)
    account = await account_service.get_account(user_id, account_id)
    if not account:
        raise ErrorResponse(404, "Account not found")
    if not account.get("is_active"):
        raise ErrorResponse(403, "Account is inactive")

    # Verify broadcast exists
    broadcast = await service.get_broadcast(account_id, broadcast_id)
    if not broadcast:
        raise ErrorResponse(404, "Broadcast campaign not found")

    await service.delete_broadcast(account_id, broadcast_id)

    return success_response(
        data={"broadcast_id": broadcast_id},
        message="Broadcast campaign deleted successfully",
        status_code=200,
    )


async def upload_contacts_controller(
    user_id: int, account_id: int, broadcast_id: int, file: UploadFile, db: AsyncSession
) -> JSONResponse:
    """Upload contacts from CSV file directly to broadcast_contacts"""
    service = BroadcastService(db)

    # Verify account exists and belongs to user
    account_service = AccountService(db)
    account = await account_service.get_account(user_id, account_id)
    if not account:
        raise ErrorResponse(404, "Account not found")
    if not account.get("is_active"):
        raise ErrorResponse(403, "Account is inactive")

    # Verify broadcast exists and belongs to account
    broadcast = await service.get_broadcast(account_id, broadcast_id)
    if not broadcast:
        raise ErrorResponse(404, "Broadcast not found")

    # Check if broadcast is in DRAFT status
    if broadcast["status"] != "DRAFT":
        raise ErrorResponse(
            400, f"Cannot upload contacts to broadcast in {broadcast['status']} status"
        )

    # Validate file
    if not file.filename:
        raise ErrorResponse(400, "No file provided")

    if not file.filename.lower().endswith(".csv"):
        raise ErrorResponse(400, "File must be a CSV file")

    # Check file size (max 10MB)
    if file.size and file.size > 10 * 1024 * 1024:
        raise ErrorResponse(400, "File size exceeds 10MB limit")

    try:
        # Parse CSV file
        valid_contacts, invalid_rows = await parse_csv_file(file)

        if not valid_contacts:
            raise ErrorResponse(
                400,
                "CSV file contains no valid contacts. "
                + "Please check the format and try again.",
            )

        # Upload contacts directly to broadcast_contacts
        result = await service.upload_contacts_to_broadcast(
            broadcast_id, valid_contacts
        )

        if not result:
            raise ErrorResponse(400, "Failed to upload contacts")

        # Format invalid rows
        formatted_invalid_rows = [
            InvalidContactRow(
                row_number=row["row_number"],
                phone_number=row["phone_number"],
                error=row["error"],
            )
            for row in invalid_rows
        ]

        return success_response(
            data={
                "broadcast_id": broadcast_id,
                "filename": file.filename,
                "contacts_uploaded": result["contacts_uploaded"],
                "duplicates_skipped": result["duplicates_skipped"],
                "invalid_contacts": len(invalid_rows),
                "invalid_rows": formatted_invalid_rows,
            },
            message="Contacts uploaded successfully",
            status_code=201,
        )

    except ErrorResponse:
        raise
    except Exception as e:
        raise ErrorResponse(400, f"Failed to upload contacts: {str(e)}")


async def trigger_broadcast_controller(
    user_id: int, account_id: int, broadcast_id: int, db: AsyncSession
) -> JSONResponse:
    """Trigger broadcast to start sending messages"""
    service = BroadcastService(db)

    # Verify account exists and belongs to user
    account_service = AccountService(db)
    account = await account_service.get_account(user_id, account_id)
    if not account:
        raise ErrorResponse(404, "Account not found")
    if not account.get("is_active"):
        raise ErrorResponse(403, "Account is inactive")

    try:
        # Trigger broadcast (DRAFT → QUEUED)
        triggered = await service.trigger_broadcast(broadcast_id, account_id)

        if not triggered:
            raise ErrorResponse(400, "Failed to trigger broadcast")

        # Push to Redis queue for background processing
        redis = get_redis_client()
        if redis:
            try:
                await redis.lpush("broadcast_queue", str(broadcast_id))
            except Exception as e:
                # Log but don't fail - worker will pick it up via polling
                import logging

                logging.warning(f"Failed to push to Redis queue: {e}")

        return success_response(
            data={"broadcast_id": broadcast_id, "status": "QUEUED"},
            message="Broadcast triggered successfully. Messages will be sent by background worker.",
            status_code=200,
        )

    except ValueError as e:
        raise ErrorResponse(400, str(e))
    except Exception as e:
        raise ErrorResponse(400, f"Failed to trigger broadcast: {str(e)}")
