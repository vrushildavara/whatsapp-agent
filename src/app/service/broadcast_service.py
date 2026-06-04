import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import ErrorResponse
from app.database.db_handler import get_db
from app.models.model import (
    Broadcast,
    BroadcastContact,
)
from app.service.template_service import template_service
from app.validation.broadcast_validation import BroadcastCreate

logger = logging.getLogger(__name__)


class BroadcastService:
    def __init__(self, db: AsyncSession) -> None:
        self.model = Broadcast
        self.contact_model = BroadcastContact
        self.db = db

    async def create_broadcast(
        self,
        account: dict,
        data: BroadcastCreate,
    ) -> dict | None:
        """Create a new broadcast campaign in DRAFT status"""

        try:
            # Validate account credentials
            if not account.get("waba_id") or not account.get("token"):
                raise ValueError("Missing WhatsApp account credentials")

            # Fetch template snapshot
            template_snapshot = await template_service.get_template_by_name(
                waba_id=account["waba_id"],
                access_token=account["token"],
                template_name=data.template_name,
                language=data.template_language,
            )

            if not template_snapshot:
                raise ValueError(
                    f"Template '{data.template_name}' not found or not approved"
                )

            # Insert broadcast record
            stmt = (
                insert(self.model)
                .values(
                    account_id=account["id"],
                    name=data.name,
                    template_name=data.template_name,
                    template_language=data.template_language,
                    template_snapshot=template_snapshot,
                    status="DRAFT",
                    total_contacts=0,
                )
                .returning(
                    self.model.id,
                    self.model.account_id,
                    self.model.name,
                    self.model.template_name,
                    self.model.template_language,
                    self.model.status,
                    self.model.total_contacts,
                )
            )

            result = await self.db.execute(stmt)
            await self.db.commit()

            return dict(result.mappings().one())

        except ValueError as e:
            raise ErrorResponse(400, str(e))

        except Exception as e:
            await self.db.rollback()
            raise ErrorResponse(400, str(e))

    async def get_broadcast(self, account_id: int, broadcast_id: int) -> dict | None:
        """Fetch a single broadcast by ID"""
        stmt = select(self.model).where(
            self.model.id == broadcast_id,
            self.model.account_id == account_id,
        )
        result = await self.db.execute(stmt)
        broadcast = result.scalars().first()

        if not broadcast:
            return None

        return {
            "id": broadcast.id,
            "account_id": broadcast.account_id,
            "name": broadcast.name,
            "template_name": broadcast.template_name,
            "template_language": broadcast.template_language,
            "template_snapshot": broadcast.template_snapshot,
            "status": broadcast.status,
            "total_contacts": broadcast.total_contacts,
            "sent_count": broadcast.sent_count,
            "delivered_count": broadcast.delivered_count,
            "failed_count": broadcast.failed_count,
            "created_at": broadcast.created_at.isoformat(),
            "started_at": broadcast.started_at.isoformat()
            if broadcast.started_at
            else None,
            "completed_at": broadcast.completed_at.isoformat()
            if broadcast.completed_at
            else None,
        }

    async def get_user_broadcasts(
        self, account_id: int, page: int = 1, page_size: int = 50
    ) -> dict:
        """Fetch paginated broadcasts for an account"""
        offset = (page - 1) * page_size

        # Get total count
        count_stmt = select(self.model).where(self.model.account_id == account_id)
        count_result = await self.db.execute(count_stmt)
        total = len(count_result.scalars().all())

        # Get paginated results
        stmt = (
            select(self.model)
            .where(self.model.account_id == account_id)
            .order_by(self.model.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        broadcasts = result.scalars().all()

        return {
            "data": [
                {
                    "id": b.id,
                    "account_id": b.account_id,
                    "name": b.name,
                    "template_name": b.template_name,
                    "template_language": b.template_language,
                    "status": b.status,
                    "total_contacts": b.total_contacts,
                    "sent_count": b.sent_count,
                    "delivered_count": b.delivered_count,
                    "failed_count": b.failed_count,
                    "created_at": b.created_at.isoformat(),
                    "started_at": b.started_at.isoformat() if b.started_at else None,
                    "completed_at": b.completed_at.isoformat()
                    if b.completed_at
                    else None,
                }
                for b in broadcasts
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def get_broadcast_contacts(
        self,
        broadcast_id: int,
        page: int = 1,
        page_size: int = 50,
        status: Optional[str] = None,
    ) -> dict:
        """Fetch paginated contacts for a broadcast"""
        offset = (page - 1) * page_size

        # Build query
        query = select(self.contact_model).where(
            self.contact_model.broadcast_id == broadcast_id
        )

        if status:
            query = query.where(self.contact_model.status == status)

        # Get total count
        count_stmt = query
        count_result = await self.db.execute(count_stmt)
        total = len(count_result.scalars().all())

        # Get paginated results
        stmt = (
            query.order_by(self.contact_model.created_at.asc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        contacts = result.scalars().all()

        return {
            "data": [
                {
                    "id": c.id,
                    "phone_number": c.phone_number,
                    "status": c.status,
                    "meta_message_id": c.meta_message_id,
                    "error_code": c.error_code,
                    "error_message": c.error_message,
                    "sent_at": c.sent_at.isoformat() if c.sent_at else None,
                    "delivered_at": c.delivered_at.isoformat()
                    if c.delivered_at
                    else None,
                    "created_at": c.created_at.isoformat(),
                }
                for c in contacts
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def update_broadcast_status(
        self,
        broadcast_id: int,
        status: str,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
    ) -> None:
        """Update broadcast status"""
        update_data: dict[str, Any] = {"status": status}
        if started_at:
            update_data["started_at"] = started_at
        if completed_at:
            update_data["completed_at"] = completed_at

        stmt = (
            update(self.model)
            .where(self.model.id == broadcast_id)
            .values(**update_data)
        )
        await self.db.execute(stmt)
        await self.db.commit()

    async def update_broadcast_counts(
        self,
        broadcast_id: int,
        sent_count: int,
        delivered_count: int,
        failed_count: int,
    ) -> None:
        """Update broadcast message counts using atomic SQL increments
        to avoid race conditions with delivery webhooks."""
        stmt = (
            update(self.model)
            .where(self.model.id == broadcast_id)
            .values(
                sent_count=self.model.sent_count + sent_count,
                delivered_count=self.model.delivered_count + delivered_count,
                failed_count=self.model.failed_count + failed_count,
            )
        )
        await self.db.execute(stmt)
        await self.db.commit()

    async def update_contact_status(
        self,
        contact_id: int,
        status: str,
        meta_message_id: Optional[str] = None,
        error_code: Optional[int] = None,
        error_message: Optional[str] = None,
        sent_at: Optional[datetime] = None,
        delivered_at: Optional[datetime] = None,
    ) -> None:
        """Update broadcast contact status"""
        update_data: dict[str, Any] = {"status": status}
        if meta_message_id:
            update_data["meta_message_id"] = meta_message_id
        if error_code:
            update_data["error_code"] = error_code
        if error_message:
            update_data["error_message"] = error_message
        if sent_at:
            update_data["sent_at"] = sent_at
        if delivered_at:
            update_data["delivered_at"] = delivered_at

        stmt = (
            update(self.contact_model)
            .where(self.contact_model.id == contact_id)
            .values(**update_data)
        )
        await self.db.execute(stmt)
        await self.db.commit()

    async def get_pending_contacts(self, broadcast_id: int) -> list:
        """Get all pending contacts for a broadcast"""
        stmt = select(self.contact_model).where(
            self.contact_model.broadcast_id == broadcast_id,
            self.contact_model.status == "PENDING",
        )
        result = await self.db.execute(stmt)
        contacts = result.scalars().all()

        return [
            {
                "id": c.id,
                "phone_number": c.phone_number,
                "template_variables": c.template_variables,
            }
            for c in contacts
        ]

    async def delete_broadcast(self, account_id: int, broadcast_id: int) -> None:
        """Delete a broadcast campaign"""
        stmt = delete(self.model).where(
            self.model.id == broadcast_id,
            self.model.account_id == account_id,
        )
        await self.db.execute(stmt)
        await self.db.commit()

    async def upload_contacts_to_broadcast(
        self,
        broadcast_id: int,
        contacts: list[dict],
    ) -> dict:
        """Upload contacts directly to broadcast_contacts table"""
        try:
            # Get existing phone numbers for this broadcast
            existing_stmt = select(self.contact_model.phone_number).where(
                self.contact_model.broadcast_id == broadcast_id
            )
            result = await self.db.execute(existing_stmt)
            existing_phones = {row[0] for row in result.fetchall()}

            # Filter out duplicates
            unique_contacts = [
                {
                    "broadcast_id": broadcast_id,
                    "phone_number": contact["phone_number"],
                    "template_variables": contact.get("variables"),
                    "status": "PENDING",
                }
                for contact in contacts
                if contact["phone_number"] not in existing_phones
            ]

            duplicates_count = len(contacts) - len(unique_contacts)

            if unique_contacts:
                await self.db.execute(
                    insert(self.contact_model).values(unique_contacts)
                )

                # Increment broadcast total_contacts count by unique contacts only
                stmt = (
                    update(self.model)
                    .where(self.model.id == broadcast_id)
                    .values(
                        total_contacts=self.model.total_contacts + len(unique_contacts)
                    )
                )
                await self.db.execute(stmt)

            await self.db.commit()

            return {
                "broadcast_id": broadcast_id,
                "contacts_uploaded": len(unique_contacts),
                "duplicates_skipped": duplicates_count,
            }

        except Exception as e:
            await self.db.rollback()
            raise e

    async def trigger_broadcast(self, broadcast_id: int, account_id: int) -> bool:
        """Trigger broadcast to change status from DRAFT to QUEUED"""
        try:
            # Verify broadcast exists and belongs to account
            broadcast = await self.get_broadcast(account_id, broadcast_id)
            if not broadcast:
                raise ValueError("Broadcast not found")

            # Check if broadcast has contacts
            if broadcast["total_contacts"] == 0:
                raise ValueError("Cannot trigger broadcast with no contacts")

            # Check if broadcast is in DRAFT status
            if broadcast["status"] != "DRAFT":
                raise ValueError(
                    f"Cannot trigger broadcast in {broadcast['status']} status"
                )

            # Update status to QUEUED
            stmt = (
                update(self.model)
                .where(
                    self.model.id == broadcast_id, self.model.account_id == account_id
                )
                .values(status="QUEUED")
            )
            result = await self.db.execute(stmt)
            await self.db.commit()

            return result.rowcount > 0  # type: ignore

        except Exception as e:
            await self.db.rollback()
            raise e

    async def handle_broadcast_status_update(self, statuses: list[dict]) -> None:
        """
        Handle WhatsApp status updates for broadcast messages.
        Updates BroadcastContact status based on delivery receipts.

        Status types:
        - sent: Message sent to WhatsApp
        - delivered: Message delivered to user's device
        - read: User opened the message
        - failed: Delivery failed
        """

        async for db in get_db():
            for status_update in statuses:
                try:
                    message_id = status_update.get("id")  # wamid from Meta
                    status = status_update.get(
                        "status"
                    )  # sent, delivered, read, failed

                    if not message_id or not status:
                        continue

                    # Find broadcast contact by meta_message_id
                    result = await db.execute(
                        select(BroadcastContact).where(
                            BroadcastContact.meta_message_id == message_id
                        )
                    )

                    contact = result.scalars().first()

                    if not contact:
                        # Not a broadcast message, ignore
                        continue

                    # Update contact status
                    update_data = {}

                    if status == "delivered":
                        update_data["status"] = "DELIVERED"
                        update_data["delivered_at"] = datetime.now(timezone.utc)

                        # Increment broadcast delivered_count
                        await db.execute(
                            update(Broadcast)
                            .where(Broadcast.id == contact.broadcast_id)
                            .values(delivered_count=Broadcast.delivered_count + 1)
                        )

                    elif status == "failed":
                        update_data["status"] = "FAILED"

                        # Extract error details
                        errors = status_update.get("errors", [])
                        if errors:
                            error = errors[0]
                            update_data["error_code"] = error.get("code")
                            update_data["error_message"] = error.get(
                                "title", "Unknown error"
                            )

                        # Increment broadcast failed_count
                        await db.execute(
                            update(Broadcast)
                            .where(Broadcast.id == contact.broadcast_id)
                            .values(failed_count=Broadcast.failed_count + 1)
                        )

                    if update_data:
                        await db.execute(
                            update(BroadcastContact)
                            .where(BroadcastContact.id == contact.id)
                            .values(**update_data)
                        )

                        await db.commit()

                        logger.info(
                            f"Broadcast status updated | contact_id={contact.id} | status={status} | message_id={message_id}"
                        )

                except Exception as e:
                    logger.error(
                        f"Failed to handle broadcast status update | error={e}",
                        exc_info=True,
                    )
                    await db.rollback()
