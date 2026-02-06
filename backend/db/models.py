"""
SQLAlchemy ORM models for Sentinel.
Maps the procurement domain to PostgreSQL tables.
"""

import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    String, Text, Integer, Float, Boolean, Date, DateTime,
    ForeignKey, UniqueConstraint, CheckConstraint, Index, JSON
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from db.config import Base


def gen_uuid():
    return uuid.uuid4()


# --- Core Entities ---

class CompanyDB(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    registration_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    registration_date: Mapped[date] = mapped_column(Date, nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    directors: Mapped[list["DirectorDB"]] = relationship(
        secondary="company_directors", back_populates="companies"
    )
    bids: Mapped[list["BidDB"]] = relationship(back_populates="company")
    won_tenders: Mapped[list["TenderDB"]] = relationship(back_populates="winning_company")


class DirectorDB(Base):
    __tablename__ = "directors"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    national_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    companies: Mapped[list["CompanyDB"]] = relationship(
        secondary="company_directors", back_populates="directors"
    )


class CompanyDirectorDB(Base):
    __tablename__ = "company_directors"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True
    )
    director_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("directors.id", ondelete="CASCADE"), primary_key=True
    )


class OfficialDB(Base):
    __tablename__ = "officials"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    department: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    related_persons: Mapped[list["OfficialRelationshipDB"]] = relationship(back_populates="official")
    tenders: Mapped[list["TenderDB"]] = relationship(back_populates="procurement_officer")


class OfficialRelationshipDB(Base):
    __tablename__ = "official_relationships"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    official_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("officials.id", ondelete="CASCADE"), nullable=False
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("directors.id", ondelete="CASCADE"), nullable=False
    )
    relationship_type: Mapped[str] = mapped_column(String(50), nullable=False)

    official: Mapped["OfficialDB"] = relationship(back_populates="related_persons")
    director: Mapped["DirectorDB"] = relationship()

    __table_args__ = (
        UniqueConstraint("official_id", "person_id", name="uq_official_person"),
    )


class TenderDB(Base):
    __tablename__ = "tenders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    reference_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    procuring_entity: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    estimated_value: Mapped[float] = mapped_column(Float, nullable=False)
    awarded_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    published_date: Mapped[date] = mapped_column(Date, nullable=False)
    deadline: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="OPEN")
    awarded_to: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True
    )
    procurement_officer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("officials.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    winning_company: Mapped[Optional["CompanyDB"]] = relationship(back_populates="won_tenders")
    procurement_officer: Mapped[Optional["OfficialDB"]] = relationship(back_populates="tenders")
    bids: Mapped[list["BidDB"]] = relationship(back_populates="tender")
    risk_assessments: Mapped[list["RiskAssessmentDB"]] = relationship(back_populates="tender")

    __table_args__ = (
        CheckConstraint("estimated_value >= 0", name="ck_positive_estimated_value"),
        Index("ix_tenders_status", "status"),
        Index("ix_tenders_category", "category"),
    )


class BidDB(Base):
    __tablename__ = "bids"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    tender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenders.id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    submission_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    technical_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    tender: Mapped["TenderDB"] = relationship(back_populates="bids")
    company: Mapped["CompanyDB"] = relationship(back_populates="bids")

    __table_args__ = (
        UniqueConstraint("tender_id", "company_id", name="uq_bid_tender_company"),
        Index("ix_bids_tender", "tender_id"),
    )


# --- Risk Assessment ---

class RiskAssessmentDB(Base):
    __tablename__ = "risk_assessments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
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
    assessed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    tender: Mapped["TenderDB"] = relationship(back_populates="risk_assessments")

    __table_args__ = (
        CheckConstraint("overall_score >= 0 AND overall_score <= 100", name="ck_score_range"),
        Index("ix_risk_tender", "tender_id"),
    )


# --- Audit Trail ---

class AuditLogDB(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_audit_entity", "entity_type", "entity_id"),
        Index("ix_audit_created", "created_at"),
    )
