"""ChromaDB vector store for agent long-term memory / RAG.

chromadb and langchain-chroma are optional dependencies. When not installed
the module degrades gracefully: all public functions return None / empty list.
"""
from __future__ import annotations

from typing import Any

import structlog

from app.core.config import settings

logger = structlog.get_logger()

try:
    import chromadb
    from langchain_chroma import Chroma
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
    _CHROMA_AVAILABLE = True
except ImportError:
    _CHROMA_AVAILABLE = False

_chroma_client: Any = None


async def init_chroma() -> None:
    """Initialize the ChromaDB HTTP client at app startup.

    Failure is logged but not fatal — agents still run without RAG memory.
    """
    global _chroma_client
    if not _CHROMA_AVAILABLE:
        logger.warning("chromadb not installed — RAG disabled (see requirements.txt)")
        return
    try:
        client_kwargs: dict[str, Any] = {"host": settings.CHROMA_HOST, "port": settings.CHROMA_PORT}
        if settings.CHROMA_AUTH_TOKEN:
            client_kwargs["headers"] = {"Authorization": f"Bearer {settings.CHROMA_AUTH_TOKEN}"}
        _chroma_client = chromadb.HttpClient(**client_kwargs)
        _chroma_client.heartbeat()
        logger.info(
            "ChromaDB connected",
            host=settings.CHROMA_HOST,
            port=settings.CHROMA_PORT,
        )
    except Exception as exc:
        logger.warning(
            "ChromaDB unavailable — RAG disabled for this session",
            error=str(exc),
        )
        _chroma_client = None


def get_client() -> Any | None:
    return _chroma_client


def get_vector_store(collection_name: str = "agent_memory") -> Any | None:
    """Return a LangChain Chroma wrapper, or None if Chroma is unavailable."""
    if not _CHROMA_AVAILABLE or _chroma_client is None:
        return None
    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/embedding-001",
        google_api_key=settings.GOOGLE_API_KEY,  # type: ignore[arg-type]  # langchain-google-genai uses pydantic v1 SecretStr internally
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
