# P0 — Complete Department-Level Authorization

## Policy decision
Department Manager user administration is not enabled in this increment because it has not been approved. Only ADMIN can create users, list users, update user roles/status, and add/remove department memberships. Department Managers and USER accounts can discover only active departments assigned through `user_departments`.

## Implemented behavior

- `GET /api/v1/departments` filters active departments through `authorized_department_ids`. Admins see all active departments; Managers and Users see their assigned active departments.
- Search and chat use the authenticated user's department scope. An explicitly requested unassigned department returns HTTP 403.
- Dashboard summaries are computed only over authorized department IDs.
- Document library listing is restricted to authorized department IDs; an explicit unauthorized department filter returns HTTP 403.
- Upload, indexing and deletion use the document department authorization check. Upload/index/delete are restricted to Admin and Department Manager roles; a regular User remains read/search-only.
- Admin user creation and membership replacement remain protected by an Admin-only dependency.
- Angular's Departments view includes an Admin-only user provisioning and department assignment panel. It supports creating an account with multiple departments and replacing an existing user's department memberships.
- CORS allows PUT/PATCH preflight requests needed by the admin management calls.

## Department Manager scope
Managers can see their own assigned departments and use the existing manager-authorized document operations inside those departments. They cannot list, create, update, deactivate or assign users. This is deliberate until manager administration is explicitly approved.

## Security tests added
Integration tests cover:
- Employee department discovery only returns memberships.
- Admin department discovery returns all active departments.
- Explicit unauthorized department IDs return HTTP 403 for search, chat and library.
- A regular user cannot index or delete a document in another department.
- Admin can create a user with multiple department memberships.
- Department Managers can see only their own departments but cannot manage user accounts.

Existing tests also cover PostgreSQL revalidation of vector hits, unauthorized library filters, dashboard scoping and regular-user upload denial.

## Local verification
From `backend`:

```powershell
$env:DATABASE_URL = "sqlite+pysqlite:///:memory:"
$env:JWT_SECRET_KEY = "test-only-secret-key-for-ekip-32-byte-minimum"
python -m pytest tests/integration/test_knowledge_api.py tests/integration/test_documents_api.py -q
python -m pytest -q
```

From `frontend`:

```powershell
npm ci
npm run build
npm test -- --watch=false
```

The changes were committed to `25nov_pending_work`. At the time of this commit, the GitHub Actions run failed before creating any jobs (zero jobs reported), so no automated test or Angular build result is claimed. Re-run the workflow once the repository Actions issue is resolved.

## Acceptance status

- Admin can create users and assign multiple departments through UI: implemented; local UI/API test still required.
- Department Manager sees assigned departments: implemented. Manager user administration is intentionally not enabled.
- Employee sees assigned departments only: implemented at department discovery, dashboard, library and knowledge API boundaries.
- Unauthorized department IDs return HTTP 403: implemented and covered by added tests, pending test execution.
- Search, chat, dashboard, library and document write operations enforce server-side scope: implemented; local integration test execution remains required.
- Cross-department retrieval and document mutation tests: added, pending execution.
