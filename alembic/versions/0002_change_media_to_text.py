"""change_media_to_text_for_multiple_images

Revision ID: 0002_media_text
Revises: 0001_initial_schema
Create Date: 2026-02-09
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_media_text"
down_revision: Union[str, Sequence[str], None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('whatsapp_message', 'media',
                    existing_type=sa.String(),
                    type_=sa.Text(),
                    existing_nullable=True)


def downgrade() -> None:
    op.alter_column('whatsapp_message', 'media',
                    existing_type=sa.Text(),
                    type_=sa.String(),
                    existing_nullable=True)
