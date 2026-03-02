"""Intelligence routes for chat, summaries, and knowledge base management."""

import json
import uuid as _uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from models import (
    KnowledgeDocument,
    KnowledgeDocumentCreate,
    KnowledgeDocumentCategory,
    KnowledgeChunk,
    KnowledgeStats,
    ChatThread,
    ChatMessage,
    ChatRequest,
    CaseSummaryResponse,
    NextStepsResponse,
    Citation,
)
from state import State
from db.config import get_db
from db import repository as repo
from auth.dependencies import CurrentUser, AdminOnly
from intelligence.agent import (
    get_agent,
    set_agent_context,
    AgentContext,
)
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


@router.get("/knowledge/documents/{document_id}/chunks", response_model=list[KnowledgeChunk])
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
    threads = await repo.get_chat_threads(
        db, _uuid.UUID(case_id), current_user.id
    )
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


@router.get("/cases/{case_id}/chat/threads/{thread_id}/messages", response_model=list[ChatMessage])
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
            created_at=m.created_at,
        )
        for m in messages
    ]


@router.post("/cases/{case_id}/chat/stream")
async def chat_stream(
    case_id: str,
    body: ChatRequest,
    state: State,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Stream a chat response with SSE."""
    case_db = await repo.get_case(db, _uuid.UUID(case_id))
    if not case_db:
        raise HTTPException(status_code=404, detail="Case not found")

    thread_id = None
    if body.thread_id:
        thread = await repo.get_chat_thread(db, _uuid.UUID(body.thread_id))
        if not thread or thread.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Thread not found")
        thread_id = thread.id
    else:
        title = body.message[:80] if len(body.message) > 80 else body.message
        thread = await repo.create_chat_thread(
            db, _uuid.UUID(case_id), current_user.id, title=title
        )
        thread_id = thread.id
        await db.flush()

    await repo.add_chat_message(db, thread_id, "user", body.message)

    history = []
    if body.thread_id:
        messages = await repo.get_thread_messages(db, thread_id, limit=20)
        for m in messages[:-1]:
            history.append({"role": m.role, "content": m.content})

    tender_id = str(case_db.tender_id) if case_db.tender_id else None

    set_agent_context(
        AgentContext(
            case_id=case_id,
            tender_id=tender_id,
            db_session=db,
            app_state=state,
        )
    )

    agent = get_agent()

    async def generate():
        try:
            response_text, citations = await agent.chat(body.message, history)

            for i in range(0, len(response_text), 20):
                chunk = response_text[i : i + 20]
                yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"

            await repo.add_chat_message(
                db, thread_id, "assistant", response_text, citations=citations
            )
            await db.commit()

            yield f"data: {json.dumps({'type': 'done', 'citations': citations, 'thread_id': str(thread_id)})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)[:200]})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.post("/cases/{case_id}/summary", response_model=CaseSummaryResponse)
async def generate_case_summary(
    case_id: str,
    state: State,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Generate an AI summary of the case."""
    case_db = await repo.get_case(db, _uuid.UUID(case_id))
    if not case_db:
        raise HTTPException(status_code=404, detail="Case not found")

    tender_id = str(case_db.tender_id) if case_db.tender_id else None

    set_agent_context(
        AgentContext(
            case_id=case_id,
            tender_id=tender_id,
            db_session=db,
            app_state=state,
        )
    )

    agent = get_agent()
    summary_text, citations, key_findings = await agent.generate_summary()

    return CaseSummaryResponse(
        summary=summary_text,
        citations=[Citation(**c) for c in citations],
        key_findings=key_findings,
    )


@router.post("/cases/{case_id}/next-steps", response_model=NextStepsResponse)
async def suggest_next_steps(
    case_id: str,
    state: State,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Get AI-suggested next steps for the investigation."""
    case_db = await repo.get_case(db, _uuid.UUID(case_id))
    if not case_db:
        raise HTTPException(status_code=404, detail="Case not found")

    tender_id = str(case_db.tender_id) if case_db.tender_id else None

    set_agent_context(
        AgentContext(
            case_id=case_id,
            tender_id=tender_id,
            db_session=db,
            app_state=state,
        )
    )

    agent = get_agent()
    suggestions, citations = await agent.suggest_next_steps()

    return NextStepsResponse(
        suggestions=suggestions,
        citations=[Citation(**c) for c in citations],
    )
