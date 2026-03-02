"""
RAG-powered investigation agent for procurement oversight.
Provides grounded, evidence-backed analysis with citations.

Uses LangChain v1 create_agent with tool-calling for RAG.
Supports OpenAI, Anthropic, Google, and local models via config.
"""

import re
import uuid
from typing import Optional, Literal, Any
from dataclasses import dataclass, field

from langchain.chat_models import init_chat_model
from langchain.tools import tool
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from config import settings
from intelligence.evidence import EvidencePack


SYSTEM_PROMPT = """You are Sentinel AI, an investigation assistant for Kenyan public procurement oversight.
You help auditors analyze cases by searching legal knowledge and case evidence.

CITATION RULES:
- When you use information from a tool, cite it with a numbered marker like [1], [2], etc.
- Number citations sequentially in order of first appearance.
- Place the marker immediately after the relevant statement.
- Do NOT fabricate URLs or document names — only reference what the tools return.

CONDUCT RULES:
- Use advisory, non-accusatory language (e.g., "this pattern may indicate..." not "this is fraud")
- Ground every claim in retrieved evidence or legal provisions
- When uncertain, say so and suggest what additional information would help
- Focus on Kenyan procurement law: PPADA 2015, PPADR 2020, Conflict of Interest Act 2025

OUTPUT FORMAT for case summaries:
## Executive Summary
2-3 sentences summarizing the key findings with citations.

## Key Concerns
- [CONCERN]: Description with citation [N]

## Recommended Actions
1. Specific action step
2. Specific action step"""


@dataclass
class ToolArtifact:
    """Metadata from a tool call for citation tracking."""

    doc_id: str
    title: str
    source_url: Optional[str]
    category: str
    excerpt: str
    page: Optional[int]
    chunk_id: str


@dataclass
class AgentContext:
    """Context passed to tools during agent execution."""

    case_id: Optional[str] = None
    tender_id: Optional[str] = None
    db_session: Any = None
    app_state: Any = None
    artifacts: list[ToolArtifact] = field(default_factory=list)


_agent_context: Optional[AgentContext] = None


def set_agent_context(ctx: AgentContext) -> None:
    """Set the current agent context for tool access."""
    global _agent_context
    _agent_context = ctx


def get_agent_context() -> Optional[AgentContext]:
    """Get the current agent context."""
    return _agent_context


def _format_risk_factors(factors: list[dict]) -> str:
    """Format risk factors for the prompt."""
    if not factors:
        return "No risk factors detected."
    lines = []
    for i, f in enumerate(factors, 1):
        lines.append(f"{i}. [{f['type']}] (weight: {f['weight']})")
        lines.append(f"   {f['description']}")
        for ev in f.get("evidence", []):
            lines.append(f"   - Evidence: {ev}")
    return "\n".join(lines)


def _format_graph_paths(paths: list[dict]) -> str:
    """Format graph paths for the prompt."""
    if not paths:
        return "No direct relationship paths detected."
    lines = []
    for p in paths:
        via = " -> ".join(p.get("via", []))
        via_str = f" via {via}" if via else ""
        lines.append(f"- {p['from']}{via_str} -> {p['to']} (distance: {p['length']})")
    return "\n".join(lines)


# ==============================================================================
# RAG Tools
# ==============================================================================


@tool(response_format="content_and_artifact")
def search_legal_knowledge(
    query: str,
    category: Literal["law", "case_law", "regulation", "guideline"],
) -> tuple[str, list[dict]]:
    """Search Kenyan legal knowledge base by category.

    Args:
        query: Search query for legal information
        category: Type of legal document to search:
            - law: Acts of Parliament (PPADA 2015, etc.)
            - case_law: Court decisions and legal precedents
            - regulation: Public Procurement Regulations, circulars
            - guideline: PPRA/EACC guidelines and advisories

    Returns:
        Relevant legal text passages with source citations.
    """
    ctx = get_agent_context()
    if not ctx or not ctx.db_session:
        return "Knowledge base not available.", []
    # Import here to avoid circular imports
    from knowledge.store import get_knowledge_store
    import asyncio

    async def _search():
        store = get_knowledge_store(ctx.db_session)
        return await store.similarity_search(query, category=category.upper(), k=5)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                results = pool.submit(asyncio.run, _search()).result()
        else:
            results = asyncio.run(_search())
    except Exception as e:
        return f"Search error: {str(e)[:100]}", []
    # Format content for model
    content_parts = []
    artifacts = []
    for i, r in enumerate(results, 1):
        content_parts.append(f"[{i}] From {r.document_title}:\n{r.content[:500]}...")
        artifacts.append(
            {
                "doc_id": r.document_id,
                "title": r.document_title,
                "source_url": r.source_url,
                "category": r.category,
                "excerpt": r.content[:200],
                "page": r.page_number,
                "chunk_id": r.chunk_id,
            }
        )
        # Track in context for citation mapping
        if ctx:
            ctx.artifacts.append(
                ToolArtifact(
                    doc_id=r.document_id,
                    title=r.document_title,
                    source_url=r.source_url,
                    category=r.category,
                    excerpt=r.content[:200],
                    page=r.page_number,
                    chunk_id=r.chunk_id,
                )
            )
    return "\n\n".join(content_parts), artifacts


@tool(response_format="content_and_artifact")
def search_case_evidence(query: str) -> tuple[str, list[dict]]:
    """Search evidence linked to the current investigation case.

    Args:
        query: Search query for case evidence

    Returns:
        Relevant evidence from the case including tender details, risk factors,
        graph connections, and investigation notes.
    """
    ctx = get_agent_context()
    if not ctx or not ctx.case_id:
        return "No case context available.", []
    # For now, return case evidence from the app state
    # This will be enhanced to search case_evidence_links
    if not ctx.app_state:
        return "Case evidence not available.", []
    artifacts = []
    content_parts = []
    # Get tender info if available
    if ctx.tender_id and ctx.tender_id in ctx.app_state.tenders:
        tender = ctx.app_state.tenders[ctx.tender_id]
        risk = ctx.app_state.risk_scores.get(ctx.tender_id)
        content_parts.append(f"[1] Tender {tender.reference_number}: {tender.title}")
        content_parts.append(f"    Procuring Entity: {tender.procuring_entity}")
        content_parts.append(
            f"    Estimated Value: KES {tender.estimated_value:,.0f}"
            if tender.estimated_value
            else ""
        )
        if risk:
            content_parts.append(
                f"    Risk Score: {risk.overall}/100 ({risk.category.value})"
            )
            for f in risk.factors:
                content_parts.append(f"    - {f.type.value}: {f.description}")
        artifacts.append(
            {
                "doc_id": ctx.tender_id,
                "title": f"Tender: {tender.reference_number}",
                "source_url": None,
                "category": "TENDER",
                "excerpt": tender.title[:200],
                "page": None,
                "chunk_id": ctx.tender_id,
            }
        )
    if not content_parts:
        return "No evidence found for this case.", []
    return "\n".join(content_parts), artifacts


@tool
def get_risk_analysis(tender_id: str) -> str:
    """Get the full risk analysis for a specific tender.

    Args:
        tender_id: The tender ID to analyze

    Returns:
        Risk score, factors, ML anomaly details, and graph metrics.
    """
    ctx = get_agent_context()
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
        for f in risk.factors:
            lines.append(f"- {f.type.value} (weight: {f.weight}): {f.description}")
            for ev in f.evidence:
                lines.append(f"  Evidence: {ev}")
    else:
        lines.append("No risk assessment available.")
    return "\n".join(lines)


@tool
def search_graph_connections(entity_name: str) -> str:
    """Search the procurement entity graph for connections.

    Args:
        entity_name: Name of company, director, or official to search

    Returns:
        Shared directors, addresses, phones, and suspicious relationship paths.
    """
    ctx = get_agent_context()
    if not ctx or not ctx.app_state:
        return "Graph not available."
    graph = ctx.app_state.graph
    if not graph:
        return "Graph not loaded."
    # Find matching nodes
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
            rel = edge_data.get("relationship", "connected to")
            lines.append(f"  - {rel}: {neighbor_data.get('label', neighbor)}")
    return "\n".join(lines)


# =============================================================================
# Agent Class
# =============================================================================


class InvestigationAgent:
    """
    LangGraph-based agent for procurement investigation assistance.
    Falls back to template-based explanations if LLM is unavailable.
    """

    def __init__(self):
        self.llm = None
        self.agent = None
        self._init_llm()
        self._init_agent()

    def _init_llm(self):
        """
        Initialize LLM using LangChain v1 init_chat_model.
        Supports any provider: openai, anthropic, google_genai, ollama, etc.
        Configure via environment variables:
          LLM_MODEL: model name (default: gpt-4o-mini)
          LLM_PROVIDER: provider name (default: openai)
          LLM_BASE_URL: custom base URL for local/proxy models
        """
        try:
            kwargs = {
                "model": settings.llm_model,
                "model_provider": settings.llm_provider,
                "temperature": settings.llm_temperature,
            }
            if settings.llm_base_url:
                kwargs["base_url"] = settings.llm_base_url
            self.llm = init_chat_model(**kwargs)
        except Exception:
            # No valid credentials or provider — LLM stays None, template fallback used
            self.llm = None

    def _init_agent(self):
        """
        Initialize the LangChain agent with RAG tools.
        """
        if self.llm is None:
            return
        tools = [
            search_legal_knowledge,
            search_case_evidence,
            get_risk_analysis,
            search_graph_connections,
        ]
        try:
            self.agent = create_agent(
                model=self.llm,
                tools=tools,
                system_prompt=SYSTEM_PROMPT,
            )
        except Exception:
            self.agent = None

    def _template_explanation(self, evidence: dict) -> str:
        """Fallback template-based explanation when LLM is unavailable."""
        summary = evidence.get("tender_summary", {})
        factors = evidence.get("risk_factors", [])
        metrics = evidence.get("key_metrics", {})
        paths = evidence.get("graph_paths", [])

        lines = ["## Executive Summary"]
        lines.append(
            f"Tender **{summary.get('reference', 'N/A')}** "
            f"(\"{summary.get('title', 'N/A')}\") has been flagged with a "
            f"risk score of **{metrics.get('risk_score', 0)}/100** "
            f"({metrics.get('risk_category', 'N/A')})."
        )

        if factors:
            lines.append(
                f"\n{len(factors)} risk factor(s) were detected requiring review."
            )

        lines.append("\n## Key Concerns")
        for f in factors:
            lines.append(
                f"- **{f['type']}** (weight: {f['weight']}): {f['description']}"
            )
            for ev in f.get("evidence", []):
                lines.append(f"  - {ev}")

        if paths:
            lines.append("\n## Relationship Paths")
            for p in paths:
                via = " -> ".join(p.get("via", []))
                via_str = f" via {via}" if via else ""
                lines.append(f"- {p['from']}{via_str} -> {p['to']}")

        lines.append("\n## Recommended Actions")
        recommendations = evidence.get("recommendations", [])
        if recommendations:
            for i, rec in enumerate(recommendations, 1):
                lines.append(f"{i}. {rec}")
        else:
            lines.append("1. Review flagged risk factors and supporting evidence")
            lines.append("2. Request additional documentation from involved parties")
            lines.append("3. Escalate to supervisor if concerns are substantiated")

        return "\n".join(lines)

    def _extract_citations(
        self, response_text: str, artifacts: list[ToolArtifact]
    ) -> list[dict]:
        """Extract citation markers from response and map to artifacts."""
        citations = []
        # Find all [N] markers in the response
        markers = re.findall(r"\[(\d+)\]", response_text)
        seen = set()

        for marker_str in markers:
            marker = int(marker_str)
            if marker in seen:
                continue
            seen.add(marker)

            # Map to artifact (1-indexed)
            if 0 < marker <= len(artifacts):
                artifact = artifacts[marker - 1]
                citations.append(
                    {
                        "marker": marker,
                        "doc_id": artifact.doc_id,
                        "title": artifact.title,
                        "source_url": artifact.source_url,
                        "category": artifact.category,
                        "excerpt": artifact.excerpt,
                        "page": artifact.page,
                        "chunk_id": artifact.chunk_id,
                    }
                )
        return citations

    async def explain(self, evidence_pack: EvidencePack) -> dict:
        """
        Generate an explanation for a tender's risk assessment.
        Returns dict with 'explanation' (str) and optional 'error'.
        """
        if self.llm is None:
            return {
                "explanation": self._template_explanation(evidence_pack.to_dict()),
                "error": "LLM not configured, using template",
                "citations": [],
                "evidence_pack": evidence_pack.to_dict(),
            }

        try:
            summary = evidence_pack.to_dict().get("tender_summary", {})
            prompt = f"""Analyze this tender and explain why it has been flagged for review.

Tender: {summary.get('reference', 'N/A')} - {summary.get('title', 'N/A')}
Procuring Entity: {summary.get('procuring_entity', 'N/A')}
Estimated Value: KES {summary.get('estimated_value', 0):,.0f}

Use the search_case_evidence tool to get the full risk analysis, then provide your assessment."""

            result = await self.agent.ainvoke(
                {"messages": [{"role": "user", "content": prompt}]}
            )

            # Extract the final response
            response_text = ""
            if "messages" in result:
                for msg in reversed(result["messages"]):
                    if hasattr(msg, "content") and isinstance(msg.content, str):
                        response_text = msg.content
                        break

            # Get artifacts from context for citation mapping
            ctx = get_agent_context()
            artifacts = ctx.artifacts if ctx else []
            citations = self._extract_citations(response_text, artifacts)

            return {
                "explanation": response_text,
                "error": None,
                "citations": citations,
                "evidence_pack": evidence_pack.to_dict(),
            }

        except Exception as e:
            return {
                "explanation": self._template_explanation(evidence_pack.to_dict()),
                "error": f"LLM error, using template: {str(e)[:100]}",
                "citations": [],
                "evidence_pack": evidence_pack.to_dict(),
            }

    async def chat(
        self,
        message: str,
        history: list[dict] | None = None,
    ) -> tuple[str, list[dict]]:
        """
        Chat with the agent about a case.

        Args:
            message: User message
            history: Previous messages [{"role": "user"|"assistant", "content": "..."}]

        Returns:
            Tuple of (response_text, citations)
        """
        if self.agent is None:
            return (
                "I'm sorry, the AI assistant is not configured. Please contact an administrator.",
                [],
            )

        try:
            # Build messages from history
            messages = []
            if history:
                for msg in history:
                    if msg["role"] == "user":
                        messages.append({"role": "user", "content": msg["content"]})
                    else:
                        messages.append(
                            {"role": "assistant", "content": msg["content"]}
                        )

            messages.append({"role": "user", "content": message})

            # Clear artifacts for this conversation turn
            ctx = get_agent_context()
            if ctx:
                ctx.artifacts = []

            result = await self.agent.ainvoke({"messages": messages})

            # Extract response
            response_text = ""
            if "messages" in result:
                for msg in reversed(result["messages"]):
                    if hasattr(msg, "content") and isinstance(msg.content, str):
                        response_text = msg.content
                        break

            # Extract citations
            artifacts = ctx.artifacts if ctx else []
            citations = self._extract_citations(response_text, artifacts)

            return response_text, citations

        except Exception as e:
            return f"I encountered an error: {str(e)[:100]}", []

    async def generate_summary(self) -> tuple[str, list[dict], list[str]]:
        """
        Generate a case summary.

        Returns:
            Tuple of (summary_text, citations, key_findings)
        """
        if self.agent is None:
            return "AI assistant not configured.", [], []

        try:
            ctx = get_agent_context()
            if ctx:
                ctx.artifacts = []

            prompt = """Generate an executive summary of this investigation case.

Use the search_case_evidence tool to gather all relevant information, then provide:
1. A concise executive summary (2-3 paragraphs)
2. Key findings as bullet points
3. Recommended next steps

Cite all sources using [N] markers."""

            result = await self.agent.ainvoke(
                {"messages": [{"role": "user", "content": prompt}]}
            )

            response_text = ""
            if "messages" in result:
                for msg in reversed(result["messages"]):
                    if hasattr(msg, "content") and isinstance(msg.content, str):
                        response_text = msg.content
                        break

            artifacts = ctx.artifacts if ctx else []
            citations = self._extract_citations(response_text, artifacts)

            # Extract key findings (lines starting with - or *)
            key_findings = []
            for line in response_text.split("\n"):
                line = line.strip()
                if line.startswith("- ") or line.startswith("* "):
                    key_findings.append(line[2:])

            return response_text, citations, key_findings[:10]

        except Exception as e:
            return f"Error generating summary: {str(e)[:100]}", [], []

    async def suggest_next_steps(self) -> tuple[list[str], list[dict]]:
        """
        Suggest next investigation steps.

        Returns:
            Tuple of (suggestions, citations)
        """
        if self.agent is None:
            return ["Configure AI assistant to get suggestions."], []

        try:
            ctx = get_agent_context()
            if ctx:
                ctx.artifacts = []

            prompt = """Based on the current case evidence and Kenyan procurement law, suggest the next steps for this investigation.

Use search_case_evidence to understand the case, and search_legal_knowledge to find relevant legal requirements.

Provide 3-5 specific, actionable next steps. Cite relevant laws or evidence."""

            result = await self.agent.ainvoke(
                {"messages": [{"role": "user", "content": prompt}]}
            )

            response_text = ""
            if "messages" in result:
                for msg in reversed(result["messages"]):
                    if hasattr(msg, "content") and isinstance(msg.content, str):
                        response_text = msg.content
                        break

            artifacts = ctx.artifacts if ctx else []
            citations = self._extract_citations(response_text, artifacts)

            # Extract numbered steps
            suggestions = []
            for line in response_text.split("\n"):
                line = line.strip()
                if re.match(r"^\d+\.\s", line):
                    suggestions.append(re.sub(r"^\d+\.\s*", "", line))

            return suggestions[:5] if suggestions else [response_text], citations

        except Exception as e:
            return [f"Error: {str(e)[:100]}"], []


# Singleton instance
_agent: InvestigationAgent | None = None


def get_agent() -> InvestigationAgent:
    """Get or create the singleton investigation agent."""
    global _agent
    if _agent is None:
        _agent = InvestigationAgent()
    return _agent


def reset_agent() -> None:
    """Reset the agent singleton (called when settings change)."""
    global _agent
    _agent = None
