"""
Graph builder using NetworkX.
Constructs the Shadow Graph from procurement data for relationship analysis.
"""

import networkx as nx
from models import (
    Tender, Company, Director, PublicOfficial, Bid,
    GraphNode, GraphEdge, GraphData, NodeType, EdgeType, RiskCategory
)


def build_procurement_graph(
    tenders: dict[str, Tender],
    companies: dict[str, Company],
    directors: dict[str, Director],
    officials: dict[str, PublicOfficial],
    bids: list[Bid],
    tender_risks: dict[str, RiskCategory] = None
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
            address=company.address,
            phone=company.phone,
            registration_date=company.registration_date.isoformat(),
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
                    suspicious=False
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
                    suspicious=True  # Family connections are flagged
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
            value=tender.estimated_value,
            status=tender.status.value,
            risk_level=risk_level.value if isinstance(risk_level, RiskCategory) else risk_level,
        )
        
        # Add AWARDED_BY edge to procurement officer
        if tender.procurement_officer_id and tender.procurement_officer_id in officials:
            G.add_edge(
                tender.id,
                tender.procurement_officer_id,
                relationship=EdgeType.AWARDED_BY.value,
                suspicious=False
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
                suspicious=False
            )
    
    # Detect and add SHARES_ADDRESS edges
    _add_shared_address_edges(G, companies)
    
    # Detect and add SHARES_PHONE edges
    _add_shared_phone_edges(G, companies)
    
    return G


def _add_shared_address_edges(G: nx.Graph, companies: dict[str, Company]):
    """Add edges between companies that share similar addresses."""
    company_list = list(companies.values())
    
    for i, comp1 in enumerate(company_list):
        for comp2 in company_list[i+1:]:
            if _addresses_similar(comp1.address, comp2.address):
                G.add_edge(
                    comp1.id,
                    comp2.id,
                    relationship=EdgeType.SHARES_ADDRESS.value,
                    suspicious=True
                )


def _add_shared_phone_edges(G: nx.Graph, companies: dict[str, Company]):
    """Add edges between companies that share the same phone number."""
    company_list = list(companies.values())
    
    for i, comp1 in enumerate(company_list):
        for comp2 in company_list[i+1:]:
            if _normalize_phone(comp1.phone) == _normalize_phone(comp2.phone):
                G.add_edge(
                    comp1.id,
                    comp2.id,
                    relationship=EdgeType.SHARES_PHONE.value,
                    suspicious=True
                )


def _addresses_similar(addr1: str, addr2: str) -> bool:
    """Check if two addresses are suspiciously similar (same plot/building)."""
    # Normalize and extract plot numbers
    addr1_lower = addr1.lower()
    addr2_lower = addr2.lower()
    
    # Extract plot number if present
    import re
    plot_pattern = r'plot\s*(\d+)'
    
    match1 = re.search(plot_pattern, addr1_lower)
    match2 = re.search(plot_pattern, addr2_lower)
    
    if match1 and match2:
        # Same plot number (ignoring letter suffixes like 45A, 45B)
        return match1.group(1) == match2.group(1)
    
    return False


def _normalize_phone(phone: str) -> str:
    """Normalize phone number for comparison."""
    return ''.join(c for c in phone if c.isdigit())


def find_cartel_clusters(
    G: nx.Graph,
    bids: list[Bid],
    min_co_bids: int = 3
) -> list[set[str]]:
    """
    Find groups of companies that consistently bid together.
    Returns list of company ID sets that form suspected cartels.
    """
    # Build co-bidding matrix
    tender_bidders = {}
    for bid in bids:
        if bid.tender_id not in tender_bidders:
            tender_bidders[bid.tender_id] = set()
        tender_bidders[bid.tender_id].add(bid.company_id)
    
    # Count co-bidding frequency
    co_bid_counts = {}
    for tender_id, bidders in tender_bidders.items():
        bidder_list = list(bidders)
        for i, comp1 in enumerate(bidder_list):
            for comp2 in bidder_list[i+1:]:
                pair = tuple(sorted([comp1, comp2]))
                co_bid_counts[pair] = co_bid_counts.get(pair, 0) + 1
    
    # Build co-bidding graph
    co_bid_graph = nx.Graph()
    for (comp1, comp2), count in co_bid_counts.items():
        if count >= min_co_bids:
            co_bid_graph.add_edge(comp1, comp2, weight=count)
    
    # Find connected components (potential cartels)
    cartels = []
    for component in nx.connected_components(co_bid_graph):
        if len(component) >= 3:  # At least 3 companies to form a cartel
            cartels.append(component)
    
    return cartels


def find_conflict_path(
    G: nx.Graph,
    company_id: str,
    official_id: str
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


def get_tender_subgraph(
    G: nx.Graph,
    tender_id: str,
    depth: int = 2
) -> nx.Graph:
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
        
        nodes.append(GraphNode(
            id=node_id,
            type=node_type,
            label=attrs.get("label", node_id),
            risk_level=risk_level,
            metadata={k: v for k, v in attrs.items() if k not in ["type", "label", "risk_level"]}
        ))
    
    for idx, (source, target, attrs) in enumerate(G.edges(data=True)):
        relationship = EdgeType(attrs.get("relationship", EdgeType.BID_ON.value))
        
        edges.append(GraphEdge(
            id=f"edge-{idx}",
            source=source,
            target=target,
            relationship=relationship,
            suspicious=attrs.get("suspicious", False),
            label=attrs.get("relation_type", None)
        ))
    
    return GraphData(nodes=nodes, edges=edges)
