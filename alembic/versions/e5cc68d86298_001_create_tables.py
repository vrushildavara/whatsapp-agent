"""initial_schema_with_whatsapp_updates

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-02-09
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -------------------- USERS --------------------
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("password", sa.String(), nullable=False),
        sa.Column("reset_code", sa.String(), nullable=True),
        sa.Column("reset_code_expires_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )

    # -------------------- WHATSAPP ACCOUNT --------------------
    op.create_table(
        "whatsapp_account",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("phone_number", sa.BigInteger(), nullable=False),
        sa.Column("phone_number_id", sa.String(), nullable=True),
        sa.Column("token", sa.String(), nullable=True),
        sa.Column("prompt", sa.Text(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # -------------------- WHATSAPP SESSION --------------------
    op.create_table(
        "whatsapp_session",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("to_number", sa.BigInteger(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["account_id"], ["whatsapp_account.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # -------------------- WHATSAPP MESSAGE --------------------
    op.create_table(
        "whatsapp_message",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=10), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("media", sa.String(), nullable=True),
        sa.Column(
            "is_summarized",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["session_id"], ["whatsapp_session.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # -------------------- SESSION SUMMARY --------------------
    op.create_table(
        "whatsapp_session_summary",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["session_id"], ["whatsapp_session.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id"),
    )


def downgrade() -> None:
    op.drop_table("whatsapp_session_summary")
    op.drop_table("whatsapp_message")
    op.drop_table("whatsapp_session")
    op.drop_table("whatsapp_account")
    op.drop_table("users")
