from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.document import Document, DocumentChunk, DocumentStatus, DocumentVersion
from app.models.user import Department, User, Role
from app.modules.embeddings.indexing_service import DocumentIndexingService, IndexingError


@pytest.fixture()
def indexed_document_db():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    db = Session()
    user = User(
        email="indexer@example.test",
        password_hash="not-used",
        role=Role.ADMIN,
        is_active=True,
    )
    department = Department(name="Payments", code="PAY", is_active=True)
    db.add_all([user, department])
    db.flush()
    document = Document(
        title="Payments policy",
        original_filename="payments.html",
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
        checksum="b" * 64,
        storage_path="doc/source.html",
        file_size=10,
    )
    db.add(version)
    db.flush()
    chunks = [
        DocumentChunk(
            document_id=document.id,
            version_id=version.id,
            chunk_index=index,
            content=f"chunk {index}",
            token_count=2,
            metadata_json={},
        )
        for index in range(3)
    ]
    db.add_all(chunks)
    db.commit()
    yield db, document, department, version, chunks
    db.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


class FakeEmbedder:
    def __init__(self):
        self.batches = []

    def embed(self, texts):
        self.batches.append(list(texts))
        return [[float(len(texts)), 0.2] for _ in texts]


class FakeVectorStore:
    def __init__(self):
        self.calls = []

    def upsert_chunks(self, rows, vectors):
        self.calls.append((list(rows), list(vectors)))


def test_index_document_batches_chunks_and_preserves_department_metadata(indexed_document_db):
    db, document, department, version, chunks = indexed_document_db
    embedder = FakeEmbedder()
    store = FakeVectorStore()
    service = DocumentIndexingService(embedder, store, batch_size=2)

    count = service.index_document(db, document.id)

    assert count == 3
    assert [len(batch) for batch in embedder.batches] == [2, 1]
    assert [len(call[0]) for call in store.calls] == [2, 1]
    assert all(row["department_id"] == department.id for call in store.calls for row in call[0])
    assert all(row["version_id"] == version.id for call in store.calls for row in call[0])


def test_index_document_returns_zero_when_document_has_no_chunks(indexed_document_db):
    db, document, _, version, chunks = indexed_document_db
    for chunk in chunks:
        db.delete(chunk)
    db.commit()
    store = FakeVectorStore()
    service = DocumentIndexingService(FakeEmbedder(), store)

    assert service.index_document(db, document.id) == 0
    assert store.calls == []


def test_index_document_rejects_unknown_document(indexed_document_db):
    db, *_ = indexed_document_db
    service = DocumentIndexingService(FakeEmbedder(), FakeVectorStore())
    with pytest.raises(IndexingError, match="Document not found"):
        service.index_document(db, uuid4())
