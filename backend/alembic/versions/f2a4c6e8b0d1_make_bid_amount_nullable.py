"""make bid amount nullable

Revision ID: f2a4c6e8b0d1
Revises: e1f2a3b4c5d6
Create Date: 2026-03-17 13:48:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f2a4c6e8b0d1"
down_revision: Union[str, Sequence[str], None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "bids",
        "amount",
        existing_type=sa.Float(),
        nullable=True,
    )


def downgrade() -> None:
    op.execute(sa.text("UPDATE bids SET amount = 0 WHERE amount IS NULL"))
    op.alter_column(
        "bids",
        "amount",
        existing_type=sa.Float(),
        nullable=False,
    )
