"""M3: Investigation workflow hardening

Revision ID: b5c6d7e8f9a0
Revises: a1b2c3d4e5f6
Create Date: 2026-02-22

Adds:
- case_events table (immutable timeline)
- case_evidence_links table (evidence references)
- case_notifications table (notification hooks)
- cases.decision_type, cases.finding, cases.closed_at columns
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b5c6d7e8f9a0"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns to cases table
    op.add_column(
        "cases",
        sa.Column("decision_type", sa.String(30), nullable=True),
    )
    op.add_column(
        "cases",
        sa.Column("finding", sa.Text(), nullable=True),
    )
    op.add_column(
        "cases",
        sa.Column("closed_at", sa.DateTime(), nullable=True),
    )

    # Add check constraint for decision_type
    op.create_check_constraint(
        "ck_case_decision_type",
        "cases",
        "decision_type IS NULL OR decision_type IN ('SUBSTANTIATED', 'UNSUBSTANTIATED', 'REFERRED', 'INCONCLUSIVE')",
    )

    # Create case_events table
    op.create_table(
        "case_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column(
            "actor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=False,
        ),
        sa.Column("old_value", sa.String(255), nullable=True),
        sa.Column("new_value", sa.String(255), nullable=True),
        sa.Column("event_metadata", postgresql.JSON(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "event_type IN ('CASE_OPENED', 'STATUS_CHANGE', 'ASSIGNMENT', 'NOTE_ADDED', 'PRIORITY_CHANGE', 'DECISION_RECORDED', 'EVIDENCE_LINKED', 'EVIDENCE_UNLINKED')",
            name="ck_event_type",
        ),
    )
    op.create_index("ix_events_case", "case_events", ["case_id"])
    op.create_index("ix_events_created", "case_events", ["created_at"])

    # Create case_evidence_links table
    op.create_table(
        "case_evidence_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("evidence_type", sa.String(30), nullable=False),
        sa.Column("reference_id", sa.String(255), nullable=False),
        sa.Column("label", sa.String(500), nullable=False),
        sa.Column("link_metadata", postgresql.JSON(), nullable=True),
        sa.Column(
            "added_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "evidence_type IN ('TENDER', 'RISK_FACTOR', 'GRAPH_PATH', 'DOCUMENT')",
            name="ck_evidence_type",
        ),
    )
    op.create_index("ix_evidence_case", "case_evidence_links", ["case_id"])
    op.create_index("ix_evidence_type", "case_evidence_links", ["evidence_type"])

    # Create case_notifications table
    op.create_table(
        "case_notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("message", sa.String(500), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_notifications_user", "case_notifications", ["user_id"])
    op.create_index(
        "ix_notifications_unread", "case_notifications", ["user_id", "is_read"]
    )


def downgrade() -> None:
    # Drop case_notifications
    op.drop_index("ix_notifications_unread", table_name="case_notifications")
    op.drop_index("ix_notifications_user", table_name="case_notifications")
    op.drop_table("case_notifications")

    # Drop case_evidence_links
    op.drop_index("ix_evidence_type", table_name="case_evidence_links")
    op.drop_index("ix_evidence_case", table_name="case_evidence_links")
    op.drop_table("case_evidence_links")

    # Drop case_events
    op.drop_index("ix_events_created", table_name="case_events")
    op.drop_index("ix_events_case", table_name="case_events")
    op.drop_table("case_events")

    # Drop cases columns
    op.drop_constraint("ck_case_decision_type", "cases", type_="check")
    op.drop_column("cases", "closed_at")
    op.drop_column("cases", "finding")
    op.drop_column("cases", "decision_type")
