# Enterprise Knowledge Intelligence Platform (EKIP)

A department-aware banking knowledge platform built with FastAPI, PostgreSQL, Qdrant and Ollama. The current MVP implements authenticated document ingestion, persistent versions/chunks, explicit vector indexing, department-scoped retrieval and evidence-grounded chat. Days 6–10 add evaluation/enrichment foundations, optional Neo4j and LangGraph adapters, and operational runbooks.

## Milestones

- **Days 1–2:** architecture, PostgreSQL/Alembic identity and document schema, Argon2id passwords and JWT authentication.
- **Day 3:** PDF/DOCX/HTML validation, parsing, normalization, chunking, private file storage and PostgreSQL persistence.
- **Day 4:** Ollama embeddings, Qdrant collection initialization and batched vector indexing.
- **Day 5:** authorized semantic search and evidence-grounded RAG chat.
- **Day 6:** golden-set smoke evaluator and candidate entity extraction.
- **Day 7:** optional Neo4j Department→Document→Chunk graph adapter.
- **Day 8:** optional fixed LangGraph retrieve→answer workflow; no autonomous write tools.
- **Day 9:** security and testing baseline plus explicit production hardening backlog.
- **Day 10:** deployment/demo runbooks and acceptance checklist.

See [Day 3–5 runbook](docs/day3-day5-runbook.md), [Day 6–10 plan](docs/day6-day10-plan.md) and [Day 6–10 runbook](docs/day6-day10-runbook.md).

## Architecture and security

- FastAPI backend and SQLAlchemy.
- PostgreSQL is authoritative for users, department memberships, documents, versions and chunks.
- Originals are stored outside public static directories.
- Ollama provides embeddings and chat models, both configurable.
- Qdrant stores vectors and department metadata. Search hits are revalidated against PostgreSQL before content is returned or sent to the LLM.
- Neo4j is optional derived graph data and is never an authorization authority.
- Retrieved document content is untrusted reference data, not instructions.
- Development data must be synthetic/public banking material. Do not use real customer or confidential bank data.

## Quick start

1. Copy .env.example to .env and set strong unique secrets.
2. Start core dependencies: `docker compose up -d postgres qdrant ollama`.
3. Create a Python 3.12+ venv inside backend and install requirements and dev requirements.
4. Pull `nomic-embed-text` and `llama3.2:latest` with Ollama.
5. Apply migrations from backend: `alembic upgrade head`.
6. Bootstrap admin: `python scripts/create_admin.py`.
7. Start API: `python -m uvicorn app.main:app --reload`.
8. Open `http://127.0.0.1:8000/docs`.

Runbook instructions are written for PowerShell. If the API runs on the host, localhost service URLs are appropriate.

## Main API flow

1. POST /api/v1/auth/login → access token.
2. POST /api/v1/documents/upload → multipart file and department_id.
3. POST /api/v1/documents/{document_id}/index → index one document's latest version.
4. POST /api/v1/search → department-scoped semantic retrieval.
5. POST /api/v1/chat → evidence-grounded answer and citation metadata.

## Tests

From backend:

```powershell
$env:DATABASE_URL = "sqlite+pysqlite:///:memory:"
$env:JWT_SECRET_KEY = "test-only-secret-key-for-ekip-32-byte-minimum"
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Unit/integration tests mock external network dependencies; separately run the Docker/Ollama/Neo4j acceptance checklist before deployment. The Angular folder is currently an Angular CLI starter, not a completed dashboard.
