"""
Community detection for procurement graph.
Uses Louvain algorithm to identify suspicious bidding communities.
"""

import networkx as nx
from collections import defaultdict
from dataclasses import dataclass

from models import Company, Bid, Tender
from models import AddressQuality
from connectors.normalize import classify_address
from graph.normalization import normalize_address_key, normalize_phone, is_generic_phone


@dataclass
class Cluster:
    """A detected community of related companies."""

    id: str
    company_ids: list[str]
    company_names: list[str]
    size: int
    suspicion_score: float
    shared_attributes: dict
    co_bid_count: int
    win_pattern: dict


def detect_communities(
    G: nx.Graph,
    tenders: dict[str, Tender],
    bids: list[Bid],
    companies: dict[str, Company],
    min_cluster_size: int = 2,
) -> list[Cluster]:
    """
    Detect suspicious bidding communities using Louvain algorithm.
    Returns clusters ranked by suspicion score.
    """
    # Build co-bidding graph (companies only)
    co_bid_graph = _build_co_bidding_graph(bids)

    if co_bid_graph.number_of_nodes() < 2:
        return []

    # Detect communities via Louvain
    try:
        communities = nx.community.louvain_communities(
            co_bid_graph, resolution=1.0, seed=42
        )
    except Exception:
        # Fallback to connected components
        communities = list(nx.connected_components(co_bid_graph))

    # Score and build cluster objects
    clusters = []
    for idx, community in enumerate(communities):
        if len(community) < min_cluster_size:
            continue

        company_ids = list(community)
        company_names = [companies[cid].name for cid in company_ids if cid in companies]

        shared = _find_shared_attributes(G, company_ids, companies)
        co_bids = _count_co_bids(bids, set(company_ids))
        wins = _analyze_win_pattern(tenders, bids, set(company_ids), companies)
        suspicious_edge_count = _count_suspicious_edges(G, company_ids)
        score = calculate_suspicion_score(
            shared, co_bids, len(company_ids), suspicious_edge_count
        )

        clusters.append(
            Cluster(
                id=f"cluster-{idx}",
                company_ids=company_ids,
                company_names=company_names,
                size=len(company_ids),
                suspicion_score=score,
                shared_attributes=shared,
                co_bid_count=co_bids,
                win_pattern=wins,
            )
        )

    return sorted(clusters, key=lambda c: c.suspicion_score, reverse=True)


def get_cartel_sets(clusters: list[Cluster]) -> list[set[str]]:
    """
    Extract company ID sets from Louvain clusters for the rule engine's cartel check.
    Returns list of sets, each containing company IDs in a community.
    """
    return [set(c.company_ids) for c in clusters]


def get_cluster_subgraph(
    G: nx.Graph,
    company_ids: list[str],
    include_tenders: bool = True,
    include_officials: bool = True,
) -> nx.Graph:
    """
    Extract a subgraph for a specific cluster.
    Includes the companies and optionally their connected tenders/officials.
    """
    nodes = set(company_ids)

    for cid in company_ids:
        if cid not in G:
            continue
        for neighbor in G.neighbors(cid):
            attrs = G.nodes.get(neighbor, {})
            ntype = attrs.get("type", "")
            if ntype == "DIRECTOR":
                nodes.add(neighbor)
            elif ntype == "TENDER" and include_tenders:
                nodes.add(neighbor)
            elif ntype == "OFFICIAL" and include_officials:
                nodes.add(neighbor)

    return G.subgraph(nodes).copy()


def find_shortest_path(
    G: nx.Graph,
    source_id: str,
    target_id: str,
) -> dict | None:
    """
    Find shortest path between two entities.
    Returns path details or None if no path exists.
    """
    if source_id not in G or target_id not in G:
        return None

    try:
        path = nx.shortest_path(G, source_id, target_id)
    except nx.NetworkXNoPath:
        return None

    # Build path with node/edge details
    path_nodes = []
    for nid in path:
        attrs = G.nodes[nid]
        path_nodes.append(
            {
                "id": nid,
                "type": attrs.get("type", "UNKNOWN"),
                "label": attrs.get("label", nid),
            }
        )

    path_edges = []
    for i in range(len(path) - 1):
        edge_data = G.edges[path[i], path[i + 1]]
        path_edges.append(
            {
                "source": path[i],
                "target": path[i + 1],
                "relationship": edge_data.get("relationship", "UNKNOWN"),
                "suspicious": edge_data.get("suspicious", False),
            }
        )

    return {
        "nodes": path_nodes,
        "edges": path_edges,
        "length": len(path) - 1,
    }


# --- Private helpers ---


def _build_co_bidding_graph(bids: list[Bid]) -> nx.Graph:
    """Build a weighted graph of companies that bid on the same tenders."""
    tender_bidders = defaultdict(set)
    for b in bids:
        tender_bidders[b.tender_id].add(b.company_id)

    G = nx.Graph()
    co_bid_counts = defaultdict(int)
    for bidders in tender_bidders.values():
        bidder_list = sorted(bidders)
        for i, c1 in enumerate(bidder_list):
            for c2 in bidder_list[i + 1 :]:
                co_bid_counts[(c1, c2)] += 1

    for (c1, c2), count in co_bid_counts.items():
        if count >= 2:
            G.add_edge(c1, c2, weight=count)

    return G


def _find_shared_attributes(
    G: nx.Graph,
    company_ids: list[str],
    companies: dict[str, Company],
) -> dict:
    """Find shared addresses, phones, and directors within a cluster."""
    shared = {"addresses": [], "phones": [], "directors": []}

    cluster_companies = [companies[cid] for cid in company_ids if cid in companies]

    # Shared addresses
    addresses = defaultdict(lambda: {"address": "", "companies": []})
    for c in cluster_companies:
        addr = c.physical_address or c.address
        if classify_address(addr) != AddressQuality.SPECIFIC:
            continue
        addr_key = normalize_address_key(addr)
        if not addr_key:
            continue
        if not addresses[addr_key]["address"]:
            addresses[addr_key]["address"] = addr
        addresses[addr_key]["companies"].append(c.name)
    for item in addresses.values():
        if len(item["companies"]) > 1:
            shared["addresses"].append(item)

    # Shared phones
    phones = defaultdict(list)
    for c in cluster_companies:
        phone_key = normalize_phone(c.phone)
        if not phone_key or is_generic_phone(c.phone):
            continue
        phones[phone_key].append(c.name)
    for phone, names in phones.items():
        if len(names) > 1:
            shared["phones"].append({"phone": phone, "companies": names})

    # Shared directors
    director_companies = defaultdict(list)
    for c in cluster_companies:
        for did in c.director_ids:
            director_companies[did].append(c.name)
    for did, names in director_companies.items():
        if len(names) > 1:
            shared["directors"].append({"director_id": did, "companies": names})

    return shared


def _count_co_bids(bids: list[Bid], company_ids: set[str]) -> int:
    """Count tenders where multiple cluster members bid."""
    tender_bidders = defaultdict(set)
    for b in bids:
        if b.company_id in company_ids:
            tender_bidders[b.tender_id].add(b.company_id)
    return sum(1 for bidders in tender_bidders.values() if len(bidders) >= 2)


def _analyze_win_pattern(
    tenders: dict[str, Tender],
    bids: list[Bid],
    company_ids: set[str],
    companies: dict[str, Company],
) -> dict:
    bid_counts = defaultdict(int)
    total_bids = 0
    for b in bids:
        if b.company_id in company_ids:
            total_bids += 1
            bid_counts[b.company_id] += 1

    award_counts = defaultdict(int)
    total_awards = 0
    for tender in tenders.values():
        awarded_to = tender.awarded_to
        if awarded_to in company_ids:
            total_awards += 1
            award_counts[awarded_to] += 1

    return {
        "total_bids": total_bids,
        "bids_per_company": {
            companies[cid].name if cid in companies else cid: count
            for cid, count in bid_counts.items()
        },
        "total_awards": total_awards,
        "awards_per_company": {
            companies[cid].name if cid in companies else cid: count
            for cid, count in award_counts.items()
        },
    }


def calculate_suspicion_score(
    shared: dict,
    co_bid_count: int,
    cluster_size: int,
    suspicious_edge_count: int,
) -> float:
    """
    Calculate a 0-100 suspicion score for a cluster.
    Factors: shared attributes, co-bidding frequency, suspicious edges.
    """
    score = 0.0

    # Shared attributes (up to 30 points)
    score += min(15, len(shared.get("addresses", [])) * 10)
    score += min(10, len(shared.get("phones", [])) * 10)
    score += min(5, len(shared.get("directors", [])) * 5)

    # Co-bidding frequency (up to 30 points)
    score += min(30, co_bid_count * 5)

    # Suspicious edges in main graph (up to 20 points)
    score += min(20, suspicious_edge_count * 5)

    # Cluster size bonus (up to 20 points)
    score += min(20, (cluster_size - 1) * 5)

    return min(100, score)


def _count_suspicious_edges(G: nx.Graph, company_ids: list[str]) -> int:
    suspicious_count = 0
    for cid in company_ids:
        if cid in G:
            for _, _, data in G.edges(cid, data=True):
                if data.get("suspicious", False):
                    suspicious_count += 1
    return suspicious_count
