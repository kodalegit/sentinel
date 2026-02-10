"""Tender-specific graph route (kept separate from graph exploration routes)."""

from fastapi import APIRouter, HTTPException, Query

from models import GraphData
from state import State
from graph.builder import get_tender_subgraph, graph_to_frontend_format

router = APIRouter(prefix="/api", tags=["tenders"])


@router.get("/tenders/{tender_id}/graph", response_model=GraphData)
def get_tender_graph(tender_id: str, state: State, depth: int = Query(2, ge=1, le=3)):
    """Get subgraph of entities connected to a specific tender."""
    if tender_id not in state.tenders:
        raise HTTPException(status_code=404, detail="Tender not found")

    subgraph = get_tender_subgraph(state.graph, tender_id, depth=depth)
    return graph_to_frontend_format(subgraph)
