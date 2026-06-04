"""replace media_text with media jsonb

Revision ID: bbeca83de7b1
Revises: 0003_media_text
Create Date: 2026-02-20 12:14:48.304669

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'bbeca83de7b1'
down_revision: Union[str, Sequence[str], None] = '0003_media_text'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



def upgrade():
    op.drop_column("whatsapp_message", "media")
    op.add_column(
        "whatsapp_message",
        sa.Column("media", postgresql.JSONB(), nullable=True),
    )


def downgrade():
    op.drop_column("whatsapp_message", "media")
    op.add_column(
        "whatsapp_message",
        sa.Column("media", sa.Text(), nullable=True),
    )
