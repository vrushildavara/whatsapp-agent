"""add_media_text_column

Revision ID: 0003_media_text
Revises: 0002_media_text
Create Date: 2026-02-09
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_media_text"
down_revision: Union[str, Sequence[str], None] = "0002_media_text"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('whatsapp_message', sa.Column('media_text', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('whatsapp_message', 'media_text')
