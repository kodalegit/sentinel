"""Case management routes with authentication and role-based permissions."""

import csv
import uuid as _uuid
from datetime import datetime, timezone
from io import StringIO

from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import StreamingResponse
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import (
    RiskScore,
    RiskCategory,
    Case,
    CaseNote,
    CaseStatus,
    CaseWithTender,
    CaseCreate,
    CaseUpdate,
    CaseNoteCreate,
    NoteType,
    # M3 models
    CaseEvent,
    EventType,
    CaseEvidenceLink,
    EvidenceType,
    CaseEvidenceLinkCreate,
    CaseDecision,
    CaseNotification,
    WorkloadItem,
)
from state import State
from db.config import get_db
from db import repository as repo
from auth.dependencies import CurrentUser, SupervisorOrAdmin
from db.models import UserDB

router = APIRouter(prefix="/api", tags=["cases"])

# Role-based permission constants
SUPERVISOR_ONLY_STATUSES = {"OPEN", "DISMISSED"}
STATUS_TRANSITIONS = {
    "OPEN": {"INVESTIGATING", "DISMISSED"},
    "INVESTIGATING": {"ESCALATED", "RESOLVED", "DISMISSED"},
    "ESCALATED": {"INVESTIGATING", "RESOLVED", "DISMISSED"},
    "RESOLVED": set(),
    "DISMISSED": {"OPEN"},
}
TERMINAL_STATUSES = {"RESOLVED", "DISMISSED"}
ASSIGNABLE_ROLES = {"auditor", "supervisor", "admin"}


def _case_db_to_pydantic(case_db) -> Case:
    """Convert CaseDB to Pydantic Case model."""
    return Case(
        id=str(case_db.id),
        tender_id=str(case_db.tender_id),
        title=case_db.title,
        status=CaseStatus(case_db.status),
        priority=RiskCategory(case_db.priority),
        assigned_to=case_db.assigned_to.full_name if case_db.assigned_to else None,
        assigned_to_id=str(case_db.assigned_to_id) if case_db.assigned_to_id else None,
        created_by=case_db.created_by.full_name if case_db.created_by else "System",
        created_by_id=str(case_db.created_by_id) if case_db.created_by_id else None,
        summary=case_db.summary,
        decision=case_db.decision,
        # M3 structured decision fields
        decision_type=case_db.decision_type,
        finding=case_db.finding,
        closed_at=case_db.closed_at,
        created_at=case_db.created_at,
        updated_at=case_db.updated_at,
        notes=[
            CaseNote(
                id=str(n.id),
                case_id=str(n.case_id),
                author=n.author.full_name if n.author else "Unknown",
                author_id=str(n.author_id) if n.author_id else None,
                content=n.content,
                note_type=NoteType(n.note_type),
                created_at=n.created_at,
            )
            for n in (case_db.notes or [])
        ],
    )


def _event_db_to_pydantic(event_db) -> CaseEvent:
    """Convert CaseEventDB to Pydantic CaseEvent model."""
    return CaseEvent(
        id=str(event_db.id),
        case_id=str(event_db.case_id),
        event_type=EventType(event_db.event_type),
        actor=event_db.actor.full_name if event_db.actor else "System",
        actor_id=str(event_db.actor_id),
        old_value=event_db.old_value,
        new_value=event_db.new_value,
        event_metadata=event_db.event_metadata,
        created_at=event_db.created_at,
    )


def _evidence_link_db_to_pydantic(link_db) -> CaseEvidenceLink:
    """Convert CaseEvidenceLinkDB to Pydantic CaseEvidenceLink model."""
    return CaseEvidenceLink(
        id=str(link_db.id),
        case_id=str(link_db.case_id),
        evidence_type=EvidenceType(link_db.evidence_type),
        reference_id=link_db.reference_id,
        label=link_db.label,
        link_metadata=link_db.link_metadata,
        added_by=link_db.added_by.full_name if link_db.added_by else "System",
        added_by_id=str(link_db.added_by_id),
        created_at=link_db.created_at,
    )


def _case_with_tender_response(case_db, state: State) -> CaseWithTender:
    case = _case_db_to_pydantic(case_db)
    tender_id = str(case_db.tender_id)
    risk = state.risk_scores.get(
        tender_id, RiskScore(overall=0, category=RiskCategory.LOW)
    )
    tender_title = case_db.tender.title if case_db.tender else "Unknown"
    return CaseWithTender(
        case=case,
        tender_title=tender_title,
        risk_score=risk.overall,
        risk_category=risk.category,
    )


def _is_supervisor_or_admin(current_user: CurrentUser) -> bool:
    return current_user.role in ("supervisor", "admin")


def _is_assigned_investigator(case_db, current_user: CurrentUser) -> bool:
    return case_db.assigned_to_id == current_user.id


def _require_case_participant(case_db, current_user: CurrentUser) -> None:
    if _is_supervisor_or_admin(current_user) or _is_assigned_investigator(
        case_db, current_user
    ):
        return
    raise HTTPException(
        status_code=403,
        detail="Only the assigned investigator or supervisors can update this case",
    )


async def _get_assignable_user(db: AsyncSession, user_id: str) -> UserDB:
    result = await db.execute(select(UserDB).where(UserDB.id == _uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active or user.role not in ASSIGNABLE_ROLES:
        raise HTTPException(status_code=400, detail="Selected assignee is not eligible")
    return user


async def _validate_case_evidence_link(
    *,
    body: CaseEvidenceLinkCreate,
    case_db,
    state: State,
    db: AsyncSession,
) -> dict | None:
    evidence_type = body.evidence_type.value
    metadata = dict(body.link_metadata or {})
    case_tender_id = str(case_db.tender_id)

    if evidence_type == "TENDER":
        if body.reference_id != case_tender_id:
            raise HTTPException(
                status_code=400,
                detail="Tender evidence must reference the tender attached to this case",
            )
        if body.reference_id not in state.tenders:
            raise HTTPException(status_code=400, detail="Tender evidence not found")
        tender = state.tenders[body.reference_id]
        metadata.setdefault("reference_number", tender.reference_number)
        metadata.setdefault("procuring_entity", tender.procuring_entity)
        metadata.setdefault("estimated_value", tender.estimated_value)
        return metadata

    if evidence_type == "RISK_FACTOR":
        tender_id, separator, factor_type = body.reference_id.partition(":")
        if not separator or tender_id != case_tender_id:
            raise HTTPException(
                status_code=400,
                detail="Risk factor evidence must reference a risk factor for this case tender",
            )
        risk = state.risk_scores.get(tender_id)
        if not risk:
            raise HTTPException(
                status_code=400, detail="Risk factor evidence not found"
            )
        factor = next(
            (item for item in risk.factors if item.type.value == factor_type),
            None,
        )
        if not factor:
            raise HTTPException(
                status_code=400, detail="Risk factor evidence not found"
            )
        metadata.setdefault("type", factor.type.value)
        metadata.setdefault("weight", factor.weight)
        metadata.setdefault("description", factor.description)
        metadata.setdefault("evidence", factor.evidence)
        return metadata

    if evidence_type == "DOCUMENT":
        try:
            document_id = _uuid.UUID(body.reference_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=400, detail="Document evidence must use a valid document ID"
            ) from exc
        document = await repo.get_knowledge_document(db, document_id)
        if not document:
            raise HTTPException(status_code=400, detail="Document evidence not found")
        metadata.setdefault("title", document.title)
        metadata.setdefault("source_url", document.source_url)
        metadata.setdefault("description", document.description)
        return metadata

    if evidence_type == "GRAPH_PATH":
        if not any(
            metadata.get(key) for key in ("path", "description", "summary", "nodes")
        ):
            raise HTTPException(
                status_code=400,
                detail="Graph path evidence requires path details in metadata",
            )
        return metadata

    return metadata or None


@router.get("/cases", response_model=list[CaseWithTender])
async def list_cases(
    state: State,
    current_user: CurrentUser,
    status: Optional[CaseStatus] = Query(None),
    priority: Optional[RiskCategory] = Query(None),
    assigned_to_id: Optional[str] = Query(
        None, description="Filter by assignee UUID, 'unassigned', or 'me'"
    ),
    db: AsyncSession = Depends(get_db),
):
    """List all investigation cases with tender context. Requires authentication."""
    # Handle 'me' filter
    assignee_filter = assigned_to_id
    if assigned_to_id == "me":
        assignee_filter = current_user.id
    elif assigned_to_id and assigned_to_id != "unassigned":
        assignee_filter = _uuid.UUID(assigned_to_id)

    cases_db = await repo.get_cases_with_filters(
        db,
        status=status.value if status else None,
        priority=priority.value if priority else None,
        assigned_to_id=assignee_filter,
    )
    results = []
    for c in cases_db:
        case = _case_db_to_pydantic(c)
        tender_id = str(c.tender_id)
        risk = state.risk_scores.get(
            tender_id, RiskScore(overall=0, category=RiskCategory.LOW)
        )
        tender_title = c.tender.title if c.tender else "Unknown"
        results.append(
            CaseWithTender(
                case=case,
                tender_title=tender_title,
                risk_score=risk.overall,
                risk_category=risk.category,
            )
        )
    return results


@router.get("/cases/export.csv")
async def export_cases_csv(
    state: State,
    current_user: CurrentUser,
    status: Optional[CaseStatus] = Query(None),
    priority: Optional[RiskCategory] = Query(None),
    assigned_to_id: Optional[str] = Query(
        None, description="Filter by assignee UUID, 'unassigned', or 'me'"
    ),
    db: AsyncSession = Depends(get_db),
):
    """Export filtered investigation cases as CSV."""
    assignee_filter = assigned_to_id
    if assigned_to_id == "me":
        assignee_filter = current_user.id
    elif assigned_to_id and assigned_to_id != "unassigned":
        assignee_filter = _uuid.UUID(assigned_to_id)

    cases_db = await repo.get_cases_with_filters(
        db,
        status=status.value if status else None,
        priority=priority.value if priority else None,
        assigned_to_id=assignee_filter,
    )

    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "case_id",
            "title",
            "status",
            "priority",
            "risk_score",
            "risk_category",
            "tender_id",
            "tender_title",
            "assigned_to",
            "created_by",
            "created_at",
            "updated_at",
            "closed_at",
            "notes_count",
            "decision_type",
            "finding",
        ]
    )

    for case_db in cases_db:
        tender_id = str(case_db.tender_id)
        risk = state.risk_scores.get(
            tender_id, RiskScore(overall=0, category=RiskCategory.LOW)
        )
        writer.writerow(
            [
                str(case_db.id),
                case_db.title,
                case_db.status,
                case_db.priority,
                risk.overall,
                risk.category.value,
                tender_id,
                case_db.tender.title if case_db.tender else "Unknown",
                case_db.assigned_to.full_name if case_db.assigned_to else "",
                case_db.created_by.full_name if case_db.created_by else "System",
                case_db.created_at.isoformat() if case_db.created_at else "",
                case_db.updated_at.isoformat() if case_db.updated_at else "",
                case_db.closed_at.isoformat() if case_db.closed_at else "",
                len(case_db.notes or []),
                case_db.decision_type or "",
                case_db.finding or "",
            ]
        )

    filename = "sentinel-cases.csv"
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/cases/stats")
async def get_case_stats(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Get case management statistics. Requires authentication."""
    return await repo.get_case_stats(db)


# --- M3: Supervisor Workload ---


@router.get("/cases/workload", response_model=list[WorkloadItem])
async def get_workload(
    current_user: SupervisorOrAdmin,
    db: AsyncSession = Depends(get_db),
):
    """Get case workload per assignee. Supervisors only."""
    workload = await repo.get_supervisor_workload(db)
    return [WorkloadItem(**w) for w in workload]


@router.get("/cases/{case_id}", response_model=CaseWithTender)
async def get_case_detail(
    case_id: str,
    state: State,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Get full case detail including notes. Requires authentication."""
    case_db = await repo.get_case(db, _uuid.UUID(case_id))
    if not case_db:
        raise HTTPException(status_code=404, detail="Case not found")

    case = _case_db_to_pydantic(case_db)
    tender_id = str(case_db.tender_id)
    risk = state.risk_scores.get(
        tender_id, RiskScore(overall=0, category=RiskCategory.LOW)
    )
    tender_title = case_db.tender.title if case_db.tender else "Unknown"

    return CaseWithTender(
        case=case,
        tender_title=tender_title,
        risk_score=risk.overall,
        risk_category=risk.category,
    )


@router.post("/cases", response_model=CaseWithTender, status_code=201)
async def create_case(
    body: CaseCreate,
    state: State,
    current_user: SupervisorOrAdmin,
    db: AsyncSession = Depends(get_db),
):
    """Open a new investigation case for a tender. Supervisors only."""
    tender_id = body.tender_id

    if tender_id not in state.tenders:
        raise HTTPException(status_code=404, detail="Tender not found")

    active_case = await repo.get_active_case_for_tender(db, _uuid.UUID(tender_id))
    if active_case:
        raise HTTPException(
            status_code=409,
            detail="An active case already exists for this tender",
        )

    # Auto-set priority from risk score if not provided
    risk = state.risk_scores.get(
        tender_id, RiskScore(overall=0, category=RiskCategory.LOW)
    )
    priority = body.priority.value if body.priority else risk.category.value

    assigned_to_id = None
    assignee = None
    if body.assigned_to_id:
        assignee = await _get_assignable_user(db, body.assigned_to_id)
        assigned_to_id = assignee.id

    initial_status = "INVESTIGATING" if assigned_to_id else "OPEN"

    case_db = await repo.create_case(
        db=db,
        tender_id=_uuid.UUID(tender_id),
        title=body.title,
        status=initial_status,
        priority=priority,
        assigned_to_id=assigned_to_id,
        created_by_id=current_user.id,
        summary=body.summary,
    )
    await db.flush()

    # M3: Emit CASE_OPENED event
    await repo.create_case_event(
        db=db,
        case_id=case_db.id,
        event_type="CASE_OPENED",
        actor_id=current_user.id,
        new_value=f"Case opened for tender {tender_id}",
        event_metadata={
            "tender_id": tender_id,
            "priority": priority,
            "status": initial_status,
        },
    )

    if assigned_to_id:
        await repo.create_case_event(
            db=db,
            case_id=case_db.id,
            event_type="ASSIGNMENT",
            actor_id=current_user.id,
            old_value=None,
            new_value=str(assigned_to_id),
            event_metadata={
                "old_assignee_name": None,
                "new_assignee_name": assignee.full_name if assignee else None,
            },
        )

    # M3: Auto-link tender as evidence
    tender = state.tenders[tender_id]
    await repo.add_case_evidence_link(
        db=db,
        case_id=case_db.id,
        evidence_type="TENDER",
        reference_id=tender_id,
        label=f"Tender: {tender.reference_number} - {tender.title[:100]}",
        added_by_id=current_user.id,
        link_metadata={
            "reference_number": tender.reference_number,
            "procuring_entity": tender.procuring_entity,
            "estimated_value": tender.estimated_value,
            "auto_linked": True,
            "protected": True,
        },
    )

    # M3: Auto-link risk factors as evidence
    for factor in risk.factors:
        await repo.add_case_evidence_link(
            db=db,
            case_id=case_db.id,
            evidence_type="RISK_FACTOR",
            reference_id=f"{tender_id}:{factor.type.value}",
            label=f"Risk Factor: {factor.type.value} (weight: {factor.weight})",
            added_by_id=current_user.id,
            link_metadata={
                "type": factor.type.value,
                "weight": factor.weight,
                "description": factor.description,
                "evidence": factor.evidence,
                "auto_linked": True,
                "protected": True,
            },
        )

    # M3: Notify assignee if assigned
    if assigned_to_id:
        await repo.create_notification(
            db=db,
            user_id=assigned_to_id,
            case_id=case_db.id,
            message=f"You have been assigned to case: {body.title}",
        )

    # Audit log
    await repo.create_audit_log(
        db=db,
        action="CASE_CREATED",
        entity_type="case",
        entity_id=case_db.id,
        user_id=current_user.id,
        details={"tender_id": tender_id},
    )
    await db.commit()
    await db.refresh(
        case_db, attribute_names=["notes", "tender", "assigned_to", "created_by"]
    )

    return _case_with_tender_response(case_db, state)


@router.patch("/cases/{case_id}", response_model=CaseWithTender)
async def update_case(
    case_id: str,
    body: CaseUpdate,
    state: State,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Update case status, priority, assignment, or decision.
    Role-based permissions:
    - Auditors cannot dismiss cases or reassign to others
    - Supervisors+ can perform all actions
    """
    update_fields = body.model_dump(exclude_unset=True)
    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Get current case state for event tracking
    case_db = await repo.get_case(db, _uuid.UUID(case_id))
    if not case_db:
        raise HTTPException(status_code=404, detail="Case not found")

    old_status = case_db.status
    old_priority = case_db.priority
    old_assigned_to_id = case_db.assigned_to_id
    old_assignee_name = case_db.assigned_to.full_name if case_db.assigned_to else None

    # Check role-based permissions
    is_supervisor_or_admin = _is_supervisor_or_admin(current_user)
    is_assigned_investigator = _is_assigned_investigator(case_db, current_user)

    if "assigned_to_id" in update_fields and not is_supervisor_or_admin:
        raise HTTPException(
            status_code=403,
            detail="Only supervisors can assign or unassign cases",
        )

    if not is_supervisor_or_admin and any(
        field in update_fields for field in ("priority", "summary", "decision")
    ):
        raise HTTPException(
            status_code=403,
            detail="Only supervisors can update case management fields",
        )

    # Convert enums to string values for DB
    if "status" in update_fields:
        update_fields["status"] = (
            update_fields["status"].value
            if hasattr(update_fields["status"], "value")
            else update_fields["status"]
        )
    if "priority" in update_fields:
        update_fields["priority"] = (
            update_fields["priority"].value
            if hasattr(update_fields["priority"], "value")
            else update_fields["priority"]
        )

    new_status = update_fields.get("status", old_status)
    new_assigned_to_id = None
    new_assignee_name = old_assignee_name
    if "assigned_to_id" in update_fields:
        if update_fields["assigned_to_id"]:
            assignee = await _get_assignable_user(db, update_fields["assigned_to_id"])
            new_assigned_to_id = assignee.id
            new_assignee_name = assignee.full_name
            update_fields["assigned_to_id"] = new_assigned_to_id
        else:
            update_fields["assigned_to_id"] = None
            new_assigned_to_id = None
            new_assignee_name = None
    else:
        new_assigned_to_id = old_assigned_to_id

    if (
        "assigned_to_id" in update_fields
        and new_assigned_to_id
        and old_status == "OPEN"
    ):
        new_status = update_fields["status"] = "INVESTIGATING"
    elif (
        "assigned_to_id" in update_fields
        and new_assigned_to_id is None
        and old_status == "INVESTIGATING"
        and "status" not in update_fields
    ):
        new_status = update_fields["status"] = "OPEN"

    if "status" in update_fields:
        if new_status == old_status and "assigned_to_id" not in update_fields:
            raise HTTPException(
                status_code=400, detail="Case is already in that status"
            )
        if new_status not in STATUS_TRANSITIONS.get(old_status, set()):
            raise HTTPException(
                status_code=400, detail="Invalid case status transition"
            )
        if new_status in SUPERVISOR_ONLY_STATUSES and not is_supervisor_or_admin:
            raise HTTPException(
                status_code=403,
                detail="Only supervisors can reopen or dismiss cases",
            )
        if not is_supervisor_or_admin:
            if not is_assigned_investigator:
                raise HTTPException(
                    status_code=403,
                    detail="Only the assigned investigator or supervisors can change case status",
                )
            if new_status not in {"ESCALATED", "RESOLVED"}:
                raise HTTPException(
                    status_code=403,
                    detail="Assigned investigators can only escalate or resolve cases",
                )

    resulting_assignee_id = update_fields.get("assigned_to_id", old_assigned_to_id)
    if new_status in {"INVESTIGATING", "RESOLVED"} and resulting_assignee_id is None:
        raise HTTPException(
            status_code=400,
            detail="This status requires an assigned investigator",
        )

    if "status" in update_fields and new_status in TERMINAL_STATUSES:
        update_fields["closed_at"] = datetime.now(timezone.utc).replace(tzinfo=None)
    elif "status" in update_fields:
        update_fields["closed_at"] = None

    case_db = await repo.update_case(db, _uuid.UUID(case_id), **update_fields)
    await db.flush()

    # M3: Emit events for tracked changes
    if "status" in update_fields and update_fields["status"] != old_status:
        await repo.create_case_event(
            db=db,
            case_id=case_db.id,
            event_type="STATUS_CHANGE",
            actor_id=current_user.id,
            old_value=old_status,
            new_value=update_fields["status"],
        )

        if update_fields["status"] == "ESCALATED":
            supervisors = await db.execute(
                select(UserDB).where(
                    UserDB.is_active == True,
                    UserDB.role.in_(["supervisor", "admin"]),
                )
            )
            for supervisor in supervisors.scalars().all():
                if supervisor.id == current_user.id:
                    continue
                await repo.create_notification(
                    db=db,
                    user_id=supervisor.id,
                    case_id=case_db.id,
                    message=f"Case escalated: {case_db.title}",
                )

    if "priority" in update_fields and update_fields["priority"] != old_priority:
        await repo.create_case_event(
            db=db,
            case_id=case_db.id,
            event_type="PRIORITY_CHANGE",
            actor_id=current_user.id,
            old_value=old_priority,
            new_value=update_fields["priority"],
        )

    if "assigned_to_id" in update_fields and new_assigned_to_id != old_assigned_to_id:
        await repo.create_case_event(
            db=db,
            case_id=case_db.id,
            event_type="ASSIGNMENT",
            actor_id=current_user.id,
            old_value=str(old_assigned_to_id) if old_assigned_to_id else None,
            new_value=str(new_assigned_to_id) if new_assigned_to_id else None,
            event_metadata={
                "old_assignee_name": old_assignee_name,
                "new_assignee_name": new_assignee_name,
            },
        )
        # Notify new assignee
        if new_assigned_to_id:
            await repo.create_notification(
                db=db,
                user_id=new_assigned_to_id,
                case_id=case_db.id,
                message=f"You have been assigned to case: {case_db.title}",
            )

    # Audit log - convert UUIDs to strings for JSON serialization
    audit_details = {}
    for key, value in update_fields.items():
        if isinstance(value, _uuid.UUID):
            audit_details[key] = str(value)
        elif isinstance(value, datetime):
            audit_details[key] = value.isoformat()
        else:
            audit_details[key] = value

    await repo.create_audit_log(
        db=db,
        action="CASE_UPDATED",
        entity_type="case",
        entity_id=case_db.id,
        user_id=current_user.id,
        details=audit_details,
    )
    await db.commit()
    await db.refresh(
        case_db, attribute_names=["notes", "tender", "assigned_to", "created_by"]
    )

    return _case_with_tender_response(case_db, state)


@router.post("/cases/{case_id}/notes", status_code=201)
async def add_note(
    case_id: str,
    body: CaseNoteCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Add a note to an existing case. Requires authentication."""
    case_db = await repo.get_case(db, _uuid.UUID(case_id))
    if not case_db:
        raise HTTPException(status_code=404, detail="Case not found")

    _require_case_participant(case_db, current_user)

    note_db = await repo.add_case_note(
        db=db,
        case_id=_uuid.UUID(case_id),
        content=body.content,
        author_id=current_user.id,
        note_type=body.note_type.value,
    )

    # M3: Emit NOTE_ADDED event
    await repo.create_case_event(
        db=db,
        case_id=_uuid.UUID(case_id),
        event_type="NOTE_ADDED",
        actor_id=current_user.id,
        new_value=body.note_type.value,
        event_metadata={"note_id": str(note_db.id)},
    )
    await db.commit()

    return {
        "id": str(note_db.id),
        "case_id": str(note_db.case_id),
        "author": current_user.full_name,
        "author_id": str(current_user.id),
        "content": note_db.content,
        "note_type": note_db.note_type,
        "created_at": note_db.created_at.isoformat(),
    }


# --- M3: Timeline & Evidence Endpoints ---


@router.get("/cases/{case_id}/timeline", response_model=list[CaseEvent])
async def get_case_timeline(
    case_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Get chronological timeline of case events."""
    case_db = await repo.get_case(db, _uuid.UUID(case_id))
    if not case_db:
        raise HTTPException(status_code=404, detail="Case not found")

    events_db = await repo.get_case_events(db, _uuid.UUID(case_id))
    return [_event_db_to_pydantic(e) for e in events_db]


@router.get("/cases/{case_id}/evidence", response_model=list[CaseEvidenceLink])
async def get_case_evidence(
    case_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Get all evidence links for a case."""
    case_db = await repo.get_case(db, _uuid.UUID(case_id))
    if not case_db:
        raise HTTPException(status_code=404, detail="Case not found")

    links_db = await repo.get_case_evidence_links(db, _uuid.UUID(case_id))
    return [_evidence_link_db_to_pydantic(l) for l in links_db]


@router.post(
    "/cases/{case_id}/evidence", response_model=CaseEvidenceLink, status_code=201
)
async def add_case_evidence(
    case_id: str,
    body: CaseEvidenceLinkCreate,
    state: State,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Link evidence to a case."""
    case_db = await repo.get_case(db, _uuid.UUID(case_id))
    if not case_db:
        raise HTTPException(status_code=404, detail="Case not found")

    _require_case_participant(case_db, current_user)

    existing_link = await repo.get_case_evidence_link_by_reference(
        db,
        _uuid.UUID(case_id),
        body.evidence_type.value,
        body.reference_id,
    )
    if existing_link:
        raise HTTPException(
            status_code=409,
            detail="This evidence is already linked to the case",
        )

    validated_metadata = await _validate_case_evidence_link(
        body=body,
        case_db=case_db,
        state=state,
        db=db,
    )

    link_db = await repo.add_case_evidence_link(
        db=db,
        case_id=_uuid.UUID(case_id),
        evidence_type=body.evidence_type.value,
        reference_id=body.reference_id,
        label=body.label,
        added_by_id=current_user.id,
        link_metadata=validated_metadata,
    )

    # Emit event
    await repo.create_case_event(
        db=db,
        case_id=_uuid.UUID(case_id),
        event_type="EVIDENCE_LINKED",
        actor_id=current_user.id,
        new_value=body.label,
        event_metadata={
            "evidence_id": str(link_db.id),
            "type": body.evidence_type.value,
            "reference_id": body.reference_id,
        },
    )
    await db.commit()

    return _evidence_link_db_to_pydantic(link_db)


@router.delete("/cases/{case_id}/evidence/{link_id}", status_code=204)
async def remove_case_evidence(
    case_id: str,
    link_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Remove an evidence link from a case."""
    link_db = await repo.get_case_evidence_link(db, _uuid.UUID(link_id))
    if not link_db or str(link_db.case_id) != case_id:
        raise HTTPException(status_code=404, detail="Evidence link not found")

    if not _is_supervisor_or_admin(current_user):
        raise HTTPException(
            status_code=403,
            detail="Only supervisors can remove evidence links",
        )

    if (link_db.link_metadata or {}).get("protected"):
        raise HTTPException(
            status_code=400,
            detail="Protected baseline evidence cannot be removed from a case",
        )

    label = link_db.label
    deleted = await repo.remove_case_evidence_link(db, _uuid.UUID(link_id))
    if not deleted:
        raise HTTPException(status_code=404, detail="Evidence link not found")

    # Emit event
    await repo.create_case_event(
        db=db,
        case_id=_uuid.UUID(case_id),
        event_type="EVIDENCE_UNLINKED",
        actor_id=current_user.id,
        old_value=label,
    )
    await db.commit()


# --- M3: Self-Assign & Decision Recording ---


@router.post("/cases/{case_id}/self-assign", response_model=CaseWithTender)
async def self_assign_case(
    case_id: str,
    current_user: CurrentUser,
):
    raise HTTPException(
        status_code=403,
        detail="Self-assignment is disabled. Supervisors must assign cases.",
    )


@router.post("/cases/{case_id}/decision", response_model=CaseWithTender)
async def record_decision(
    case_id: str,
    body: CaseDecision,
    state: State,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Record a structured decision on a case."""
    case_db = await repo.get_case(db, _uuid.UUID(case_id))
    if not case_db:
        raise HTTPException(status_code=404, detail="Case not found")

    if not _is_supervisor_or_admin(current_user):
        raise HTTPException(
            status_code=403,
            detail="Only supervisors can record formal case decisions",
        )

    if case_db.status not in ("INVESTIGATING", "ESCALATED"):
        raise HTTPException(
            status_code=400,
            detail="Decisions can only be recorded on cases in INVESTIGATING or ESCALATED status",
        )

    valid_evidence_ids = {
        str(link.id)
        for link in await repo.get_case_evidence_links(db, _uuid.UUID(case_id))
    }
    invalid_references = [
        reference_id
        for reference_id in body.evidence_references
        if reference_id not in valid_evidence_ids
    ]
    if invalid_references:
        raise HTTPException(
            status_code=400,
            detail="Decision evidence references must point to evidence linked to this case",
        )

    # Update case with structured decision
    case_db = await repo.update_case(
        db,
        _uuid.UUID(case_id),
        decision_type=body.decision_type.value,
        finding=body.finding,
        decision=body.recommendation,
    )
    await db.flush()

    # Emit decision event
    await repo.create_case_event(
        db=db,
        case_id=case_db.id,
        event_type="DECISION_RECORDED",
        actor_id=current_user.id,
        new_value=body.decision_type.value,
        event_metadata={
            "finding": body.finding[:200] if body.finding else None,
            "evidence_references": body.evidence_references,
        },
    )
    await db.commit()
    await db.refresh(
        case_db, attribute_names=["notes", "tender", "assigned_to", "created_by"]
    )

    case = _case_db_to_pydantic(case_db)
    tender_id = str(case_db.tender_id)
    risk = state.risk_scores.get(
        tender_id, RiskScore(overall=0, category=RiskCategory.LOW)
    )
    tender_title = case_db.tender.title if case_db.tender else "Unknown"

    return CaseWithTender(
        case=case,
        tender_title=tender_title,
        risk_score=risk.overall,
        risk_category=risk.category,
    )


# --- M3: Notifications ---


@router.get("/notifications", response_model=list[CaseNotification])
async def get_notifications(
    current_user: CurrentUser,
    unread_only: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    """Get notifications for the current user."""
    notifications = await repo.get_user_notifications(
        db, current_user.id, unread_only=unread_only
    )
    return [
        CaseNotification(
            id=str(n.id),
            case_id=str(n.case_id),
            case_title=n.case.title if n.case else None,
            message=n.message,
            is_read=n.is_read,
            created_at=n.created_at,
        )
        for n in notifications
    ]


@router.get("/notifications/count")
async def get_notification_count(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Get count of unread notifications for the current user."""
    count = await repo.get_unread_notification_count(db, current_user.id)
    return {"unread_count": count}


@router.patch("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Mark a notification as read."""
    notification = await repo.mark_notification_read(db, _uuid.UUID(notification_id))
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    await db.commit()
    return {"success": True}


@router.get("/tenders/{tender_id}/cases", response_model=list[Case])
async def get_tender_cases(
    tender_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Get all cases associated with a tender. Requires authentication."""
    cases_db = await repo.get_cases_for_tender(db, _uuid.UUID(tender_id))
    return [_case_db_to_pydantic(c) for c in cases_db]
