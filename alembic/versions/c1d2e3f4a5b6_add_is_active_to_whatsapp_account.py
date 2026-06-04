"""add is_active to whatsapp_account

Revision ID: c1d2e3f4a5b6
Revises: f0f63f4c66f9
Create Date: 2026-04-07
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, Sequence[str], None] = "f0f63f4c66f9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "whatsapp_account",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade() -> None:
    op.drop_column("whatsapp_account", "is_active")
