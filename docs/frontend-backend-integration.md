# EKIP frontend ↔ FastAPI integration

## API base URL

The Angular client currently targets `http://localhost:8000/api/v1`. Change
`API_BASE_URL` in `frontend/src/app/core/ekip-api.service.ts` for a different
backend origin. The FastAPI CORS allow-list currently permits
`http://localhost:4200`; update it in `backend/app/main.py` for the deployed
frontend origin. Do not use wildcard CORS with credentials in production.

## Start locally

1. Start PostgreSQL, Qdrant and Ollama using the repository Compose setup.
2. Configure the backend `.env` with `DATABASE_URL`, a strong
   `JWT_SECRET_KEY`, document storage path, Ollama and Qdrant URLs.
3. Apply database migrations and start FastAPI from the backend environment:
   `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`.
4. From `frontend`, run `npm ci` then `npm start`.
5. Open `http://localhost:4200` and sign in with an active provisioned user.

## Connected endpoints

| Capability | Endpoint | Notes |
|---|---|---|
| Login | `POST /api/v1/auth/login` | Returns short-lived JWT access token |
| Current profile | `GET /api/v1/users/me` | Validates current session |
| Dashboard metrics | `GET /api/v1/dashboard/summary` | Counts only accessible departments |
| Document library | `GET /api/v1/library/documents` | Server-side ACL, search and department filter |
| Upload | `POST /api/v1/documents/upload` | Multipart file + department UUID; Admin/Department Manager only |
| Vector indexing | `POST /api/v1/documents/{id}/index` | Explicitly invoked after upload |
| Semantic search | `POST /api/v1/search` | Department-scoped retrieval |
| Chat | `POST /api/v1/chat` | Answer plus validated source references |

## Authentication and security

- Access tokens are kept in `sessionStorage`, not persistent local storage, and
  are attached only to the configured API origin by the HTTP interceptor.
- The backend remains the authority for identity, department membership and
  document authorization. UI filters are not security controls.
- A 401 response clears the session and returns the user to sign-in.
- The backend currently issues 15-minute access tokens and does not expose a
  refresh-token endpoint. The user must sign in again after expiry.
- For a production deployment, prefer a same-site, HttpOnly, Secure cookie
  architecture or a carefully reviewed token design with XSS protections,
  CSRF controls where applicable, TLS, rate limiting and refresh-token rotation.

## Upload and indexing lifecycle

Upload first persists the file, document, version and chunks in PostgreSQL /
document storage. The frontend then calls the indexing endpoint. Upload success
does not imply vector indexing success: if Qdrant or Ollama is unavailable, the
document remains persisted and the UI reports the indexing failure separately.
The current backend does not persist an indexed/not-indexed flag, so dashboard
metrics intentionally say **completed documents**, not vector-indexed documents.

## Citation handling

The chat backend rehydrates vector candidates from PostgreSQL and restricts
them to the caller's currently authorised department IDs before sending any
content to the model. The response's citation metadata is built from those
same database-verified chunks. The answer's `[S#]` markers are checked against
the source IDs supplied for that request; unknown markers are rewritten as
`[unverified citation S#]` and excluded from the citation metadata. The UI
renders only citation records returned by the API.

This validates source identity and access scope, not whether the model's
natural-language claim is semantically entailed by the cited passage. That
requires a separate citation-entailment evaluation layer.

## Dashboard metric boundaries

The current API exposes total documents, completed documents, processing
documents, chunk count and accessible department counts. Query-volume,
answer-confidence and audit-event analytics are not stored/exposed by the
current backend and are deliberately not represented as live values in the UI.
