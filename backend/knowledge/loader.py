"""Document loading and chunking for the knowledge base."""

import io
from dataclasses import dataclass
from typing import Optional

import pymupdf
from langchain_text_splitters import RecursiveCharacterTextSplitter


@dataclass
class DocumentChunk:
    """A chunk of text from a document with metadata."""

    content: str
    chunk_index: int
    page_number: Optional[int] = None
    metadata: Optional[dict] = None


def chunk_pdf_document(
    pdf_bytes: bytes,
    chunk_size: int = 800,
    chunk_overlap: int = 200,
) -> list[DocumentChunk]:
    """
    Extract text from a PDF and split into chunks.

    Args:
        pdf_bytes: Raw PDF file bytes
        chunk_size: Target size of each chunk in characters
        chunk_overlap: Overlap between consecutive chunks

    Returns:
        List of DocumentChunk objects with page numbers
    """
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    pages_text: list[tuple[int, str]] = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()
        if text.strip():
            pages_text.append((page_num + 1, text))

    doc.close()

    if not pages_text:
        return []

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks: list[DocumentChunk] = []
    chunk_index = 0

    for page_num, page_text in pages_text:
        page_chunks = splitter.split_text(page_text)
        for chunk_text in page_chunks:
            if chunk_text.strip():
                chunks.append(
                    DocumentChunk(
                        content=chunk_text.strip(),
                        chunk_index=chunk_index,
                        page_number=page_num,
                        metadata={"source_page": page_num},
                    )
                )
                chunk_index += 1

    return chunks


def chunk_text_document(
    text: str,
    chunk_size: int = 800,
    chunk_overlap: int = 200,
) -> list[DocumentChunk]:
    """
    Split plain text into chunks.

    Args:
        text: Plain text content
        chunk_size: Target size of each chunk in characters
        chunk_overlap: Overlap between consecutive chunks

    Returns:
        List of DocumentChunk objects
    """
    if not text.strip():
        return []

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    text_chunks = splitter.split_text(text)
    chunks: list[DocumentChunk] = []

    for idx, chunk_text in enumerate(text_chunks):
        if chunk_text.strip():
            chunks.append(
                DocumentChunk(
                    content=chunk_text.strip(),
                    chunk_index=idx,
                    page_number=None,
                    metadata={},
                )
            )

    return chunks
