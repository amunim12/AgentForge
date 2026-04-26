"""ChromaDB vector store for agent long-term memory / RAG."""
from __future__ import annotations

from typing import Any

import chromadb
import structlog
from chromadb.config import Settings as ChromaSettings
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from app.core.config import settings

logger = structlog.get_logger()

_chroma_client: chromadb.ClientAPI | None = None


async def init_chroma() -> None:
    """Initialize the ChromaDB HTTP client at app startup.

    Failure is logged but not fatal â agents still run without RAG memory.
    """
    global _chroma_client
    try:
        _chroma_client = chromadb.HttpClient(
            host=settings.CHROMA_HOST,
            port=settings.CHROMA_PORT,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        _chroma_client.heartbeat()
        logger.info(
            "ChromaDB connected",
            host=settings.CHROMA_HOST,
            port=settings.CHROMA_PORT,
        )
    except Exception as exc:
        logger.warning(
            "ChromaDB unavailable â RAG disabled for this session",
            error=str(exc),
        )
        _chroma_client = None


def get_client() -> chromadb.ClientAPI | None:
    return _chroma_client


def get_vector_store(collection_name: str = "agent_memory") -> Chroma | None:
    """Return a LangChain Chroma wrapper, or None if Chroma is unavailable."""
    if _chroma_client is None:
        return None
    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/embedding-001",
        google_api_key=settings.GOOGLE_API_KEY,
    )
    return Chroma(
        client=_chroma_client,
        collection_name=collection_name,
        embedding_function=embeddings,
    )


async def store_task_memory(
    task_id: str,
    content: str,
    metadata: dict[str, Any],
) -> None:
    """Persist an executor output chunk for later retrieval."""
    store = get_vector_store()
    if store is None:
        return
    try:
        store.add_texts(
            texts=[content],
            metadatas=[{"task_id": task_id, **metadata}],
            ids=[f"{task_id}_{metadata.get('step', 0)}"],
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("Failed to store task memory", task_id=task_id, error=str(exc))


async def retrieve_similar_tasks(query: str, k: int = 3) -> list[str]:
    """Return up to k similar past task excerpts for RAG context."""
    store = get_vector_store()
    if store is None:
        return []
    try:
        docs = store.similarity_search(query, k=k)
        return [doc.page_content for doc in docs]
    except Exception as exc:  # pragma: no cover
        logger.warning("Similarity search failed", error=str(exc))
        return []
