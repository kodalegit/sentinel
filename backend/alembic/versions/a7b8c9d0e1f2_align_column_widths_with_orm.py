"""align column widths with orm

Revision ID: a7b8c9d0e1f2
Revises: f2a4c6e8b0d1
Create Date: 2026-03-24 01:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = "f2a4c6e8b0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- companies ---
    op.alter_column(
        "companies",
        "registration_number",
        existing_type=sa.String(length=50),
        type_=sa.String(length=255),
        existing_nullable=False,
    )
    op.alter_column(
        "companies",
        "source_record_id",
        existing_type=sa.String(length=100),
        type_=sa.String(length=500),
        existing_nullable=True,
    )
    op.alter_column(
        "companies",
        "postal_code",
        existing_type=sa.String(length=20),
        type_=sa.Text(),
        existing_nullable=True,
    )

    # --- tenders ---
    op.alter_column(
        "tenders",
        "reference_number",
        existing_type=sa.String(length=100),
        type_=sa.String(length=255),
        existing_nullable=False,
    )
    op.alter_column(
        "tenders",
        "category",
        existing_type=sa.String(length=100),
        type_=sa.String(length=255),
        existing_nullable=True,
    )
    op.alter_column(
        "tenders",
        "procurement_method",
        existing_type=sa.String(length=100),
        type_=sa.String(length=255),
        existing_nullable=True,
    )
    op.alter_column(
        "tenders",
        "procurement_category",
        existing_type=sa.String(length=100),
        type_=sa.String(length=255),
        existing_nullable=True,
    )
    op.alter_column(
        "tenders",
        "pe_type",
        existing_type=sa.String(length=100),
        type_=sa.String(length=255),
        existing_nullable=True,
    )
    op.alter_column(
        "tenders",
        "ocds_id",
        existing_type=sa.String(length=255),
        type_=sa.String(length=500),
        existing_nullable=True,
    )
    op.alter_column(
        "tenders",
        "source_record_id",
        existing_type=sa.String(length=255),
        type_=sa.String(length=500),
        existing_nullable=True,
    )

    # --- contracts ---
    op.alter_column(
        "contracts",
        "contract_number",
        existing_type=sa.String(length=100),
        type_=sa.String(length=255),
        existing_nullable=False,
    )
    op.alter_column(
        "contracts",
        "procurement_method",
        existing_type=sa.String(length=100),
        type_=sa.String(length=255),
        existing_nullable=True,
    )
    op.alter_column(
        "contracts",
        "procurement_category",
        existing_type=sa.String(length=100),
        type_=sa.String(length=255),
        existing_nullable=True,
    )
    op.alter_column(
        "contracts",
        "pe_type",
        existing_type=sa.String(length=100),
        type_=sa.String(length=255),
        existing_nullable=True,
    )
    op.alter_column(
        "contracts",
        "source_record_id",
        existing_type=sa.String(length=255),
        type_=sa.String(length=500),
        existing_nullable=True,
    )


def downgrade() -> None:
    # --- contracts ---
    op.alter_column(
        "contracts",
        "source_record_id",
        existing_type=sa.String(length=500),
        type_=sa.String(length=255),
        existing_nullable=True,
    )
    op.alter_column(
        "contracts",
        "pe_type",
        existing_type=sa.String(length=255),
        type_=sa.String(length=100),
        existing_nullable=True,
    )
    op.alter_column(
        "contracts",
        "procurement_category",
        existing_type=sa.String(length=255),
        type_=sa.String(length=100),
        existing_nullable=True,
    )
    op.alter_column(
        "contracts",
        "procurement_method",
        existing_type=sa.String(length=255),
        type_=sa.String(length=100),
        existing_nullable=True,
    )
    op.alter_column(
        "contracts",
        "contract_number",
        existing_type=sa.String(length=255),
        type_=sa.String(length=100),
        existing_nullable=False,
    )

    # --- tenders ---
    op.alter_column(
        "tenders",
        "source_record_id",
        existing_type=sa.String(length=500),
        type_=sa.String(length=255),
        existing_nullable=True,
    )
    op.alter_column(
        "tenders",
        "ocds_id",
        existing_type=sa.String(length=500),
        type_=sa.String(length=255),
        existing_nullable=True,
    )
    op.alter_column(
        "tenders",
        "pe_type",
        existing_type=sa.String(length=255),
        type_=sa.String(length=100),
        existing_nullable=True,
    )
    op.alter_column(
        "tenders",
        "procurement_category",
        existing_type=sa.String(length=255),
        type_=sa.String(length=100),
        existing_nullable=True,
    )
    op.alter_column(
        "tenders",
        "procurement_method",
        existing_type=sa.String(length=255),
        type_=sa.String(length=100),
        existing_nullable=True,
    )
    op.alter_column(
        "tenders",
        "category",
        existing_type=sa.String(length=255),
        type_=sa.String(length=100),
        existing_nullable=True,
    )
    op.alter_column(
        "tenders",
        "reference_number",
        existing_type=sa.String(length=255),
        type_=sa.String(length=100),
        existing_nullable=False,
    )

    # --- companies ---
    op.alter_column(
        "companies",
        "postal_code",
        existing_type=sa.Text(),
        type_=sa.String(length=20),
        existing_nullable=True,
    )
    op.alter_column(
        "companies",
        "source_record_id",
        existing_type=sa.String(length=500),
        type_=sa.String(length=100),
        existing_nullable=True,
    )
    op.alter_column(
        "companies",
        "registration_number",
        existing_type=sa.String(length=255),
        type_=sa.String(length=50),
        existing_nullable=False,
    )
