# P1 — Reliable document lifecycle and audit/observability

## Implemented foundation

- PostgreSQL `processing_jobs` table provides durable work queue records.
- Workers claim rows with `FOR UPDATE SKIP LOCKED`, lease expiry and owner checks.
- Failures retry with capped exponential backoff; exhausted jobs transition to `DEAD`.
- Upload persists document/version/chunks and enqueues the indexing job in one transaction.
- Documents retain indexing status, error, indexed chunk count and indexed timestamp.
- `audit_logs` stores request-level activity and explicit document upload/index-queue actions.
- Middleware generates/accepts a safe `X-Request-ID`, echoes it and scopes it through a context variable.
- JSON log formatting redacts credential-like keys and email addresses.
- LLM calls log model, request ID, duration and size/count metadata; prompt and response bodies are not logged.

## Run

```bash
cd backend
alembic upgrade head
python -m app.modules.operations.worker
```

The Compose worker service can be started with `docker compose up -d ekip-worker`.

## Remaining P1 work

- Document replacement/version retention is not yet implemented. Existing `DocumentVersion` metadata is retained, but a safe active-version pointer, replacement endpoint, retention cleanup and vector cutover are still required.
- Reconciliation currently repairs PostgreSQL job/document status drift only. Qdrant and Neo4j inventory reconciliation is still open.
- Audit event coverage is foundational; domain-specific events for user/role changes, retrieval/access decisions, deletes and version operations should be expanded.
- Metrics export/dashboard integration and distributed trace/span support are not included in this slice.
- Live PostgreSQL/Qdrant/Ollama execution and CI verification remain required before production rollout.
