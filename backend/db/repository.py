"""
Database repository layer for Sentinel.
Provides async CRUD operations for all entities.
"""

import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import (
    CompanyDB, DirectorDB, OfficialDB, OfficialRelationshipDB,
    TenderDB, BidDB, RiskAssessmentDB, CompanyDirectorDB, AuditLogDB,
)


# --- Company ---

async def get_companies(db: AsyncSession) -> list[CompanyDB]:
    result = await db.execute(
        select(CompanyDB).options(selectinload(CompanyDB.directors))
    )
    return list(result.scalars().all())


async def get_company(db: AsyncSession, company_id: uuid.UUID) -> CompanyDB | None:
    result = await db.execute(
        select(CompanyDB)
        .options(selectinload(CompanyDB.directors))
        .where(CompanyDB.id == company_id)
    )
    return result.scalar_one_or_none()


# --- Director ---

async def get_directors(db: AsyncSession) -> list[DirectorDB]:
    result = await db.execute(
        select(DirectorDB).options(selectinload(DirectorDB.companies))
    )
    return list(result.scalars().all())


# --- Official ---

async def get_officials(db: AsyncSession) -> list[OfficialDB]:
    result = await db.execute(
        select(OfficialDB).options(selectinload(OfficialDB.related_persons))
    )
    return list(result.scalars().all())


# --- Tender ---

async def get_tenders(
    db: AsyncSession,
    status: Optional[str] = None,
    category: Optional[str] = None,
) -> list[TenderDB]:
    query = select(TenderDB).options(
        selectinload(TenderDB.bids),
        selectinload(TenderDB.winning_company),
        selectinload(TenderDB.procurement_officer),
    )
    if status:
        query = query.where(TenderDB.status == status)
    if category:
        query = query.where(TenderDB.category == category)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_tender(db: AsyncSession, tender_id: uuid.UUID) -> TenderDB | None:
    result = await db.execute(
        select(TenderDB)
        .options(
            selectinload(TenderDB.bids).selectinload(BidDB.company),
            selectinload(TenderDB.winning_company).selectinload(CompanyDB.directors),
            selectinload(TenderDB.procurement_officer).selectinload(OfficialDB.related_persons),
            selectinload(TenderDB.risk_assessments),
        )
        .where(TenderDB.id == tender_id)
    )
    return result.scalar_one_or_none()


# --- Bid ---

async def get_bids(db: AsyncSession, tender_id: Optional[uuid.UUID] = None) -> list[BidDB]:
    query = select(BidDB)
    if tender_id:
        query = query.where(BidDB.tender_id == tender_id)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_all_bids(db: AsyncSession) -> list[BidDB]:
    result = await db.execute(select(BidDB))
    return list(result.scalars().all())


# --- Risk Assessment ---

async def get_latest_risk_assessment(
    db: AsyncSession, tender_id: uuid.UUID
) -> RiskAssessmentDB | None:
    result = await db.execute(
        select(RiskAssessmentDB)
        .where(RiskAssessmentDB.tender_id == tender_id)
        .order_by(RiskAssessmentDB.version.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_all_latest_risk_assessments(db: AsyncSession) -> list[RiskAssessmentDB]:
    """Get the latest risk assessment for each tender."""
    # Subquery: max version per tender
    subq = (
        select(
            RiskAssessmentDB.tender_id,
            func.max(RiskAssessmentDB.version).label("max_version"),
        )
        .group_by(RiskAssessmentDB.tender_id)
        .subquery()
    )
    result = await db.execute(
        select(RiskAssessmentDB).join(
            subq,
            (RiskAssessmentDB.tender_id == subq.c.tender_id)
            & (RiskAssessmentDB.version == subq.c.max_version),
        )
    )
    return list(result.scalars().all())


async def upsert_risk_assessment(
    db: AsyncSession,
    tender_id: uuid.UUID,
    overall_score: int,
    category: str,
    rule_factors: list[dict],
    recommendation: str | None = None,
    ml_anomaly_score: float | None = None,
    ml_feature_importance: dict | None = None,
    model_version: str | None = None,
) -> RiskAssessmentDB:
    """Create or update (new version) a risk assessment for a tender."""
    existing = await get_latest_risk_assessment(db, tender_id)
    new_version = (existing.version + 1) if existing else 1

    assessment = RiskAssessmentDB(
        tender_id=tender_id,
        version=new_version,
        overall_score=overall_score,
        category=category,
        rule_factors=rule_factors,
        ml_anomaly_score=ml_anomaly_score,
        ml_feature_importance=ml_feature_importance,
        recommendation=recommendation,
        model_version=model_version,
    )
    db.add(assessment)
    await db.flush()
    return assessment


# --- Dashboard Stats ---

async def get_dashboard_stats(db: AsyncSession) -> dict:
    """Compute dashboard statistics from the database."""
    tender_count = await db.execute(select(func.count(TenderDB.id)))
    total = tender_count.scalar_one()

    total_value_result = await db.execute(
        select(func.coalesce(func.sum(TenderDB.estimated_value), 0))
    )
    total_value = total_value_result.scalar_one()

    pending_result = await db.execute(
        select(func.count(TenderDB.id)).where(
            TenderDB.status.in_(["OPEN", "EVALUATION"])
        )
    )
    pending = pending_result.scalar_one()

    # Risk counts from latest assessments
    assessments = await get_all_latest_risk_assessments(db)
    high = sum(1 for a in assessments if a.category == "HIGH")
    medium = sum(1 for a in assessments if a.category == "MEDIUM")
    low = sum(1 for a in assessments if a.category == "LOW")

    return {
        "total_tenders": total,
        "high_risk_count": high,
        "medium_risk_count": medium,
        "low_risk_count": low,
        "pending_review": pending,
        "total_value": float(total_value),
        "flagged_today": high,
    }


# --- Audit Log ---

async def create_audit_log(
    db: AsyncSession,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    details: dict | None = None,
) -> AuditLogDB:
    log = AuditLogDB(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
    )
    db.add(log)
    await db.flush()
    return log
