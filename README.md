# Enterprise Knowledge Intelligence Platform (EKIP)

A department-aware banking knowledge platform built with FastAPI, PostgreSQL, Qdrant and Ollama. The current MVP implements authenticated document ingestion, persistent document versions/chunks, explicit vector indexing, department-scoped semantic search and evidence-grounded chat with source citations.

## Implemented milestones

- **Day 1–2:** architecture, PostgreSQL/Alembic identity and document schema, Argon2id password hashing and JWT authentication foundation.
- **Day 3:** PDF/DOCX/HTML validation, parsing, normalization, chunking, private original-file storage, checksum/version metadata, PostgreSQL persistence and department-scoped upload authorization.
- **Day 4:** configurable Ollama embeddings, Qdrant collection initialization, batched vector indexing and department payload filtering.
- **Day 5:** authorized semantic search and RAG chat endpoints with source citations and an explicit insufficient-evidence response.

See [`docs/day3-day5-runbook.md`](docs/day3-day5-runbook.md) for setup, API usage and operational checks.

## Architecture

- Angular 18 frontend (planned/in progress; this repository snapshot currently focuses on backend APIs).
- FastAPI backend and SQLAlchemy 2.x.
- PostgreSQL is the source of truth for users, memberships, documents, versions and chunks.
- Local filesystem storage keeps originals outside public static directories.
- Ollama provides `nomic-embed-text` embeddings and `llama3.2:latest` chat by default. Both are configurable.
- Qdrant stores vectors and department metadata; every search result is revalidated against PostgreSQL before content is returned or sent to the LLM.

## Quick start

1. Copy `.env.example` to `.env` and set strong local secrets.
2. Start infrastructure: `docker compose up -d postgres qdrant ollama`.
3. Create a Python 3.12+ virtual environment in `backend` and install dependencies:
   - `python -m pip install -r requirements.txt`
   - `python -m pip install -r requirements-dev.txt`
4. Pull the local Ollama models:
   - `ollama pull nomic-embed-text`
   - `ollama pull llama3.2:latest`
5. Apply migrations from `backend`: `alembic upgrade head`.
6. Bootstrap an administrator: `python scripts/create_admin.py`.
7. Start the API from `backend`: `python -m uvicorn app.main:app --reload`.
8. Open `http://127.0.0.1:8000/docs`.

The backend must be able to reach PostgreSQL, Qdrant and Ollama at the URLs configured in `.env`. If the API runs on the host, the default localhost URLs are appropriate.

## Main API flow

1. `POST /api/v1/auth/login` → obtain an access token.
2. `POST /api/v1/documents/upload` → multipart form with `file` and `department_id`. Only Admins and Department Managers assigned to that department can upload.
3. `POST /api/v1/documents/{document_id}/index` → generate embeddings and upsert chunks to Qdrant. This is explicit so document persistence can succeed even while AI services are offline.
4. `POST /api/v1/search` → department-scoped semantic search.
5. `POST /api/v1/chat` → evidence-grounded answer and citations.

## Security notes

- Never commit `.env`, tokens, passwords, private documents or local storage.
- Use synthetic/public banking documents for development.
- PostgreSQL remains the authorization authority; Qdrant filters are defense in depth.
- Retrieved text is treated as untrusted data by the answer prompt.
- The initial MVP does not yet provide enterprise SSO/MFA, malware scanning, background job workers, production rate limiting or a formal retention workflow.

## Tests

From `backend`, with test dependencies installed:

```powershell
$env:DATABASE_URL = "sqlite+pysqlite:///:memory:"
$env:JWT_SECRET_KEY = "test-only-secret-key-for-ekip-32-byte-minimum"
python -m pytest -q
```

The test suite uses SQLite and mocks Ollama/Qdrant network calls; it does not require running those services.
