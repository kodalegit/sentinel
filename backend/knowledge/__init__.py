"""Knowledge base package for RAG-powered legal document search."""

from knowledge.loader import chunk_pdf_document, chunk_text_document
from knowledge.embeddings import get_embedding_model
from knowledge.store import KnowledgeStore, get_knowledge_store

__all__ = [
    "chunk_pdf_document",
    "chunk_text_document",
    "get_embedding_model",
    "KnowledgeStore",
    "get_knowledge_store",
]
