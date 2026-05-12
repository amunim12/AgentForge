"""Unit tests for ChromaDB graceful degradation and vector memory helpers."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.memory import chroma as chroma_module

# Import real functions before conftest's autouse _stub_chroma replaces them
# on the module attribute.  Calling these references bypasses the stub.
from app.memory.chroma import init_chroma as _real_init_chroma
from app.memory.chroma import store_task_memory as _real_store_task_memory


# ---------------------------------------------------------------------------
# get_vector_store — returns None when ChromaDB is unavailable
# ---------------------------------------------------------------------------
class TestGetVectorStore:
    def test_returns_none_when_chroma_not_available(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(chroma_module, "_CHROMA_AVAILABLE", False)
        assert chroma_module.get_vector_store() is None

    def test_returns_none_when_client_not_initialized(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(chroma_module, "_CHROMA_AVAILABLE", True)
        monkeypatch.setattr(chroma_module, "_chroma_client", None)
        assert chroma_module.get_vector_store() is None

    def test_returns_store_when_available(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_client = MagicMock()
        fake_store = MagicMock()

        monkeypatch.setattr(chroma_module, "_CHROMA_AVAILABLE", True)
        monkeypatch.setattr(chroma_module, "_chroma_client", fake_client)

        # Patch with create=True because these names only exist in the module
        # namespace when chromadb is actually installed.
        with (
            patch.object(chroma_module, "Chroma", return_value=fake_store, create=True),
            patch.object(
                chroma_module,
                "GoogleGenerativeAIEmbeddings",
                return_value=MagicMock(),
                create=True,
            ),
        ):
            store = chroma_module.get_vector_store("my_collection")

        assert store is fake_store


# ---------------------------------------------------------------------------
# get_client
# ---------------------------------------------------------------------------
def test_get_client_returns_none_before_init(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(chroma_module, "_chroma_client", None)
    assert chroma_module.get_client() is None


def test_get_client_returns_client_after_init(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = MagicMock()
    monkeypatch.setattr(chroma_module, "_chroma_client", fake)
    assert chroma_module.get_client() is fake


# ---------------------------------------------------------------------------
# init_chroma — gracefully degrades when chromadb is not installed
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_init_chroma_skips_when_not_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(chroma_module, "_CHROMA_AVAILABLE", False)
    monkeypatch.setattr(chroma_module, "_chroma_client", None)

    await chroma_module.init_chroma()

    assert chroma_module._chroma_client is None


@pytest.mark.asyncio
async def test_init_chroma_sets_client_to_none_on_connection_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(chroma_module, "_CHROMA_AVAILABLE", True)

    fake_client = MagicMock()
    fake_client.heartbeat.side_effect = ConnectionRefusedError("refused")

    with patch.object(chroma_module, "chromadb", create=True) as mock_chromadb:
        mock_chromadb.HttpClient.return_value = fake_client
        await _real_init_chroma()

    assert chroma_module._chroma_client is None


@pytest.mark.asyncio
async def test_init_chroma_connects_successfully(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(chroma_module, "_CHROMA_AVAILABLE", True)
    monkeypatch.setattr(chroma_module, "_chroma_client", None)

    fake_client = MagicMock()
    fake_client.heartbeat.return_value = 1

    with patch.object(chroma_module, "chromadb", create=True) as mock_chromadb:
        mock_chromadb.HttpClient.return_value = fake_client
        await _real_init_chroma()

    assert chroma_module._chroma_client is fake_client

    # Cleanup
    monkeypatch.setattr(chroma_module, "_chroma_client", None)


# ---------------------------------------------------------------------------
# store_task_memory — no-op when store unavailable
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_store_task_memory_noop_when_no_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(chroma_module, "_CHROMA_AVAILABLE", False)
    monkeypatch.setattr(chroma_module, "_chroma_client", None)

    # Should not raise.
    await _real_store_task_memory(
        task_id="t1",
        content="some result text",
        metadata={"step": 0, "score": 0.8},
    )


@pytest.mark.asyncio
async def test_store_task_memory_calls_add_texts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_store = MagicMock()
    fake_store.add_texts = MagicMock()

    monkeypatch.setattr(chroma_module, "get_vector_store", lambda *_a, **_kw: fake_store)

    await _real_store_task_memory(
        task_id="task-42",
        content="final result text here",
        metadata={"step": 0, "score": 0.85},
    )

    fake_store.add_texts.assert_called_once()
    call_kwargs = fake_store.add_texts.call_args
    texts = call_kwargs.kwargs.get("texts") or call_kwargs.args[0]
    assert texts == ["final result text here"]
    metadatas = call_kwargs.kwargs.get("metadatas") or call_kwargs.args[1]
    assert metadatas[0]["task_id"] == "task-42"
    assert metadatas[0]["score"] == 0.85
    ids = call_kwargs.kwargs.get("ids") or call_kwargs.args[2]
    assert ids == ["task-42_0"]


@pytest.mark.asyncio
async def test_store_task_memory_swallows_store_exceptions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_store = MagicMock()
    fake_store.add_texts.side_effect = RuntimeError("chroma write failed")

    monkeypatch.setattr(chroma_module, "get_vector_store", lambda *_a, **_kw: fake_store)

    # Must not raise; storage errors are best-effort.
    await _real_store_task_memory(
        task_id="task-err",
        content="content",
        metadata={"step": 0},
    )


# ---------------------------------------------------------------------------
# retrieve_similar_tasks — returns empty list when unavailable
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_retrieve_similar_tasks_returns_empty_when_no_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(chroma_module, "_CHROMA_AVAILABLE", False)
    monkeypatch.setattr(chroma_module, "_chroma_client", None)

    results = await chroma_module.retrieve_similar_tasks("compare vector databases")
    assert results == []


@pytest.mark.asyncio
async def test_retrieve_similar_tasks_returns_page_contents(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_doc_1 = MagicMock()
    fake_doc_1.page_content = "past result about Pinecone"
    fake_doc_2 = MagicMock()
    fake_doc_2.page_content = "past result about Weaviate"

    fake_store = MagicMock()
    fake_store.similarity_search.return_value = [fake_doc_1, fake_doc_2]

    monkeypatch.setattr(chroma_module, "get_vector_store", lambda *_a, **_kw: fake_store)

    results = await chroma_module.retrieve_similar_tasks("vector db comparison", k=2)
    assert results == ["past result about Pinecone", "past result about Weaviate"]
    fake_store.similarity_search.assert_called_once_with("vector db comparison", k=2)


@pytest.mark.asyncio
async def test_retrieve_similar_tasks_returns_empty_on_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_store = MagicMock()
    fake_store.similarity_search.side_effect = RuntimeError("search failed")

    monkeypatch.setattr(chroma_module, "get_vector_store", lambda *_a, **_kw: fake_store)

    results = await chroma_module.retrieve_similar_tasks("some query")
    assert results == []
