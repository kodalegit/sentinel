"""
Database repository layer for Sentinel.
Provides async CRUD operations for all entities.
"""

import uuid
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import select, func, insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import (
    CompanyDB,
    DirectorDB,
    OfficialDB,
    OfficialRelationshipDB,
    TenderDB,
    BidDB,
    RiskAssessmentDB,
    CompanyDirectorDB,
    AuditLogDB,
    AnalysisRunDB,
    CompanyGraphFeatureDB,
    CaseDB,
    CaseNoteDB,
    CaseEventDB,
    CaseEvidenceLinkDB,
    CaseNotificationDB,
    UserDB,
    KnowledgeDocumentDB,
    KnowledgeChunkDB,
    ChatThreadDB,
    ChatMessageDB,
    AgentSettingDB,
)

_UNSET = object()
_BULK_INSERT_BATCH_SIZE = 1000


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
            selectinload(TenderDB.procurement_officer).selectinload(
                OfficialDB.related_persons
            ),
            selectinload(TenderDB.risk_assessments),
        )
        .where(TenderDB.id == tender_id)
    )
    return result.scalar_one_or_none()


# --- Bid ---


async def get_bids(
    db: AsyncSession, tender_id: Optional[uuid.UUID] = None
) -> list[BidDB]:
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
    db: AsyncSession,
    tender_id: uuid.UUID,
    analysis_run_id: uuid.UUID | None = None,
) -> RiskAssessmentDB | None:
    query = select(RiskAssessmentDB).where(RiskAssessmentDB.tender_id == tender_id)
    if analysis_run_id is not None:
        query = query.where(RiskAssessmentDB.analysis_run_id == analysis_run_id)
    result = await db.execute(query.order_by(RiskAssessmentDB.version.desc()).limit(1))
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


async def get_risk_assessments_for_run(
    db: AsyncSession,
    analysis_run_id: uuid.UUID,
) -> list[RiskAssessmentDB]:
    result = await db.execute(
        select(RiskAssessmentDB).where(
            RiskAssessmentDB.analysis_run_id == analysis_run_id
        )
    )
    return list(result.scalars().all())


async def upsert_risk_assessment(
    db: AsyncSession,
    analysis_run_id: uuid.UUID,
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
        analysis_run_id=analysis_run_id,
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


# --- Analysis Run ---


async def get_latest_analysis_run(db: AsyncSession) -> AnalysisRunDB | None:
    result = await db.execute(
        select(AnalysisRunDB).order_by(AnalysisRunDB.created_at.desc()).limit(1)
    )
    return result.scalar_one_or_none()


async def create_analysis_run(
    db: AsyncSession,
    *,
    status: str,
    graph_source: str,
    model_version: str,
    tender_count: int,
    company_count: int,
    node_count: int,
    edge_count: int,
    community_count: int,
    run_metadata: dict | None = None,
    communities: list | None = None,
) -> AnalysisRunDB:
    analysis_run = AnalysisRunDB(
        status=status,
        graph_source=graph_source,
        model_version=model_version,
        tender_count=tender_count,
        company_count=company_count,
        node_count=node_count,
        edge_count=edge_count,
        community_count=community_count,
        run_metadata=run_metadata,
        communities=communities,
    )
    db.add(analysis_run)
    await db.flush()
    return analysis_run


# --- Company Graph Features ---


async def create_company_graph_features(
    db: AsyncSession,
    *,
    analysis_run_id: uuid.UUID,
    company_features: dict[str, dict[str, int]],
) -> None:
    if not company_features:
        return

    created_at = datetime.now(timezone.utc).replace(tzinfo=None)
    rows = [
        {
            "id": uuid.uuid4(),
            "analysis_run_id": analysis_run_id,
            "company_id": uuid.UUID(company_id),
            "graph_degree": feature_values.get("graph_degree", 0),
            "suspicious_edges": feature_values.get("suspicious_edges", 0),
            "official_distance": feature_values.get("official_distance", 99),
            "community_size": feature_values.get("community_size", 0),
            "created_at": created_at,
        }
        for company_id, feature_values in company_features.items()
    ]
    for start in range(0, len(rows), _BULK_INSERT_BATCH_SIZE):
        await db.execute(
            insert(CompanyGraphFeatureDB),
            rows[start : start + _BULK_INSERT_BATCH_SIZE],
        )
    await db.flush()


async def create_risk_assessments(
    db: AsyncSession,
    *,
    analysis_run_id: uuid.UUID,
    risk_assessments: list[dict],
) -> None:
    if not risk_assessments:
        return

    tender_ids = [payload["tender_id"] for payload in risk_assessments]
    version_result = await db.execute(
        select(
            RiskAssessmentDB.tender_id,
            func.max(RiskAssessmentDB.version).label("max_version"),
        )
        .where(RiskAssessmentDB.tender_id.in_(tender_ids))
        .group_by(RiskAssessmentDB.tender_id)
    )
    versions_by_tender = {
        tender_id: int(max_version or 0)
        for tender_id, max_version in version_result.all()
    }
    assessed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    rows: list[dict] = []
    for payload in risk_assessments:
        tender_id = payload["tender_id"]
        next_version = versions_by_tender.get(tender_id, 0) + 1
        versions_by_tender[tender_id] = next_version
        rows.append(
            {
                "id": uuid.uuid4(),
                "analysis_run_id": analysis_run_id,
                "tender_id": tender_id,
                "version": next_version,
                "overall_score": payload["overall_score"],
                "category": payload["category"],
                "rule_factors": payload["rule_factors"],
                "recommendation": payload["recommendation"],
                "ml_anomaly_score": payload["ml_anomaly_score"],
                "ml_feature_importance": payload["ml_feature_importance"],
                "model_version": payload["model_version"],
                "assessed_at": assessed_at,
            }
        )

    for start in range(0, len(rows), _BULK_INSERT_BATCH_SIZE):
        await db.execute(
            insert(RiskAssessmentDB),
            rows[start : start + _BULK_INSERT_BATCH_SIZE],
        )
    await db.flush()


async def get_company_graph_features_for_run(
    db: AsyncSession,
    analysis_run_id: uuid.UUID,
) -> list[CompanyGraphFeatureDB]:
    result = await db.execute(
        select(CompanyGraphFeatureDB).where(
            CompanyGraphFeatureDB.analysis_run_id == analysis_run_id
        )
    )
    return list(result.scalars().all())


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
    analysis_run = await get_latest_analysis_run(db)
    if analysis_run is not None:
        assessments = await get_risk_assessments_for_run(db, analysis_run.id)
    else:
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


# --- Case Management ---


async def get_cases(
    db: AsyncSession,
    status: Optional[str] = None,
    priority: Optional[str] = None,
) -> list[CaseDB]:
    query = (
        select(CaseDB)
        .options(
            selectinload(CaseDB.notes).selectinload(CaseNoteDB.author),
            selectinload(CaseDB.tender),
            selectinload(CaseDB.assigned_to),
            selectinload(CaseDB.created_by),
        )
        .order_by(CaseDB.created_at.desc())
    )
    if status:
        query = query.where(CaseDB.status == status)
    if priority:
        query = query.where(CaseDB.priority == priority)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_case(db: AsyncSession, case_id: uuid.UUID) -> CaseDB | None:
    result = await db.execute(
        select(CaseDB)
        .options(
            selectinload(CaseDB.notes).selectinload(CaseNoteDB.author),
            selectinload(CaseDB.tender),
            selectinload(CaseDB.assigned_to),
            selectinload(CaseDB.created_by),
        )
        .where(CaseDB.id == case_id)
    )
    return result.scalar_one_or_none()


async def get_cases_for_tender(db: AsyncSession, tender_id: uuid.UUID) -> list[CaseDB]:
    result = await db.execute(
        select(CaseDB)
        .options(
            selectinload(CaseDB.notes).selectinload(CaseNoteDB.author),
            selectinload(CaseDB.assigned_to),
            selectinload(CaseDB.created_by),
        )
        .where(CaseDB.tender_id == tender_id)
        .order_by(CaseDB.created_at.desc())
    )
    return list(result.scalars().all())


async def get_active_case_for_tender(
    db: AsyncSession, tender_id: uuid.UUID
) -> CaseDB | None:
    result = await db.execute(
        select(CaseDB)
        .options(
            selectinload(CaseDB.notes).selectinload(CaseNoteDB.author),
            selectinload(CaseDB.tender),
            selectinload(CaseDB.assigned_to),
            selectinload(CaseDB.created_by),
        )
        .where(
            CaseDB.tender_id == tender_id,
            CaseDB.status.in_(["OPEN", "INVESTIGATING", "ESCALATED"]),
        )
        .order_by(CaseDB.created_at.desc())
    )
    return result.scalars().first()


async def create_case(
    db: AsyncSession,
    tender_id: uuid.UUID,
    title: str,
    priority: str = "MEDIUM",
    status: str = "OPEN",
    assigned_to_id: uuid.UUID | None = None,
    created_by_id: uuid.UUID = None,
    summary: str | None = None,
) -> CaseDB:
    case = CaseDB(
        tender_id=tender_id,
        title=title,
        status=status,
        priority=priority,
        assigned_to_id=assigned_to_id,
        created_by_id=created_by_id,
        summary=summary,
    )
    db.add(case)
    await db.flush()
    await db.refresh(
        case, attribute_names=["notes", "tender", "assigned_to", "created_by"]
    )
    return case


async def update_case(
    db: AsyncSession,
    case_id: uuid.UUID,
    **kwargs,
) -> CaseDB | None:
    case = await get_case(db, case_id)
    if not case:
        return None
    for key, value in kwargs.items():
        if hasattr(case, key):
            setattr(case, key, value)
    await db.flush()
    await db.refresh(
        case, attribute_names=["notes", "tender", "assigned_to", "created_by"]
    )
    return case


async def add_case_note(
    db: AsyncSession,
    case_id: uuid.UUID,
    content: str,
    author_id: uuid.UUID,
    note_type: str = "OBSERVATION",
) -> CaseNoteDB:
    note = CaseNoteDB(
        case_id=case_id,
        content=content,
        author_id=author_id,
        note_type=note_type,
    )
    db.add(note)
    await db.flush()
    await db.refresh(note, attribute_names=["author"])
    return note


async def get_case_stats(db: AsyncSession) -> dict:
    """Get case management statistics."""
    total = (await db.execute(select(func.count(CaseDB.id)))).scalar_one()
    open_count = (
        await db.execute(select(func.count(CaseDB.id)).where(CaseDB.status == "OPEN"))
    ).scalar_one()
    investigating = (
        await db.execute(
            select(func.count(CaseDB.id)).where(CaseDB.status == "INVESTIGATING")
        )
    ).scalar_one()
    escalated = (
        await db.execute(
            select(func.count(CaseDB.id)).where(CaseDB.status == "ESCALATED")
        )
    ).scalar_one()
    resolved = (
        await db.execute(
            select(func.count(CaseDB.id)).where(CaseDB.status == "RESOLVED")
        )
    ).scalar_one()
    dismissed = (
        await db.execute(
            select(func.count(CaseDB.id)).where(CaseDB.status == "DISMISSED")
        )
    ).scalar_one()

    return {
        "total": total,
        "open": open_count,
        "investigating": investigating,
        "escalated": escalated,
        "resolved": resolved,
        "dismissed": dismissed,
    }


# --- Case Events (M3) ---


async def create_case_event(
    db: AsyncSession,
    case_id: uuid.UUID,
    event_type: str,
    actor_id: uuid.UUID,
    old_value: str | None = None,
    new_value: str | None = None,
    event_metadata: dict | None = None,
) -> CaseEventDB:
    """Create an immutable case event for the timeline."""
    event = CaseEventDB(
        case_id=case_id,
        event_type=event_type,
        actor_id=actor_id,
        old_value=old_value,
        new_value=new_value,
        event_metadata=event_metadata,
    )
    db.add(event)
    await db.flush()
    await db.refresh(event, attribute_names=["actor"])
    return event


async def get_case_events(db: AsyncSession, case_id: uuid.UUID) -> list[CaseEventDB]:
    """Get chronological timeline of case events."""
    result = await db.execute(
        select(CaseEventDB)
        .options(selectinload(CaseEventDB.actor))
        .where(CaseEventDB.case_id == case_id)
        .order_by(CaseEventDB.created_at.asc())
    )
    return list(result.scalars().all())


# --- Case Evidence Links (M3) ---


async def add_case_evidence_link(
    db: AsyncSession,
    case_id: uuid.UUID,
    evidence_type: str,
    reference_id: str,
    label: str,
    added_by_id: uuid.UUID,
    link_metadata: dict | None = None,
) -> CaseEvidenceLinkDB:
    """Link evidence to a case."""
    link = CaseEvidenceLinkDB(
        case_id=case_id,
        evidence_type=evidence_type,
        reference_id=reference_id,
        label=label,
        link_metadata=link_metadata,
        added_by_id=added_by_id,
    )
    db.add(link)
    await db.flush()
    await db.refresh(link, attribute_names=["added_by"])
    return link


async def get_case_evidence_links(
    db: AsyncSession, case_id: uuid.UUID
) -> list[CaseEvidenceLinkDB]:
    """Get all evidence links for a case."""
    result = await db.execute(
        select(CaseEvidenceLinkDB)
        .options(selectinload(CaseEvidenceLinkDB.added_by))
        .where(CaseEvidenceLinkDB.case_id == case_id)
        .order_by(CaseEvidenceLinkDB.created_at.desc())
    )
    return list(result.scalars().all())


async def get_case_evidence_link_by_reference(
    db: AsyncSession,
    case_id: uuid.UUID,
    evidence_type: str,
    reference_id: str,
) -> CaseEvidenceLinkDB | None:
    """Get a case evidence link by case/type/reference tuple."""
    result = await db.execute(
        select(CaseEvidenceLinkDB)
        .options(selectinload(CaseEvidenceLinkDB.added_by))
        .where(
            CaseEvidenceLinkDB.case_id == case_id,
            CaseEvidenceLinkDB.evidence_type == evidence_type,
            CaseEvidenceLinkDB.reference_id == reference_id,
        )
    )
    return result.scalar_one_or_none()


async def get_case_evidence_link(
    db: AsyncSession, link_id: uuid.UUID
) -> CaseEvidenceLinkDB | None:
    """Get a single evidence link by ID."""
    result = await db.execute(
        select(CaseEvidenceLinkDB).where(CaseEvidenceLinkDB.id == link_id)
    )
    return result.scalar_one_or_none()


async def remove_case_evidence_link(db: AsyncSession, link_id: uuid.UUID) -> bool:
    """Remove an evidence link. Returns True if deleted."""
    link = await get_case_evidence_link(db, link_id)
    if not link:
        return False
    await db.delete(link)
    await db.flush()
    return True


# --- Case Notifications (M3) ---


async def create_notification(
    db: AsyncSession,
    user_id: uuid.UUID,
    case_id: uuid.UUID,
    message: str,
) -> CaseNotificationDB:
    """Create a notification for a user."""
    notification = CaseNotificationDB(
        user_id=user_id,
        case_id=case_id,
        message=message,
    )
    db.add(notification)
    await db.flush()
    return notification


async def get_user_notifications(
    db: AsyncSession,
    user_id: uuid.UUID,
    unread_only: bool = False,
    limit: int = 20,
) -> list[CaseNotificationDB]:
    """Get notifications for a user."""
    query = (
        select(CaseNotificationDB)
        .options(selectinload(CaseNotificationDB.case))
        .where(CaseNotificationDB.user_id == user_id)
        .order_by(CaseNotificationDB.created_at.desc())
        .limit(limit)
    )
    if unread_only:
        query = query.where(CaseNotificationDB.is_read == False)
    result = await db.execute(query)
    return list(result.scalars().all())


async def mark_notification_read(
    db: AsyncSession, notification_id: uuid.UUID
) -> CaseNotificationDB | None:
    """Mark a notification as read."""
    result = await db.execute(
        select(CaseNotificationDB).where(CaseNotificationDB.id == notification_id)
    )
    notification = result.scalar_one_or_none()
    if notification:
        notification.is_read = True
        await db.flush()
    return notification


async def get_unread_notification_count(db: AsyncSession, user_id: uuid.UUID) -> int:
    """Get count of unread notifications for a user."""
    result = await db.execute(
        select(func.count(CaseNotificationDB.id)).where(
            CaseNotificationDB.user_id == user_id,
            CaseNotificationDB.is_read == False,
        )
    )
    return result.scalar_one()


# --- Supervisor Workload (M3) ---


async def get_cases_with_filters(
    db: AsyncSession,
    status: str | None = None,
    priority: str | None = None,
    assigned_to_id: uuid.UUID | str | None = None,
) -> list[CaseDB]:
    """Get cases with extended filters including assignee."""
    query = (
        select(CaseDB)
        .options(
            selectinload(CaseDB.notes).selectinload(CaseNoteDB.author),
            selectinload(CaseDB.tender),
            selectinload(CaseDB.assigned_to),
            selectinload(CaseDB.created_by),
        )
        .order_by(CaseDB.created_at.desc())
    )
    if status:
        query = query.where(CaseDB.status == status)
    if priority:
        query = query.where(CaseDB.priority == priority)
    if assigned_to_id == "unassigned":
        query = query.where(CaseDB.assigned_to_id.is_(None))
    elif assigned_to_id:
        query = query.where(CaseDB.assigned_to_id == assigned_to_id)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_supervisor_workload(db: AsyncSession) -> list[dict]:
    """Get case workload per assignee for supervisor dashboard."""
    # Get all active users who can be assigned cases
    users_result = await db.execute(
        select(UserDB).where(
            UserDB.is_active == True,
            UserDB.role.in_(["auditor", "supervisor", "admin"]),
        )
    )
    users = list(users_result.scalars().all())

    workload = []
    for user in users:
        # Count cases by status for this user
        cases_result = await db.execute(
            select(CaseDB.status, func.count(CaseDB.id))
            .where(CaseDB.assigned_to_id == user.id)
            .group_by(CaseDB.status)
        )
        status_counts = {row[0]: row[1] for row in cases_result.fetchall()}

        workload.append(
            {
                "user_id": str(user.id),
                "username": user.username,
                "full_name": user.full_name,
                "role": user.role,
                "open": status_counts.get("OPEN", 0),
                "investigating": status_counts.get("INVESTIGATING", 0),
                "escalated": status_counts.get("ESCALATED", 0),
                "total_active": (
                    status_counts.get("OPEN", 0)
                    + status_counts.get("INVESTIGATING", 0)
                    + status_counts.get("ESCALATED", 0)
                ),
            }
        )

    # Add unassigned count
    unassigned_result = await db.execute(
        select(func.count(CaseDB.id)).where(
            CaseDB.assigned_to_id.is_(None),
            CaseDB.status.in_(["OPEN", "INVESTIGATING", "ESCALATED"]),
        )
    )
    unassigned_count = unassigned_result.scalar_one()

    workload.append(
        {
            "user_id": None,
            "username": "unassigned",
            "full_name": "Unassigned",
            "role": None,
            "open": unassigned_count,
            "investigating": 0,
            "escalated": 0,
            "total_active": unassigned_count,
        }
    )

    return workload


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


# =============================================================================
# M5: Knowledge Base
# =============================================================================


async def get_knowledge_documents(db: AsyncSession) -> list[KnowledgeDocumentDB]:
    """Get all knowledge documents with chunk counts."""
    result = await db.execute(
        select(KnowledgeDocumentDB)
        .options(selectinload(KnowledgeDocumentDB.uploaded_by))
        .order_by(KnowledgeDocumentDB.created_at.desc())
    )
    return list(result.scalars().all())


async def get_knowledge_document(
    db: AsyncSession, document_id: uuid.UUID
) -> KnowledgeDocumentDB | None:
    """Get a single knowledge document by ID."""
    result = await db.execute(
        select(KnowledgeDocumentDB)
        .options(selectinload(KnowledgeDocumentDB.uploaded_by))
        .where(KnowledgeDocumentDB.id == document_id)
    )
    return result.scalar_one_or_none()


async def create_knowledge_document(
    db: AsyncSession,
    title: str,
    category: str,
    uploaded_by_id: uuid.UUID,
    description: str | None = None,
    source_url: str | None = None,
    file_name: str | None = None,
) -> KnowledgeDocumentDB:
    """Create a new knowledge document."""
    doc = KnowledgeDocumentDB(
        title=title,
        description=description,
        category=category,
        source_url=source_url,
        file_name=file_name,
        uploaded_by_id=uploaded_by_id,
    )
    db.add(doc)
    await db.flush()
    return doc


async def update_knowledge_document(
    db: AsyncSession,
    document_id: uuid.UUID,
    *,
    title: str | None | object = _UNSET,
    description: str | None | object = _UNSET,
    category: str | None | object = _UNSET,
    source_url: str | None | object = _UNSET,
) -> KnowledgeDocumentDB | None:
    """Update metadata for a knowledge document without touching its chunks."""
    doc = await db.get(KnowledgeDocumentDB, document_id)
    if not doc:
        return None

    if title is not _UNSET:
        doc.title = title
    if description is not _UNSET:
        doc.description = description
    if category is not _UNSET:
        doc.category = category
    if source_url is not _UNSET:
        doc.source_url = source_url

    await db.flush()
    return doc


async def delete_knowledge_document(db: AsyncSession, document_id: uuid.UUID) -> bool:
    """Delete a knowledge document (chunks cascade delete)."""
    doc = await db.get(KnowledgeDocumentDB, document_id)
    if not doc:
        return False
    await db.delete(doc)
    await db.flush()
    return True


async def get_knowledge_stats(db: AsyncSession) -> dict:
    """Get knowledge base statistics."""
    doc_count = await db.execute(select(func.count(KnowledgeDocumentDB.id)))
    chunk_count = await db.execute(select(func.count(KnowledgeChunkDB.id)))

    category_result = await db.execute(
        select(
            KnowledgeDocumentDB.category, func.count(KnowledgeDocumentDB.id)
        ).group_by(KnowledgeDocumentDB.category)
    )
    by_category = {row[0]: row[1] for row in category_result.fetchall()}

    return {
        "total_documents": doc_count.scalar_one(),
        "total_chunks": chunk_count.scalar_one(),
        "by_category": by_category,
    }


async def get_document_chunks(
    db: AsyncSession, document_id: uuid.UUID
) -> list[KnowledgeChunkDB]:
    """Get all chunks for a document."""
    result = await db.execute(
        select(KnowledgeChunkDB)
        .where(KnowledgeChunkDB.document_id == document_id)
        .order_by(KnowledgeChunkDB.chunk_index)
    )
    return list(result.scalars().all())


# =============================================================================
# M5: Chat Threads & Messages
# =============================================================================


async def get_chat_threads(
    db: AsyncSession, case_id: uuid.UUID, user_id: uuid.UUID
) -> list[ChatThreadDB]:
    """Get all chat threads for a case/user pair."""
    result = await db.execute(
        select(ChatThreadDB)
        .where(ChatThreadDB.case_id == case_id, ChatThreadDB.user_id == user_id)
        .order_by(ChatThreadDB.updated_at.desc())
    )
    return list(result.scalars().all())


async def get_chat_thread(
    db: AsyncSession, thread_id: uuid.UUID
) -> ChatThreadDB | None:
    """Get a single chat thread by ID."""
    result = await db.execute(
        select(ChatThreadDB)
        .options(selectinload(ChatThreadDB.messages))
        .where(ChatThreadDB.id == thread_id)
    )
    return result.scalar_one_or_none()


async def create_chat_thread(
    db: AsyncSession,
    case_id: uuid.UUID,
    user_id: uuid.UUID,
    title: str | None = None,
) -> ChatThreadDB:
    """Create a new chat thread."""
    thread = ChatThreadDB(
        case_id=case_id,
        user_id=user_id,
        title=title,
    )
    db.add(thread)
    await db.flush()
    return thread


async def delete_chat_thread(db: AsyncSession, thread_id: uuid.UUID) -> bool:
    """Delete a chat thread by ID."""
    thread = await db.get(ChatThreadDB, thread_id)
    if not thread:
        return False

    await db.delete(thread)
    await db.flush()
    return True


async def get_thread_messages(
    db: AsyncSession, thread_id: uuid.UUID, limit: int | None = None
) -> list[ChatMessageDB]:
    """Get messages for a thread, optionally limited to last N."""
    query = (
        select(ChatMessageDB)
        .where(ChatMessageDB.thread_id == thread_id)
        .order_by(ChatMessageDB.created_at.asc())
    )
    if limit:
        subquery = (
            select(ChatMessageDB.id)
            .where(ChatMessageDB.thread_id == thread_id)
            .order_by(ChatMessageDB.created_at.desc())
            .limit(limit)
        )
        query = (
            select(ChatMessageDB)
            .where(ChatMessageDB.id.in_(subquery))
            .order_by(ChatMessageDB.created_at.asc())
        )
    result = await db.execute(query)
    return list(result.scalars().all())


async def add_chat_message(
    db: AsyncSession,
    thread_id: uuid.UUID,
    role: str,
    content: str,
    citations: list[dict] | None = None,
    events: list[dict] | None = None,
) -> ChatMessageDB:
    """Add a message to a chat thread."""
    from datetime import datetime, timezone

    message = ChatMessageDB(
        thread_id=thread_id,
        role=role,
        content=content,
        citations=citations,
        events=events,
    )
    db.add(message)

    thread = await db.get(ChatThreadDB, thread_id)
    if thread:
        thread.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    await db.flush()
    return message


async def get_thread_message_count(db: AsyncSession, thread_id: uuid.UUID) -> int:
    """Get the number of messages in a thread."""
    result = await db.execute(
        select(func.count(ChatMessageDB.id)).where(ChatMessageDB.thread_id == thread_id)
    )
    return result.scalar_one()


# =============================================================================
# M5: Agent Settings
# =============================================================================


async def get_agent_settings(db: AsyncSession) -> dict[str, str]:
    """Get all agent settings as a dictionary."""
    result = await db.execute(select(AgentSettingDB))
    settings = result.scalars().all()
    return {s.key: s.value for s in settings}


async def get_agent_setting(db: AsyncSession, key: str) -> str | None:
    """Get a single agent setting by key."""
    result = await db.execute(select(AgentSettingDB).where(AgentSettingDB.key == key))
    setting = result.scalar_one_or_none()
    return setting.value if setting else None


async def set_agent_setting(
    db: AsyncSession,
    key: str,
    value: str,
    updated_by_id: uuid.UUID | None = None,
) -> AgentSettingDB:
    """Set an agent setting (upsert)."""
    from datetime import datetime, timezone

    result = await db.execute(select(AgentSettingDB).where(AgentSettingDB.key == key))
    setting = result.scalar_one_or_none()

    if setting:
        setting.value = value
        setting.updated_by_id = updated_by_id
        setting.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    else:
        setting = AgentSettingDB(
            key=key,
            value=value,
            updated_by_id=updated_by_id,
        )
        db.add(setting)

    await db.flush()
    return setting


async def delete_agent_setting(db: AsyncSession, key: str) -> bool:
    """Delete an agent setting."""
    result = await db.execute(select(AgentSettingDB).where(AgentSettingDB.key == key))
    setting = result.scalar_one_or_none()
    if not setting:
        return False
    await db.delete(setting)
    await db.flush()
    return True
