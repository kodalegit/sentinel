"""
Graph builder using NetworkX.
Constructs the Shadow Graph from procurement data for relationship analysis.
"""

import re

import networkx as nx
from models import (
    Tender,
    Company,
    Director,
    PublicOfficial,
    Bid,
    GraphNode,
    GraphEdge,
    GraphData,
    NodeType,
    EdgeType,
    RiskCategory,
    AddressQuality,
)
from connectors.normalize import classify_address
from graph.normalization import (
    normalize_phone,
    normalize_address_key,
    is_generic_email,
    is_generic_phone,
    MAX_SHARED_EDGES_PER_COMPANY,
    MAX_GROUP_SIZE_ADDRESS,
    MAX_GROUP_SIZE_PHONE,
    MAX_GROUP_SIZE_EMAIL,
)


def build_procurement_graph(
    tenders: dict[str, Tender],
    companies: dict[str, Company],
    directors: dict[str, Director],
    officials: dict[str, PublicOfficial],
    bids: list[Bid],
    tender_risks: dict[str, RiskCategory] = None,
) -> nx.Graph:
    """
    Build a NetworkX graph from procurement data.

    Node types: COMPANY, DIRECTOR, OFFICIAL, TENDER
    Edge types: DIRECTOR_OF, BID_ON, WON, AWARDED_BY, RELATED_TO, SHARES_ADDRESS, SHARES_PHONE
    """
    G = nx.Graph()
    tender_risks = tender_risks or {}

    # Add company nodes
    for company in companies.values():
        G.add_node(
            company.id,
            type=NodeType.COMPANY.value,
            label=company.name,
            address=company.address or company.physical_address,
            phone=company.phone,
            registration_date=(
                company.registration_date.isoformat()
                if company.registration_date
                else None
            ),
            contact_email=company.contact_email,
            supplier_type=company.supplier_type,
            source_system=company.source_system,
        )

    # Add director nodes
    for director in directors.values():
        G.add_node(
            director.id,
            type=NodeType.DIRECTOR.value,
            label=director.name,
        )
        # Add DIRECTOR_OF edges
        for company_id in director.company_ids:
            if company_id in companies:
                G.add_edge(
                    director.id,
                    company_id,
                    relationship=EdgeType.DIRECTOR_OF.value,
                    suspicious=False,
                )

    # Add official nodes
    for official in officials.values():
        G.add_node(
            official.id,
            type=NodeType.OFFICIAL.value,
            label=official.name,
            department=official.department,
            position=official.position,
        )
        # Add RELATED_TO edges for family/business connections
        for person_id, relationship in official.related_persons.items():
            if person_id in directors:
                G.add_edge(
                    official.id,
                    person_id,
                    relationship=EdgeType.RELATED_TO.value,
                    relation_type=relationship.value,
                    suspicious=True,  # Family connections are flagged
                )

    # Add tender nodes
    for tender in tenders.values():
        risk_level = tender_risks.get(tender.id, RiskCategory.LOW)
        G.add_node(
            tender.id,
            type=NodeType.TENDER.value,
            label=tender.title[:50] + "..." if len(tender.title) > 50 else tender.title,
            full_title=tender.title,
            procuring_entity=tender.procuring_entity,
            value=tender.estimated_value or 0,
            status=tender.status.value,
            risk_level=(
                risk_level.value if isinstance(risk_level, RiskCategory) else risk_level
            ),
        )

        # Add AWARDED_BY edge to procurement officer
        if tender.procurement_officer_id and tender.procurement_officer_id in officials:
            G.add_edge(
                tender.id,
                tender.procurement_officer_id,
                relationship=EdgeType.AWARDED_BY.value,
                suspicious=False,
            )

    # Add bid edges (BID_ON and WON)
    for bid in bids:
        if bid.company_id in companies and bid.tender_id in tenders:
            tender = tenders[bid.tender_id]
            is_winner = tender.awarded_to == bid.company_id

            G.add_edge(
                bid.company_id,
                bid.tender_id,
                relationship=EdgeType.WON.value if is_winner else EdgeType.BID_ON.value,
                amount=bid.amount,
                suspicious=False,
            )

    # Detect and add SHARES_ADDRESS edges
    _add_shared_address_edges(G, companies)

    # Detect and add SHARES_PHONE edges
    _add_shared_phone_edges(G, companies)

    # Detect and add SHARES_EMAIL edges
    _add_shared_email_edges(G, companies)

    return G


def _add_shared_address_edges(G: nx.Graph, companies: dict[str, Company]):
    """Add edges between companies that share similar addresses.
    Uses hash-based grouping for O(n) performance instead of O(n²) pairwise comparison.
    Excludes placeholder addresses (e.g., 'PO Box 123') which are common
    defaults in Kenya's e-GP system and would create false connections."""
    from collections import defaultdict

    # Group companies by normalized address key
    address_groups: dict[str, list[tuple[str, str, AddressQuality]]] = defaultdict(list)

    for company in companies.values():
        addr = company.physical_address or company.address
        if not addr:
            continue
        quality = classify_address(addr)
        if quality != AddressQuality.SPECIFIC:
            continue

        addr_key = normalize_address_key(addr)
        if addr_key:
            address_groups[addr_key].append((company.id, addr, quality))

    # Track edges per company to enforce limit
    edge_count: dict[str, int] = defaultdict(int)

    # Create edges within each group
    for group in address_groups.values():
        if len(group) < 2:
            continue
        # Limit group size to prevent explosion from common addresses
        if len(group) > MAX_GROUP_SIZE_ADDRESS:
            continue  # Skip overly common addresses (likely vague)

        for i, (id1, addr1, q1) in enumerate(group):
            if edge_count[id1] >= MAX_SHARED_EDGES_PER_COMPANY:
                continue
            for id2, addr2, q2 in group[i + 1 :]:
                if edge_count[id2] >= MAX_SHARED_EDGES_PER_COMPANY:
                    continue
                G.add_edge(
                    id1,
                    id2,
                    relationship=EdgeType.SHARES_ADDRESS.value,
                    suspicious=True,
                    confidence="high",
                )
                edge_count[id1] += 1
                edge_count[id2] += 1


def _add_shared_phone_edges(G: nx.Graph, companies: dict[str, Company]):
    """Add edges between companies that share the same phone number.
    Uses hash-based grouping for O(n) performance."""
    from collections import defaultdict

    # Group companies by normalized phone
    phone_groups: dict[str, list[str]] = defaultdict(list)

    for company in companies.values():
        phone = normalize_phone(company.phone)
        if phone and not is_generic_phone(company.phone):
            phone_groups[phone].append(company.id)

    # Track edges per company to enforce limit
    edge_count: dict[str, int] = defaultdict(int)

    # Create edges within each group
    for group in phone_groups.values():
        if len(group) < 2:
            continue
        # Skip overly common phones (likely placeholder/default)
        if len(group) > MAX_GROUP_SIZE_PHONE:
            continue

        for i, id1 in enumerate(group):
            if edge_count[id1] >= MAX_SHARED_EDGES_PER_COMPANY:
                continue
            for id2 in group[i + 1 :]:
                if edge_count[id2] >= MAX_SHARED_EDGES_PER_COMPANY:
                    continue
                G.add_edge(
                    id1,
                    id2,
                    relationship=EdgeType.SHARES_PHONE.value,
                    suspicious=True,
                )
                edge_count[id1] += 1
                edge_count[id2] += 1


def _add_shared_email_edges(G: nx.Graph, companies: dict[str, Company]):
    """Add edges between companies that share the same contact email.
    Uses hash-based grouping for O(n) performance."""
    from collections import defaultdict

    # Group companies by normalized email
    email_groups: dict[str, list[str]] = defaultdict(list)

    for company in companies.values():
        email = company.contact_email
        if email:
            normalized = email.strip().lower()
            # Skip generic/placeholder emails
            if normalized and "@" in normalized and not is_generic_email(normalized):
                email_groups[normalized].append(company.id)

    # Track edges per company to enforce limit
    edge_count: dict[str, int] = defaultdict(int)

    # Create edges within each group
    for group in email_groups.values():
        if len(group) < 2:
            continue
        # Skip overly common emails
        if len(group) > MAX_GROUP_SIZE_EMAIL:
            continue

        for i, id1 in enumerate(group):
            if edge_count[id1] >= MAX_SHARED_EDGES_PER_COMPANY:
                continue
            for id2 in group[i + 1 :]:
                if edge_count[id2] >= MAX_SHARED_EDGES_PER_COMPANY:
                    continue
                G.add_edge(
                    id1,
                    id2,
                    relationship=EdgeType.SHARES_EMAIL.value,
                    suspicious=True,
                )
                edge_count[id1] += 1
                edge_count[id2] += 1


def find_conflict_path(
    G: nx.Graph, company_id: str, official_id: str
) -> list[str] | None:
    """
    Find path between a company and an official through directors/relationships.
    Returns the path if found, None otherwise.
    """
    try:
        path = nx.shortest_path(G, company_id, official_id)
        return path
    except nx.NetworkXNoPath:
        return None


def get_tender_subgraph(G: nx.Graph, tender_id: str, depth: int = 2) -> nx.Graph:
    """
    Extract a subgraph centered on a specific tender.
    Includes all nodes within `depth` hops of the tender.
    """
    if tender_id not in G:
        return nx.Graph()

    # Get all nodes within depth hops
    nodes = {tender_id}
    current_frontier = {tender_id}

    for _ in range(depth):
        next_frontier = set()
        for node in current_frontier:
            next_frontier.update(G.neighbors(node))
        nodes.update(next_frontier)
        current_frontier = next_frontier

    return G.subgraph(nodes).copy()


def graph_to_frontend_format(G: nx.Graph) -> GraphData:
    """Convert NetworkX graph to frontend-compatible format for React Flow."""
    nodes = []
    edges = []

    for node_id, attrs in G.nodes(data=True):
        node_type = NodeType(attrs.get("type", NodeType.COMPANY.value))
        risk_level = None
        if "risk_level" in attrs:
            try:
                risk_level = RiskCategory(attrs["risk_level"])
            except ValueError:
                pass

        nodes.append(
            GraphNode(
                id=node_id,
                type=node_type,
                label=attrs.get("label", node_id),
                risk_level=risk_level,
                metadata={
                    k: v
                    for k, v in attrs.items()
                    if k not in ["type", "label", "risk_level"]
                },
            )
        )

    for idx, (source, target, attrs) in enumerate(G.edges(data=True)):
        relationship = EdgeType(attrs.get("relationship", EdgeType.BID_ON.value))

        edges.append(
            GraphEdge(
                id=f"edge-{idx}",
                source=source,
                target=target,
                relationship=relationship,
                suspicious=attrs.get("suspicious", False),
                label=attrs.get("relation_type", None),
            )
        )

    return GraphData(nodes=nodes, edges=edges)
