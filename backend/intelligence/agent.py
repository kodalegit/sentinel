"""
LangGraph-based investigation agent for procurement oversight.
Provides grounded, evidence-backed explanations of risk scores.

Uses LangChain v1 init_chat_model for provider-agnostic model initialization.
Supports OpenAI, Anthropic, Google, and local models (e.g. Ollama) via config.
"""

from typing import TypedDict, Optional

from langchain.chat_models import init_chat_model
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END

from config import settings
from intelligence.evidence import EvidencePack


SYSTEM_PROMPT = """You are a senior procurement auditor assistant for Kenya's government agencies.
Your role is ADVISORY - you help auditors understand risk patterns, not make accusations.

CRITICAL RULES:
1. ONLY cite facts from the provided evidence pack - never invent information
2. Use advisory language: "elevated risk", "warrants review", "pattern consistent with"
3. NEVER accuse individuals or companies of wrongdoing
4. Always cite specific evidence items by reference
5. Recommend concrete next steps for investigation
6. Be concise and professional

OUTPUT FORMAT (use exactly this structure):
## Executive Summary
2-3 sentences summarizing the key concern.

## Key Concerns
- [CONCERN 1]: Description citing evidence
- [CONCERN 2]: Description citing evidence

## Recommended Actions
1. Specific action step
2. Specific action step
3. Specific action step"""


USER_PROMPT_TEMPLATE = """Analyze this tender and explain why it has been flagged for review.

TENDER DETAILS:
- Reference: {reference}
- Title: {title}
- Procuring Entity: {procuring_entity}
- Category: {category}
- Estimated Value: KES {estimated_value:,.0f}
- Awarded Amount: {awarded_amount}
- Published: {published_date}
- Deadline: {deadline}
- Status: {status}
- Winning Company: {winning_company}
- Number of Bidders: {bidder_count}

DETECTED RISK FACTORS:
{risk_factors_text}

KEY METRICS:
- Price Deviation: {price_deviation_pct}%
- Company Age: {company_age_days} days
- Submission Window: {timeline_days} days
- Risk Score: {risk_score}/100 ({risk_category})

RELATIONSHIP PATHS:
{graph_paths_text}

Provide your analysis following the required format."""


class InvestigationState(TypedDict):
    """State for the investigation agent."""

    evidence: dict
    explanation: Optional[str]
    error: Optional[str]


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


class InvestigationAgent:
    """
    LangGraph-based agent for procurement investigation assistance.
    Falls back to template-based explanations if LLM is unavailable.
    """

    def __init__(self):
        self.llm = None
        self.graph = self._build_graph()
        self._init_llm()

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

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(InvestigationState)

        workflow.add_node("generate_explanation", self._generate_explanation)

        workflow.set_entry_point("generate_explanation")
        workflow.add_edge("generate_explanation", END)

        return workflow.compile()

    async def _generate_explanation(self, state: InvestigationState) -> dict:
        """Generate a grounded explanation using LLM or fallback template."""
        evidence = state["evidence"]

        if self.llm is None:
            return {"explanation": self._template_explanation(evidence)}

        try:
            summary = evidence.get("tender_summary", {})
            metrics = evidence.get("key_metrics", {})

            awarded_amount = summary.get("awarded_amount")
            awarded_str = (
                f"KES {awarded_amount:,.0f}" if awarded_amount else "Not yet awarded"
            )

            prompt = USER_PROMPT_TEMPLATE.format(
                reference=summary.get("reference", "N/A"),
                title=summary.get("title", "N/A"),
                procuring_entity=summary.get("procuring_entity", "N/A"),
                category=summary.get("category", "N/A"),
                estimated_value=summary.get("estimated_value", 0),
                awarded_amount=awarded_str,
                published_date=summary.get("published_date", "N/A"),
                deadline=summary.get("deadline", "N/A"),
                status=summary.get("status", "N/A"),
                winning_company=summary.get("winning_company", "N/A"),
                bidder_count=summary.get("bidder_count", 0),
                risk_factors_text=_format_risk_factors(
                    evidence.get("risk_factors", [])
                ),
                price_deviation_pct=metrics.get("price_deviation_pct", 0),
                company_age_days=metrics.get("company_age_days", "N/A"),
                timeline_days=metrics.get("timeline_days", "N/A"),
                risk_score=metrics.get("risk_score", 0),
                risk_category=metrics.get("risk_category", "N/A"),
                graph_paths_text=_format_graph_paths(evidence.get("graph_paths", [])),
            )

            messages = [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ]

            response = await self.llm.ainvoke(messages)
            return {"explanation": response.content, "error": None}

        except Exception as e:
            # Fallback to template on any LLM error
            return {
                "explanation": self._template_explanation(evidence),
                "error": f"LLM unavailable, using template: {str(e)[:100]}",
            }

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

    async def explain(self, evidence_pack: EvidencePack) -> dict:
        """
        Generate an explanation for a tender's risk assessment.
        Returns dict with 'explanation' (str) and optional 'error'.
        """
        result = await self.graph.ainvoke(
            {
                "evidence": evidence_pack.to_dict(),
                "explanation": None,
                "error": None,
            }
        )
        return {
            "explanation": result.get("explanation", ""),
            "error": result.get("error"),
            "evidence_pack": evidence_pack.to_dict(),
        }


# Singleton instance
_agent: InvestigationAgent | None = None


def get_agent() -> InvestigationAgent:
    """Get or create the singleton investigation agent."""
    global _agent
    if _agent is None:
        _agent = InvestigationAgent()
    return _agent
