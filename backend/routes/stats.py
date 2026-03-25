"""Dashboard statistics routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from db.config import get_db
from db import repository as repo
from models import (
    AnalysisSnapshotInfo,
    DashboardStats,
)
from state import State

router = APIRouter(prefix="/api", tags=["stats"])


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
):
    """Get dashboard statistics."""
    return DashboardStats(**(await repo.get_dashboard_stats(db)))


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
