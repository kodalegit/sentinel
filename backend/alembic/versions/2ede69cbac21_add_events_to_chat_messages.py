"""add_events_to_chat_messages

Revision ID: 2ede69cbac21
Revises: c5d6e7f8g9h0
Create Date: 2026-03-03 22:32:52.713343

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "2ede69cbac21"
down_revision: Union[str, Sequence[str], None] = "c5d6e7f8g9h0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("chat_messages", sa.Column("events", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("chat_messages", "events")
