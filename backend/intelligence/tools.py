import logging
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Literal, Optional

from langchain.tools import ToolRuntime, tool

logger = logging.getLogger(__name__)


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


def _format_source_block(artifact: ToolArtifact, body_lines: list[str]) -> str:
    lines = [f"[{artifact.marker}] {artifact.title}", f"Category: {artifact.category}"]
    if artifact.page is not None:
        lines.append(f"Page: {artifact.page}")
    if artifact.source_url:
        lines.append(f"Source URL: {artifact.source_url}")
    lines.extend(line for line in body_lines if line)
    return "\n".join(lines)


@tool(response_format="content_and_artifact")
async def search_legal_knowledge(
    query: str,
    category: Literal["law", "case_law", "regulation", "guideline"],
    runtime: ToolRuntime[AgentRuntimeContext],
) -> tuple[str, list[dict]]:
    """Search Kenyan legal knowledge base by category."""
    ctx = runtime.context
    registry = _require_citation_registry()
    if not ctx or not ctx.db_session or not registry:
        return "Knowledge base not available.", []

    from knowledge.store import get_knowledge_store

    try:
        store = get_knowledge_store(ctx.db_session)
        results = await store.similarity_search(query, category=category.upper(), k=5)
    except Exception as exc:
        logger.exception(
            "search_legal_knowledge failed",
            extra={"category": category, "query_prefix": query[:120]},
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
def search_graph_connections(
    entity_name: str,
    runtime: ToolRuntime[AgentRuntimeContext],
) -> str:
    """Search the procurement entity graph for connections."""
    ctx = runtime.context
    if not ctx or not ctx.app_state:
        return "Graph not available."

    graph = ctx.app_state.graph
    if not graph:
        return "Graph not loaded."

    matching_nodes = []
    entity_lower = entity_name.lower()
    for node in graph.nodes():
        node_data = graph.nodes[node]
        label = node_data.get("label", "").lower()
        if entity_lower in label or entity_lower in node.lower():
            matching_nodes.append((node, node_data))

    if not matching_nodes:
        return f"No entities found matching '{entity_name}'."

    lines = [f"Found {len(matching_nodes)} matching entities:"]
    for node_id, data in matching_nodes[:5]:
        lines.append(f"\n{data.get('label', node_id)} ({data.get('type', 'unknown')}):")
        neighbors = list(graph.neighbors(node_id))[:10]
        for neighbor in neighbors:
            edge_data = graph.edges.get((node_id, neighbor), {})
            neighbor_data = graph.nodes.get(neighbor, {})
            relationship = edge_data.get("relationship", "connected to")
            lines.append(f"  - {relationship}: {neighbor_data.get('label', neighbor)}")
    return "\n".join(lines)
