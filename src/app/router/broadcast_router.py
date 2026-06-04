from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.controller.broadcast_controller import (
    create_broadcast_controller,
    delete_broadcast_controller,
    get_broadcast_contacts_controller,
    get_broadcast_controller,
    get_broadcasts_controller,
    trigger_broadcast_controller,
    upload_contacts_controller,
)
from app.database.db_handler import get_db
from app.utils.middleware import CurrentUser, get_current_user
from app.validation.broadcast_validation import BroadcastCreate

router = APIRouter(prefix="/broadcasts", tags=["Broadcasts"])


@router.post("/account/{account_id}")
async def create_broadcast(
    account_id: int,
    data: BroadcastCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Create a new broadcast campaign in DRAFT status.

    Request body:
    - name: Campaign display name
    - template_name: Meta template name (must be APPROVED)
    - template_language: BCP-47 language code (e.g., en_US, hi)

    After creation, upload contacts using POST /account/{account_id}/{broadcast_id}/contacts/upload
    Then trigger the broadcast using POST /account/{account_id}/{broadcast_id}/trigger
    """
    return await create_broadcast_controller(current_user.id, account_id, data, db)


@router.get("/account/{account_id}")
async def get_broadcasts(
    account_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> JSONResponse:
    """Get paginated list of broadcast campaigns for an account.

    Query parameters:
    - page: Page number (default: 1)
    - page_size: Items per page (default: 50, max: 100)
    """
    return await get_broadcasts_controller(
        current_user.id, db, account_id, page, page_size
    )


@router.get("/account/{account_id}/{broadcast_id}")
async def get_broadcast(
    account_id: int,
    broadcast_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Get a specific broadcast campaign with full details."""
    return await get_broadcast_controller(current_user.id, account_id, broadcast_id, db)


@router.get("/account/{account_id}/{broadcast_id}/contacts")
async def get_broadcast_contacts(
    account_id: int,
    broadcast_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    status: Annotated[Optional[str], Query()] = None,
) -> JSONResponse:
    """Get paginated list of contacts for a broadcast with their delivery status."""
    return await get_broadcast_contacts_controller(
        current_user.id,
        db,
        account_id,
        broadcast_id,
        page,
        page_size,
        status,
    )


@router.delete("/account/{account_id}/{broadcast_id}")
async def delete_broadcast(
    account_id: int,
    broadcast_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Delete a broadcast campaign (only before it starts processing)."""
    return await delete_broadcast_controller(
        current_user.id, account_id, broadcast_id, db
    )


@router.post("/account/{account_id}/{broadcast_id}/contacts/upload")
async def upload_contacts(
    account_id: int,
    broadcast_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    file: UploadFile = File(...),
) -> JSONResponse:
    """Upload contacts from CSV file directly to broadcast."""
    return await upload_contacts_controller(
        current_user.id, account_id, broadcast_id, file, db
    )


@router.post("/account/{account_id}/{broadcast_id}/trigger")
async def trigger_broadcast(
    account_id: int,
    broadcast_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Trigger broadcast to start sending messages.
    Background worker will process and send messages to all contacts.
    """
    return await trigger_broadcast_controller(
        current_user.id, account_id, broadcast_id, db
    )
