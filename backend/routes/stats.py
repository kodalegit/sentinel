"""Dashboard statistics routes."""

from fastapi import APIRouter

from models import (
    RiskCategory,
    TenderStatus,
    DashboardStats,
)
from state import State

router = APIRouter(prefix="/api", tags=["stats"])


@router.get("/stats", response_model=DashboardStats)
def get_dashboard_stats(state: State):
    """Get dashboard statistics."""
    high_risk = sum(
        1 for r in state.risk_scores.values() if r.category == RiskCategory.HIGH
    )
    medium_risk = sum(
        1 for r in state.risk_scores.values() if r.category == RiskCategory.MEDIUM
    )
    low_risk = sum(
        1 for r in state.risk_scores.values() if r.category == RiskCategory.LOW
    )

    pending = sum(
        1
        for t in state.tenders.values()
        if t.status in [TenderStatus.OPEN, TenderStatus.EVALUATION]
    )

    total_value = sum((t.estimated_value or 0) for t in state.tenders.values())
    flagged_today = high_risk

    return DashboardStats(
        total_tenders=len(state.tenders),
        high_risk_count=high_risk,
        medium_risk_count=medium_risk,
        low_risk_count=low_risk,
        pending_review=pending,
        total_value=total_value,
        flagged_today=flagged_today,
    )
