import json
from uuid import uuid4

import httpx
import pytest

from app.modules.embeddings.ollama_embeddings import (
    EmbeddingServiceError,
    OllamaEmbeddingService,
)
from app.modules.retrieval.qdrant_store import QdrantVectorStore


def test_ollama_embed_batch_uses_api_embed(monkeypatch):
    class Response:
        def raise_for_status(self):
            pass
        def json(self):
            return {"embeddings": [[0.1, 0.2], [0.3, 0.4]]}

    captured = {}
    def fake_post(url, json, timeout):
        captured.update(url=url, payload=json)
        return Response()

    monkeypatch.setattr("app.modules.embeddings.ollama_embeddings.httpx.post", fake_post)
    service = OllamaEmbeddingService("http://ollama", "test-embed")
    assert service.embed(["one", "two"]) == [[0.1, 0.2], [0.3, 0.4]]
    assert captured["url"] == "http://ollama/api/embed"
    assert captured["payload"]["input"] == ["one", "two"]


def test_ollama_rejects_inconsistent_embedding_batch(monkeypatch):
    class Response:
        def raise_for_status(self):
            pass
        def json(self):
            return {"embeddings": [[0.1, 0.2], [0.3]]}
    monkeypatch.setattr(
        "app.modules.embeddings.ollama_embeddings.httpx.post",
        lambda *args, **kwargs: Response(),
    )
    with pytest.raises(EmbeddingServiceError):
        OllamaEmbeddingService().embed(["one", "two"])


def test_qdrant_upsert_creates_collection_and_points():
    calls = []
    def handler(request):
        calls.append(request)
        if request.method == "GET":
            return httpx.Response(404, json={"status": "not found"})
        return httpx.Response(200, json={"result": {"status": "ok"}})

    client = httpx.Client(base_url='http://qdrant.test', transport=httpx.MockTransport(handler))
    store = QdrantVectorStore(
        url="http://qdrant.test", collection="unit_test", client=client
    )
    chunk_id, document_id, department_id, version_id = (
        uuid4(), uuid4(), uuid4(), uuid4()
    )
    store.upsert_chunks(
        [{
            "chunk_id": chunk_id,
            "document_id": document_id,
            "department_id": department_id,
            "version_id": version_id,
            "chunk_index": 0,
            "document_name": "policy.html",
            "page_number": None,
            "section_title": "Payments",
        }],
        [[0.1, 0.2, 0.3]],
    )
    assert any(call.method == "PUT" and call.url.path.endswith("/unit_test") for call in calls)
    point_call = [call for call in calls if call.url.path.endswith("/points")][-1]
    payload = json.loads(point_call.content)
    assert payload["points"][0]["id"] == str(chunk_id)
    assert payload["points"][0]["payload"]["department_id"] == str(department_id)


def test_qdrant_search_filters_department_and_returns_hits():
    department_id = uuid4()
    def handler(request):
        payload = json.loads(request.content)
        assert payload["filter"]["must"][0]["key"] == "department_id"
        assert str(department_id) in payload["filter"]["must"][0]["match"]["any"]
        return httpx.Response(200, json={"result": {"points": [
            {"id": str(uuid4()), "score": 0.87, "payload": {"department_id": str(department_id)}}
        ]}})
    client = httpx.Client(base_url='http://qdrant.test', transport=httpx.MockTransport(handler))
    store = QdrantVectorStore(
        url="http://qdrant.test", collection="unit_test", client=client
    )
    result = store.search([0.1, 0.2], [department_id], 4)
    assert len(result) == 1
    assert result[0]["score"] == 0.87
