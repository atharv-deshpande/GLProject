from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.dependencies.auth import get_current_user
from app.main import app
from app.models.document import Document, DocumentChunk, DocumentStatus, DocumentVersion
from app.models.user import Department, Role, User, UserDepartment
from app.modules.auth.password import hash_password


@pytest.fixture()
def knowledge_context(monkeypatch, tmp_path):
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    db = TestSession()

    user = User(
        email="payments-user@example.test",
        password_hash=hash_password("not-used-in-this-test"),
        role=Role.USER,
        is_active=True,
    )
    payments = Department(name="Payments", code="PAY", is_active=True)
    risk = Department(name="Risk", code="RISK", is_active=True)
    db.add_all([user, payments, risk])
    db.flush()
    db.add(UserDepartment(user_id=user.id, department_id=payments.id))

    def add_document(department, filename, text):
        document = Document(
            title=filename,
            original_filename=filename,
            file_type="html",
            department_id=department.id,
            uploaded_by=user.id,
            status=DocumentStatus.COMPLETED,
        )
        db.add(document)
        db.flush()
        version = DocumentVersion(
            document_id=document.id,
            version_number=1,
            checksum="a" * 64,
            storage_path=f"{uuid4()}/source.html",
            file_size=len(text),
        )
        db.add(version)
        db.flush()
        chunk = DocumentChunk(
            document_id=document.id,
            version_id=version.id,
            chunk_index=0,
            content=text,
            page_number=None,
            section_title="Policy",
            token_count=10,
            metadata_json={},
        )
        db.add(chunk)
        db.flush()
        return chunk

    allowed_chunk = add_document(payments, "payments.html", "Approved payment workflow.")
    forbidden_chunk = add_document(risk, "risk.html", "Restricted risk workflow.")
    db.commit()

    def override_db():
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: user

    class FakeEmbedder:
        def embed_query(self, query):
            return [0.1, 0.2, 0.3]

    class FakeVectorStore:
        results = []
        last_limit = None

        def search(self, vector, department_ids, limit):
            self.last_limit = limit
            return list(self.results)

    monkeypatch.setattr(
        "app.api.v1.knowledge.OllamaEmbeddingService", FakeEmbedder
    )
    monkeypatch.setattr(
        "app.api.v1.knowledge.QdrantVectorStore", FakeVectorStore
    )

    yield (
        TestClient(app), TestSession, user, payments, risk,
        allowed_chunk, forbidden_chunk, FakeVectorStore,
    )

    app.dependency_overrides.clear()
    db.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_search_returns_only_postgres_authorized_department_chunks(knowledge_context):
    client, _, _, payments, _, allowed, forbidden, vector_store = knowledge_context
    vector_store.results = [
        {"chunk_id": str(allowed.id), "score": 0.91, "payload": {}},
        {"chunk_id": str(forbidden.id), "score": 0.99, "payload": {}},
    ]

    response = client.post("/api/v1/search", json={"query": "payment workflow"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    assert body["results"][0]["chunk_id"] == str(allowed.id)
    assert "Restricted risk workflow" not in response.text


def test_search_rejects_unassigned_department(knowledge_context):
    client, _, _, _, risk, *_ = knowledge_context
    response = client.post(
        "/api/v1/search",
        json={"query": "risk workflow", "department_id": str(risk.id)},
    )
    assert response.status_code == 403


def test_chat_returns_insufficient_evidence_when_no_chunks(knowledge_context):
    client, _, _, _, _, _, _, vector_store = knowledge_context
    vector_store.results = []

    response = client.post("/api/v1/chat", json={"query": "payment exception handling"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["insufficient_evidence"] is True
    assert body["citations"] == []
    assert "not find sufficiently relevant information" in body["answer"]


def test_chat_returns_source_citations_for_grounded_answer(knowledge_context, monkeypatch):
    client, _, _, _, _, allowed, _, vector_store = knowledge_context
    vector_store.results = [
        {"chunk_id": str(allowed.id), "score": 0.93, "payload": {}}
    ]

    class FakeAnswerService:
        def answer(self, question, sources):
            assert sources[0]["source_id"] == "S1"
            return "Follow the approved workflow [S1]."

    monkeypatch.setattr("app.api.v1.knowledge.OllamaAnswerService", FakeAnswerService)
    response = client.post("/api/v1/chat", json={"query": "payment workflow"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["insufficient_evidence"] is False
    assert len(body["citations"]) == 1
    assert body["citations"][0]["chunk_id"] == str(allowed.id)


def test_chat_citations_are_limited_to_markers_present_in_answer(knowledge_context, monkeypatch):
    client, _, _, _, _, allowed, _, vector_store = knowledge_context
    vector_store.results = [
        {"chunk_id": str(allowed.id), "score": 0.93, "payload": {}}
    ]

    class FakeAnswerService:
        def answer(self, question, sources):
            return "Use the approved workflow [S1]. Do not trust [S9]."

    monkeypatch.setattr("app.api.v1.knowledge.OllamaAnswerService", FakeAnswerService)
    response = client.post("/api/v1/chat", json={"query": "payment workflow"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["citations"]) == 1
    assert body["citations"][0]["source_id"] == "S1"
    assert "[unverified citation S9]" in body["answer"]


def test_chat_returns_no_citations_when_answer_has_no_valid_source_marker(knowledge_context, monkeypatch):
    client, _, _, _, _, allowed, _, vector_store = knowledge_context
    vector_store.results = [
        {"chunk_id": str(allowed.id), "score": 0.93, "payload": {}}
    ]

    class FakeAnswerService:
        def answer(self, question, sources):
            return "The available evidence is inconclusive."

    monkeypatch.setattr("app.api.v1.knowledge.OllamaAnswerService", FakeAnswerService)
    response = client.post("/api/v1/chat", json={"query": "payment workflow"})

    assert response.status_code == 200, response.text
    assert response.json()["citations"] == []


def test_dashboard_summary_is_scoped_to_authorized_departments(knowledge_context):
    client, _, _, payments, _, _, _, _ = knowledge_context

    response = client.get("/api/v1/dashboard/summary")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["department_count"] == 1
    assert body["departments"][0]["name"] == payments.name
    assert body["total_documents"] == 1
    assert body["total_chunks"] == 1


def test_document_library_never_returns_unassigned_department_documents(knowledge_context):
    client, _, _, _, _, allowed, forbidden, _ = knowledge_context

    response = client.get("/api/v1/library/documents")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == str(allowed.document_id)
    assert str(forbidden.document_id) not in response.text


def test_document_library_rejects_explicit_unassigned_department(knowledge_context):
    client, _, _, _, risk, *_ = knowledge_context

    response = client.get(
        "/api/v1/library/documents",
        params={"department_id": str(risk.id)},
    )

    assert response.status_code == 403
