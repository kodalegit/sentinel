"""Graph exploration routes."""

from fastapi import APIRouter, HTTPException, Query

from models import GraphData
from state import State
from graph.builder import (
    get_tender_subgraph,
    graph_to_frontend_format,
)
from graph.communities import (
    get_cluster_subgraph,
    find_shortest_path,
)

router = APIRouter(prefix="/api/graph", tags=["graph"])


@router.get("/explore", response_model=GraphData)
def get_full_graph(state: State):
    """Get the full shadow graph for exploration."""
    return graph_to_frontend_format(state.graph)


@router.get("/communities")
def get_communities(state: State):
    """Get detected bidding communities with suspicion scores (cached at startup)."""
    return {
        "clusters": [
            {
                "id": c.id,
                "company_ids": c.company_ids,
                "company_names": c.company_names,
                "size": c.size,
                "suspicion_score": round(c.suspicion_score, 1),
                "shared_attributes": c.shared_attributes,
                "co_bid_count": c.co_bid_count,
                "win_pattern": c.win_pattern,
            }
            for c in state.communities
        ],
        "total": len(state.communities),
    }


@router.get("/communities/{cluster_id}", response_model=GraphData)
def get_community_graph(
    cluster_id: str,
    state: State,
    include_tenders: bool = Query(True),
    include_officials: bool = Query(True),
):
    """Get the subgraph for a specific community cluster."""
    cluster = next((c for c in state.communities if c.id == cluster_id), None)
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")

    subgraph = get_cluster_subgraph(
        state.graph, cluster.company_ids, include_tenders, include_officials
    )
    return graph_to_frontend_format(subgraph)


@router.get("/path")
def get_path(
    state: State,
    source: str = Query(..., description="Source entity ID"),
    target: str = Query(..., description="Target entity ID"),
):
    """Find shortest path between two entities in the graph."""
    result = find_shortest_path(state.graph, source, target)
    if result is None:
        raise HTTPException(status_code=404, detail="No path found between entities")
    return result


@router.get("/entity/{entity_id}", response_model=GraphData)
def get_entity_neighborhood(
    entity_id: str,
    state: State,
    depth: int = Query(2, ge=1, le=3),
):
    """Get k-hop neighborhood around any entity."""
    if entity_id not in state.graph:
        raise HTTPException(status_code=404, detail="Entity not found in graph")

    subgraph = get_tender_subgraph(state.graph, entity_id, depth=depth)
    return graph_to_frontend_format(subgraph)
