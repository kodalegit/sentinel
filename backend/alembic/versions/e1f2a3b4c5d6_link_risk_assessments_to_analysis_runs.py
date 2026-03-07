"""link risk assessments to analysis runs

Revision ID: e1f2a3b4c5d6
Revises: d8e9f0a1b2c3
Create Date: 2026-03-07 22:42:00.000000

"""

import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, Sequence[str], None] = "d8e9f0a1b2c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "risk_assessments",
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    conn = op.get_bind()
    existing_count = (
        conn.execute(sa.text("SELECT COUNT(*) FROM risk_assessments")).scalar() or 0
    )

    if existing_count:
        legacy_run_id = conn.execute(sa.text("SELECT gen_random_uuid()")).scalar_one()
        conn.execute(
            sa.text(
                """
                INSERT INTO analysis_runs (
                    id,
                    status,
                    graph_source,
                    model_version,
                    tender_count,
                    company_count,
                    node_count,
                    edge_count,
                    community_count,
                    run_metadata,
                    communities,
                    created_at
                )
                VALUES (
                    :id,
                    'COMPLETED',
                    'legacy',
                    'legacy-backfill',
                    0,
                    0,
                    0,
                    0,
                    0,
                    CAST(:run_metadata AS JSON),
                    CAST(:communities AS JSON),
                    NOW()
                )
                """
            ),
            {
                "id": legacy_run_id,
                "run_metadata": json.dumps({"backfilled": True}),
                "communities": json.dumps([]),
            },
        )
        conn.execute(
            sa.text(
                """
                UPDATE risk_assessments
                SET analysis_run_id = :analysis_run_id
                WHERE analysis_run_id IS NULL
                """
            ),
            {"analysis_run_id": legacy_run_id},
        )

    op.alter_column("risk_assessments", "analysis_run_id", nullable=False)
    op.create_foreign_key(
        "fk_risk_assessments_analysis_run_id",
        "risk_assessments",
        "analysis_runs",
        ["analysis_run_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_risk_analysis_run",
        "risk_assessments",
        ["analysis_run_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_risk_analysis_run", table_name="risk_assessments")
    op.drop_constraint(
        "fk_risk_assessments_analysis_run_id",
        "risk_assessments",
        type_="foreignkey",
    )
    op.drop_column("risk_assessments", "analysis_run_id")
