# EKIP Day 3–5 Runbook

## Day 3 — Persistent document ingestion

### Supported input

- PDF (`.pdf`)
- Word Open XML (`.docx`)
- HTML (`.html`, `.htm`)

Uploads are limited to 20 MiB by the validator. The server checks extension and file signature/structure, parses the file, normalizes extracted text and generates chunks. PDF chunks retain 1-based page numbers; DOCX and HTML retain block/section provenance without inventing page numbers.

### Persistence behavior

`POST /api/v1/documents/upload` requires a Bearer token and a `department_id` multipart field. Admins may upload to any active department. Department Managers must belong to the target department. Regular Users cannot upload.

The service writes original bytes to `DOCUMENT_STORAGE_ROOT` using generated UUID path components, computes SHA-256, and commits `documents`, `document_versions` and `document_chunks` in one PostgreSQL transaction. If the database write fails, it rolls back and attempts to remove the stored original. The storage path is never returned to the client.

Filesystem and PostgreSQL do not share a distributed transaction. A process crash between file creation and database commit can leave an orphan; a reconciliation job is a production hardening item.

## Day 4 — Embeddings and vector indexing

### Configuration

| Setting | Default | Purpose |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API |
| `OLLAMA_EMBEDDING_MODEL` | `nomic-embed-text` | Embedding model |
| `OLLAMA_TIMEOUT_SECONDS` | `120` | Inference timeout |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant REST API |
| `QDRANT_COLLECTION` | `ekip_document_chunks` | Vector collection |
| `QDRANT_API_KEY` | empty | Optional Qdrant API key |

Pull the model before indexing: `ollama pull nomic-embed-text`. The service uses Ollama's `/api/embed` endpoint, validates batch count, numeric values and consistent vector dimensions.

`POST /api/v1/documents/{document_id}/index` indexes the latest version in batches (default 32 chunks). Qdrant collection size is inferred from the first embedding batch; an existing collection with a different vector dimension is rejected. A new collection is required if the embedding model/dimension changes.

Qdrant payload includes document, department, version, chunk, page and section metadata. Department IDs are indexed as keyword payloads. The API filters by authorized department IDs and then rechecks candidate chunk/document IDs against PostgreSQL before returning content.

Indexing is explicit rather than part of upload: upload/persistence can complete when Ollama or Qdrant is unavailable, and the caller can retry indexing. A durable Redis-backed worker/retry queue is not implemented yet.

## Day 5 — Semantic search and grounded chat

### Search

`POST /api/v1/search`

Example body:

```json
{
  "query": "How are failed payment transactions handled?",
  "department_id": "optional-department-uuid",
  "top_k": 5
}
```

`department_id` is optional. If omitted, retrieval spans only the active departments the authenticated user is authorized to access. If a specific unauthorized department is requested, the API returns 403. `top_k` is bounded from 1 to 20 and defaults to `RAG_TOP_K`. Results below `RAG_MIN_SCORE` are omitted.

### Chat

`POST /api/v1/chat` accepts the same request body. The service passes only PostgreSQL-authorized retrieved excerpts to Ollama. The prompt treats retrieved content as untrusted reference data and asks the model to cite only supplied source IDs (`[S1]`, `[S2]`, ...). The response includes document/chunk/page/section citation metadata. If no relevant authorized chunks are found, it returns a fixed insufficient-evidence response without calling the LLM.

### Operational limitations

- Similarity score threshold and top-k require evaluation against a banking golden set; defaults are provisional.
- Citation strings are requested from the model; a future hardening step should parse/validate every inline citation marker against the returned citation list.
- No hybrid keyword retrieval or reranker is included yet.
- No answer/query audit history is persisted yet.
- No GraphRAG or autonomous agent behavior is included in Days 3–5.

## Verification checklist

1. Confirm PostgreSQL migration head and the `documents`, `document_versions`, `document_chunks` tables.
2. Create an active department and an Admin or Department Manager membership.
3. Log in and authorize Swagger with the returned Bearer token.
4. Upload a small synthetic/public PDF, DOCX or HTML document.
5. Verify the document, version, checksum and chunks in PostgreSQL and confirm the private original exists under `DOCUMENT_STORAGE_ROOT`.
6. Index the document and verify points in Qdrant.
7. Search using a question covered by the document.
8. Chat and verify that citations identify returned source chunks.
9. Attempt the same request as a user outside the department and verify no content is returned.

## Security and production follow-up

Before production, add malware scanning and decompression-bomb protections; upload quotas/rate limiting; background jobs with retries/idempotency; orphan-file reconciliation; version replacement and vector cleanup; citation marker validation; audit/query history; JWT issuer/audience validation and refresh-token rotation; SSO/MFA; and a retention/deletion workflow across PostgreSQL, filesystem and Qdrant.
