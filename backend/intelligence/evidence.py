"""
Evidence pack builder for LLM grounding.
Structures all relevant data about a tender into a format
that prevents LLM hallucination.
"""

from dataclasses import dataclass, asdict
from datetime import date
from typing import Optional

import networkx as nx

from models import (
    Tender, Company, Bid, RiskScore, RiskFactor,
)


@dataclass
class EvidencePack:
    """Structured context for LLM grounding."""
    tender_id: str
    tender_summary: dict
    risk_factors: list[dict]
    key_metrics: dict
    graph_paths: list[dict]
    recommendations: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def build_evidence_pack(
    tender: Tender,
    risk: RiskScore,
    bids: list[Bid],
    companies: dict[str, Company],
    graph: nx.Graph,
) -> EvidencePack:
    """Build a structured evidence pack for a tender."""

    # Tender summary
    winning_company = companies.get(tender.awarded_to) if tender.awarded_to else None
    tender_summary = {
        "reference": tender.reference_number,
        "title": tender.title,
        "procuring_entity": tender.procuring_entity,
        "category": tender.category,
        "estimated_value": tender.estimated_value,
        "awarded_amount": tender.awarded_amount,
        "published_date": str(tender.published_date),
        "deadline": str(tender.deadline),
        "status": tender.status.value,
        "winning_company": winning_company.name if winning_company else None,
        "bidder_count": len(bids),
    }

    # Risk factors
    risk_factors = [
        {
            "type": f.type.value,
            "description": f.description,
            "weight": f.weight,
            "evidence": f.evidence,
        }
        for f in risk.factors
    ]

    # Key metrics
    price_deviation = 0.0
    if tender.awarded_amount and tender.estimated_value and tender.estimated_value > 0:
        price_deviation = (
            (tender.awarded_amount - tender.estimated_value) / tender.estimated_value * 100
        )

    company_age_days = None
    if winning_company:
        if isinstance(winning_company.registration_date, date) and isinstance(tender.deadline, date):
            company_age_days = (tender.deadline - winning_company.registration_date).days

    timeline_days = None
    if isinstance(tender.published_date, date) and isinstance(tender.deadline, date):
        timeline_days = (tender.deadline - tender.published_date).days

    bid_amounts = [b.amount for b in bids]
    key_metrics = {
        "price_deviation_pct": round(price_deviation, 1),
        "company_age_days": company_age_days,
        "timeline_days": timeline_days,
        "bidder_count": len(bids),
        "bid_range": {
            "min": min(bid_amounts) if bid_amounts else None,
            "max": max(bid_amounts) if bid_amounts else None,
        },
        "risk_score": risk.overall,
        "risk_category": risk.category.value,
    }

    # Graph paths (connections between winner and officials)
    # Uses NetworkX graph that is always available in AppState.
    # The /api/graph/path endpoint serves real-time Neo4j paths;
    # here we pre-compute the path once for LLM context.
    graph_paths = []
    if tender.awarded_to and tender.procurement_officer_id:
        if tender.awarded_to in graph and tender.procurement_officer_id in graph:
            try:
                path = nx.shortest_path(graph, tender.awarded_to, tender.procurement_officer_id)
                path_details = [
                    {
                        "id": nid,
                        "type": graph.nodes.get(nid, {}).get("type", "UNKNOWN"),
                        "label": graph.nodes.get(nid, {}).get("label", nid),
                    }
                    for nid in path
                ]
                graph_paths.append({
                    "from": path_details[0]["label"],
                    "to": path_details[-1]["label"],
                    "via": [n["label"] for n in path_details[1:-1]],
                    "length": len(path) - 1,
                })
            except nx.NetworkXNoPath:
                pass

    # Recommendations
    recommendations = []
    if risk.recommendation:
        recommendations = [r.strip() for r in risk.recommendation.split("\u2022") if r.strip()]

    return EvidencePack(
        tender_id=tender.id,
        tender_summary=tender_summary,
        risk_factors=risk_factors,
        key_metrics=key_metrics,
        graph_paths=graph_paths,
        recommendations=recommendations,
    )


async def build_evidence_pack_async(
    tender: Tender,
    risk: RiskScore,
    bids: list[Bid],
    companies: dict[str, Company],
    graph: nx.Graph,
) -> EvidencePack:
    """
    Build an evidence pack with Neo4j-first path resolution.
    Falls back to the sync NetworkX version on failure.

    Use this variant in async routes (e.g. /explain) so the conflict-of-interest
    path uses Neo4j's index-free adjacency instead of an in-memory BFS.
    """
    from config import settings
    from graph.neo4j_driver import check_neo4j_health
    from graph.neo4j_communities import find_shortest_path_neo4j

    # Start with the synchronous base pack (no graph paths yet)
    pack = build_evidence_pack(tender, risk, bids, companies, graph)

    # Attempt to upgrade the graph paths using Neo4j
    if (
        settings.neo4j_enabled
        and tender.awarded_to
        and tender.procurement_officer_id
        and not pack.graph_paths  # Only hit Neo4j if NetworkX found nothing
    ):
        try:
            health = await check_neo4j_health()
            if health["status"] == "healthy":
                path_result = await find_shortest_path_neo4j(
                    tender.awarded_to, tender.procurement_officer_id
                )
                if path_result and path_result.get("nodes"):
                    nodes = path_result["nodes"]
                    pack.graph_paths = [
                        {
                            "from": nodes[0]["label"],
                            "to": nodes[-1]["label"],
                            "via": [n["label"] for n in nodes[1:-1]],
                            "length": path_result["length"],
                        }
                    ]
        except Exception:
            pass  # Keep the NetworkX result (which may be empty)

    return pack
