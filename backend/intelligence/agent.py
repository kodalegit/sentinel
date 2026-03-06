"""
RAG-powered investigation agent for procurement oversight.
Provides grounded, evidence-backed analysis with citations.

Uses LangChain v1 create_agent with tool-calling for RAG.
Supports OpenAI, Anthropic, Google, and local models via config.
"""

import re
from typing import AsyncGenerator

import logging

from langchain.chat_models import init_chat_model
from langchain.agents import create_agent

from config import settings
from intelligence.evidence import EvidencePack, build_case_evidence_context
from intelligence.prompts import (
    BASE_SYSTEM_PROMPT,
    build_runtime_system_prompt,
    get_prompt_for_action,
)
from intelligence.streaming import (
    AgentStreamFSM,
    AgentState,
    StreamEvent,
    TokenEvent,
    ReasoningEvent,
    ToolStartEvent,
    ToolEndEvent,
    CitationEvent,
    DoneEvent,
    ErrorEvent,
)
from intelligence.tools import (
    search_legal_knowledge,
    search_case_evidence,
    get_risk_analysis,
    search_graph_connections,
    get_agent_context,
    clear_agent_context,
)

logger = logging.getLogger(__name__)


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

            provider = settings.llm_provider.lower()
            if provider == "openai" and settings.openai_api_key:
                kwargs["api_key"] = settings.openai_api_key
            elif provider == "anthropic" and settings.anthropic_api_key:
                kwargs["api_key"] = settings.anthropic_api_key
            elif provider in {"google", "google_genai"} and settings.google_api_key:
                kwargs["api_key"] = settings.google_api_key

            self.llm = init_chat_model(**kwargs)
        except Exception:
            # No valid credentials or provider — LLM stays None, template fallback used
            logger.exception(
                "Failed to initialize LLM",
                extra={"provider": settings.llm_provider, "model": settings.llm_model},
            )
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
                system_prompt=BASE_SYSTEM_PROMPT,
            )
        except Exception:
            logger.exception("Failed to initialize investigation agent")
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

    def _extract_citation_markers(self, response_text: str) -> list[int]:
        markers = re.findall(r"\[(\d+)\]", response_text or "")
        ordered_markers: list[int] = []
        seen: set[int] = set()
        for marker_str in markers:
            marker = int(marker_str)
            if marker in seen:
                continue
            seen.add(marker)
            ordered_markers.append(marker)
        return ordered_markers

    def _extract_citations(self, response_text: str) -> list[dict]:
        ctx = get_agent_context()
        if not ctx:
            return []
        return ctx.citation_registry.to_citation_dicts(
            self._extract_citation_markers(response_text)
        )

    def _citation_event_for_marker(self, marker: int) -> CitationEvent | None:
        ctx = get_agent_context()
        if not ctx:
            return None
        artifact = ctx.citation_registry.get(marker)
        if not artifact:
            return None
        return CitationEvent(
            marker=artifact.marker,
            doc_id=artifact.doc_id,
            title=artifact.title,
            category=artifact.category,
            excerpt=artifact.excerpt,
            chunk_id=artifact.chunk_id,
            source_url=artifact.source_url,
            page=artifact.page,
        )

    async def _prepare_case_context(self) -> None:
        ctx = get_agent_context()
        if not ctx or not ctx.case_id:
            return

        ctx.citation_registry.clear()
        case_record = {
            "id": ctx.case_id,
            "title": ctx.case_title,
            "status": ctx.case_status,
            "priority": ctx.case_priority,
            "summary": ctx.case_summary,
        }
        (
            ctx.case_evidence_context,
            ctx.case_evidence_blocks,
            ctx.baseline_markers,
        ) = await build_case_evidence_context(
            case_record=case_record,
            case_id=ctx.case_id,
            tender_id=ctx.tender_id,
            db_session=ctx.db_session,
            app_state=ctx.app_state,
            citation_registry=ctx.citation_registry,
        )

    def _build_messages(
        self,
        *,
        message: str,
        action: str,
        history: list[dict] | None,
    ) -> list[dict]:
        ctx = get_agent_context()
        runtime_prompt = build_runtime_system_prompt(
            action,
            ctx.case_evidence_context if ctx else None,
        )
        messages = [{"role": "system", "content": runtime_prompt}]
        if history:
            for msg in history:
                role = "user" if msg["role"] == "user" else "assistant"
                messages.append({"role": role, "content": msg["content"]})

        prompt = get_prompt_for_action(action, message)
        if prompt:
            messages.append({"role": "user", "content": prompt})
        return messages

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

Evidence Pack:
{evidence_pack.to_dict()}

Provide a grounded assessment using only the evidence above and any additional legal research you need."""

            result = await self.agent.ainvoke(
                {
                    "messages": [
                        {"role": "system", "content": BASE_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ]
                }
            )

            # Extract the final response
            response_text = ""
            if "messages" in result:
                for msg in reversed(result["messages"]):
                    if hasattr(msg, "content") and isinstance(msg.content, str):
                        response_text = msg.content
                        break

            citations = self._extract_citations(response_text)

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

    def _summarize_tool_output(self, tool_name: str, result: str) -> str:
        """Create a brief summary of tool output for UI display."""
        if len(result) <= 150:
            return result
        return result[:150] + "..."

    async def stream(
        self,
        message: str,
        action: str = "chat",
        history: list[dict] | None = None,
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        Stream agent response with real-time events.

        Yields StreamEvent instances: reasoning, tool_start, tool_end,
        citation, token, done, error.
        """
        if self.agent is None:
            clear_agent_context()
            yield ErrorEvent(
                message="AI assistant not configured.", code="NOT_CONFIGURED"
            )
            return

        fsm = AgentStreamFSM()
        final_content = ""
        emitted_citations: set[int] = set()
        ctx = get_agent_context()

        try:
            await self._prepare_case_context()

            if ctx:
                for marker in ctx.baseline_markers:
                    citation_event = self._citation_event_for_marker(marker)
                    if citation_event and marker not in emitted_citations:
                        emitted_citations.add(marker)
                        yield citation_event

            messages = self._build_messages(
                message=message,
                action=action,
                history=history,
            )

            stream = self.agent.astream(
                {"messages": messages},
                stream_mode=["updates", "messages"],
            )

            try:
                async for mode, chunk in stream:
                    if mode == "updates":
                        for node_name, node_data in chunk.items():
                            if node_data is None:
                                continue
                            node_messages = node_data.get("messages", [])
                            if not node_messages:
                                continue

                            if node_name == "model":
                                msg = node_messages[-1]
                                state, data = fsm.on_model_update(msg)

                                if state == AgentState.PLANNING:
                                    if data.get("turn_text"):
                                        yield ReasoningEvent(
                                            content=data["turn_text"],
                                            step=data["step"],
                                        )
                                    for tc in data.get("tool_calls", []):
                                        yield ToolStartEvent(
                                            tool=tc["name"],
                                            tool_call_id=tc["id"],
                                            input=tc["args"],
                                        )

                                elif state == AgentState.STREAMING_ANSWER:
                                    if data.get("emit_text"):
                                        final_content = data["emit_text"]

                            elif node_name == "tools":
                                # Process ALL tool messages (parallel calls)
                                for msg in node_messages:
                                    _state, data = fsm.on_tool_update(msg)
                                    tool_name = data.get("tool_name", "unknown")
                                    result = data.get("result", "")

                                    yield ToolEndEvent(
                                        tool=tool_name,
                                        tool_call_id=data.get("tool_call_id", ""),
                                        summary=self._summarize_tool_output(
                                            tool_name, result
                                        ),
                                    )

                                if ctx:
                                    for (
                                        artifact
                                    ) in ctx.citation_registry.list_artifacts():
                                        marker = artifact.marker
                                        if marker not in emitted_citations:
                                            emitted_citations.add(marker)
                                            yield CitationEvent(
                                                marker=marker,
                                                doc_id=artifact.doc_id,
                                                title=artifact.title,
                                                category=artifact.category,
                                                excerpt=artifact.excerpt,
                                                chunk_id=artifact.chunk_id,
                                                source_url=artifact.source_url,
                                                page=artifact.page,
                                            )

                                fsm.reset_turn()

                    elif mode == "messages":
                        token_chunk, metadata = chunk
                        _state, data = fsm.on_message_token(token_chunk, metadata)

                        if data.get("token"):
                            yield TokenEvent(delta=data["token"])
                            final_content += data["token"]
                            fsm.accumulate_final(data["token"])

            finally:
                await stream.aclose()

        except Exception as e:
            logger.exception("Agent stream error")
            yield ErrorEvent(message=f"Error: {str(e)[:200]}", code="AGENT_ERROR")

        fsm.mark_done()

        citations = self._extract_citations(final_content or fsm.get_final_content())
        yield DoneEvent(citations=citations)

        clear_agent_context()


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
