"""analysis snapshots and materialized graph features

Revision ID: d8e9f0a1b2c3
Revises: 2ede69cbac21
Create Date: 2026-03-07 22:25:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "d8e9f0a1b2c3"
down_revision: Union[str, Sequence[str], None] = "2ede69cbac21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "analysis_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("graph_source", sa.String(20), nullable=False),
        sa.Column("model_version", sa.String(50), nullable=False),
        sa.Column("tender_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("company_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("node_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("edge_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("community_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("run_metadata", sa.JSON(), nullable=True),
        sa.Column("communities", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_analysis_runs_created_at", "analysis_runs", ["created_at"])

    op.create_table(
        "company_graph_features",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "analysis_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analysis_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("graph_degree", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("suspicious_edges", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("official_distance", sa.Integer(), nullable=False, server_default="99"),
        sa.Column("community_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint(
            "analysis_run_id",
            "company_id",
            name="uq_company_graph_features_run_company",
        ),
    )
    op.create_index(
        "ix_company_graph_features_run",
        "company_graph_features",
        ["analysis_run_id"],
    )
    op.create_index(
        "ix_company_graph_features_company",
        "company_graph_features",
        ["company_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_company_graph_features_company", table_name="company_graph_features")
    op.drop_index("ix_company_graph_features_run", table_name="company_graph_features")
    op.drop_table("company_graph_features")
    op.drop_index("ix_analysis_runs_created_at", table_name="analysis_runs")
    op.drop_table("analysis_runs")
