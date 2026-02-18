"""Case management routes with authentication and role-based permissions."""

import uuid as _uuid

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional
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
)
from state import State
from db.config import get_db
from db import repository as repo
from auth.dependencies import CurrentUser, require_roles
from db.models import UserDB

router = APIRouter(prefix="/api", tags=["cases"])

# Role-based permission constants
SUPERVISOR_ONLY_STATUSES = {"DISMISSED"}  # Only supervisors+ can dismiss
SUPERVISOR_ACTIONS = {"reassign"}  # Only supervisors+ can reassign


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


@router.get("/cases", response_model=list[CaseWithTender])
async def list_cases(
    state: State,
    current_user: CurrentUser,
    status: Optional[CaseStatus] = Query(None),
    priority: Optional[RiskCategory] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List all investigation cases with tender context. Requires authentication."""
    cases_db = await repo.get_cases(
        db,
        status=status.value if status else None,
        priority=priority.value if priority else None,
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


@router.get("/cases/stats")
async def get_case_stats(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Get case management statistics. Requires authentication."""
    return await repo.get_case_stats(db)


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
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Open a new investigation case for a tender. Requires authentication."""
    tender_id = body.tender_id

    if tender_id not in state.tenders:
        raise HTTPException(status_code=404, detail="Tender not found")

    # Auto-set priority from risk score if not provided
    risk = state.risk_scores.get(
        tender_id, RiskScore(overall=0, category=RiskCategory.LOW)
    )
    priority = body.priority.value if body.priority else risk.category.value

    # Parse assigned_to_id if provided
    assigned_to_id = None
    if body.assigned_to_id:
        assigned_to_id = _uuid.UUID(body.assigned_to_id)

    case_db = await repo.create_case(
        db=db,
        tender_id=_uuid.UUID(tender_id),
        title=body.title,
        priority=priority,
        assigned_to_id=assigned_to_id,
        created_by_id=current_user.id,  # Auto-attribute to logged-in user
        summary=body.summary,
    )
    await db.commit()
    await db.refresh(
        case_db, attribute_names=["notes", "tender", "assigned_to", "created_by"]
    )

    # Audit log with user attribution
    await repo.create_audit_log(
        db=db,
        action="CASE_CREATED",
        entity_type="case",
        entity_id=case_db.id,
        user_id=current_user.id,
        details={"tender_id": tender_id},
    )
    await db.commit()

    case = _case_db_to_pydantic(case_db)
    tender_title = state.tenders[tender_id].title

    return CaseWithTender(
        case=case,
        tender_title=tender_title,
        risk_score=risk.overall,
        risk_category=risk.category,
    )


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
    update_fields = body.model_dump(exclude_none=True)
    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Check role-based permissions
    is_supervisor_or_admin = current_user.role in ("supervisor", "admin")

    # Only supervisors+ can dismiss cases
    if "status" in update_fields:
        new_status = (
            update_fields["status"].value
            if hasattr(update_fields["status"], "value")
            else update_fields["status"]
        )
        if new_status in SUPERVISOR_ONLY_STATUSES and not is_supervisor_or_admin:
            raise HTTPException(
                status_code=403,
                detail="Only supervisors can dismiss cases",
            )

    # Only supervisors+ can reassign cases
    if "assigned_to_id" in update_fields and not is_supervisor_or_admin:
        raise HTTPException(
            status_code=403,
            detail="Only supervisors can reassign cases",
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

    # Convert assigned_to_id string to UUID
    if "assigned_to_id" in update_fields and update_fields["assigned_to_id"]:
        update_fields["assigned_to_id"] = _uuid.UUID(update_fields["assigned_to_id"])

    case_db = await repo.update_case(db, _uuid.UUID(case_id), **update_fields)
    if not case_db:
        raise HTTPException(status_code=404, detail="Case not found")

    await db.commit()
    await db.refresh(
        case_db, attribute_names=["notes", "tender", "assigned_to", "created_by"]
    )

    # Audit log with user attribution
    await repo.create_audit_log(
        db=db,
        action="CASE_UPDATED",
        entity_type="case",
        entity_id=case_db.id,
        user_id=current_user.id,
        details=update_fields,
    )
    await db.commit()

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

    note_db = await repo.add_case_note(
        db=db,
        case_id=_uuid.UUID(case_id),
        content=body.content,
        author_id=current_user.id,  # Auto-attribute to logged-in user
        note_type=body.note_type.value,
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


@router.get("/tenders/{tender_id}/cases", response_model=list[Case])
async def get_tender_cases(
    tender_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Get all cases associated with a tender. Requires authentication."""
    cases_db = await repo.get_cases_for_tender(db, _uuid.UUID(tender_id))
    return [_case_db_to_pydantic(c) for c in cases_db]
