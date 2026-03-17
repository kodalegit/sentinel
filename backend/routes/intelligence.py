"""Intelligence routes for chat, summaries, and knowledge base management."""

import asyncio
import json
import logging
import uuid as _uuid
import re
from typing import Optional

logger = logging.getLogger(__name__)

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from langchain_core.prompts import ChatPromptTemplate
from sqlalchemy.ext.asyncio import AsyncSession

from models import (
    KnowledgeDocument,
    KnowledgeDocumentCategory,
    KnowledgeDocumentUpdate,
    KnowledgeChunk,
    KnowledgeStats,
    ChatThread,
    ChatMessage,
    ChatRequest,
)
from state import State
from db.config import get_db
from db import repository as repo
from auth.dependencies import CurrentUser, AdminOnly
from intelligence.agent import get_agent
from intelligence.streaming import (
    TokenEvent,
    ReasoningEvent,
    ToolStartEvent,
    ToolEndEvent,
    CitationEvent,
    DoneEvent,
    TitleEvent,
    ErrorEvent,
)
from intelligence.tools import AgentRuntimeContext
from knowledge.loader import chunk_pdf_document
from knowledge.store import get_knowledge_store

router = APIRouter(prefix="/api", tags=["intelligence"])


# =============================================================================
# Knowledge Base Endpoints
# =============================================================================


def _doc_db_to_pydantic(doc_db) -> KnowledgeDocument:
    """Convert KnowledgeDocumentDB to Pydantic model."""
    return KnowledgeDocument(
        id=str(doc_db.id),
        title=doc_db.title,
        description=doc_db.description,
        category=KnowledgeDocumentCategory(doc_db.category),
        source_url=doc_db.source_url,
        file_name=doc_db.file_name,
        chunk_count=doc_db.chunk_count,
        uploaded_by=doc_db.uploaded_by.full_name if doc_db.uploaded_by else None,
        created_at=doc_db.created_at,
    )


@router.get("/knowledge/documents", response_model=list[KnowledgeDocument])
async def list_knowledge_documents(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """List all knowledge base documents."""
    docs = await repo.get_knowledge_documents(db)
    return [_doc_db_to_pydantic(d) for d in docs]


@router.get("/knowledge/documents/{document_id}", response_model=KnowledgeDocument)
async def get_knowledge_document(
    document_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Get a single knowledge document."""
    doc = await repo.get_knowledge_document(db, _uuid.UUID(document_id))
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return _doc_db_to_pydantic(doc)


@router.post("/knowledge/documents", response_model=KnowledgeDocument, status_code=201)
async def upload_knowledge_document(
    current_user: AdminOnly,
    db: AsyncSession = Depends(get_db),
    file: UploadFile = File(...),
    title: str = Form(...),
    category: str = Form(...),
    description: Optional[str] = Form(None),
    source_url: Optional[str] = Form(None),
):
    """Upload and process a PDF document for the knowledge base."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    try:
        category_enum = KnowledgeDocumentCategory(category.upper())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Must be one of: {[c.value for c in KnowledgeDocumentCategory]}",
        )

    pdf_bytes = await file.read()

    chunks = chunk_pdf_document(pdf_bytes)
    if not chunks:
        raise HTTPException(status_code=400, detail="Could not extract text from PDF")

    doc_db = await repo.create_knowledge_document(
        db=db,
        title=title,
        category=category_enum.value,
        uploaded_by_id=current_user.id,
        description=description,
        source_url=source_url,
        file_name=file.filename,
    )

    store = get_knowledge_store(db)
    chunk_count = await store.add_document_chunks(doc_db.id, chunks)

    doc_db.chunk_count = chunk_count
    await db.commit()
    await db.refresh(doc_db, attribute_names=["uploaded_by"])

    return _doc_db_to_pydantic(doc_db)


@router.patch("/knowledge/documents/{document_id}", response_model=KnowledgeDocument)
async def update_knowledge_document(
    document_id: str,
    body: KnowledgeDocumentUpdate,
    current_user: AdminOnly,
    db: AsyncSession = Depends(get_db),
):
    """Update metadata for a knowledge document without reprocessing chunks."""
    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No changes submitted")

    if "title" in update_data:
        title = (update_data.get("title") or "").strip()
        if not title:
            raise HTTPException(status_code=400, detail="Title is required")
        update_data["title"] = title

    if "description" in update_data and isinstance(update_data["description"], str):
        update_data["description"] = update_data["description"].strip() or None

    if "source_url" in update_data and isinstance(update_data["source_url"], str):
        update_data["source_url"] = update_data["source_url"].strip() or None

    if "category" in update_data and update_data["category"] is not None:
        update_data["category"] = update_data["category"].value

    doc_db = await repo.update_knowledge_document(
        db,
        _uuid.UUID(document_id),
        **update_data,
    )
    if not doc_db:
        raise HTTPException(status_code=404, detail="Document not found")

    await db.commit()
    doc_db = await repo.get_knowledge_document(db, _uuid.UUID(document_id))
    if not doc_db:
        raise HTTPException(status_code=404, detail="Document not found")
    return _doc_db_to_pydantic(doc_db)


@router.delete("/knowledge/documents/{document_id}", status_code=204)
async def delete_knowledge_document(
    document_id: str,
    current_user: AdminOnly,
    db: AsyncSession = Depends(get_db),
):
    """Delete a knowledge document and its chunks."""
    deleted = await repo.delete_knowledge_document(db, _uuid.UUID(document_id))
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")
    await db.commit()


@router.get(
    "/knowledge/documents/{document_id}/chunks", response_model=list[KnowledgeChunk]
)
async def get_document_chunks(
    document_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Get all chunks for a document."""
    chunks = await repo.get_document_chunks(db, _uuid.UUID(document_id))
    return [
        KnowledgeChunk(
            id=str(c.id),
            document_id=str(c.document_id),
            content=c.content,
            chunk_index=c.chunk_index,
            page_number=c.page_number,
            chunk_metadata=c.chunk_metadata,
        )
        for c in chunks
    ]


@router.get("/knowledge/stats", response_model=KnowledgeStats)
async def get_knowledge_stats(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Get knowledge base statistics."""
    stats = await repo.get_knowledge_stats(db)
    return KnowledgeStats(**stats)


# =============================================================================
# Chat Endpoints
# =============================================================================


@router.get("/cases/{case_id}/chat/threads", response_model=list[ChatThread])
async def get_case_chat_threads(
    case_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Get all chat threads for a case (current user only)."""
    threads = await repo.get_chat_threads(db, _uuid.UUID(case_id), current_user.id)
    result = []
    for t in threads:
        msg_count = await repo.get_thread_message_count(db, t.id)
        result.append(
            ChatThread(
                id=str(t.id),
                case_id=str(t.case_id),
                user_id=str(t.user_id),
                title=t.title,
                message_count=msg_count,
                created_at=t.created_at,
                updated_at=t.updated_at,
            )
        )
    return result


@router.get(
    "/cases/{case_id}/chat/threads/{thread_id}/messages",
    response_model=list[ChatMessage],
)
async def get_thread_messages(
    case_id: str,
    thread_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Get messages for a chat thread."""
    thread = await repo.get_chat_thread(db, _uuid.UUID(thread_id))
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    if str(thread.case_id) != case_id or thread.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    messages = await repo.get_thread_messages(db, _uuid.UUID(thread_id))
    return [
        ChatMessage(
            id=str(m.id),
            thread_id=str(m.thread_id),
            role=m.role,
            content=m.content,
            citations=m.citations,
            events=m.events,
            created_at=m.created_at,
        )
        for m in messages
    ]


@router.delete("/cases/{case_id}/chat/threads/{thread_id}", status_code=204)
async def delete_case_chat_thread(
    case_id: str,
    thread_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Delete a chat thread for the current user."""
    thread = await repo.get_chat_thread(db, _uuid.UUID(thread_id))
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    if str(thread.case_id) != case_id or thread.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    deleted = await repo.delete_chat_thread(db, _uuid.UUID(thread_id))
    if not deleted:
        raise HTTPException(status_code=404, detail="Thread not found")

    await db.commit()


class ChatStreamRequest(ChatRequest):
    """Chat request with action type."""

    action: str = "chat"


@router.post("/cases/{case_id}/chat/stream")
async def chat_stream(
    case_id: str,
    body: ChatStreamRequest,
    state: State,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Unified streaming endpoint for all agent interactions.

    Actions: chat, summary, next_steps, risk_analysis.
    All actions stream through the same event protocol.
    """
    case_db = await repo.get_case(db, _uuid.UUID(case_id))
    if not case_db:
        raise HTTPException(status_code=404, detail="Case not found")

    agent = get_agent()

    thread_id = None
    is_new_thread = False
    if body.thread_id:
        thread = await repo.get_chat_thread(db, _uuid.UUID(body.thread_id))
        if not thread or thread.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Thread not found")
        thread_id = thread.id
    else:
        is_new_thread = True
        title = await _generate_thread_title(agent, body.message, body.action)
        thread = await repo.create_chat_thread(
            db, _uuid.UUID(case_id), current_user.id, title=title
        )
        thread_id = thread.id
        await db.flush()

    await repo.add_chat_message(db, thread_id, "user", body.message)
    await db.commit()

    history = []
    if body.thread_id and thread_id:
        messages = await repo.get_thread_messages(db, thread_id, limit=20)
        for m in messages[:-1]:
            history.append({"role": m.role, "content": m.content})

    tender_id = str(case_db.tender_id) if case_db.tender_id else None
    runtime_context = AgentRuntimeContext(
        action=body.action,
        case_id=case_id,
        tender_id=tender_id,
        case_title=case_db.title,
        case_status=case_db.status,
        case_priority=case_db.priority,
        case_summary=case_db.summary,
        db_session=db,
        app_state=state,
    )

    async def generate():
        final_content = ""
        final_citations: list[dict] = []
        events_log: list[dict] = []
        aborted = False
        persisted_assistant_message = False

        try:
            if is_new_thread and thread.title:
                title_event = TitleEvent(
                    title=thread.title,
                    thread_id=str(thread_id) if thread_id else None,
                )
                yield f"data: {json.dumps(title_event.to_dict())}\n\n"

            async for event in agent.stream(
                message=body.message,
                action=body.action,
                history=history,
                runtime_context=runtime_context,
            ):
                event_dict = event.to_dict()

                if isinstance(event, TokenEvent):
                    final_content += event.delta
                    yield f"data: {json.dumps(event_dict)}\n\n"

                elif isinstance(event, ReasoningEvent):
                    events_log.append(event_dict)
                    yield f"data: {json.dumps(event_dict)}\n\n"

                elif isinstance(event, ToolStartEvent):
                    events_log.append(event_dict)
                    yield f"data: {json.dumps(event_dict)}\n\n"

                elif isinstance(event, ToolEndEvent):
                    events_log.append(event_dict)
                    yield f"data: {json.dumps(event_dict)}\n\n"

                elif isinstance(event, CitationEvent):
                    events_log.append(event_dict)
                    yield f"data: {json.dumps(event_dict)}\n\n"

                elif isinstance(event, DoneEvent):
                    final_citations = event.citations

                elif isinstance(event, ErrorEvent):
                    yield f"data: {json.dumps(event_dict)}\n\n"
                    if not event.recoverable:
                        return

            # Persist assistant message with events for auditability
            if thread_id and final_content:
                await repo.add_chat_message(
                    db,
                    thread_id,
                    "assistant",
                    final_content,
                    citations=final_citations,
                    events=events_log if events_log else None,
                )

                await db.commit()
                persisted_assistant_message = True

            yield f"data: {json.dumps({'type': 'done', 'citations': final_citations, 'thread_id': str(thread_id) if thread_id else None})}\n\n"

        except asyncio.CancelledError:
            # Client disconnected / aborted - persist partial response
            aborted = True
            raise
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)[:200], 'code': 'STREAM_ERROR', 'recoverable': False})}\n\n"
        finally:
            # Persist partial response on abort (shielded against cancellation)
            if (
                aborted
                and thread_id
                and final_content
                and not persisted_assistant_message
            ):
                try:
                    await asyncio.shield(
                        _persist_partial_response(
                            db, thread_id, final_content, final_citations, events_log
                        )
                    )
                except Exception as e:
                    logger.error(f"Error persisting partial response: {e}")

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _persist_partial_response(
    db: AsyncSession,
    thread_id: _uuid.UUID,
    content: str,
    citations: list[dict],
    events: list[dict],
) -> None:
    """Persist a partial assistant response when stream is aborted."""
    # Append a note indicating the response was interrupted
    partial_content = content.rstrip()
    if partial_content:
        partial_content += "\n\n*[Response interrupted]*"

    await repo.add_chat_message(
        db,
        thread_id,
        "assistant",
        partial_content,
        citations=citations,
        events=events if events else None,
    )
    await db.commit()


def _derive_thread_title(message: str, action: str) -> str:
    """Derive a concise thread title from the first user message."""
    normalized = " ".join((message or "").split()).strip().strip('"').strip("'")
    if normalized:
        if len(normalized) <= 72:
            return normalized
        return normalized[:69].rstrip(" ,.;:!?") + "…"

    action_titles = {
        "summary": "Case Summary",
        "next_steps": "Next Steps",
        "risk_analysis": "Risk Analysis",
    }
    return action_titles.get(action, "New Thread")


async def _generate_thread_title(agent, user_message: str, action: str) -> str:
    """Generate a concise thread title from the first user message using the LLM."""
    fallback = _derive_thread_title(user_message, action)
    if not user_message or not agent or not getattr(agent, "llm", None):
        return fallback

    truncated_query = user_message[:500]
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You generate concise, descriptive titles for chat conversations. "
                "Capture the main intent of the user's initial query in 3-7 words. "
                "Use clear, user-friendly language. Return only the title text.",
            ),
            ("human", "{query}"),
        ]
    )

    try:
        prompt_messages = prompt.format_messages(query=truncated_query)
        response = await agent.llm.ainvoke(prompt_messages)
        content = response.content
        if isinstance(content, list):
            content = " ".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in content
            )

        title = re.sub(r"\s+", " ", str(content).strip()).strip('"').strip("'")
        if not title:
            return fallback
        return title[:80]
    except Exception:
        return fallback
