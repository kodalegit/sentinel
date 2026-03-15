"""
Evidence pack builder for LLM grounding.
Structures all relevant data about a tender into a format
that prevents LLM hallucination.
"""

from dataclasses import dataclass, asdict
from datetime import date
from typing import Optional, Any

import networkx as nx

from models import (
    Tender,
    Company,
    Bid,
    RiskScore,
    RiskFactor,
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
            (tender.awarded_amount - tender.estimated_value)
            / tender.estimated_value
            * 100
        )

    company_age_days = None
    if winning_company:
        if isinstance(winning_company.registration_date, date) and isinstance(
            tender.deadline, date
        ):
            company_age_days = (
                tender.deadline - winning_company.registration_date
            ).days

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
                path = nx.shortest_path(
                    graph, tender.awarded_to, tender.procurement_officer_id
                )
                path_details = [
                    {
                        "id": nid,
                        "type": graph.nodes.get(nid, {}).get("type", "UNKNOWN"),
                        "label": graph.nodes.get(nid, {}).get("label", nid),
                    }
                    for nid in path
                ]
                graph_paths.append(
                    {
                        "from": path_details[0]["label"],
                        "to": path_details[-1]["label"],
                        "via": [n["label"] for n in path_details[1:-1]],
                        "length": len(path) - 1,
                    }
                )
            except nx.NetworkXNoPath:
                pass

    # Recommendations
    recommendations = []
    if risk.recommendation:
        recommendations = [
            r.strip() for r in risk.recommendation.split("\u2022") if r.strip()
        ]

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


def _truncate_text(value: Any, limit: int = 240) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _format_context_block(
    marker: int,
    title: str,
    category: str,
    body_lines: list[str],
    page: Optional[int] = None,
    source_url: Optional[str] = None,
) -> str:
    lines = [f"[{marker}] {title}", f"Category: {category}"]
    if page is not None:
        lines.append(f"Page: {page}")
    if source_url:
        lines.append(f"Source URL: {source_url}")
    lines.extend(line for line in body_lines if line)
    return "\n".join(lines)


def _register_context_source(
    citation_registry: Any,
    *,
    doc_id: str,
    title: str,
    category: str,
    excerpt: str,
    chunk_id: str,
    source_url: Optional[str] = None,
    page: Optional[int] = None,
):
    return citation_registry.register(
        doc_id=doc_id,
        title=title,
        source_url=source_url,
        category=category,
        excerpt=excerpt,
        page=page,
        chunk_id=chunk_id,
    )


def _build_case_record_block(
    case_record: dict, citation_registry: Any
) -> tuple[str, int]:
    title = case_record.get("title") or "Case Record"
    summary = case_record.get("summary") or "No case summary recorded."
    artifact = _register_context_source(
        citation_registry,
        doc_id=case_record.get("id") or "case-record",
        title=f"Case Record: {title}",
        category="CASE_RECORD",
        excerpt=_truncate_text(summary),
        chunk_id=f"case:{case_record.get('id') or 'record'}",
    )
    block = _format_context_block(
        artifact.marker,
        artifact.title,
        artifact.category,
        [
            f"Status: {case_record.get('status') or 'UNKNOWN'}",
            f"Priority: {case_record.get('priority') or 'UNKNOWN'}",
            f"Summary: {summary}",
        ],
        page=artifact.page,
        source_url=artifact.source_url,
    )
    return block, artifact.marker


def _build_tender_block(
    tender_id: Optional[str],
    app_state: Any,
    citation_registry: Any,
) -> tuple[Optional[str], Optional[int]]:
    if not tender_id or not app_state or tender_id not in app_state.tenders:
        return None, None
    tender = app_state.tenders[tender_id]
    risk = app_state.risk_scores.get(tender_id)
    title = f"Tender: {tender.reference_number} - {tender.title}"
    excerpt = _truncate_text(tender.title)
    artifact = _register_context_source(
        citation_registry,
        doc_id=tender_id,
        title=title,
        category="TENDER",
        excerpt=excerpt,
        chunk_id=f"tender:{tender_id}",
    )
    estimated_value = (
        f"KES {tender.estimated_value:,.0f}"
        if tender.estimated_value is not None
        else "Unknown"
    )
    awarded_amount = (
        f"KES {tender.awarded_amount:,.0f}"
        if tender.awarded_amount is not None
        else "Unknown"
    )
    body_lines = [
        f"Reference Number: {tender.reference_number}",
        f"Procuring Entity: {tender.procuring_entity}",
        f"Category: {tender.category}",
        f"Status: {tender.status.value}",
        f"Estimated Value: {estimated_value}",
        f"Awarded Amount: {awarded_amount}",
    ]
    if risk:
        body_lines.append(f"Risk Score: {risk.overall}/100 ({risk.category.value})")
    return (
        _format_context_block(
            artifact.marker,
            artifact.title,
            artifact.category,
            body_lines,
            page=artifact.page,
            source_url=artifact.source_url,
        ),
        artifact.marker,
    )


def _build_risk_factor_blocks(
    tender_id: Optional[str],
    app_state: Any,
    citation_registry: Any,
) -> list[tuple[str, int]]:
    if not tender_id or not app_state:
        return []
    risk = app_state.risk_scores.get(tender_id)
    if not risk:
        return []
    blocks: list[tuple[str, int]] = []
    for factor in risk.factors:
        artifact = _register_context_source(
            citation_registry,
            doc_id=tender_id,
            title=f"Risk Factor: {factor.type.value}",
            category="RISK_FACTOR",
            excerpt=_truncate_text(factor.description),
            chunk_id=f"risk_factor:{tender_id}:{factor.type.value}",
        )
        evidence_lines = [f"- {item}" for item in factor.evidence[:5]]
        block = _format_context_block(
            artifact.marker,
            artifact.title,
            artifact.category,
            [
                f"Weight: {factor.weight}",
                f"Description: {factor.description}",
                "Evidence:",
                *evidence_lines,
            ],
            page=artifact.page,
            source_url=artifact.source_url,
        )
        blocks.append((block, artifact.marker))
    return blocks


def _build_link_block(
    link: Any, citation_registry: Any
) -> tuple[Optional[str], Optional[int]]:
    metadata = getattr(link, "link_metadata", None) or {}
    evidence_type = str(getattr(link, "evidence_type", "EVIDENCE") or "EVIDENCE")
    reference_id = str(getattr(link, "reference_id", "") or "")
    label = str(getattr(link, "label", "Evidence") or "Evidence")

    title = label
    category = evidence_type
    chunk_id = f"case_evidence:{evidence_type.lower()}:{reference_id or label}"
    page = metadata.get("page") or metadata.get("page_number")
    source_url = metadata.get("source_url")
    excerpt = _truncate_text(
        metadata.get("description")
        or metadata.get("excerpt")
        or metadata.get("summary")
        or label
    )

    body_lines: list[str] = []
    if evidence_type == "TENDER":
        chunk_id = f"tender:{reference_id}"
        body_lines = [
            f"Reference Number: {metadata.get('reference_number') or reference_id or 'Unknown'}",
            f"Procuring Entity: {metadata.get('procuring_entity') or 'Unknown'}",
            (
                f"Estimated Value: KES {metadata.get('estimated_value'):,.0f}"
                if metadata.get("estimated_value") is not None
                else "Estimated Value: Unknown"
            ),
        ]
    elif evidence_type == "RISK_FACTOR":
        tender_id, _, factor_key = reference_id.partition(":")
        factor_type = metadata.get("type") or reference_id.split(":")[-1] or "UNKNOWN"
        if tender_id and factor_key:
            reference_id = tender_id
            chunk_id = f"risk_factor:{tender_id}:{factor_key}"
        body_lines = [
            f"Type: {factor_type}",
            f"Weight: {metadata.get('weight') if metadata.get('weight') is not None else 'Unknown'}",
            f"Description: {metadata.get('description') or label}",
            "Evidence:",
            *[f"- {item}" for item in (metadata.get("evidence") or [])[:5]],
        ]
    elif evidence_type == "GRAPH_PATH":
        chunk_id = f"graph_path:{reference_id}"
        body_lines = [
            f"Path: {metadata.get('path') or label}",
            f"Length: {metadata.get('length') if metadata.get('length') is not None else 'Unknown'}",
            f"Notes: {metadata.get('description') or metadata.get('summary') or 'No additional notes provided.'}",
        ]
    elif evidence_type == "DOCUMENT":
        chunk_id = f"document:{reference_id}:{page or ''}"
        title = metadata.get("title") or label
        excerpt = _truncate_text(metadata.get("excerpt") or label)
        body_lines = [
            f"Document ID: {reference_id}",
            f"Excerpt: {metadata.get('excerpt') or 'No excerpt stored.'}",
        ]
    else:
        body_lines = [
            f"Reference ID: {reference_id or 'Unknown'}",
            f"Details: {metadata.get('description') or metadata.get('summary') or label}",
        ]

    artifact = _register_context_source(
        citation_registry,
        doc_id=reference_id or label,
        title=title,
        category=category,
        excerpt=excerpt,
        chunk_id=chunk_id,
        source_url=source_url,
        page=page,
    )
    return (
        _format_context_block(
            artifact.marker,
            artifact.title,
            artifact.category,
            body_lines,
            page=artifact.page,
            source_url=artifact.source_url,
        ),
        artifact.marker,
    )


async def build_case_evidence_context(
    *,
    case_record: dict,
    case_id: str,
    tender_id: Optional[str],
    db_session: Any,
    app_state: Any,
    citation_registry: Any,
) -> tuple[str, list[dict], list[int]]:
    from uuid import UUID

    from db import repository as repo

    links = []
    if db_session and case_id:
        links = await repo.get_case_evidence_links(db_session, UUID(case_id))

    blocks: list[dict] = []
    seen_markers: set[int] = set()

    def add_block(block_text: Optional[str], marker: Optional[int]) -> None:
        if not block_text or marker is None or marker in seen_markers:
            return
        seen_markers.add(marker)
        blocks.append({"marker": marker, "text": block_text})

    case_block, case_marker = _build_case_record_block(case_record, citation_registry)
    add_block(case_block, case_marker)

    tender_block, tender_marker = _build_tender_block(
        tender_id, app_state, citation_registry
    )
    add_block(tender_block, tender_marker)

    for block_text, marker in _build_risk_factor_blocks(
        tender_id, app_state, citation_registry
    ):
        add_block(block_text, marker)

    priority = {"TENDER": 0, "RISK_FACTOR": 1, "GRAPH_PATH": 2, "DOCUMENT": 3}
    sorted_links = sorted(
        links,
        key=lambda link: (
            priority.get(str(getattr(link, "evidence_type", "")), 99),
            str(getattr(link, "created_at", "")),
        ),
    )
    for link in sorted_links:
        block_text, marker = _build_link_block(link, citation_registry)
        add_block(block_text, marker)

    if not blocks:
        return "No structured case evidence was available.", [], []

    return (
        "\n\n".join(block["text"] for block in blocks),
        blocks,
        [block["marker"] for block in blocks],
    )
