"""Dashboard statistics routes."""

from fastapi import APIRouter

from models import (
    AnalysisSnapshotInfo,
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


@router.get("/analysis/latest", response_model=AnalysisSnapshotInfo)
def get_latest_analysis_snapshot(state: State):
    summary = state.analysis_summary or {}
    return AnalysisSnapshotInfo(
        analysis_run_id=state.analysis_run_id,
        status=state.analysis_status,
        snapshot_source=state.snapshot_source,
        graph_source=state.graph_source,
        graph_loaded=state.graph_loaded,
        model_version=state.analysis_model_version,
        created_at=state.analysis_created_at,
        tender_count=summary.get("tenders", len(state.tenders)),
        company_count=summary.get("companies", len(state.companies)),
        node_count=summary.get("nodes", state.graph.number_of_nodes()),
        edge_count=summary.get("edges", state.graph.number_of_edges()),
        community_count=summary.get("communities", len(state.communities)),
        risk_score_count=summary.get("risk_scores", len(state.risk_scores)),
        company_feature_count=len(state.company_graph_features),
    )
