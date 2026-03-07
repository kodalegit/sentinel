"""
Feature engineering for procurement anomaly detection.
Extracts tender-level and graph-level features for the Isolation Forest model.
"""

import numpy as np
import pandas as pd
import networkx as nx
from datetime import date, timedelta
from collections import defaultdict, deque

from models import Tender, Company, Bid, TenderStatus


def _precompute_official_distances(graph: nx.Graph) -> dict[str, int]:
    """
    Pre-compute shortest distance from every node to the nearest OFFICIAL node.
    Uses multi-source BFS from all officials — O(V + E) total.
    """
    officials = [
        n for n, attrs in graph.nodes(data=True) if attrs.get("type") == "OFFICIAL"
    ]
    if not officials:
        return {}

    distances: dict[str, int] = {}

    queue = deque((src, 0) for src in officials)
    while queue:
        node, dist = queue.popleft()
        if node in distances:
            continue
        distances[node] = dist
        for neighbor in graph.neighbors(node):
            if neighbor not in distances:
                queue.append((neighbor, dist + 1))

    return distances


def materialize_company_graph_features(graph: nx.Graph) -> dict[str, dict[str, int]]:
    official_distances = _precompute_official_distances(graph)
    company_features: dict[str, dict[str, int]] = {}

    for node_id, attrs in graph.nodes(data=True):
        if attrs.get("type") != "COMPANY":
            continue

        neighbors_2hop = nx.single_source_shortest_path_length(graph, node_id, cutoff=2)
        company_features[node_id] = {
            "graph_degree": int(graph.degree(node_id)),
            "suspicious_edges": int(
                sum(
                    1
                    for _, _, edge_attrs in graph.edges(node_id, data=True)
                    if edge_attrs.get("suspicious", False)
                )
            ),
            "official_distance": int(official_distances.get(node_id, 99)),
            "community_size": int(
                sum(
                    1
                    for neighbor_id in neighbors_2hop
                    if graph.nodes[neighbor_id].get("type") == "COMPANY"
                )
            ),
        }

    return company_features


def extract_tender_features(
    tenders: dict[str, Tender],
    companies: dict[str, Company],
    bids: list[Bid],
    graph: nx.Graph,
    bids_by_tender: dict[str, list[Bid]] | None = None,
    company_graph_features: dict[str, dict[str, int]] | None = None,
) -> pd.DataFrame:
    """
    Extract numerical features for each tender.
    Returns a DataFrame indexed by tender_id.

    All features are category-agnostic (ratios / natural units) so a single
    Isolation Forest works across procurement domains.
    """
    # Use pre-computed bids_by_tender if provided, otherwise build it
    if bids_by_tender is None:
        bids_by_tender = defaultdict(list)
        for b in bids:
            bids_by_tender[b.tender_id].append(b)

    if company_graph_features is None:
        company_graph_features = materialize_company_graph_features(graph)

    # Category-level stats for z-scores
    category_values = defaultdict(list)
    for t in tenders.values():
        if t.awarded_amount:
            category_values[t.category].append(t.awarded_amount)

    category_stats = {}
    for cat, values in category_values.items():
        arr = np.array(values)
        category_stats[cat] = {
            "mean": float(np.mean(arr)),
            "std": float(np.std(arr)) if len(arr) > 1 else 1.0,
        }

    # Company win history
    company_bids = defaultdict(int)
    company_wins = defaultdict(int)
    for t in tenders.values():
        for b in bids_by_tender.get(t.id, []):
            company_bids[b.company_id] += 1
        if t.awarded_to:
            company_wins[t.awarded_to] += 1

    rows = []
    for tid, tender in tenders.items():
        tender_bids = bids_by_tender.get(tid, [])
        bid_amounts = [b.amount for b in tender_bids]
        est = tender.estimated_value or 0.0

        # Price features
        price_ratio = (
            tender.awarded_amount / est if tender.awarded_amount and est > 0 else 0.0
        )

        stats = category_stats.get(tender.category, {"mean": 0, "std": 1})
        price_zscore = (
            (tender.awarded_amount - stats["mean"]) / stats["std"]
            if tender.awarded_amount and stats["std"] > 0
            else 0.0
        )

        # Timeline features
        pub = tender.published_date
        dl = tender.deadline
        timeline_days = (
            (dl - pub).days if isinstance(pub, date) and isinstance(dl, date) else 30
        )

        # Competition features (ratios of estimated_value — category-agnostic)
        bidder_count = len(tender_bids)
        raw_spread = (
            max(bid_amounts) - min(bid_amounts) if len(bid_amounts) >= 2 else 0.0
        )
        bid_spread_ratio = raw_spread / est if est > 0 else 0.0

        winner_margin_ratio = 0.0
        if tender.awarded_to and len(bid_amounts) >= 2:
            winning_bid = next(
                (b.amount for b in tender_bids if b.company_id == tender.awarded_to),
                None,
            )
            if winning_bid is not None:
                other_bids = sorted([a for a in bid_amounts if a != winning_bid])
                if other_bids:
                    winner_margin_ratio = (
                        (other_bids[0] - winning_bid) / est if est > 0 else 0.0
                    )

        # Vendor maturity
        company_age_days = 0
        win_rate = 0.0
        if tender.awarded_to and tender.awarded_to in companies:
            company = companies[tender.awarded_to]
            if isinstance(company.registration_date, date) and isinstance(dl, date):
                company_age_days = (dl - company.registration_date).days
            total_bids = company_bids.get(tender.awarded_to, 1)
            wins = company_wins.get(tender.awarded_to, 0)
            win_rate = wins / total_bids if total_bids > 0 else 0.0

        # Graph features
        graph_degree = 0
        suspicious_edges = 0
        official_distance = 99
        community_size = 0

        if tender.awarded_to:
            graph_features = company_graph_features.get(tender.awarded_to, {})
            graph_degree = graph_features.get("graph_degree", 0)
            suspicious_edges = graph_features.get("suspicious_edges", 0)
            official_distance = min(graph_features.get("official_distance", 99), 10)
            community_size = graph_features.get("community_size", 0)

        rows.append(
            {
                "tender_id": tid,
                "price_ratio": price_ratio,
                "price_zscore": price_zscore,
                "timeline_days": timeline_days,
                "bidder_count": bidder_count,
                "bid_spread_ratio": bid_spread_ratio,
                "winner_margin_ratio": winner_margin_ratio,
                "company_age_days": company_age_days,
                "win_rate": win_rate,
                "graph_degree": graph_degree,
                "suspicious_edges": suspicious_edges,
                "official_distance": min(official_distance, 10),
                "community_size": community_size,
            }
        )

    df = pd.DataFrame(rows).set_index("tender_id")
    return df


FEATURE_COLUMNS = [
    "price_ratio",
    "price_zscore",
    "timeline_days",
    "bidder_count",
    "bid_spread_ratio",
    "winner_margin_ratio",
    "company_age_days",
    "win_rate",
    "graph_degree",
    "suspicious_edges",
    "official_distance",
    "community_size",
]
