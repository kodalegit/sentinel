"""Tender-specific graph route (kept separate from graph exploration routes)."""

from fastapi import APIRouter, HTTPException, Query

from config import settings
from models import GraphData, GraphNode, GraphEdge
from state import State
from graph.builder import get_tender_subgraph, graph_to_frontend_format
from graph.neo4j_communities import get_entity_neighborhood_neo4j
from runtime_graph import ensure_runtime_graph

router = APIRouter(prefix="/api", tags=["tenders"])


@router.get("/tenders/{tender_id}/graph", response_model=GraphData)
async def get_tender_graph(
    tender_id: str, state: State, depth: int = Query(2, ge=1, le=3)
):
    """Get subgraph of entities connected to a specific tender."""
    if tender_id not in state.tenders:
        raise HTTPException(status_code=404, detail="Tender not found")

    # Neo4j-first: index-free adjacency is ideal for k-hop tender subgraphs
    if settings.neo4j_enabled:
        try:
            result = await get_entity_neighborhood_neo4j(tender_id, depth)
            if result and result.get("nodes"):
                return GraphData(
                    nodes=[GraphNode(**n) for n in result["nodes"]],
                    edges=[GraphEdge(**e) for e in result["edges"]],
                )
        except Exception:
            pass  # Fall through to NetworkX

    # NetworkX fallback
    try:
        graph = ensure_runtime_graph(state)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    subgraph = get_tender_subgraph(graph, tender_id, depth=depth)
    return graph_to_frontend_format(subgraph)
