import logging
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Optional

from langchain.tools import ToolRuntime, tool
from config import settings
from graph.neo4j_communities import (
    get_entity_neighborhood_neo4j,
    search_graph_entities_neo4j,
)

logger = logging.getLogger(__name__)

LEGAL_KNOWLEDGE_CATEGORIES = ["LAW", "REGULATION", "GUIDELINE"]
CASE_LAW_CATEGORY = "CASE_LAW"


@dataclass
class ToolArtifact:
    marker: int
    doc_id: str
    title: str
    source_url: Optional[str]
    category: str
    excerpt: str
    page: Optional[int]
    chunk_id: str

    def to_dict(self) -> dict:
        return {
            "marker": self.marker,
            "doc_id": self.doc_id,
            "title": self.title,
            "source_url": self.source_url,
            "category": self.category,
            "excerpt": self.excerpt,
            "page": self.page,
            "chunk_id": self.chunk_id,
        }


class CitationRegistry:
    def __init__(self):
        self._artifacts_by_key: dict[str, ToolArtifact] = {}
        self._artifacts_by_marker: dict[int, ToolArtifact] = {}

    def clear(self) -> None:
        self._artifacts_by_key.clear()
        self._artifacts_by_marker.clear()

    def register(
        self,
        *,
        doc_id: str,
        title: str,
        source_url: Optional[str],
        category: str,
        excerpt: str,
        page: Optional[int],
        chunk_id: str,
    ) -> ToolArtifact:
        key = self._make_key(
            doc_id=doc_id, category=category, chunk_id=chunk_id, page=page
        )
        existing = self._artifacts_by_key.get(key)
        if existing:
            if excerpt and len(existing.excerpt) < len(excerpt):
                existing.excerpt = excerpt[:240]
            if not existing.source_url and source_url:
                existing.source_url = source_url
            if existing.page is None and page is not None:
                existing.page = page
            return existing

        marker = len(self._artifacts_by_marker) + 1
        artifact = ToolArtifact(
            marker=marker,
            doc_id=doc_id,
            title=title,
            source_url=source_url,
            category=category,
            excerpt=(excerpt or title)[:240],
            page=page,
            chunk_id=chunk_id,
        )
        self._artifacts_by_key[key] = artifact
        self._artifacts_by_marker[marker] = artifact
        return artifact

    def get(self, marker: int) -> Optional[ToolArtifact]:
        return self._artifacts_by_marker.get(marker)

    def list_artifacts(self) -> list[ToolArtifact]:
        return [self._artifacts_by_marker[m] for m in sorted(self._artifacts_by_marker)]

    def to_citation_dicts(self, markers: Optional[list[int]] = None) -> list[dict]:
        if markers is None:
            return [artifact.to_dict() for artifact in self.list_artifacts()]
        citations = []
        seen: set[int] = set()
        for marker in markers:
            if marker in seen:
                continue
            seen.add(marker)
            artifact = self.get(marker)
            if artifact:
                citations.append(artifact.to_dict())
        return citations

    def _make_key(
        self,
        *,
        doc_id: str,
        category: str,
        chunk_id: str,
        page: Optional[int],
    ) -> str:
        return f"{category}:{doc_id}:{chunk_id}:{page or ''}"


@dataclass
class AgentRuntimeContext:
    action: str = "chat"
    case_id: Optional[str] = None
    tender_id: Optional[str] = None
    case_title: Optional[str] = None
    case_status: Optional[str] = None
    case_priority: Optional[str] = None
    case_summary: Optional[str] = None
    db_session: Any = None
    app_state: Any = None
    case_evidence_context: str = ""
    case_evidence_blocks: list[dict] = field(default_factory=list)
    baseline_markers: list[int] = field(default_factory=list)


_citation_registry: ContextVar[Optional[CitationRegistry]] = ContextVar(
    "sentinel_citation_registry", default=None
)


def set_citation_registry(registry: CitationRegistry) -> None:
    _citation_registry.set(registry)


def get_citation_registry() -> Optional[CitationRegistry]:
    return _citation_registry.get()


def clear_citation_registry() -> None:
    _citation_registry.set(None)


def _require_citation_registry() -> Optional[CitationRegistry]:
    return get_citation_registry()


def _search_graph_connections_from_state(entity_name: str, app_state: Any) -> str:
    entity_lower = entity_name.lower().strip()
    if not entity_lower:
        return "Please provide an entity name to search."

    matches: list[tuple[str, str, str, Optional[str], Optional[str]]] = []

    for company in app_state.companies.values():
        haystacks = [company.name, company.id, company.registration_number or ""]
        if any(entity_lower in value.lower() for value in haystacks if value):
            matches.append((company.id, company.name, "COMPANY", None, company.address))

    for director in app_state.directors.values():
        haystacks = [director.name, director.id, director.national_id or ""]
        if any(entity_lower in value.lower() for value in haystacks if value):
            matches.append((director.id, director.name, "DIRECTOR", None, None))

    for official in app_state.officials.values():
        haystacks = [official.name, official.id, official.department, official.position]
        if any(entity_lower in value.lower() for value in haystacks if value):
            subtitle = " · ".join(
                value for value in [official.department, official.position] if value
            )
            matches.append(
                (official.id, official.name, "OFFICIAL", None, subtitle or None)
            )

    for tender in app_state.tenders.values():
        haystacks = [tender.title, tender.id, tender.reference_number]
        if any(entity_lower in value.lower() for value in haystacks if value):
            risk_score = app_state.risk_scores.get(tender.id)
            risk = risk_score.category.value if risk_score else None
            matches.append(
                (
                    tender.id,
                    tender.title,
                    "TENDER",
                    risk,
                    tender.procuring_entity,
                )
            )

    if not matches:
        return f"No entities found matching '{entity_name}'."

    lines = [f"Found {len(matches[:5])} matching entities:"]
    for entity_id, label, node_type, risk, subtitle in matches[:5]:
        header = f"\n{label} ({node_type})"
        if risk:
            header += f" — risk: {risk}"
        if subtitle:
            header += f" — {subtitle}"
        lines.append(header + ":")

        connections: list[str] = []
        if node_type == "COMPANY":
            company = app_state.companies[entity_id]
            for director_id in company.director_ids[:5]:
                director = app_state.directors.get(director_id)
                if director:
                    connections.append(f"  - DIRECTED_BY: {director.name}")
            awarded_tenders = [
                tender
                for tender in app_state.tenders.values()
                if tender.awarded_to == entity_id
            ][:5]
            for tender in awarded_tenders:
                connections.append(f"  - WON: {tender.title}")

        elif node_type == "DIRECTOR":
            director = app_state.directors[entity_id]
            for company_id in director.company_ids[:5]:
                company = app_state.companies.get(company_id)
                if company:
                    connections.append(f"  - DIRECTOR_OF: {company.name}")

        elif node_type == "OFFICIAL":
            official_tenders = [
                tender
                for tender in app_state.tenders.values()
                if tender.procurement_officer_id == entity_id
            ][:5]
            for tender in official_tenders:
                connections.append(f"  - AWARDED_BY: {tender.title}")

        elif node_type == "TENDER":
            tender = app_state.tenders[entity_id]
            if tender.awarded_to:
                company = app_state.companies.get(tender.awarded_to)
                if company:
                    connections.append(f"  - WON_BY: {company.name}")
            if tender.procurement_officer_id:
                official = app_state.officials.get(tender.procurement_officer_id)
                if official:
                    connections.append(f"  - AWARDED_BY: {official.name}")

        if not connections:
            connections.append("  (no direct connections found in persisted state)")
        lines.extend(connections)

    return "\n".join(lines)


def _format_source_block(artifact: ToolArtifact, body_lines: list[str]) -> str:
    lines = [f"[{artifact.marker}] {artifact.title}", f"Category: {artifact.category}"]
    if artifact.page is not None:
        lines.append(f"Page: {artifact.page}")
    if artifact.source_url:
        lines.append(f"Source URL: {artifact.source_url}")
    lines.extend(line for line in body_lines if line)
    return "\n".join(lines)


async def _search_knowledge_categories(
    *,
    query: str,
    categories: list[str],
    runtime: ToolRuntime[AgentRuntimeContext],
    failure_label: str,
) -> tuple[str, list[dict]]:
    ctx = runtime.context
    registry = _require_citation_registry()
    if not ctx or not ctx.db_session or not registry:
        return "Knowledge base not available.", []

    from knowledge.store import get_knowledge_store

    try:
        store = get_knowledge_store(ctx.db_session)
        results = await store.similarity_search(query, categories=categories, k=5)
    except Exception as exc:
        logger.exception(
            failure_label,
            extra={"categories": categories, "query_prefix": query[:120]},
        )
        return f"Search error: {str(exc)[:100]}", []

    content_parts: list[str] = []
    artifacts: list[dict] = []
    for result in results:
        artifact = registry.register(
            doc_id=str(result.document_id),
            title=result.document_title,
            source_url=result.source_url,
            category=result.category,
            excerpt=result.content[:240],
            page=result.page_number,
            chunk_id=result.chunk_id,
        )
        content_parts.append(
            _format_source_block(
                artifact,
                [
                    "Excerpt:",
                    result.content[:800],
                ],
            )
        )
        artifacts.append(artifact.to_dict())

    if not content_parts:
        return "No matching legal sources found.", []
    return "\n\n".join(content_parts), artifacts


@tool(response_format="content_and_artifact")
async def search_legal_knowledge(
    query: str,
    runtime: ToolRuntime[AgentRuntimeContext],
) -> tuple[str, list[dict]]:
    """Search Kenyan procurement law, regulations, and guidelines. Use this for legal rules and procedural requirements, not judicial precedent."""
    return await _search_knowledge_categories(
        query=query,
        categories=LEGAL_KNOWLEDGE_CATEGORIES,
        runtime=runtime,
        failure_label="search_legal_knowledge failed",
    )


@tool(response_format="content_and_artifact")
async def search_case_law(
    query: str,
    runtime: ToolRuntime[AgentRuntimeContext],
) -> tuple[str, list[dict]]:
    """Search Kenyan procurement case law and precedent. Use this when you need judicial decisions, precedent, or tribunal/court reasoning."""
    return await _search_knowledge_categories(
        query=query,
        categories=[CASE_LAW_CATEGORY],
        runtime=runtime,
        failure_label="search_case_law failed",
    )


@tool(response_format="content_and_artifact")
def search_case_evidence(
    query: str,
    runtime: ToolRuntime[AgentRuntimeContext],
) -> tuple[str, list[dict]]:
    """Search evidence linked to the current investigation case."""
    ctx = runtime.context
    registry = _require_citation_registry()
    if not ctx or not ctx.case_id:
        return "No case context available.", []
    if not ctx.case_evidence_blocks or not registry:
        return "Case evidence not available.", []

    terms = [term.lower() for term in query.split() if len(term.strip()) >= 3]
    scored_blocks: list[tuple[int, dict]] = []
    for block in ctx.case_evidence_blocks:
        haystack = block["text"].lower()
        score = sum(haystack.count(term) for term in terms)
        scored_blocks.append((score, block))

    if terms:
        matched = [block for score, block in scored_blocks if score > 0]
        selected = matched[:6] if matched else [block for _, block in scored_blocks[:6]]
    else:
        selected = [block for _, block in scored_blocks[:6]]

    markers = [block["marker"] for block in selected]
    return (
        "\n\n".join(block["text"] for block in selected),
        registry.to_citation_dicts(markers),
    )


@tool
def get_risk_analysis(
    tender_id: str,
    runtime: ToolRuntime[AgentRuntimeContext],
) -> str:
    """Get the full risk analysis for a specific tender."""
    ctx = runtime.context
    if not ctx or not ctx.app_state:
        return "Risk analysis not available."
    if tender_id not in ctx.app_state.tenders:
        return f"Tender {tender_id} not found."

    tender = ctx.app_state.tenders[tender_id]
    risk = ctx.app_state.risk_scores.get(tender_id)
    lines = [f"Risk Analysis for Tender {tender.reference_number}:"]
    if risk:
        lines.append(f"Overall Score: {risk.overall}/100 ({risk.category.value})")
        lines.append("\nRisk Factors:")
        for factor in risk.factors:
            lines.append(
                f"- {factor.type.value} (weight: {factor.weight}): {factor.description}"
            )
            for evidence in factor.evidence:
                lines.append(f"  Evidence: {evidence}")
    else:
        lines.append("No risk assessment available.")
    return "\n".join(lines)


@tool
async def search_graph_connections(
    entity_name: str,
    runtime: ToolRuntime[AgentRuntimeContext],
) -> str:
    """Search the procurement entity graph for connections."""
    ctx = runtime.context
    if not ctx or not ctx.app_state:
        return "Graph not available."

    # --- Neo4j-first path ---
    if settings.neo4j_enabled:
        try:
            matches = await search_graph_entities_neo4j(entity_name, limit=5)
            logger.info(
                "search_graph_connections: using Neo4j (found %d matches)", len(matches)
            )
            if not matches:
                return f"No entities found matching '{entity_name}'."

            lines = [f"Found {len(matches)} matching entities:"]
            for match in matches:
                entity_id = match["id"]
                label = match.get("label", entity_id)
                node_type = match.get("type", "unknown")
                risk = match.get("risk_level")
                subtitle = match.get("subtitle")

                header = f"\n{label} ({node_type})"
                if risk:
                    header += f" — risk: {risk}"
                if subtitle:
                    header += f" — {subtitle}"
                lines.append(header + ":")

                try:
                    neighborhood = await get_entity_neighborhood_neo4j(
                        entity_id, depth=1
                    )
                    edges = neighborhood.get("edges", [])
                    nodes_by_id = {n["id"]: n for n in neighborhood.get("nodes", [])}
                    seen: set[str] = set()
                    for edge in edges[:10]:
                        src, tgt = edge.get("source"), edge.get("target")
                        rel = edge.get("relationship", "connected to")
                        neighbor_id = tgt if src == entity_id else src
                        if neighbor_id in seen or neighbor_id == entity_id:
                            continue
                        seen.add(neighbor_id)
                        neighbor_label = nodes_by_id.get(neighbor_id, {}).get(
                            "label", neighbor_id
                        )
                        suspicious = " (suspicious)" if edge.get("suspicious") else ""
                        lines.append(f"  - {rel}: {neighbor_label}{suspicious}")
                    if not seen:
                        lines.append("  (no direct connections found)")
                except Exception:
                    lines.append("  (could not load connections)")

            return "\n".join(lines)
        except Exception as exc:
            logger.warning("Neo4j graph search failed, using state fallback: %s", exc)
            logger.info("search_graph_connections: falling back to persisted state")
    else:
        logger.info("search_graph_connections: Neo4j disabled, using persisted state")

    return _search_graph_connections_from_state(entity_name, ctx.app_state)
