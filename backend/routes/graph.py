"""Graph exploration routes."""

from fastapi import APIRouter, HTTPException, Query

from models import GraphData, GraphNode, GraphEdge
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

# Maximum nodes/edges to return in a single response to prevent memory exhaustion
MAX_GRAPH_NODES = 500
MAX_GRAPH_EDGES = 2000


@router.get("/stats")
def get_graph_stats(state: State):
    """Get graph statistics without loading full graph data."""
    G = state.graph

    # Count nodes by type
    node_types = {}
    for _, attrs in G.nodes(data=True):
        ntype = attrs.get("type", "UNKNOWN")
        node_types[ntype] = node_types.get(ntype, 0) + 1

    # Count edges by relationship
    edge_types = {}
    for _, _, attrs in G.edges(data=True):
        etype = attrs.get("relationship", "UNKNOWN")
        edge_types[etype] = edge_types.get(etype, 0) + 1

    return {
        "total_nodes": G.number_of_nodes(),
        "total_edges": G.number_of_edges(),
        "node_types": node_types,
        "edge_types": edge_types,
        "communities": len(state.communities),
        "is_large": G.number_of_nodes() > MAX_GRAPH_NODES
        or G.number_of_edges() > MAX_GRAPH_EDGES,
    }


@router.get("/explore", response_model=GraphData)
def get_full_graph(
    state: State,
    limit_nodes: int = Query(
        MAX_GRAPH_NODES, ge=1, le=1000, description="Max nodes to return"
    ),
    limit_edges: int = Query(
        MAX_GRAPH_EDGES, ge=1, le=5000, description="Max edges to return"
    ),
    node_type: str = Query(
        None, description="Filter by node type (COMPANY, TENDER, etc.)"
    ),
):
    """Get the shadow graph for exploration with pagination/limits.
    For large graphs, use /communities or /entity/{id} endpoints instead."""
    G = state.graph

    # If graph is small enough, return full graph
    if G.number_of_nodes() <= limit_nodes and G.number_of_edges() <= limit_edges:
        return graph_to_frontend_format(G)

    # Otherwise, return a limited subset
    # Prioritize high-risk tenders and their connected entities
    import networkx as nx

    selected_nodes = set()

    # First, add high-risk tender nodes
    for node_id, attrs in G.nodes(data=True):
        if len(selected_nodes) >= limit_nodes:
            break
        if node_type and attrs.get("type") != node_type:
            continue
        if attrs.get("type") == "TENDER" and attrs.get("risk_level") in (
            "HIGH",
            "MEDIUM",
        ):
            selected_nodes.add(node_id)

    # Then add companies connected to those tenders
    for tender_id in list(selected_nodes):
        if len(selected_nodes) >= limit_nodes:
            break
        for neighbor in G.neighbors(tender_id):
            if len(selected_nodes) >= limit_nodes:
                break
            if node_type and G.nodes[neighbor].get("type") != node_type:
                continue
            selected_nodes.add(neighbor)

    # Fill remaining slots with other nodes
    for node_id, attrs in G.nodes(data=True):
        if len(selected_nodes) >= limit_nodes:
            break
        if node_type and attrs.get("type") != node_type:
            continue
        selected_nodes.add(node_id)

    subgraph = G.subgraph(selected_nodes).copy()
    result = graph_to_frontend_format(subgraph)

    # Limit edges if still too many
    if len(result.edges) > limit_edges:
        result.edges = result.edges[:limit_edges]

    return result


@router.get("/communities")
def get_communities(
    state: State,
    skip: int = Query(0, ge=0, description="Number of clusters to skip"),
    limit: int = Query(50, ge=1, le=100, description="Max clusters to return"),
    min_suspicion: float = Query(
        0, ge=0, le=100, description="Minimum suspicion score"
    ),
):
    """Get detected bidding communities with suspicion scores (cached at startup)."""
    # Filter by minimum suspicion score
    filtered = [c for c in state.communities if c.suspicion_score >= min_suspicion]

    # Paginate
    paginated = filtered[skip : skip + limit]

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
            for c in paginated
        ],
        "total": len(filtered),
        "skip": skip,
        "limit": limit,
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
