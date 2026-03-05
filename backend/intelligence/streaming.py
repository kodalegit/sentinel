"""
State machine and event types for agent streaming.

Processes LangChain stream events and determines when to emit
tool and final answer events to the UI.

Strategy:
1. Always stream tokens immediately during model execution
2. On model update (from `updates` mode):
   - Has tool calls → PLANNING, emit reasoning + tool_start events
   - No tool calls → STREAMING_ANSWER
3. Persist final answer to chat_messages; persist intermediate
   reasoning and tool events alongside in events_json
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional
import json


# ---------------------------------------------------------------------------
# FSM States
# ---------------------------------------------------------------------------


class AgentState(Enum):
    IDLE = auto()
    BUFFERING = auto()  # Tokens arriving, don't know if reasoning or answer yet
    PLANNING = auto()  # Model decided to call tools
    TOOL_EXECUTING = auto()  # Tool is running
    STREAMING_ANSWER = auto()
    DONE = auto()


# ---------------------------------------------------------------------------
# Stream Events
# ---------------------------------------------------------------------------


@dataclass
class StreamEvent:
    """Base class for all stream events."""

    def to_dict(self) -> dict:
        return {"type": getattr(self, "type", "unknown")}


@dataclass
class TokenEvent(StreamEvent):
    delta: str
    type: str = field(default="token")

    def to_dict(self) -> dict:
        return {"type": self.type, "delta": self.delta}


@dataclass
class ReasoningEvent(StreamEvent):
    content: str
    step: int = 0
    type: str = field(default="reasoning")

    def to_dict(self) -> dict:
        return {"type": self.type, "content": self.content, "step": self.step}


@dataclass
class ToolStartEvent(StreamEvent):
    tool: str
    tool_call_id: str
    input: Optional[dict] = None
    type: str = field(default="tool_start")

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "tool": self.tool,
            "tool_call_id": self.tool_call_id,
            "input": self.input,
        }


@dataclass
class ToolEndEvent(StreamEvent):
    tool: str
    tool_call_id: str
    summary: str = ""
    type: str = field(default="tool_end")

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "tool": self.tool,
            "tool_call_id": self.tool_call_id,
            "summary": self.summary,
        }


@dataclass
class CitationEvent(StreamEvent):
    marker: int
    doc_id: str
    title: str
    category: str
    excerpt: str
    chunk_id: str
    source_url: Optional[str] = None
    page: Optional[int] = None
    type: str = field(default="citation")

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "marker": self.marker,
            "doc_id": self.doc_id,
            "title": self.title,
            "source_url": self.source_url,
            "category": self.category,
            "excerpt": self.excerpt,
            "page": self.page,
            "chunk_id": self.chunk_id,
        }


@dataclass
class DoneEvent(StreamEvent):
    citations: list[dict] = field(default_factory=list)
    thread_id: Optional[str] = None
    type: str = field(default="done")

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "citations": self.citations,
            "thread_id": self.thread_id,
        }


@dataclass
class TitleEvent(StreamEvent):
    title: str
    type: str = field(default="title")

    def to_dict(self) -> dict:
        return {"type": self.type, "title": self.title}


@dataclass
class ErrorEvent(StreamEvent):
    message: str
    code: str = "AGENT_ERROR"
    recoverable: bool = False
    type: str = field(default="error")

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "message": self.message,
            "code": self.code,
            "recoverable": self.recoverable,
        }


# ---------------------------------------------------------------------------
# Agent Stream FSM
# ---------------------------------------------------------------------------


class AgentStreamFSM:
    """
    State machine for processing LangChain agent streaming events.

    Driven by stream_mode=["updates", "messages"]:
    - "updates": Step-level events (model finished, tool returned result)
    - "messages": Token-level streaming from LLM calls
    """

    def __init__(self):
        self.state: AgentState = AgentState.IDLE
        self.step_count: int = 0
        self._pending_tool_calls: list[dict] = []
        self._turn_text: str = ""
        self._turn_emitted: bool = False
        self._final_text: str = ""

    # -- helpers --

    def _extract_text_content(self, message: Any) -> str:
        """Extract text from a message, handling multiple content formats."""
        text = getattr(message, "text", None)
        if isinstance(text, str) and text:
            return text

        content = getattr(message, "content", None)
        if content is None:
            content = getattr(message, "content_blocks", None)

        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            parts: list[str] = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text" and isinstance(
                        block.get("text"), str
                    ):
                        parts.append(block["text"])
                    elif isinstance(block.get("content"), str):
                        parts.append(block["content"])
                elif isinstance(block, str):
                    parts.append(block)
                else:
                    block_text = getattr(block, "text", None)
                    if isinstance(block_text, str):
                        parts.append(block_text)
                    else:
                        inner = getattr(block, "content", None)
                        if isinstance(inner, str):
                            parts.append(inner)
            return "".join(parts)
        return ""

    def _extract_token(self, chunk: Any) -> str:
        """Extract token text from a message chunk."""
        return self._extract_text_content(chunk)

    # -- event handlers --

    def on_model_update(self, message: Any) -> tuple[AgentState, dict]:
        """Handle 'updates' event from model node (model turn complete)."""
        tool_calls = getattr(message, "tool_calls", None) or []
        has_tool_calls = len(tool_calls) > 0
        text_content = self._extract_text_content(message)

        turn_text = (self._turn_text or "").strip() or (text_content or "").strip()
        emit_text = turn_text if (turn_text and not self._turn_emitted) else None

        if has_tool_calls:
            self.state = AgentState.PLANNING
            self.step_count += 1
            self._pending_tool_calls = [
                {
                    "name": (
                        tc.get("name", "unknown")
                        if isinstance(tc, dict)
                        else getattr(tc, "name", "unknown")
                    ),
                    "args": (
                        tc.get("args", {})
                        if isinstance(tc, dict)
                        else getattr(tc, "args", {})
                    ),
                    "id": (
                        tc.get("id", "")
                        if isinstance(tc, dict)
                        else getattr(tc, "id", "")
                    ),
                }
                for tc in tool_calls
            ]
            self._turn_text = ""
            self._turn_emitted = False

            return self.state, {
                "tool_calls": self._pending_tool_calls,
                "turn_text": turn_text if turn_text else None,
                "emit_text": emit_text,
                "step": self.step_count,
            }
        else:
            self.state = AgentState.STREAMING_ANSWER
            self._turn_text = ""
            self._turn_emitted = False

            return self.state, {
                "final_text": turn_text if turn_text else "",
                "emit_text": emit_text,
            }

    def on_tool_update(self, message: Any) -> tuple[AgentState, dict]:
        """Handle 'updates' event from tools node."""
        self.state = AgentState.TOOL_EXECUTING
        return self.state, {
            "tool_name": getattr(message, "name", "unknown"),
            "tool_call_id": getattr(message, "tool_call_id", ""),
            "result": (
                getattr(message, "content", "")
                if isinstance(getattr(message, "content", ""), str)
                else str(getattr(message, "content", ""))
            ),
        }

    def on_message_token(
        self, chunk: Any, metadata: dict | None = None
    ) -> tuple[AgentState, dict]:
        """Handle 'messages' token chunk during streaming."""
        node = (metadata or {}).get("langgraph_node")
        if node and node != "model":
            return self.state, {}

        token = self._extract_token(chunk)
        if not token:
            return self.state, {}

        if self.state == AgentState.IDLE:
            self.state = AgentState.BUFFERING

        self._turn_text += token
        self._turn_emitted = True
        return self.state, {"token": token}

    # -- state management --

    def reset_turn(self) -> None:
        self._turn_text = ""
        self._turn_emitted = False

    def mark_done(self) -> None:
        self.state = AgentState.DONE

    def get_final_content(self) -> str:
        return self._final_text

    def accumulate_final(self, text: str) -> None:
        self._final_text += text


# ---------------------------------------------------------------------------
# Prompt Templates
# ---------------------------------------------------------------------------

PROMPT_TEMPLATES = {
    "summary": """Generate an executive summary of this investigation case.

Use the search_case_evidence tool to gather all relevant information, then provide:
1. A concise executive summary (2-3 paragraphs)
2. Key findings as bullet points
3. Recommended next steps

Cite all sources using [N] markers.""",
    "next_steps": """Based on the current case evidence and Kenyan procurement law, suggest the next steps for this investigation.

Use search_case_evidence to understand the case, and search_legal_knowledge to find relevant legal requirements.

Provide 3-5 specific, actionable next steps. Cite relevant laws or evidence.""",
    "risk_analysis": """Analyze the risk factors for this tender/case.

Use search_case_evidence to get the full risk analysis and get_risk_analysis for detailed metrics.
Then provide:
1. Summary of key risk indicators
2. Assessment of each risk factor's severity
3. Recommendations for mitigation

Cite all evidence using [N] markers.""",
}


def get_prompt_for_action(action: str, user_message: str | None = None) -> str:
    """Get the appropriate prompt for an action type."""
    if action == "chat" and user_message:
        return user_message
    template = PROMPT_TEMPLATES.get(action)
    if template:
        return template
    return user_message or ""
