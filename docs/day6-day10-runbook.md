# EKIP Days 6–10 Runbook

## 1. Configure local environment

From the repository root, copy `.env.example` to `.env`. Set strong, unique local values for database credentials, `JWT_SECRET_KEY` and `NEO4J_PASSWORD`. Do not commit `.env`.

## 2. Start core services

Run in PowerShell from the repository root:

```powershell
docker compose up -d postgres qdrant redis ollama
```

Neo4j is optional for the base API. Start it when exercising Day 7:

```powershell
docker compose up -d neo4j
```

Pull the configured Ollama models:

```powershell
ollama pull nomic-embed-text
ollama pull llama3.2:latest
```

## 3. Start the backend

From `backend`, activate your virtual environment, install dependencies and apply migrations:

```powershell
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
alembic upgrade head
python -m uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs`.

## 4. Day 6 — Evaluate and enrich

Run the automated tests:

```powershell
$env:DATABASE_URL = "sqlite+pysqlite:///:memory:"
$env:JWT_SECRET_KEY = "test-only-secret-key-for-ekip-32-byte-minimum"
python -m pytest -q
```

Add reviewed, synthetic/public banking examples to the golden dataset. The evaluator checks required terms deterministically; it is a smoke metric, not a semantic-quality score. Entity extraction outputs candidates only and must not be treated as verified facts.

## 5. Verify Qdrant indexing

1. Login through `POST /api/v1/auth/login`.
2. Copy the returned access token into the Swagger Authorize control as a Bearer token.
3. Upload a synthetic PDF, DOCX or HTML document using `POST /api/v1/documents/upload`.
4. Call `POST /api/v1/documents/{document_id}/index` for that document ID.
5. Repeat the indexing request for each other document ID that needs indexing.
6. Confirm `indexed_chunks` matches the chunk count for that document's latest version.

The current endpoint indexes one document's latest version per request. Qdrant `points_count` is collection-wide, not per-document. Point IDs are chunk UUIDs, so re-indexing the same version upserts the same points.

If the collection is missing, check whether indexing was actually invoked and whether the document has persisted chunks. Do not manually create a collection with an assumed vector dimension; the collection must match the configured embedding model.

## 6. Day 7 — Neo4j graph adapter

Configure `NEO4J_URI`, `NEO4J_USER` and `NEO4J_PASSWORD`, install the Neo4j Python driver if using the adapter, and verify connectivity. Invoke graph upsert only with document and chunk rows already authorized through PostgreSQL. The graph is derived data and is not an access-control source.

## 7. Day 8 — LangGraph workflow

Install LangGraph only when exercising the optional workflow. The current workflow has a fixed retrieve → answer path and deliberately has no privileged tools. Do not expose it as production chat until vector hits are joined to PostgreSQL, authorized chunk text is loaded, and citation IDs are validated.

## 8. Day 9 — Security gate

Before production, implement and verify:
- durable indexing queue, retries, idempotency and reconciliation;
- citation validation and structured audit events;
- rate limiting and upload malware scanning;
- deletion propagation across PostgreSQL, file storage, Qdrant and Neo4j;
- secret rotation, token issuer/audience checks, refresh-token controls and SSO/MFA;
- dependency scanning, backup/restore tests and structured traces.

Use only synthetic or public banking documents in development. Never upload real customer or confidential bank data.

## 9. Day 10 — End-to-end demo checklist

- [ ] Login and retrieve the current user.
- [ ] Upload a synthetic PDF/DOCX/HTML file.
- [ ] Confirm document, version and chunk rows in PostgreSQL.
- [ ] Index every document and confirm per-document indexed chunk counts.
- [ ] Confirm Qdrant points exist.
- [ ] Search and chat; verify returned sources are authorized.
- [ ] Test department isolation with a second user.
- [ ] Stop Ollama or Qdrant temporarily and confirm controlled 503 responses.
- [ ] Check logs for secrets, source text and private storage paths.
- [ ] Restore services and repeat the successful request.

The Angular directory is currently an Angular CLI starter; this runbook validates the backend API and data services.
