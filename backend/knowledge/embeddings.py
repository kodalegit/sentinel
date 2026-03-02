"""Embedding model initialization for the knowledge base."""

from typing import Optional

from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings

from config import settings


_embedding_model: Optional[Embeddings] = None


def get_embedding_model(
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> Embeddings:
    """
    Get or initialize the embedding model.

    Args:
        provider: Embedding provider (default: "openai")
        model: Model name (default: "text-embedding-3-small")

    Returns:
        LangChain Embeddings instance
    """
    global _embedding_model

    provider = provider or "openai"
    model = model or "text-embedding-3-small"

    if _embedding_model is not None:
        return _embedding_model

    if provider == "openai":
        _embedding_model = OpenAIEmbeddings(model=model)
    else:
        _embedding_model = OpenAIEmbeddings(model=model)

    return _embedding_model


def reset_embedding_model() -> None:
    """Reset the cached embedding model (used when settings change)."""
    global _embedding_model
    _embedding_model = None


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Embed a list of texts.

    Args:
        texts: List of text strings to embed

    Returns:
        List of embedding vectors
    """
    model = get_embedding_model()
    return await model.aembed_documents(texts)


async def embed_query(text: str) -> list[float]:
    """
    Embed a single query text.

    Args:
        text: Query text to embed

    Returns:
        Embedding vector
    """
    model = get_embedding_model()
    return await model.aembed_query(text)
