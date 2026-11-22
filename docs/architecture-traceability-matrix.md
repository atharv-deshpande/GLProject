# EKIP Architecture Traceability Matrix

**Baseline:** Original Day 1 architecture in `brain.md` (requirements FR-01–FR-18, NFRs, component architecture, STRIDE + AI threat model, data model, ADR-001–ADR-007).  
**Implementation snapshot reviewed:** `Day6-Day10ChangesNew`, branch head `114a472903ac0c09a9e248858fe8581f75cc851d` (2026-11-22).  
**Review type:** Evidence-based desk review of documented source state and prior user-confirmed test reports. This is not a fresh local checkout, live-service test, penetration test or production-readiness certification.

## 1. Status definitions

| Status | Meaning |
|---|---|
| Implemented (reported) | Implementation and relevant tests are documented, but this review did not rerun them. |
| Partial | Some behavior exists; acceptance criteria or security/reliability controls remain incomplete. |
| Foundation only | Adapter, prototype or design exists, but end-to-end behavior is not established. |
| Not implemented / not evidenced | No implementation or verification evidence was found in the reviewed material. |
| Needs verification | The requirement may exist, but source-level or live evidence is insufficient. |

A class, container, route or dependency alone does not prove an end-to-end requirement is complete.

## 2. Functional requirement traceability

| ID | Day 1 requirement | Current evidence / implementation area | Status | Remaining acceptance work |
|---|---|---|---|---|
| FR-01 | Authentication — user can log in securely | Argon2id password hashing; PyJWT access token; `POST /api/v1/auth/login`; `GET /api/v1/users/me`. Four auth security tests were previously user-confirmed. | Partial | Verify admin bootstrap and real PostgreSQL login/profile flow; validate issuer/audience; decide refresh-token lifecycle; rate-limit login; audit auth events; test inactive/unknown users and expired tokens end-to-end. |
| FR-02 | RBAC — enforce Admin, Department Manager and User permissions | Role enum and selected upload/index/retrieval checks. Retrieval resolves active memberships; Admin resolves all active departments. | Partial | Build a permission matrix for every endpoint/action; centralize policy checks; test all role × department combinations, privilege escalation and cross-department denial. |
| FR-03 | Department management | Department model and membership relationship exist. | Not implemented / not evidenced | Admin create/read/update/deactivate endpoints; validation, uniqueness, seed/provisioning flow, audit events and tests. |
| FR-04 | User management within permitted scope | User identity model and current-user endpoint exist. | Partial | Admin user lifecycle; manager-scoped user administration; department assignment/removal; deactivation; password reset/provisioning; audit and authorization tests. |
| FR-05 | Upload PDF, DOCX and HTML | Authenticated multipart `POST /api/v1/documents/upload`; private generated-UUID file storage; PostgreSQL document/version/chunk persistence. | Implemented (reported) | Live PostgreSQL upload smoke test; frontend upload workflow; enforce quotas and operational limits. |
| FR-06 | Reject unsupported, malformed or unsafe files | Extension/content checks and 20 MiB cap; PDF/DOCX/HTML validators. | Partial | Malware scanning, decompression/ZIP-bomb limits, parser isolation/timeouts, content-disarm strategy, adversarial fixtures and security tests. HTML extraction is not a full sanitizer. |
| FR-07 | Parse text and page/section metadata | PDF page extraction; DOCX block/heading/table order; HTML title/meta/heading/section context. | Implemented (reported) | Add corrupted/large/edge-case document fixtures; verify parser resource limits and provenance fidelity. |
| FR-08 | Chunk with searchable provenance | Approximate token chunker; default 500-token target and 75 overlap; page/section metadata. | Implemented (reported) | Benchmark chunk sizes/overlap with a reviewed dataset; evaluate table/code/list boundaries; use model tokenizer if justified. |
| FR-09 | Generate embeddings | Ollama `/api/embed`, configurable embedding model, batch and vector validation. | Implemented (reported) | Run live model compatibility and dimension checks; benchmark CPU latency and embedding quality; document model/version migration strategy. |
| FR-10 | Retrieve relevant chunks within authorized scope | Qdrant cosine collection and department filter; hit IDs are revalidated against PostgreSQL/document department before content is exposed. | Implemented (reported) | Add adversarial cross-department and stale-index tests against live services; test deleted/reassigned documents and filter failures. |
| FR-11 | Evidence-grounded question answering | `POST /api/v1/chat`; Ollama answer service; no-evidence response avoids LLM call; retrieved text is framed as untrusted. | Partial | Golden-set faithfulness tests; ensure answer claims are source-supported; test prompt injection and model outage; add conversation/streaming only if required. |
| FR-12 | Return document/page/section citations | Retrieved source metadata returned; prompt requests inline `[S#]` markers. | Partial | Parse and validate every marker against the retrieved source set; reject fabricated IDs; ensure page/section correctness; preferably assemble citation references server-side. |
| FR-13 | Document classification | No complete classifier or classification workflow evidenced. | Not implemented / not evidenced | Define labels and policy first; implement classifier with confidence/review workflow; persist label, model/version, provenance and reviewer override; evaluate on labeled synthetic/public documents. |
| FR-14 | Extract systems, products, policies and processes | Regex candidate extraction for currency, percentage, date and account/transaction-reference-like strings. | Partial | Add banking-domain entity types (systems, products, policies, processes); entity normalization, deduplication, provenance, confidence and human review; distinguish candidates from verified facts. |
| FR-15 | GraphRAG with related entities and relationships | Optional Neo4j adapter creates Department→Document→Chunk metadata relationships. No verified authorized graph retrieval pipeline. | Foundation only | Define entity/relationship schema; extract and persist domain graph with provenance; query graph under PostgreSQL-derived authorization; integrate graph retrieval/ranking into RAG; test leakage and deletion. |
| FR-16 | Controlled multi-step knowledge searches | Optional fixed LangGraph retrieve→answer workflow; no arbitrary write/shell tools. Known issue: it does not yet re-join hit IDs to PostgreSQL and load authorized chunk text before LLM use. | Foundation only | Fix PostgreSQL revalidation and authorized text loading; validate citations; enforce allow-listed tools, user scope, budgets, timeouts and approvals before API exposure. |
| FR-17 | Audit important user/system actions | No complete audit event model/pipeline evidenced. | Not implemented / not evidenced | Define event schema and retention; record actor, action, target, timestamp, request/correlation ID and outcome; protect against tampering; mask secrets and sensitive content; test critical events. |
| FR-18 | Delete source and derived data across stores | No complete deletion workflow evidenced. | Not implemented / not evidenced | Implement lifecycle state and idempotent deletion across filesystem, PostgreSQL, Qdrant and (when populated) Neo4j; handle retries, tombstones, reconciliation and deletion verification. |

## 3. Non-functional requirement traceability

| NFR area | Day 1 expectation | Current evidence | Status / next acceptance test |
|---|---|---|---|
| Security | Department isolation; least privilege | Selected API checks and PostgreSQL revalidation are reported. | **Partial:** endpoint-wide authorization matrix and negative tests required. |
| Performance | Proposed p95 retrieval <2 seconds, excluding LLM | No reproducible benchmark reported. | **Needs verification:** define dataset, concurrency, warm/cold conditions and measure p50/p95/p99. |
| Availability | Graceful handling of Ollama, Qdrant, Neo4j and Redis outages | Runbook proposes service-outage checks; live results not confirmed. | **Needs verification:** health/readiness, timeouts, bounded retries and controlled errors per dependency. |
| Scalability | Asynchronous document processing | Upload/index currently synchronous; Redis not a durable job queue. | **Not met:** durable jobs, workers, backpressure, retries and dead-letter/reconciliation. |
| Maintainability | Modular backend and clear service/repository boundaries | Modular backend structure exists. | **Partial:** review dependency direction, shared contracts, configuration and integration boundaries. |
| Observability | Request IDs, structured logs, traces and error metrics | Langfuse planned; implementation not evidenced. | **Not met / not evidenced:** structured logs, correlation IDs, traces, metrics and redaction tests. |
| Reliability | Safe retries and idempotent jobs | Qdrant upsert uses chunk UUIDs; no durable job retry system. | **Partial:** define idempotency for full pipeline and recoverable job state. |
| Data integrity | Document versioning and checksums | Document/version/chunk schema exists; checksum behavior not fully evidenced. | **Partial:** verify checksum generation/uniqueness, version replacement and integrity reconciliation. |
| Explainability | Citations and insufficient-evidence behavior | No-evidence response exists; citation metadata returned but inline IDs unvalidated. | **Partial:** deterministic citation validation and answer-evidence evaluation. |
| Privacy | Synthetic/public documents only in MVP | Project rule and runbooks state this constraint. | **Policy established:** add upload warnings, access controls, log redaction and data-retention enforcement. |

## 4. STRIDE threat-model traceability

| Threat | Day 1 scenario | Current control evidence | Status / required validation |
|---|---|---|---|
| Spoofing | Attacker impersonates employee | Argon2id and JWT access token foundation. | **Partial:** issuer/audience, expiry, token lifecycle, rate limiting, session revocation and end-to-end auth tests. |
| Tampering | Malicious document upload | File type/signature checks, private storage, atomic file write. | **Partial:** malware scanning, parser isolation, checksum verification, decompression limits and tamper tests. |
| Repudiation | User denies upload/access | No complete audit trail evidenced. | **Gap:** append-only/tamper-resistant audit events with actor, target, time, request ID and outcome. |
| Information disclosure | User accesses another department | PostgreSQL revalidation of Qdrant hits and selected department checks. | **Partial:** exhaustive endpoint, graph, cache, error and citation leakage tests. |
| Denial of service | Huge/repeated uploads | 20 MiB upload cap. | **Partial:** quotas, rate limiting, concurrency limits, parser timeouts, queue backpressure and resource ceilings. |
| Elevation of privilege | User invokes admin operation | Role checks exist in selected operations. | **Partial:** central authorization policy and negative tests for every privileged endpoint. |

## 5. AI-specific threat traceability

| Threat | Current control evidence | Status / required acceptance |
|---|---|---|
| Prompt injection in retrieved documents | Prompt says retrieved content is untrusted reference data. | **Partial:** adversarial prompt-injection test corpus; ensure retrieved text cannot alter policy or authorize tools. |
| Cross-department leakage | Qdrant filters plus PostgreSQL revalidation in core retrieval. | **Partial:** cross-tenant tests across RAG, graph, agents, cache, history and citations. |
| Sensitive information disclosure | Synthetic/public data rule; no evidence of comprehensive redaction. | **Partial:** PII/secret handling, log redaction, response controls and retention verification. |
| Agent tool abuse | LangGraph prototype has fixed retrieve→answer flow and no arbitrary write tools. | **Foundation only:** user-scoped allow-list, tool input validation, budgets, timeouts, approval gates and security tests. |
| Malicious uploads | Extension/content checks and size limit. | **Partial:** malware scanning, decompression limits, parser sandbox and malicious-file test suite. |
| Hallucinated citations | Source metadata returned; model asked for `[S#]` references. | **Gap:** deterministic citation ID/page validation and unsupported-claim tests. |

## 6. Component architecture alignment

| Component | Day 1 responsibility | Current implementation alignment |
|---|---|---|
| Angular 18 | Presentation and user interactions; must not authorize | Angular CLI starter only; complete dashboard and workflows not delivered. |
| FastAPI | API orchestration and backend authorization | Core API and selected authorization paths exist. |
| PostgreSQL | Identity, roles, departments, permissions, documents and metadata | Identity and document/version/chunk foundations exist; query history, audit, processing jobs and full admin workflows are not evidenced. |
| Qdrant | Embeddings and vector payloads; never permission authority | Implemented adapter; PostgreSQL revalidation exists in core retrieval. |
| Neo4j | Entity relationships and graph retrieval | Metadata graph adapter foundation only; no verified GraphRAG. |
| Ollama | Model inference; never authorization | Embedding and chat adapters integrated; live performance/availability tests not established by mocked tests. |
| LangGraph | Bounded workflow; no unrestricted data access | Prototype exists; known PostgreSQL revalidation gap blocks production use. |
| Redis | Cache and job coordination, not permanent records | Service configured; durable job coordination not implemented. |
| Langfuse | LLM observability | Not implemented / not evidenced. |

## 7. Data model traceability

| Day 1 data concept | Current evidence | Status |
|---|---|---|
| `users` | Implemented; role stored as enum on user. | Partial: full lifecycle and provisioning. |
| `roles` | Separate normalized roles table not implemented; enum is used. | Architecture deviation to explicitly accept or revise. |
| `departments` | Model/table implemented. | Partial: admin CRUD and seed management. |
| `user_departments` | Many-to-many membership model and uniqueness constraint. | Partial: membership administration and policy tests. |
| `documents` | Model/table and upload persistence. | Implemented foundation. |
| `document_versions` | Model/table and latest-version indexing. | Partial: replacement/retention/checksum lifecycle. |
| `document_chunks` | Model/table with text and provenance metadata. | Implemented foundation. |
| `query_history` | No implementation evidenced. | Gap. |
| `audit_logs` | No complete implementation evidenced. | Gap. |
| `processing_jobs` | No durable job model/queue evidenced. | Gap. |

Qdrant payloads are derived retrieval metadata, not an authorization source. Neo4j is derived graph data and must retain source-document provenance and access scope.

## 8. Architecture decision record (ADR) status

| ADR | Accepted Day 1 decision | Current status | Decision needed |
|---|---|---|---|
| ADR-001 | Modular monolith | Aligned | Keep. |
| ADR-002 | PostgreSQL is source of truth | Aligned | Keep; ensure Qdrant/Neo4j remain derived. |
| ADR-003 | Qdrant for vector retrieval | Aligned | Keep; benchmark and pin compatible versions. |
| ADR-004 | Neo4j for graph knowledge | Partially realized | Keep as target; graph retrieval and authorization still required. |
| ADR-005 | Ollama local inference | Aligned | Keep provisionally; benchmark model choice on target hardware. |
| ADR-006 | Department-scoped authorization | Partially realized | Keep; complete policy coverage and cross-department tests. |
| ADR-007 | Asynchronous document ingestion | Not realized | Either implement durable async processing or formally supersede ADR with documented rationale and trade-offs. |

## 9. Open architecture decisions retained from Day 1

Do not silently assume these are resolved:

1. Exact Ollama chat and embedding models, selected by measured quality, latency and resource use.
2. Chunk size, overlap and retrieval top-k, selected through evaluation.
3. Hybrid lexical/vector retrieval approach (for example PostgreSQL full-text search or another engine).
4. Document storage backend and retention policy.
5. MFA timing for MVP versus later hardening.
6. Document classification labels and information-classification policy.
7. RAG evaluation thresholds and reviewed golden-set composition.
8. Langfuse local versus hosted deployment.
9. Production malware scanning and enterprise identity-provider integration scope.

## 10. Recommended closure sequence

| Order | Work package | Exit criteria |
|---|---|---|
| P0 | Authentication, RBAC and department administration | Complete role/endpoint matrix; positive and negative authorization tests; no cross-department leakage. |
| P0 | Secure LangGraph retrieval | PostgreSQL revalidation and authorized chunk loading before LLM; citation IDs validated; not exposed until tests pass. |
| P0 | Citation correctness | Every returned citation maps to an actual retrieved document/version/chunk/page/section; fabricated markers rejected. |
| P1 | Document lifecycle and asynchronous jobs | Durable job state, retries, idempotency, reconciliation, version replacement and cross-store deletion. |
| P1 | Audit and observability | Security/action audit coverage, correlation IDs, metrics/traces, redaction and retention. |
| P1 | Upload hardening | Malware scan, archive/decompression limits, parser isolation, quotas and adversarial fixtures. |
| P2 | Classification and entity enrichment | Approved taxonomy, reviewed labels, provenance/confidence and evaluation. |
| P2 | Neo4j GraphRAG | Derived graph schema, authorized traversal, provenance, deletion propagation and leakage tests. |
| P2 | RAG and system evaluation | Reviewed golden set; retrieval recall, answer faithfulness, citation precision, latency and isolation measurements. |
| P3 | Angular application and deployment | Complete user/admin flows, clean-environment deployment, backup/restore and operational acceptance. |

## 11. Review evidence and limitations

- The current Day 3–5 implementation notes report 75 tests passing and compile checks succeeding. Those tests used SQLite and mocked Ollama/Qdrant; they are not proof of live PostgreSQL/Ollama/Qdrant end-to-end behavior.
- Day 6 unit tests cover deterministic required-term evaluation and candidate entity extraction.
- Neo4j and LangGraph adapters are described as optional foundations; their full live integration is not verified here.
- The Angular application is documented as a CLI starter.
- No performance benchmark, penetration test, disaster-recovery exercise or production deployment evidence was reviewed.
- This matrix intentionally distinguishes implementation evidence from acceptance-test evidence. Update each row only when the relevant test or operational proof is available.

## 12. Review sign-off

**Current conclusion:** Core document RAG foundations exist, but the original enterprise architecture is not yet fully satisfied. The largest blockers are complete authorization, citation validation, durable asynchronous processing, audit/observability, deletion lifecycle, secure graph/agent retrieval and the Angular user experience.

**Rule for closure:** A requirement is complete only when its implementation is present, the acceptance criteria are explicit, relevant tests pass, and any live-service requirement has been verified in the target environment.
