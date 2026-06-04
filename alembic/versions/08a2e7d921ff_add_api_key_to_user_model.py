"""add api_key to user model

Revision ID: 03fead509a51
Revises: 0e5b445a4cc6
Create Date: 2026-03-26 15:33:22.709542

"""

from typing import Sequence, Union
import secrets

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = "03fead509a51"
down_revision: Union[str, Sequence[str], None] = "0e5b445a4cc6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def generate_api_key() -> str:
    """Generate unique API key"""
    return f"wa_{secrets.token_urlsafe(32)}"


def upgrade() -> None:
    """Upgrade schema."""
    # Step 1: Add column as nullable first
    op.add_column("users", sa.Column("api_key", sa.String(), nullable=True))

    # Step 2: Generate API keys for existing users
    connection = op.get_bind()
    result = connection.execute(text("SELECT id FROM users WHERE api_key IS NULL"))

    for row in result:
        user_id = row[0]
        api_key = generate_api_key()
        connection.execute(
            text("UPDATE users SET api_key = :api_key WHERE id = :user_id"),
            {"api_key": api_key, "user_id": user_id},
        )

    # Step 3: Make column NOT NULL
    op.alter_column("users", "api_key", nullable=False)

    # Step 4: Create unique index
    op.create_index(op.f("ix_users_api_key"), "users", ["api_key"], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_users_api_key"), table_name="users")
    op.drop_column("users", "api_key")
