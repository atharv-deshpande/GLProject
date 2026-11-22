# EKIP Days 6–10 Implementation Plan

This plan extends the Day 1–5 modular monolith. PostgreSQL remains the source of truth for identity, memberships, documents, versions, chunks and authorization. Qdrant is a derived vector index. Neo4j is optional derived graph data.

## Day 6 — Evaluation and metadata enrichment

**Implemented foundations**
- Deterministic golden-set smoke evaluator using reviewer-specified required terms.
- Candidate entity extraction for currency, percentage, date and account/transaction reference-like values.
- Unit tests for passing answers, missing terms, empty datasets and entity extraction.

**Acceptance**
- Maintain reviewed synthetic/public banking question-answer cases.
- Record pass rate and missing terms for each evaluation run.
- Review extracted metadata before treating it as a verified fact.

## Day 7 — GraphRAG foundation

**Implemented foundation**
- Optional, lazy Neo4j adapter for Department → Document → Chunk relationships.
- Stores identifiers and metadata only; it does not store original document text.

**Security requirement**
- PostgreSQL remains the authorization authority. Resolve department access in PostgreSQL before graph queries. Never use graph relationships alone to authorize a user.

**Acceptance**
- Start Neo4j with configured credentials.
- Upsert a synthetic document and its chunk metadata.
- Verify relationships and idempotent re-upsert.
- Verify a user without department membership cannot access that department's graph data through any future API.

## Day 8 — Agent workflow

**Implemented foundation**
- Optional fixed LangGraph retrieve → answer workflow.
- No arbitrary tools, writes, shell commands or external actions.

**Outstanding before production**
- Re-join vector hit IDs to PostgreSQL and retrieve authorized chunk text before calling the LLM.
- Apply the same department authorization checks as the existing /api/v1/search and /api/v1/chat endpoints.
- Validate citation IDs against actual retrieved sources.

## Day 9 — Security, tests and observability

**Existing baseline**
- Argon2id password hashing and JWT authentication.
- Department-scoped retrieval and PostgreSQL revalidation of Qdrant hits.
- Retrieved document text is untrusted input, not instructions.

**Production hardening backlog**
- Durable indexing jobs, retries, idempotency and reconciliation.
- Citation marker validation and structured audit events.
- API rate limiting, upload malware scanning and file retention/deletion workflow.
- Cross-store deletion propagation to PostgreSQL, filesystem, Qdrant and Neo4j.
- JWT issuer/audience and refresh-token controls, SSO/MFA, secrets rotation.
- Structured tracing, dependency scanning, backups and restore drills.

## Day 10 — Deployment and demo

**Acceptance**
- Start the required services and API from a clean environment.
- Complete login → upload → index → search → chat using synthetic documents.
- Verify department isolation with two users in different departments.
- Verify controlled service-unavailable responses when Ollama or Qdrant is offline.
- Confirm secrets, source text and private storage paths are not written to logs.

The Angular directory is still the CLI starter; a complete dashboard is not part of this branch's delivered scope.

## Local test command

From the backend directory in PowerShell:

```powershell
$env:DATABASE_URL = "sqlite+pysqlite:///:memory:"
$env:JWT_SECRET_KEY = "test-only-secret-key-for-ekip-32-byte-minimum"
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

This command runs the automated suite. Real-service acceptance checks require Docker, configured .env values, database migrations and the Ollama models.
