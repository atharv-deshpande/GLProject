# Priority 2 — Reliable document lifecycle

## Scope

This increment hardens document deletion and derived-index cleanup. PostgreSQL remains the source of truth; filesystem, Qdrant and optional Neo4j data are derived copies.

## Implemented in this branch

- Qdrant supports idempotent deletion of all points filtered by `document_id`. A missing collection is treated as already-clean.
- Optional Neo4j cleanup removes a document node and its owned chunk nodes. It is gated by `NEO4J_ENABLED` and remains disabled by default until Neo4j is provisioned.
- `DELETE /api/v1/documents/{document_id}` checks the caller's department upload/admin permission before cleanup.
- Deletion order is filesystem versions → Qdrant points → optional Neo4j graph → PostgreSQL document row (cascading versions/chunks).
- Each external cleanup operation is safe to retry. If a dependency fails, PostgreSQL metadata is retained so the caller can retry rather than losing the identifiers needed for cleanup.
- Repeated deletion of a missing document returns HTTP 204.
- File deletion tolerates an already-removed file/directory.
- Integration tests cover successful cleanup, repeated deletion and a simulated Qdrant outage.

## Configuration

- `NEO4J_ENABLED=false` by default. Set it to `true` only when Neo4j is configured and the graph contains EKIP document metadata.
- Configure `NEO4J_URI`, `NEO4J_USER` and `NEO4J_PASSWORD` when enabling graph cleanup.
- Qdrant uses the existing `QDRANT_URL`, `QDRANT_COLLECTION` and optional `QDRANT_API_KEY`.

## Operational behavior

A failed deletion returns HTTP 503 for a dependent-store failure and retains the PostgreSQL document row. Retry the same DELETE after the dependency is healthy. Some earlier steps may already have completed; they are intentionally idempotent.

Do not manually delete PostgreSQL rows or source files to recover a partial deletion. Doing so can remove the identifiers required to reconcile derived stores.

## Remaining lifecycle work (not claimed complete)

1. Durable `processing_jobs` table/outbox and worker with leases, bounded retries, backoff and dead-letter state.
2. Asynchronous ingestion/indexing; current upload and index endpoints still execute synchronously.
3. Persisted per-version indexing state and an idempotency key for job submission. Qdrant upsert IDs are deterministic chunk UUIDs, but repeat indexing still regenerates embeddings.
4. Version replacement endpoint and retention policy. Current upload creates version 1 for a new document.
5. Reconciliation command to detect orphaned files and stale Qdrant/Neo4j records after process or host crashes.
6. Live PostgreSQL/Qdrant/Neo4j fault-injection and restore tests.

## Verification

From `backend/`:

```powershell
$env:DATABASE_URL = "sqlite+pysqlite:///:memory:"
$env:JWT_SECRET_KEY = "test-only-secret-key-for-ekip-32-byte-minimum"
python -m pytest tests/integration/test_documents_api.py -q
```

The automated tests use SQLite and mocked Qdrant cleanup. They do not prove live cross-store deletion against a running Qdrant or Neo4j deployment.
