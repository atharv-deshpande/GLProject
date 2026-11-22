from io import BytesIO
from uuid import UUID, uuid4

import pytest
from docx import Document as DocxDocument
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import Base, get_db
from app.dependencies.auth import get_current_user
from app.main import app
from app.models.document import Document, DocumentChunk, DocumentVersion
from app.models.user import Department, Role, User
from app.modules.auth.password import hash_password
from app.modules.ingestion.processing.file_storage import resolve_storage_path


@pytest.fixture()
def api_context(tmp_path, monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    db = TestSession()
    admin = User(
        email="admin@example.test",
        password_hash=hash_password("not-used-in-this-test"),
        role=Role.ADMIN,
        is_active=True,
    )
    department = Department(name="Payments", code="PAYMENTS", is_active=True)
    db.add_all([admin, department])
    db.commit()
    db.refresh(admin)
    db.refresh(department)

    def override_db():
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: admin
    monkeypatch.setattr(settings, "DOCUMENT_STORAGE_ROOT", tmp_path / "private-documents")

    yield TestClient(app), TestSession, admin, department, tmp_path / "private-documents"

    app.dependency_overrides.clear()
    db.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def _upload(client, department_id, filename, content, content_type):
    return client.post(
        "/api/v1/documents/upload",
        data={"department_id": str(department_id)},
        files={"file": (filename, content, content_type)},
    )


def _docx_bytes():
    document = DocxDocument()
    document.add_heading("Payment controls", level=1)
    document.add_paragraph("Every payment must follow approved controls.")
    stream = BytesIO()
    document.save(stream)
    return stream.getvalue()


def _pdf_bytes():
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    stream = BytesIO()
    writer.write(stream)
    return stream.getvalue()


def test_html_upload_persists_document_version_chunks_and_original(api_context):
    client, sessions, admin, department, storage_root = api_context
    html = b"""<!doctype html><html><head><title>Payments Policy</title></head>
    <body><h1>Payments</h1><p>Payment processing must follow approved policies.</p>
    </body></html>"""
    response = _upload(client, department.id, "payments.html", html, "text/html")

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert body["total_chunks"] >= 1
    assert len(body["checksum"]) == 64

    db = sessions()
    try:
        document = db.get(Document, UUID(body["document_id"]))
        version = db.scalar(select(DocumentVersion).where(
            DocumentVersion.document_id == document.id
        ))
        chunks = db.scalars(select(DocumentChunk).where(
            DocumentChunk.document_id == document.id
        )).all()
        assert document.uploaded_by == admin.id
        assert document.department_id == department.id
        assert version.version_number == 1
        assert version.checksum == body["checksum"]
        assert chunks
        stored = resolve_storage_path(version.storage_path, storage_root)
        assert stored.read_bytes() == html
    finally:
        db.close()


def test_docx_upload_persists(api_context):
    client, sessions, _, department, _ = api_context
    response = _upload(
        client, department.id, "payments.docx", _docx_bytes(),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    assert response.status_code == 201, response.text
    assert response.json()["file_type"] == "docx"


def test_blank_pdf_is_stored_even_when_no_chunks(api_context):
    client, sessions, _, department, _ = api_context
    response = _upload(client, department.id, "blank.pdf", _pdf_bytes(), "application/pdf")
    assert response.status_code == 201, response.text
    assert response.json()["total_chunks"] == 0


def test_upload_requires_department_and_rejects_unsupported_type(api_context):
    client, _, _, department, _ = api_context
    response = _upload(client, department.id, "notes.txt", b"plain text", "text/plain")
    assert response.status_code == 415


def test_upload_rejects_missing_authentication():
    response = TestClient(app).post("/api/v1/documents/upload", files={
        "file": ("a.html", b"<html><body><p>hi</p></body></html>", "text/html")
    }, data={"department_id": str(uuid4())})
    assert response.status_code == 401


def test_regular_user_cannot_upload_even_with_department_membership(api_context):
    client, sessions, _, department, _ = api_context
    from app.models.user import UserDepartment

    db = sessions()
    try:
        regular_user = User(
            email="employee@example.test",
            password_hash=hash_password("not-used-in-this-test"),
            role=Role.USER,
            is_active=True,
        )
        db.add(regular_user)
        db.flush()
        db.add(UserDepartment(user_id=regular_user.id, department_id=department.id))
        db.commit()
    finally:
        db.close()

    from app.dependencies.auth import get_current_user
    app.dependency_overrides[get_current_user] = lambda: regular_user
    try:
        response = _upload(
            client,
            department.id,
            "payments.html",
            b"<!doctype html><html><body><p>Policy</p></body></html>",
            "text/html",
        )
        assert response.status_code == 403
    finally:
        app.dependency_overrides[get_current_user] = lambda: api_context[2]



def test_document_delete_removes_source_file_and_database_rows(api_context, monkeypatch):
    client, sessions, _, department, storage_root = api_context
    html = b"<!doctype html><html><body><p>Lifecycle test document.</p></body></html>"
    uploaded = _upload(client, department.id, "lifecycle.html", html, "text/html")
    assert uploaded.status_code == 201, uploaded.text
    document_id = UUID(uploaded.json()["document_id"])

    removed = []
    monkeypatch.setattr(
        "app.api.v1.documents.QdrantVectorStore.delete_document",
        lambda self, value: removed.append(value),
    )

    response = client.delete(f"/api/v1/documents/{document_id}")

    assert response.status_code == 204
    assert removed == [document_id]
    db = sessions()
    try:
        assert db.get(Document, document_id) is None
        assert db.scalar(
            select(DocumentVersion).where(DocumentVersion.document_id == document_id)
        ) is None
        assert db.scalar(
            select(DocumentChunk).where(DocumentChunk.document_id == document_id)
        ) is None
    finally:
        db.close()


def test_document_delete_is_idempotent_for_missing_document(api_context):
    client, _, _, _, _ = api_context
    response = client.delete(f"/api/v1/documents/{uuid4()}")
    assert response.status_code == 204


def test_document_delete_retains_database_record_when_vector_cleanup_fails(api_context, monkeypatch):
    client, sessions, _, department, _ = api_context
    html = b"<!doctype html><html><body><p>Retry cleanup test.</p></body></html>"
    uploaded = _upload(client, department.id, "retry.html", html, "text/html")
    assert uploaded.status_code == 201, uploaded.text
    document_id = UUID(uploaded.json()["document_id"])

    from app.modules.retrieval.qdrant_store import VectorStoreError

    def fail_cleanup(self, value):
        raise VectorStoreError("simulated outage")

    monkeypatch.setattr(
        "app.api.v1.documents.QdrantVectorStore.delete_document",
        fail_cleanup,
    )
    response = client.delete(f"/api/v1/documents/{document_id}")
    assert response.status_code == 503

    db = sessions()
    try:
        assert db.get(Document, document_id) is not None
    finally:
        db.close()
