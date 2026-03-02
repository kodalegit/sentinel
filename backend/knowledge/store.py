"""Knowledge store for vector similarity search using pgvector."""

import json
import uuid
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import KnowledgeDocumentDB, KnowledgeChunkDB
from knowledge.embeddings import embed_query, embed_texts
from knowledge.loader import DocumentChunk


@dataclass
class SearchResult:
    """A search result from the knowledge base."""

    chunk_id: str
    document_id: str
    document_title: str
    category: str
    source_url: Optional[str]
    content: str
    page_number: Optional[int]
    score: float


class KnowledgeStore:
    """
    Vector store wrapper for knowledge base operations.
    Uses pgvector for similarity search with HNSW index.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def add_document_chunks(
        self,
        document_id: uuid.UUID,
        chunks: list[DocumentChunk],
    ) -> int:
        """
        Embed and store document chunks.

        Args:
            document_id: UUID of the parent document
            chunks: List of DocumentChunk objects

        Returns:
            Number of chunks stored
        """
        if not chunks:
            return 0

        texts = [c.content for c in chunks]
        embeddings = await embed_texts(texts)

        for chunk, embedding in zip(chunks, embeddings):
            # Convert embedding to PostgreSQL array literal format
            embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
            chunk_id = uuid.uuid4()

            # Use proper SQL with explicit cast - avoid named parameter issues with ::vector cast
            await self.db.execute(
                text(
                    """
                    INSERT INTO knowledge_chunks
                    (id, document_id, content, chunk_index, page_number, chunk_metadata, embedding)
                    VALUES (:id, :document_id, :content, :chunk_index, :page_number, :metadata, CAST(:embedding AS vector))
                    """
                ),
                {
                    "id": chunk_id,
                    "document_id": document_id,
                    "content": chunk.content,
                    "chunk_index": chunk.chunk_index,
                    "page_number": chunk.page_number,
                    "metadata": json.dumps(chunk.metadata or {}),
                    "embedding": embedding_str,
                },
            )

        doc = await self.db.get(KnowledgeDocumentDB, document_id)
        if doc:
            doc.chunk_count = len(chunks)

        return len(chunks)

    async def similarity_search(
        self,
        query: str,
        category: Optional[str] = None,
        k: int = 5,
    ) -> list[SearchResult]:
        """
        Search for similar chunks using cosine similarity.

        Args:
            query: Search query text
            category: Optional category filter (LAW, CASE_LAW, REGULATION, GUIDELINE)
            k: Number of results to return

        Returns:
            List of SearchResult objects ordered by similarity
        """
        query_embedding = await embed_query(query)
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        category_filter = ""
        params = {"embedding": embedding_str, "k": k}

        if category:
            category_filter = "AND d.category = :category"
            params["category"] = category.upper()

        result = await self.db.execute(
            text(
                f"""
                SELECT
                    c.id as chunk_id,
                    c.document_id,
                    d.title as document_title,
                    d.category,
                    d.source_url,
                    c.content,
                    c.page_number,
                    1 - (c.embedding <=> CAST(:embedding AS vector)) as score
                FROM knowledge_chunks c
                JOIN knowledge_documents d ON c.document_id = d.id
                WHERE c.embedding IS NOT NULL
                {category_filter}
                ORDER BY c.embedding <=> CAST(:embedding AS vector)
                LIMIT :k
                """
            ),
            params,
        )

        rows = result.fetchall()
        return [
            SearchResult(
                chunk_id=str(row.chunk_id),
                document_id=str(row.document_id),
                document_title=row.document_title,
                category=row.category,
                source_url=row.source_url,
                content=row.content,
                page_number=row.page_number,
                score=float(row.score),
            )
            for row in rows
        ]

    async def delete_document_chunks(self, document_id: uuid.UUID) -> int:
        """
        Delete all chunks for a document.

        Args:
            document_id: UUID of the document

        Returns:
            Number of chunks deleted
        """
        result = await self.db.execute(
            text("DELETE FROM knowledge_chunks WHERE document_id = :doc_id"),
            {"doc_id": document_id},
        )
        return result.rowcount or 0


_knowledge_store: Optional[KnowledgeStore] = None


def get_knowledge_store(db: AsyncSession) -> KnowledgeStore:
    """Get a KnowledgeStore instance for the given database session."""
    return KnowledgeStore(db)
