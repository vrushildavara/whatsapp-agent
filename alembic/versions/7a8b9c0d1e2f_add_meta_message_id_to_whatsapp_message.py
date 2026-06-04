"""add meta message id to whatsapp message

Revision ID: 7a8b9c0d1e2f
Revises: 4eb873a31173
Create Date: 2026-04-29 11:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7a8b9c0d1e2f"
down_revision: Union[str, Sequence[str], None] = "4eb873a31173"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "whatsapp_message",
        sa.Column("meta_message_id", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("whatsapp_message", "meta_message_id")
