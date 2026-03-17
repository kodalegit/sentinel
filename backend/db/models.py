"""
SQLAlchemy ORM models for Sentinel.
Maps the procurement domain to PostgreSQL tables.
"""

import uuid
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import (
    String,
    Text,
    Integer,
    Float,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    Index,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from db.config import Base


def gen_uuid():
    return uuid.uuid4()


# --- User & Authentication ---


class UserDB(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=gen_uuid
    )
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="auditor")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )

    __table_args__ = (
        CheckConstraint(
            "role IN ('auditor', 'supervisor', 'admin', 'system')",
            name="ck_user_role",
        ),
        Index("ix_users_username", "username"),
        Index("ix_users_email", "email"),
    )


# --- Core Entities ---


class CompanyDB(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=gen_uuid
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    registration_number: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False
    )
    registration_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    # Kenya-specific fields
    supplier_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    brs_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    egp_registration_number: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )
    contact_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    physical_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    postal_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    postal_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Provenance
    source_system: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    source_record_id: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    ingested_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    data_quality_flags: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    directors: Mapped[list["DirectorDB"]] = relationship(
        secondary="company_directors", back_populates="companies"
    )
    bids: Mapped[list["BidDB"]] = relationship(back_populates="company")
    won_tenders: Mapped[list["TenderDB"]] = relationship(
        back_populates="winning_company"
    )
    ownership_records: Mapped[list["OwnershipDB"]] = relationship(
        back_populates="company"
    )
    contracts: Mapped[list["ContractDB"]] = relationship(back_populates="supplier")


class DirectorDB(Base):
    __tablename__ = "directors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=gen_uuid
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    national_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    companies: Mapped[list["CompanyDB"]] = relationship(
        secondary="company_directors", back_populates="directors"
    )


class CompanyDirectorDB(Base):
    __tablename__ = "company_directors"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        primary_key=True,
    )
    director_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("directors.id", ondelete="CASCADE"),
        primary_key=True,
    )


class OfficialDB(Base):
    __tablename__ = "officials"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=gen_uuid
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    department: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    related_persons: Mapped[list["OfficialRelationshipDB"]] = relationship(
        back_populates="official"
    )
    tenders: Mapped[list["TenderDB"]] = relationship(
        back_populates="procurement_officer"
    )


class OfficialRelationshipDB(Base):
    __tablename__ = "official_relationships"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=gen_uuid
    )
    official_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("officials.id", ondelete="CASCADE"),
        nullable=False,
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("directors.id", ondelete="CASCADE"),
        nullable=False,
    )
    relationship_type: Mapped[str] = mapped_column(String(50), nullable=False)

    official: Mapped["OfficialDB"] = relationship(back_populates="related_persons")
    director: Mapped["DirectorDB"] = relationship()

    __table_args__ = (
        UniqueConstraint("official_id", "person_id", name="uq_official_person"),
    )


class TenderDB(Base):
    __tablename__ = "tenders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=gen_uuid
    )
    reference_number: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    procuring_entity: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    estimated_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    awarded_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    published_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    deadline: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="OPEN")
    awarded_to: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True
    )
    procurement_officer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("officials.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )

    # Kenya-specific fields
    procurement_method: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    procurement_category: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    pe_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="KES")
    ocds_id: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    buyer_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Provenance
    source_system: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    source_record_id: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    ingested_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    data_quality_flags: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    winning_company: Mapped[Optional["CompanyDB"]] = relationship(
        back_populates="won_tenders"
    )
    procurement_officer: Mapped[Optional["OfficialDB"]] = relationship(
        back_populates="tenders"
    )
    bids: Mapped[list["BidDB"]] = relationship(back_populates="tender")
    risk_assessments: Mapped[list["RiskAssessmentDB"]] = relationship(
        back_populates="tender"
    )
    contracts: Mapped[list["ContractDB"]] = relationship(back_populates="tender")

    __table_args__ = (
        Index("ix_tenders_status", "status"),
        Index("ix_tenders_category", "category"),
        Index("ix_tenders_source", "source_system"),
    )


class BidDB(Base):
    __tablename__ = "bids"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=gen_uuid
    )
    tender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenders.id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    submission_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    technical_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    tender: Mapped["TenderDB"] = relationship(back_populates="bids")
    company: Mapped["CompanyDB"] = relationship(back_populates="bids")

    __table_args__ = (
        UniqueConstraint("tender_id", "company_id", name="uq_bid_tender_company"),
        Index("ix_bids_tender", "tender_id"),
    )


# --- Risk Assessment ---


class RiskAssessmentDB(Base):
    __tablename__ = "risk_assessments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=gen_uuid
    )
    analysis_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysis_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    tender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenders.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    overall_score: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str] = mapped_column(String(10), nullable=False)
    rule_factors: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ml_anomaly_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ml_feature_importance: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    recommendation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    model_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    assessed_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    analysis_run: Mapped["AnalysisRunDB"] = relationship(
        back_populates="risk_assessments"
    )
    tender: Mapped["TenderDB"] = relationship(back_populates="risk_assessments")

    __table_args__ = (
        CheckConstraint(
            "overall_score >= 0 AND overall_score <= 100", name="ck_score_range"
        ),
        Index("ix_risk_tender", "tender_id"),
        Index("ix_risk_analysis_run", "analysis_run_id"),
    )


class AnalysisRunDB(Base):
    __tablename__ = "analysis_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=gen_uuid
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    graph_source: Mapped[str] = mapped_column(String(20), nullable=False)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    tender_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    company_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    node_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    edge_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    community_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    run_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    communities: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    risk_assessments: Mapped[list["RiskAssessmentDB"]] = relationship(
        back_populates="analysis_run", cascade="all, delete-orphan"
    )
    company_graph_features: Mapped[list["CompanyGraphFeatureDB"]] = relationship(
        back_populates="analysis_run", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_analysis_runs_created_at", "created_at"),)


class CompanyGraphFeatureDB(Base):
    __tablename__ = "company_graph_features"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=gen_uuid
    )
    analysis_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysis_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    graph_degree: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    suspicious_edges: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    official_distance: Mapped[int] = mapped_column(Integer, nullable=False, default=99)
    community_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    analysis_run: Mapped["AnalysisRunDB"] = relationship(
        back_populates="company_graph_features"
    )

    __table_args__ = (
        UniqueConstraint(
            "analysis_run_id",
            "company_id",
            name="uq_company_graph_features_run_company",
        ),
        Index("ix_company_graph_features_run", "analysis_run_id"),
        Index("ix_company_graph_features_company", "company_id"),
    )


# --- Audit Trail ---

# --- Case Management ---


class CaseDB(Base):
    __tablename__ = "cases"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=gen_uuid
    )
    tender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenders.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="OPEN")
    priority: Mapped[str] = mapped_column(String(10), nullable=False, default="MEDIUM")
    assigned_to_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    decision: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Structured decision fields (M3)
    decision_type: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    finding: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )

    tender: Mapped["TenderDB"] = relationship()
    notes: Mapped[list["CaseNoteDB"]] = relationship(
        back_populates="case", order_by="CaseNoteDB.created_at.desc()"
    )
    events: Mapped[list["CaseEventDB"]] = relationship(
        back_populates="case", order_by="CaseEventDB.created_at.asc()"
    )
    evidence_links: Mapped[list["CaseEvidenceLinkDB"]] = relationship(
        back_populates="case", order_by="CaseEvidenceLinkDB.created_at.desc()"
    )
    notifications: Mapped[list["CaseNotificationDB"]] = relationship(
        back_populates="case"
    )
    assigned_to: Mapped[Optional["UserDB"]] = relationship(
        foreign_keys=[assigned_to_id]
    )
    created_by: Mapped["UserDB"] = relationship(foreign_keys=[created_by_id])

    __table_args__ = (
        CheckConstraint(
            "status IN ('OPEN', 'INVESTIGATING', 'ESCALATED', 'RESOLVED', 'DISMISSED')",
            name="ck_case_status",
        ),
        CheckConstraint(
            "priority IN ('HIGH', 'MEDIUM', 'LOW')",
            name="ck_case_priority",
        ),
        CheckConstraint(
            "decision_type IS NULL OR decision_type IN ('SUBSTANTIATED', 'UNSUBSTANTIATED', 'REFERRED', 'INCONCLUSIVE')",
            name="ck_case_decision_type",
        ),
        Index("ix_cases_status", "status"),
        Index("ix_cases_tender", "tender_id"),
        Index("ix_cases_assigned", "assigned_to_id"),
    )


class CaseNoteDB(Base):
    __tablename__ = "case_notes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=gen_uuid
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    note_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="OBSERVATION"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    case: Mapped["CaseDB"] = relationship(back_populates="notes")
    author: Mapped["UserDB"] = relationship()

    __table_args__ = (
        CheckConstraint(
            "note_type IN ('OBSERVATION', 'EVIDENCE', 'DECISION', 'ACTION')",
            name="ck_note_type",
        ),
        Index("ix_notes_case", "case_id"),
        Index("ix_notes_author", "author_id"),
    )


class CaseEventDB(Base):
    """Immutable event log for case timeline (M3)."""

    __tablename__ = "case_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=gen_uuid
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )
    old_value: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    new_value: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    event_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    case: Mapped["CaseDB"] = relationship(back_populates="events")
    actor: Mapped["UserDB"] = relationship()

    __table_args__ = (
        CheckConstraint(
            "event_type IN ('CASE_OPENED', 'STATUS_CHANGE', 'ASSIGNMENT', 'NOTE_ADDED', 'PRIORITY_CHANGE', 'DECISION_RECORDED', 'EVIDENCE_LINKED', 'EVIDENCE_UNLINKED')",
            name="ck_event_type",
        ),
        Index("ix_events_case", "case_id"),
        Index("ix_events_created", "created_at"),
    )


class CaseEvidenceLinkDB(Base):
    """Links cases to evidence items (M3). Becomes LLM context envelope in M5."""

    __tablename__ = "case_evidence_links"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=gen_uuid
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    evidence_type: Mapped[str] = mapped_column(String(30), nullable=False)
    reference_id: Mapped[str] = mapped_column(String(255), nullable=False)
    label: Mapped[str] = mapped_column(String(500), nullable=False)
    link_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    added_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    case: Mapped["CaseDB"] = relationship(back_populates="evidence_links")
    added_by: Mapped["UserDB"] = relationship()

    __table_args__ = (
        CheckConstraint(
            "evidence_type IN ('TENDER', 'RISK_FACTOR', 'GRAPH_PATH', 'DOCUMENT')",
            name="ck_evidence_type",
        ),
        Index("ix_evidence_case", "case_id"),
        Index("ix_evidence_type", "evidence_type"),
    )


class CaseNotificationDB(Base):
    """Notification hooks for case events (M3 placeholder)."""

    __tablename__ = "case_notifications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=gen_uuid
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    user: Mapped["UserDB"] = relationship()
    case: Mapped["CaseDB"] = relationship(back_populates="notifications")

    __table_args__ = (
        Index("ix_notifications_user", "user_id"),
        Index("ix_notifications_unread", "user_id", "is_read"),
    )


class ContractDB(Base):
    __tablename__ = "contracts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=gen_uuid
    )
    tender_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenders.id", ondelete="SET NULL"), nullable=True
    )
    company_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="SET NULL"),
        nullable=True,
    )
    contract_number: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False
    )
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    contract_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="KES")
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    effective_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    date_signed: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    procurement_method: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    procurement_category: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )

    # AGPO fields
    agpo_group: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    reservation_group: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_agpo_reserved: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    # Procuring entity details
    pe_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    pe_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Provenance
    source_system: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    source_record_id: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    ingested_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    data_quality_flags: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    tender: Mapped[Optional["TenderDB"]] = relationship(back_populates="contracts")
    supplier: Mapped[Optional["CompanyDB"]] = relationship(back_populates="contracts")

    __table_args__ = (
        Index("ix_contracts_tender", "tender_id"),
        Index("ix_contracts_company", "company_id"),
        Index("ix_contracts_source", "source_system"),
    )


class OwnershipDB(Base):
    __tablename__ = "ownership_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=gen_uuid
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    owner_name: Mapped[str] = mapped_column(String(255), nullable=False)
    nationality: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    postal_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    company: Mapped["CompanyDB"] = relationship(back_populates="ownership_records")

    __table_args__ = (
        Index("ix_ownership_company", "company_id"),
        Index("ix_ownership_name", "owner_name"),
    )


class AuditLogDB(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=gen_uuid
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    __table_args__ = (
        Index("ix_audit_entity", "entity_type", "entity_id"),
        Index("ix_audit_created", "created_at"),
    )


# =============================================================================
# M5: Knowledge Base, Chat, and Agent Settings
# =============================================================================


class KnowledgeDocumentDB(Base):
    """Stores metadata for uploaded legal documents (PPADA, case law, etc.)."""

    __tablename__ = "knowledge_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=gen_uuid
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    file_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    uploaded_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    uploaded_by: Mapped[Optional["UserDB"]] = relationship()
    chunks: Mapped[list["KnowledgeChunkDB"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class KnowledgeChunkDB(Base):
    """Chunked text from documents with vector embeddings for similarity search."""

    __tablename__ = "knowledge_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=gen_uuid
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    chunk_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    document: Mapped["KnowledgeDocumentDB"] = relationship(back_populates="chunks")

    __table_args__ = (Index("ix_knowledge_chunks_document", "document_id"),)


class ChatThreadDB(Base):
    """Conversation thread scoped to a case and user."""

    __tablename__ = "chat_threads"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=gen_uuid
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    case: Mapped["CaseDB"] = relationship()
    user: Mapped["UserDB"] = relationship()
    messages: Mapped[list["ChatMessageDB"]] = relationship(
        back_populates="thread", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_chat_threads_case_user", "case_id", "user_id"),)


class ChatMessageDB(Base):
    """Individual message within a chat thread."""

    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=gen_uuid
    )
    thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_threads.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    events: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    thread: Mapped["ChatThreadDB"] = relationship(back_populates="messages")

    __table_args__ = (Index("ix_chat_messages_thread", "thread_id"),)


class AgentSettingDB(Base):
    """Key-value store for agent configuration (LLM provider, model, etc.)."""

    __tablename__ = "agent_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=gen_uuid
    )
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    updated_by: Mapped[Optional["UserDB"]] = relationship()
