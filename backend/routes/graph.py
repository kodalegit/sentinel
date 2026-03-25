"""Graph exploration routes."""

import networkx as nx
from fastapi import APIRouter, HTTPException, Query

from config import settings
from models import GraphData, GraphNode, GraphEdge, GraphSearchResult
from state import State
from graph.builder import (
    get_tender_subgraph,
    graph_to_frontend_format,
)
from graph.communities import (
    get_cluster_subgraph,
    find_shortest_path,
)
from graph.neo4j_communities import (
    find_shortest_path_neo4j,
    get_entity_neighborhood_neo4j,
    get_cluster_subgraph_neo4j,
    search_graph_entities_neo4j,
)
from graph.neo4j_sync import get_graph_stats_from_neo4j
from runtime_graph import ensure_runtime_graph

router = APIRouter(prefix="/api/graph", tags=["graph"])

# Maximum nodes/edges to return in a single response to prevent memory exhaustion
MAX_GRAPH_NODES = 500
MAX_GRAPH_EDGES = 2000
MAX_GRAPH_SEARCH_RESULTS = 12


def _normalize_shared_node_id(
    value: str | None,
    ids: set[str],
    name_to_id: dict[str, str],
) -> str | None:
    if not value:
        return None
    if value in ids:
        return value
    return name_to_id.get(value)


def _normalize_shared_attributes(shared_attributes: dict, state: State) -> dict:
    company_ids = set(state.companies.keys())
    director_ids = set(state.directors.keys())
    company_name_to_id = {
        company.name: company.id for company in state.companies.values()
    }
    director_name_to_id = {
        director.name: director.id for director in state.directors.values()
    }

    normalized = {
        "addresses": [],
        "phones": [],
        "directors": [],
    }

    for item in shared_attributes.get("addresses", []):
        normalized_companies = list(
            dict.fromkeys(
                company_id
                for company_id in (
                    _normalize_shared_node_id(company, company_ids, company_name_to_id)
                    for company in item.get("companies", [])
                )
                if company_id
            )
        )
        normalized["addresses"].append(
            {
                "address": item.get("address"),
                "companies": normalized_companies,
            }
        )

    for item in shared_attributes.get("phones", []):
        normalized_companies = list(
            dict.fromkeys(
                company_id
                for company_id in (
                    _normalize_shared_node_id(company, company_ids, company_name_to_id)
                    for company in item.get("companies", [])
                )
                if company_id
            )
        )
        normalized["phones"].append(
            {
                "phone": item.get("phone"),
                "companies": normalized_companies,
            }
        )

    for item in shared_attributes.get("directors", []):
        normalized_companies = list(
            dict.fromkeys(
                company_id
                for company_id in (
                    _normalize_shared_node_id(company, company_ids, company_name_to_id)
                    for company in item.get("companies", [])
                )
                if company_id
            )
        )
        normalized_director_id = _normalize_shared_node_id(
            item.get("director_id"), director_ids, director_name_to_id
        )
        normalized["directors"].append(
            {
                "director_id": normalized_director_id or item.get("director_id"),
                "companies": normalized_companies,
            }
        )

    return normalized


def _build_search_subtitle(graph: nx.Graph, node_id: str, attrs: dict) -> str | None:
    node_type = attrs.get("type")
    if node_type == "TENDER":
        return attrs.get("procuring_entity")
    if node_type == "OFFICIAL":
        department = attrs.get("department")
        position = attrs.get("position")
        if department and position:
            return f"{department} · {position}"
        return department or position
    if node_type == "COMPANY":
        return attrs.get("address") or attrs.get("source_system")
    if node_type == "DIRECTOR":
        company_count = sum(
            1
            for neighbor_id in graph.neighbors(node_id)
            if graph.nodes[neighbor_id].get("type") == "COMPANY"
        )
        if company_count:
            suffix = "company" if company_count == 1 else "companies"
            return f"Linked to {company_count} {suffix}"
    return None


@router.get("/stats")
async def get_graph_stats(state: State):
    """Get graph statistics. Uses Neo4j counts when available, falls back to NetworkX."""
    if settings.neo4j_enabled:
        try:
            if not state.graph_loaded:
                neo4j_stats = await get_graph_stats_from_neo4j()
                return {
                    "total_nodes": neo4j_stats.get("total_nodes", 0),
                    "total_edges": neo4j_stats.get("total_edges", 0),
                    "node_types": neo4j_stats.get("node_types", {}),
                    "edge_types": neo4j_stats.get("edge_types", {}),
                    "communities": len(state.communities),
                    "is_large": (
                        neo4j_stats.get("total_nodes", 0) > MAX_GRAPH_NODES
                        or neo4j_stats.get("total_edges", 0) > MAX_GRAPH_EDGES
                    ),
                    "source": "neo4j",
                }
        except Exception:
            pass

    G = ensure_runtime_graph(state)

    # Count edges by relationship from NetworkX (always available, used for type breakdowns)
    node_types: dict[str, int] = {}
    for _, attrs in G.nodes(data=True):
        ntype = attrs.get("type", "UNKNOWN")
        node_types[ntype] = node_types.get(ntype, 0) + 1

    edge_types: dict[str, int] = {}
    for _, _, attrs in G.edges(data=True):
        etype = attrs.get("relationship", "UNKNOWN")
        edge_types[etype] = edge_types.get(etype, 0) + 1

    total_nodes = G.number_of_nodes()
    total_edges = G.number_of_edges()

    return {
        "total_nodes": total_nodes,
        "total_edges": total_edges,
        "node_types": node_types,
        "edge_types": edge_types,
        "communities": len(state.communities),
        "is_large": total_nodes > MAX_GRAPH_NODES or total_edges > MAX_GRAPH_EDGES,
        "source": "networkx",
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
    G = ensure_runtime_graph(state)

    # If graph is small enough, return full graph
    if G.number_of_nodes() <= limit_nodes and G.number_of_edges() <= limit_edges:
        return graph_to_frontend_format(G)

    # Otherwise, return a limited subset
    # Prioritize high-risk tenders and their connected entities
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
                "shared_attributes": _normalize_shared_attributes(
                    c.shared_attributes, state
                ),
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
async def get_community_graph(
    cluster_id: str,
    state: State,
    include_tenders: bool = Query(True),
    include_officials: bool = Query(True),
):
    """Get the subgraph for a specific community cluster."""
    cluster = next((c for c in state.communities if c.id == cluster_id), None)
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")

    # Neo4j-first: richer multi-hop sub-graph from the graph DB
    if settings.neo4j_enabled:
        try:
            neo4j_result = await get_cluster_subgraph_neo4j(
                cluster.company_ids, include_tenders, include_officials
            )
            if neo4j_result and neo4j_result.get("nodes"):
                return GraphData(
                    nodes=[GraphNode(**n) for n in neo4j_result["nodes"]],
                    edges=[GraphEdge(**e) for e in neo4j_result["edges"]],
                )
        except Exception:
            pass  # Fall through to NetworkX

    # NetworkX fallback
    graph = ensure_runtime_graph(state)
    subgraph = get_cluster_subgraph(
        graph, cluster.company_ids, include_tenders, include_officials
    )
    return graph_to_frontend_format(subgraph)


@router.get("/search", response_model=list[GraphSearchResult])
async def search_graph_entities(
    state: State,
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(
        MAX_GRAPH_SEARCH_RESULTS,
        ge=1,
        le=25,
        description="Maximum results to return",
    ),
):
    if settings.neo4j_enabled:
        try:
            neo4j_matches = await search_graph_entities_neo4j(q, limit)
            return [GraphSearchResult(**match) for match in neo4j_matches]
        except Exception:
            pass

    graph = ensure_runtime_graph(state)
    query = q.strip().lower()
    matches: list[tuple[tuple[int, int, str], GraphSearchResult]] = []

    for node_id, attrs in graph.nodes(data=True):
        label = str(attrs.get("label", node_id)).strip()
        if not label:
            continue
        label_lower = label.lower()
        if query not in label_lower:
            continue

        result = GraphSearchResult(
            id=node_id,
            type=attrs.get("type", "COMPANY"),
            label=label,
            risk_level=attrs.get("risk_level"),
            subtitle=_build_search_subtitle(graph, node_id, attrs),
        )
        rank = (
            0 if label_lower.startswith(query) else 1,
            len(label),
            label_lower,
        )
        matches.append((rank, result))

    matches.sort(key=lambda item: item[0])
    return [result for _, result in matches[:limit]]


@router.get("/path")
async def get_path(
    state: State,
    source: str = Query(..., description="Source entity ID"),
    target: str = Query(..., description="Target entity ID"),
):
    """Find shortest path between two entities in the graph."""
    # Neo4j-first
    if settings.neo4j_enabled:
        try:
            result = await find_shortest_path_neo4j(source, target)
            if result:
                return result
        except Exception:
            pass

    # NetworkX fallback
    graph = ensure_runtime_graph(state)
    result = find_shortest_path(graph, source, target)
    if result is None:
        raise HTTPException(status_code=404, detail="No path found between entities")
    return result


@router.get("/entity/{entity_id}", response_model=GraphData)
async def get_entity_neighborhood(
    entity_id: str,
    state: State,
    depth: int = Query(2, ge=1, le=3),
):
    """Get k-hop neighborhood around any entity."""
    # Neo4j-first
    if settings.neo4j_enabled:
        try:
            result = await get_entity_neighborhood_neo4j(entity_id, depth)
            if result and result.get("nodes"):
                return GraphData(
                    nodes=[GraphNode(**n) for n in result["nodes"]],
                    edges=[GraphEdge(**e) for e in result["edges"]],
                )
        except Exception:
            pass

    # NetworkX fallback
    graph = ensure_runtime_graph(state)
    if entity_id not in graph:
        raise HTTPException(status_code=404, detail="Entity not found in graph")

    subgraph = get_tender_subgraph(graph, entity_id, depth=depth)
    return graph_to_frontend_format(subgraph)
