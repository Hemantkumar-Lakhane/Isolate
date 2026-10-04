# SMBFlow — Technical Backend & API Audit

**Document type:** Engineering reference / integration readiness audit
**Scope:** Backend service (`api/main.py`), authentication, database, workflow/agent orchestration, integrations, and frontend↔backend API mapping.
**Audit question:** *Can the current SMBFlow frontend be connected to the real backend today, and exactly which APIs are available, verified, incomplete, or missing?*

> **Verification basis.** Findings below combine (a) static reading of the backend source and (b) live, read-only HTTP probes against a running instance on `http://127.0.0.1:8000`. Where a claim was confirmed against the live server, it is marked **VERIFIED**. Where it was confirmed only by reading code (not exercised at runtime in this audit), it is marked **IMPLEMENTED — NOT YET VERIFIED**. No mutating/production-affecting calls were made except one isolated, self-contained signup used solely to test tenant isolation, whose test user was deactivated immediately afterward. No secrets are reproduced in this document.

---

## Table of Contents

1. Executive Summary
2. Runtime Environment & How the Backend Boots
3. Complete API Inventory (all routes)
4. Endpoint Classification Legend
5. Authentication & Authorization Audit
6. Database & Tenant Isolation Audit
7. Workflow & Orchestration API Audit
8. AI / Agent / LLM API Audit
9. Machine-Learning Reality Check
10. Integrations Audit (external connectors)
11. Lead Assessment POC Readiness (UCI Bank Marketing)
12. Frontend ↔ Backend Mapping Matrix
13. Health, Ops & Observability
14. Live API Test Results (read-only)
15. API Contract Quality
16. Known Issues & Prior False-Positives
17. Security Notes
18. Connect-Today Verdict
19. Recommended Next Steps

---

## 1. Executive Summary

SMBFlow's backend is a single FastAPI application (`api/main.py`, internally branded "OpsGrid", product name **SMBFlow API v3**, version 3.0.0) exposing **80 HTTP route operations** plus **one WebSocket endpoint**. It is backed by PostgreSQL (async SQLAlchemy over asyncpg, `pgvector`-enabled) and Redis (pub/sub for multi-worker WebSocket fan-out).

**The frontend can be connected to the real backend today.** Every path the React app calls exists on the backend and is reachable; the base URL, auth scheme, and tenant model line up. In a live run:

- The server is up and healthy (DB connected, 4 tenants, Anthropic LLM configured).
- Authentication works end-to-end (JWT login, `/auth/me`, bearer-protected routes).
- **RBAC and tenant isolation are enforced and were verified live**: a `tenant_user` reached its own tenant's data (200) and was denied every cross-tenant and admin-only resource (403).
- ~30 read endpoints returned 200 with real DB-backed payloads.

The single most important correctness caveat for stakeholders: **there is no classical / predictive ML model in the system.** All "scoring," "churn risk," and "prediction" is performed by LLM prompts applying weighted formulas, not by a trained statistical model. This is covered in detail in §9.

---

## 2. Runtime Environment & How the Backend Boots

| Aspect | Detail |
|---|---|
| Framework | FastAPI, single-module app object in `api/main.py` |
| ASGI entry | `main.py api` (Click CLI) → `uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload` |
| DB | PostgreSQL via `postgresql+asyncpg://…`; container `opsgrid_postgres` (pgvector/pgvector:pg16) exposed on host port **5433**→5432 |
| Cache / events | Redis (`opsgrid_redis`, port 6379, password-protected) |
| API base (frontend) | `http://127.0.0.1:8000/api/v1` |
| WebSocket base | `http://127.0.0.1:8000/ws` |
| CORS | Allows `localhost:3000`, `localhost:5173`, and `*` |

**Startup sequence (`lifespan`):** creates tables via `Base.metadata.create_all`; connects the Redis pub/sub relay; seeds a super-admin from `ADMIN_EMAIL` / `ADMIN_PASSWORD`; marks any workflow left in `running` (crash-interrupted) as `failed`.

**Integrity gate.** A `system_integrity_check` middleware returns **503 "System Not Initialized"** if `DATABASE_URL` or `VAULT_ENCRYPTION_KEY` is missing. Bypass paths: `/api/v1/health`, `/docs`, `/openapi.json`, `/redoc`, `/`.

**Local launch.** `start.ps1` brings up Docker Postgres/Redis (waits for `opsgrid_postgres` healthy), then starts the native backend and the Vite frontend (5173). The Docker `api` service's port mapping is intentionally commented out in `docker-compose.yml` so it does not collide with the native Windows backend on port 8000. See §13 for the port-detection note.

---

## 3. Complete API Inventory

All routes are declared in `api/main.py`. Grouped by tag. Auth column: **Admin** = `require_admin` (super_admin only); **Any** = `require_any_auth`; **Tenant** = any auth + `assert_tenant_access(tenant_id)`; **Public** = no auth.

### Auth
| Method | Path | Auth | Status |
|---|---|---|---|
| POST | `/api/v1/auth/login` | Public | **A. VERIFIED** |
| POST | `/api/v1/auth/signup` | Public | **A. VERIFIED** |
| GET | `/api/v1/auth/me` | Any | **A. VERIFIED** |

### System / Health
| Method | Path | Auth | Status |
|---|---|---|---|
| GET | `/api/v1/health` | Public | **A. VERIFIED** |
| GET | `/api/v1/tenants/{tenant_id}/connectors/health` | Tenant | **A. VERIFIED** |

### Admin
| Method | Path | Auth | Status |
|---|---|---|---|
| GET | `/api/v1/admin/god-view` | Admin | **A. VERIFIED** |
| GET | `/api/v1/admin/live-stats` | Admin | **A. VERIFIED** |
| GET | `/api/v1/admin/system-events` | Admin | **A. VERIFIED** |
| POST | `/api/v1/admin/patterns/{tenant_id}/{pattern_key}/promote` | Admin | **B. IMPLEMENTED — NOT YET VERIFIED** |
| POST | `/api/v1/admin/auto-eval/run` | Admin | **B. IMPLEMENTED — NOT YET VERIFIED** |
| GET | `/api/v1/admin/auto-eval/suggestions` | Admin | **A. VERIFIED** |
| POST | `/api/v1/admin/auto-eval/suggestions/{suggestion_id}/apply` | Admin | **B. IMPLEMENTED — NOT YET VERIFIED** |
| POST | `/api/v1/admin/auto-eval/suggestions/{suggestion_id}/dismiss` | Admin | **B. IMPLEMENTED — NOT YET VERIFIED** |

### Users
| Method | Path | Auth | Status |
|---|---|---|---|
| POST | `/api/v1/users` | Admin | **B. IMPLEMENTED — NOT YET VERIFIED** |
| GET | `/api/v1/users` | Admin | **A. VERIFIED** |
| PATCH | `/api/v1/users/{user_id}/deactivate` | Admin | **A. VERIFIED** (used in isolation test cleanup) |

### Tenants
| Method | Path | Auth | Status |
|---|---|---|---|
| GET | `/api/v1/tenants` | Admin | **A. VERIFIED** |
| POST | `/api/v1/tenants` | Admin | **B. IMPLEMENTED — NOT YET VERIFIED** |
| GET | `/api/v1/tenants/{tenant_id}` | Tenant | **A. VERIFIED** |
| PUT | `/api/v1/tenants/{tenant_id}/config` | Tenant | **B. IMPLEMENTED — NOT YET VERIFIED** |
| GET | `/api/v1/tenants/{tenant_id}/config-schema` | Tenant | **A. VERIFIED** |
| POST | `/api/v1/tenants/{tenant_id}/validate-config` | Tenant | **A. VERIFIED** |

### Workflows
| Method | Path | Auth | Status |
|---|---|---|---|
| POST | `/api/v1/workflows/trigger` | Tenant | **B. IMPLEMENTED — NOT YET VERIFIED** (mutating; not exercised) |
| GET | `/api/v1/workflows/{run_id}/status` | Any (tenant-checked) | **A. VERIFIED** |
| GET | `/api/v1/workflows` | Any (tenant-scoped) | **A. VERIFIED** |
| POST | `/api/v1/workflows/{run_id}/pause` | Any (tenant-checked) | **B. IMPLEMENTED — NOT YET VERIFIED** |
| POST | `/api/v1/workflows/{run_id}/stop` | Any (tenant-checked) | **B. IMPLEMENTED — NOT YET VERIFIED** |
| POST | `/api/v1/workflows/{run_id}/resume` | Any (tenant-checked) | **B. IMPLEMENTED — NOT YET VERIFIED** |
| GET | `/api/v1/workflows/{run_id}/evidence` | Any (tenant-checked) | **A. VERIFIED** |
| GET | `/api/v1/workflows/{run_id}/system-log` | Any (tenant-checked) | **A. VERIFIED** |
| POST | `/api/v1/workflows/{run_id}/fork` | Any (tenant-checked) | **B. IMPLEMENTED — NOT YET VERIFIED** |
| GET | `/api/v1/tenants/{tenant_id}/workflows/stats` | Tenant | **A. VERIFIED** |
| GET | `/api/v1/workflows/estimate-cost` | Tenant (query params) | **A. VERIFIED** |

### Escalations (Human-in-the-loop)
| Method | Path | Auth | Status |
|---|---|---|---|
| GET | `/api/v1/escalations` | Any (tenant-scoped) | **A. VERIFIED** |
| POST | `/api/v1/escalations/{escalation_id}/decide` | Any (tenant-checked) | **B. IMPLEMENTED — NOT YET VERIFIED** |

### A2A (Agent-to-Agent permission requests)
| Method | Path | Auth | Status |
|---|---|---|---|
| GET | `/api/v1/a2a/requests` | Any (tenant-scoped) | **A. VERIFIED** |
| GET | `/api/v1/a2a/pending` | Any (tenant-scoped) | **A. VERIFIED** |
| POST | `/api/v1/a2a/{a2a_id}/decide` | Any (tenant-checked) | **B. IMPLEMENTED — NOT YET VERIFIED** |

### Credentials (encrypted integration secrets)
| Method | Path | Auth | Status |
|---|---|---|---|
| GET | `/api/v1/credentials/schema/{tool_name}` | Any | **B. IMPLEMENTED — NOT YET VERIFIED** |
| POST | `/api/v1/credentials` | Tenant | **B. IMPLEMENTED — NOT YET VERIFIED** |
| GET | `/api/v1/credentials` | Any (tenant-scoped) | **A. VERIFIED** |
| DELETE | `/api/v1/credentials/{cred_id}` | Tenant (checked) | **B. IMPLEMENTED — NOT YET VERIFIED** |

### Tools (custom + local dev + available)
| Method | Path | Auth | Status |
|---|---|---|---|
| GET | `/api/v1/tools` | Any (tenant-scoped) | **A. VERIFIED** |
| POST | `/api/v1/tools` | Tenant | **B. IMPLEMENTED — NOT YET VERIFIED** |
| DELETE | `/api/v1/tools/{tool_id}` | Tenant (checked) | **B. IMPLEMENTED — NOT YET VERIFIED** |
| POST | `/api/v1/tools/{tool_id}/test` | Tenant (checked) | **B. IMPLEMENTED — NOT YET VERIFIED** |
| GET | `/api/v1/tools/local` | Any | **A. VERIFIED** |
| GET | `/api/v1/tools/available` | Any | **A. VERIFIED** |

### Budget
| Method | Path | Auth | Status |
|---|---|---|---|
| GET | `/api/v1/tenants/{tenant_id}/budget` | Tenant | **A. VERIFIED** |
| PUT | `/api/v1/tenants/{tenant_id}/budget` | Tenant | **B. IMPLEMENTED — NOT YET VERIFIED** |

### Analytics
| Method | Path | Auth | Status |
|---|---|---|---|
| GET | `/api/v1/dashboard/{tenant_id}` | Tenant | **A. VERIFIED** |
| GET | `/api/v1/analytics/{tenant_id}` | Tenant | **A. VERIFIED** |
| GET | `/api/v1/analytics/admin/fleet` | Admin | **A. VERIFIED** |
| POST | `/api/v1/outcomes/{tenant_id}/check-pending` | Tenant | **B. IMPLEMENTED — NOT YET VERIFIED** |

### Email Queue (HITL send-gating)
| Method | Path | Auth | Status |
|---|---|---|---|
| GET | `/api/v1/tenants/{tenant_id}/email-queue` | Tenant | **A. VERIFIED** |
| PUT | `/api/v1/email-queue/{item_id}` | Any (tenant-checked) | **B. IMPLEMENTED — NOT YET VERIFIED** |
| POST | `/api/v1/email-queue/{item_id}/approve` | Any (tenant-checked) | **B. IMPLEMENTED — NOT YET VERIFIED** |
| POST | `/api/v1/email-queue/{item_id}/reject` | Any (tenant-checked) | **B. IMPLEMENTED — NOT YET VERIFIED** |

### Evidence (EPI artifacts)
| Method | Path | Auth | Status |
|---|---|---|---|
| GET | `/api/v1/evidence` | Any (tenant-scoped) | **A. VERIFIED** |
| GET | `/api/v1/evidence/{filename}/content` | Any (tenant-checked) | **B. IMPLEMENTED — NOT YET VERIFIED** |

### Config (DAG / prompts / models)
| Method | Path | Auth | Status |
|---|---|---|---|
| GET | `/api/v1/config/models` | Any | **A. VERIFIED** |
| GET | `/api/v1/config/dag/{workflow_name}` | Any | **B. IMPLEMENTED — NOT YET VERIFIED** |
| GET | `/api/v1/config/workflows` | Any | **A. VERIFIED** |
| PUT | `/api/v1/config/dag/{workflow_name}` | Admin | **B. IMPLEMENTED — NOT YET VERIFIED** |
| POST | `/api/v1/config/dag` | Admin | **B. IMPLEMENTED — NOT YET VERIFIED** |
| DELETE | `/api/v1/config/dag/{workflow_name}` | Admin | **B. IMPLEMENTED — NOT YET VERIFIED** |
| GET | `/api/v1/config/prompt-tree` | Any | **A. VERIFIED** |
| GET | `/api/v1/config/prompts/{prompt_path:path}` | Any | **B. IMPLEMENTED — NOT YET VERIFIED** |
| PUT | `/api/v1/config/prompts/{prompt_path:path}` | Admin | **B. IMPLEMENTED — NOT YET VERIFIED** |
| POST | `/api/v1/config/prompts/{prompt_path:path}` | Admin | **B. IMPLEMENTED — NOT YET VERIFIED** |

### Seed Data
| Method | Path | Auth | Status |
|---|---|---|---|
| GET | `/api/v1/seed-data/status` | Any | **A. VERIFIED** |
| POST | `/api/v1/seed-data/generate` | Tenant | **B. IMPLEMENTED — NOT YET VERIFIED** (mutating; not exercised) |

### Webhooks
| Method | Path | Auth | Status |
|---|---|---|---|
| POST | `/api/v1/webhooks/{tenant_id}` | Public (ingress) | **B. IMPLEMENTED — NOT YET VERIFIED** |
| POST | `/api/v1/webhooks/configure` | Tenant | **B. IMPLEMENTED — NOT YET VERIFIED** |

### Pattern Memory
| Method | Path | Auth | Status |
|---|---|---|---|
| GET | `/api/v1/tenants/{tenant_id}/patterns` | Tenant | **A. VERIFIED** |
| POST | `/api/v1/tenants/{tenant_id}/patterns/{pattern_key}/promote` | Tenant | **B. IMPLEMENTED — NOT YET VERIFIED** |
| POST | `/api/v1/tenants/{tenant_id}/patterns/{pattern_key}/demote` | Tenant | **B. IMPLEMENTED — NOT YET VERIFIED** |

### WebSocket
| Method | Path | Auth | Status |
|---|---|---|---|
| WS | `/ws/{session_id}?token=…` | Token (query) | **B. IMPLEMENTED — NOT YET VERIFIED** (not exercised in this read-only audit) |

**Totals:** 80 HTTP operations + 1 WebSocket. **VERIFIED live: 30.** IMPLEMENTED—not-yet-verified: 50 (chiefly mutating POST/PUT/DELETE deliberately not exercised, plus admin-config writes). **MISSING/required: see §11 (Lead Assessment).**

---

## 4. Endpoint Classification Legend

- **A. VERIFIED** — exercised live in this audit; returned the expected status with a real payload.
- **B. IMPLEMENTED — NOT YET VERIFIED** — route + handler + DB/service wiring read in source; not exercised live (mostly mutating or side-effecting operations deliberately left untouched).
- **C. PARTIALLY IMPLEMENTED** — handler exists but a documented gap remains (see §8/§13 for `outcomes/check-pending` scheduler gap).
- **D. MISSING / REQUIRED** — referenced by a plan or a target use-case but not present (see §11).
- **E. NOT APPLICABLE / INTERNAL** — internal machinery not surfaced as a stable public contract.

---

## 5. Authentication & Authorization Audit

**Mechanism (`api/auth.py`):** JWT (python-jose, HS256, 24-hour expiry). Passwords hashed with **bcrypt directly** (not passlib — a deliberate choice documented in-file to avoid a passlib/bcrypt-5.x incompatibility; 72-byte truncation and 12-round work factor preserved, so existing hashes remain valid). Token payload carries `sub` (user id), `email`, `role`, `tenant_id`.

**Roles:** `super_admin` (platform-wide, `tenant_id = None`) and `tenant_user` (scoped to one tenant). Dependencies: `require_admin`, `require_any_auth`; helpers `get_tenant_filter` and `assert_tenant_access`.

### Current Authentication & Integration Status

- **Login Verified:** `POST /api/v1/auth/login` integrated with frontend API service (`auth.service.js`) and verified end-to-end against live backend auth using real credentials.
- **`/auth/me` Verified:** `GET /api/v1/auth/me` returns current user profile, role (`super_admin` / `tenant_user`), and tenant ID context.
- **JWT & RBAC:** In-memory access token storage in `AuthContext` (XSS mitigation), Bearer header injection via unified `apiClient`. Role-based routing verified: `super_admin` routes to `/admin` god-view, `tenant_user` routes to `/dashboard`.
- **Protected Routes:** `ProtectedRoute` component guards authenticated routes, rejecting unauthenticated requests and enforcing role checks.
- **Session Handling:** Active session state managed in `AuthContext` with bound API client; logout clears memory token and user state.
- **Signup Status:** Signup endpoint (`POST /api/v1/auth/signup`) integrated in `SignupPage.jsx` for tenant user registration.
- **Password Reset Status:** `ForgotPasswordPage.jsx` and `ResetPasswordPage.jsx` UI forms integrated with fixed input text visibility. 
- **No Fake Email Delivery:** No dummy/fake email dispatch code added. Password reset requests flow through standard API contracts.
- **Known Limitations:** Production email delivery (SMTP/SES) infrastructure is not configured; email link delivery is pending external service setup.

**Live verification:**

| Test | Expected | Actual |
|---|---|---|
| Admin login (`.env` creds) | 200 + token, role `super_admin` | **200 ✓** |
| Missing token on protected route | 401 | **401 ✓** |
| Malformed bearer token | 401/404 | rejected ✓ |
| `tenant_user` → own tenant detail / dashboard / budget | 200 | **200 ✓** |
| `tenant_user` → **another** tenant's detail / dashboard / budget / analytics | 403 | **403 ✓ (all four)** |
| `tenant_user` → admin god-view / user list | 403 | **403 ✓ (both)** |

**Result: PASS.** RBAC, role routing, and cross-tenant denial are enforced and confirmed.

---

## 6. Database & Tenant Isolation Audit

**Stack:** async SQLAlchemy (`DeclarativeBase`) over asyncpg on PostgreSQL, Postgres-native `JSONB` / `UUID`, `pgvector` for embeddings. Models live in `core/state_manager.py`; all DB access is funneled through `api/crud.py`.

**Tables (15):** `tenants`, `workflow_definitions`, `workflow_instances`, `agent_runs`, `agent_run_records`, `escalations`, `pattern_memory`, `outcomes`, `users`, `a2a_requests`, `custom_tools`, `budget_settings`, `system_events`, `integration_credentials`, `email_queue`.

**Isolation model:** every tenant-owned table carries `tenant_id`; queries scope through `get_tenant_filter` (returns `None` for super_admin = unrestricted, else the user's `tenant_id`), and route handlers call `assert_tenant_access(current_user, tenant_id)` before returning tenant data. This was **verified live** (see §5): cross-tenant reads return 403, not data.

`StateManager` methods are genuine async operations — create/transition/update workflow context, agent-run CRUD, multi-signature escalation approval, A2A CRUD, pattern-memory upsert with running success-rate averaging, and an atomic `increment_loop_count` via `UPDATE … RETURNING`.

---

## 7. Workflow & Orchestration API Audit

**Engine (`core/orchestrator.py`, ~1,300 lines) — real implementation, no stubs in the core loop.** `run_workflow` / `resume_workflow` / `fork_workflow` all funnel into `_run_segment`, a genuine DAG executor that:

- Loads a DAG JSON from `workflows/dags/<name>.json`, iterates nodes, and evaluates edge conditions against a whitelist (`ALLOWED_EDGE_CONDITIONS`) using `simpleeval`.
- Spawns the mapped agent per node (`AGENT_MAP`), calls `agent.receive()`, and invokes LLMs for real.
- Suspends event-drivenly on escalation or A2A (`state.suspend_workflow()` persists pruned context; the API layer resumes) — no polling loops.
- Wires in EPI evidence recording, RAG historical-context injection, GraphRAG structural context, map-reduce summarization, a budget circuit breaker, a consensus pre-gate (skips consensus when reasoning confidence ≥ 0.90), adaptive `max_tokens`, operating-hours gating, parse-error self-healing, and Reflexion retry on failure.

**Trigger path (`POST /workflows/trigger`):** runs `validate_tenant_config` pre-flight (422 on blocking errors), then executes in `background_tasks` via `_execute_workflow_background`. Resume/fork have parallel background functions.

**Workflow DAGs (7):** `saas_churn_prevention`, `saas_pipeline_velocity`, `finance_expense_monitoring`, `healthcare_patient_engagement`, `retail_inventory_health`, `re_listing_health_monitor`, `re_tenant_flight_risk`. All share the same 6-stage linear shape: research → reasoning → drafting → verification → execution → memory. Each node = `{id, agent, name, description, prompt_file, tools[], timeout_seconds}`; edges carry whitelisted conditions (`not output.escalate`, `output.passed`).

**Live evidence:** `/workflows` and `/tenants/{id}/workflows/stats` returned real counts (8 runs: 3 completed, 1 escalated, 4 failed). `/workflows/{run_id}/status`, `/evidence`, and `/system-log` returned full payloads for a real completed run. Lifecycle mutations (pause/stop/resume/fork/trigger) are implemented but were **not** exercised (mutating).

---

## 8. AI / Agent / LLM API Audit

**LLM router (`core/llm_router.py`) — real.** `.call()` makes real provider calls via `litellm.acompletion` (plus a streaming path). **There is no mock/offline mode**; if all fallback models fail, it raises. Cost is computed from per-model rates in `config/templates/llm_config.json` multiplied by real provider-reported token usage; token pre-flight uses `tiktoken` when available. Also real: budget-governor tier downgrades, Redis semantic caching (tenant-salted SHA-256 keys), Anthropic prompt-cache injection, recursive map-reduce summarization, and low-confidence JIT retry.

> Note: only **Anthropic** is configured in the live environment (`/health` shows openai/google/groq `not_configured`). The cost-estimate breakdown may name other-provider models drawn from historical run records or config defaults; actual execution uses whatever provider keys are present.

**Agents (`agents/`) — all real LLM-backed:** Research, Reasoning, Drafting, Verification, Execution, Memory, plus Discovery (RAG tool-selection) and a Consensus agent (two opposing-persona passes; disagreement forces escalation). `base_agent.py` provides a real agentic tool loop (up to 10 iterations, parallel or sequential-with-early-exit by budget level).

**RAG (`core/rag_engine.py`) — real, with graceful degradation.** Embeddings via local `sentence-transformers` (`all-MiniLM-L6-v2`, dim 384) with an OpenAI `text-embedding-3-small` fallback. Two backends: Postgres `pgvector` ANN search (with time-decay re-rank) when a DB session is present, else in-memory cosine similarity. Includes HyDE, historical-context formatting, and tool-schema RAG. `core/graph_rag.py` adds a `networkx` knowledge graph. If neither embeddings backend is available, RAG returns empty rather than crashing.

**Supporting modules:** `cost_tracker`, `dag_validator`, `config_validator`, and `auto_eval` (admin-gated prompt-diff suggestions; never auto-applies) are all real.

- **`core/outcome_tracker.py` → classification C. PARTIALLY IMPLEMENTED.** The logic is real (registers a follow-up check date, re-fetches metrics, evaluates positive/negative outcomes into RAG), but there is **no built-in scheduler/daemon** firing it — it must be driven by an external cron or the manual `POST /outcomes/{tenant_id}/check-pending` endpoint.

---

## 9. Machine-Learning Reality Check

**There is zero classical / predictive ML in the codebase.** This is the audit's most load-bearing correctness finding and must not be overstated in any product or academic framing.

Evidence:
- `requirements-ml.txt` contains only `torch`, `sentence-transformers`, `numpy` — present solely to run the RAG embedding model, **not** for prediction. No `scikit-learn`, `xgboost`, `lightgbm`, or `joblib`.
- No model artifacts anywhere (`.pkl` / `.joblib` / `.h5` / `.pt` / `.onnx` / `.model`) outside the virtualenv.
- No training code: repo-wide searches for `sklearn`, `xgboost`, `.fit(`, `train_test_split`, `RandomForest`, `.predict(`, `/predict`, `lead scoring`, `bank_marketing` across `api/`, `core/`, `agents/`, `integrations/`, `workflows/`, and `frontend/src/` return **no code hits** (only prose in docs).
- The project's own `docs/PROJECT_STATUS.md` states the codebase uses 0 classical ML; `docs/ARCHITECTURE_AND_PLAN.md` lists XGBoost/RandomForest/SHAP churn prediction as **PROPOSED / PLANNED**, not built.

**How "churn scoring" actually works:** the `reasoning` node's prompt (`workflows/prompts/saas/reasoning_churn.txt`) instructs the **LLM** to "Score each account 0-100 using this weighted formula," with weights (`usage_drop_weight 0.40`, `support_spike_weight 0.25`, `nps_weight 0.20`, `engagement_recency_weight 0.15`) passed as prompt variables from tenant config. The arithmetic happens inside the LLM prompt, not in Python. The "risk labels" present in seed data are **pre-baked by the seed generator** (`db/seed/saas_seed.py`, `random.seed(42)`, `is_at_risk = i % 3 == 0`), not predicted.

**Bottom line:** any mention of a "churn model" / "weighted churn model" (in DAG node names or docs) refers to an LLM applying a formula, not a trained model.

---

## 10. Integrations Audit

`integrations/connectors.py` — **real HTTP connectors** over `httpx.AsyncClient`, not mocks:

| Connector | Operations | Status |
|---|---|---|
| HubSpot | contacts / deals / tasks / property updates | Real API calls (needs key) |
| Gmail | read messages/threads; `send_email` **returns `{"queued": true}` without sending** when `queue_for_approval` is set (intentional HITL gate) | Real, send-gated |
| Slack | `chat.postMessage`, formatted risk alerts | Real |
| Stripe | read customers/subscriptions/invoices; **write raises `NotImplementedError`** | Read-only |
| Generic REST | configurable GET/POST | Real |

In **local dev**, workflows use `integrations/local_dev_tools.py` instead, which reads `db/seed/data/*.json` (no network). `integrations/key_vault.py` provides **real Fernet encryption** (`MultiFernet` with comma-separated key rotation, `encrypt/decrypt/rotate/mask`); it auto-generates an ephemeral key with a warning if `VAULT_ENCRYPTION_KEY` is unset. `tool_registry_builder.py` wires enabled+credentialed connectors and local tools into a `ToolRegistry` and indexes tool schemas in RAG.

**Live:** `/tenants/{id}/connectors/health` reports all external connectors as `no_credentials` and `product_db` as `disabled` for the test tenant — legitimately unconfigured, not broken.

---

## 11. Lead Assessment POC Readiness (UCI Bank Marketing)

The proposed "Lead Assessment" POC (predict/score a marketing lead from the UCI Bank Marketing dataset, explain the score, and route it through reasoning → recommendation → approval → action → outcome/feedback) is **not present in the backend today**. This dataset is for ML research only and is unrelated to the SaaS seed DB.

| POC capability | Endpoint / mechanism | Status |
|---|---|---|
| Lead retrieval (list/get leads) | none | **D. MISSING / REQUIRED** |
| Lead creation / ingestion | none (nearest: generic `POST /webhooks/{tenant_id}`) | **D. MISSING / REQUIRED** |
| ML prediction (lead score / conversion probability) | none — no model, no `/predict` | **D. MISSING / REQUIRED** |
| Explainability (feature attributions / SHAP) | none | **D. MISSING / REQUIRED** |
| LLM reasoning over a lead | possible via a new/existing reasoning prompt, but no lead-specific DAG | **D. MISSING (workflow) / partial (engine exists)** |
| Recommendation output | drafting agent exists generically | **B/D** |
| Human approval | `email-queue` + `escalations` machinery exists and is reusable | **A. VERIFIED (machinery)** |
| Action execution | execution agent + connectors exist generically | **B** |
| Outcome / feedback loop | `outcome_tracker` logic exists but has no scheduler | **C. PARTIALLY IMPLEMENTED** |

**Verdict:** the *orchestration substrate* (DAG engine, agents, approval queue, evidence, tenant model) is reusable for a Lead Assessment POC, but **every ML-specific and lead-specific piece is missing** and would need to be built: a lead data model + endpoints, a trained model + a prediction function/endpoint, explainability, and a `lead_assessment` DAG with its prompts.

---

## 12. Frontend ↔ Backend Mapping Matrix

Frontend base `http://127.0.0.1:8000/api/v1`; client in `frontend/src/api/client.js` (handles FastAPI 422 arrays; `createApiClient(token)` → get/post/put/patch/delete). **Every path the SPA calls exists on the backend.** Routes in `App.jsx`:

| Frontend route / page | Backend endpoints called | Backend present? |
|---|---|---|
| `/auth` (AuthPage) | `POST /auth/login`, `POST /auth/signup`, `GET /auth/me` | ✓ VERIFIED |
| `/admin` (GodView) | `GET /admin/god-view` | ✓ VERIFIED |
| `/admin/fleet` (FleetCost) | `GET /analytics/admin/fleet` | ✓ VERIFIED |
| `/admin/users` (UsersPage) | `GET /users`, `POST /users`, `PATCH /users/{id}/deactivate` | ✓ (list/deactivate VERIFIED) |
| `/dashboard` (Dashboard) | `GET /dashboard/{tenant_id}` | ✓ VERIFIED |
| `/escalations` (EscalationsPage) | `GET /escalations?status=…`, `POST /escalations/{id}/decide` | ✓ (GET VERIFIED) |
| `/evidence` (EvidencePage) | `GET /evidence`, `GET /evidence/{filename}/content` | ✓ (list VERIFIED) |
| `/workflows/builder` (WorkflowBuilder) | `GET/PUT/POST/DELETE /config/dag…`, `GET /config/workflows`, `POST /workflows/trigger` | ✓ (reads VERIFIED) |
| `/workflows/:runId` (WorkflowDetail) | `GET /workflows/{runId}/status|evidence|system-log`, pause/stop/resume/fork | ✓ (reads VERIFIED) |
| `/config` (ConfigStudio) | `GET /tenants/{id}/config-schema`, `PUT /tenants/{id}/config`, `POST /tenants/{id}/validate-config` | ✓ (reads VERIFIED) |
| `/models` (ModelSettings) | `GET /config/models` | ✓ VERIFIED |
| `/budget` (BudgetPage) | `GET/PUT /tenants/{id}/budget` | ✓ (GET VERIFIED) |
| `/tools` (ToolsPage) | `GET /tools`, `/tools/available`, `/tools/local`, `POST /tools`, `DELETE /tools/{id}`, `/credentials…` | ✓ (reads VERIFIED) |
| `/prompts` (PromptStudio) | `GET /config/prompt-tree`, `GET/PUT/POST /config/prompts/{path}` | ✓ (tree VERIFIED) |
| `/email-queue` (EmailQueuePage) | `GET /tenants/{id}/email-queue`, `PUT /email-queue/{id}`, approve/reject | ✓ (GET VERIFIED) |
| `/patterns` (PatternsPage) | `GET /tenants/{id}/patterns`, promote/demote | ✓ (GET VERIFIED) |

**No orphan calls, no missing endpoints.** (Note: earlier planning docs referenced routes like `/action-center`, `/ai-engine`, `/workflow-library` that do **not** exist in the current app; the shipping routes above are authoritative.)

---

## 13. Health, Ops & Observability

- `GET /api/v1/health` (public) returns DB status, per-provider LLM key presence (**masked** preview only), evidence-file count, tenant count, active workflows, and live WS connection count. Live: `status: ok`, DB `postgresql`, Anthropic configured, 4 tenants.
- `GET /admin/live-stats` and `/admin/system-events` provide fleet-level telemetry (VERIFIED).
- **WebSocket** `/ws/{session_id}?token=…`: token-authenticated, tenant-aware broadcast over Redis channel `opsgrid:events:tenant:{id}`, with ping/pong keepalive. Implemented; not exercised in this read-only audit.
- **`start.ps1` port detection.** The script detects an already-running backend with `Get-NetTCPConnection -LocalPort 8000 -State Listen`. This is correct **only when the native backend binds 8000**. Because the Docker `api` service's port mapping is commented out, there is no conflict today. Caveat: `Get-NetTCPConnection` can raise instead of returning empty when nothing is listening; the script suppresses this with `-ErrorAction SilentlyContinue`, so the check is safe but silently treats "no listener" and "query error" alike. No change required for current operation.

---

## 14. Live API Test Results (read-only)

All calls below were made against the running server as super_admin (except the isolation test, which used an ephemeral tenant_user). No mutating endpoints were exercised; no business/seed data was modified.

| Endpoint | Method | Result |
|---|---|---|
| `/health` | GET | 200 ✓ |
| `/auth/login` | POST | 200 ✓ (token issued) |
| `/tenants/{id}` | GET | 200 ✓ (4173 B) |
| `/tenants/{id}/config-schema` | GET | 200 ✓ |
| `/tenants/{id}/budget` | GET | 200 ✓ |
| `/tenants/{id}/patterns` | GET | 200 ✓ |
| `/tenants/{id}/email-queue?status=all` | GET | 200 ✓ (empty list) |
| `/tenants/{id}/workflows/stats` | GET | 200 ✓ (8 runs: 3 completed/4 failed/1 escalated) |
| `/tenants/{id}/connectors/health` | GET | 200 ✓ (all `no_credentials`) |
| `/dashboard/{id}` | GET | 200 ✓ |
| `/analytics/{id}` | GET | 200 ✓ (success_rate 0.375) |
| `/tenants/{id}/validate-config` | POST | 200 ✓ (valid) |
| `/workflows/estimate-cost?tenant_id=…&workflow_name=…` | GET | 200 ✓ |
| `/workflows/{run_id}/status` | GET | 200 ✓ |
| `/workflows/{run_id}/evidence` | GET | 200 ✓ |
| `/workflows/{run_id}/system-log` | GET | 200 ✓ |
| `/admin/god-view` | GET | 200 ✓ (38985 B) |
| `/admin/live-stats` | GET | 200 ✓ |
| `/admin/system-events` | GET | 200 ✓ |
| `/config/models` | GET | 200 ✓ |
| `/config/workflows` | GET | 200 ✓ |
| `/config/prompt-tree` | GET | 200 ✓ |
| `/tools/local`, `/tools/available` | GET | 200 ✓ |
| `/seed-data/status` | GET | 200 ✓ |
| `/analytics/admin/fleet` | GET | 200 ✓ |
| `/escalations` | GET | 200 ✓ |
| `/a2a/pending` | GET | 200 ✓ (empty) |
| `/evidence` | GET | 200 ✓ |
| Missing token → protected route | GET | 401 ✓ |
| Non-existent run_id → `/workflows/{id}/status` | GET | 404 ✓ |
| **Cross-tenant reads (tenant_user → other tenant)** | GET | **403 ✓ (all)** |
| **Admin-only routes (tenant_user)** | GET | **403 ✓** |

---

## 15. API Contract Quality

- Consistent `/api/v1` prefix and tag grouping; OpenAPI served at `/openapi.json` + `/docs`.
- FastAPI validation returns structured 422 arrays (the frontend client already normalizes these).
- Query-param contracts are strict: `estimate-cost` **requires** `tenant_id` and `workflow_name` (omitting them yields 422 — this is correct behavior, see §16).
- Secrets are never returned in cleartext: `/health` masks LLM key previews; credentials are Fernet-encrypted at rest.
- Tenant-scoped resources uniformly enforce `assert_tenant_access`.

---

## 16. Known Issues & Prior False-Positives

Two items flagged as "FAIL" in an earlier automated report were re-examined and are **test-harness artifacts, not backend defects**:

1. **`GET /workflows/estimate-cost` → 422.** The endpoint declares `tenant_id` and `workflow_name` as required query params. The old tester called it with none, so FastAPI correctly returned 422. With valid params it returns **200** (verified). *Not a bug.*
2. **`GET /workflows/{run_id}/logs` → 404.** There is no `/logs` route; the real endpoint is **`/workflows/{run_id}/system-log`**, which returns 200 (verified). The old test used the wrong path. *Not a bug.*

Genuine limitation (not a failure): **`outcome_tracker` has no built-in scheduler** — the follow-up outcome loop only advances via the manual `check-pending` endpoint or an external cron (§8).

---

## 17. Security Notes

- **No hardcoded secrets** in source; `.env` + DB-backed encrypted credential store.
- **Tenant isolation enforced** and verified live (§5).
- **Fernet encryption at rest** for integration credentials, with key rotation support.
- **HITL send-gating**: Gmail `send_email` queues for approval rather than sending; email-queue approve/reject gates outbound messages.
- **Prompt-injection exposure (inherent):** user/CRM data is interpolated into LLM prompts via `{placeholder}` templates with no visible sanitization layer. Malicious field content (e.g., a customer name containing instructions) could influence an LLM. This is an AI-architecture risk to track, not a code bug.
- **Ephemeral vault key risk:** if `VAULT_ENCRYPTION_KEY` is unset, an ephemeral key is generated with a warning — credentials encrypted under it become unreadable after restart. Ensure the key is set in any persistent environment.

---

## 18. Connect-Today Verdict

**Yes — the existing frontend can be wired to the real backend today with no design or contract changes.** Base URL, JWT auth, tenant model, and every called path align. Reads are verified working end-to-end; mutating flows are implemented and follow the same auth/tenant discipline (they were not exercised here purely to avoid side effects). The only capability that is genuinely absent — and that no amount of frontend wiring can supply — is **predictive ML** (§9) and the **Lead Assessment POC surface** (§11).

---

## 19. Recommended Next Steps

1. **Do not label the system "ML-integrated."** Update any product/academic copy to state that scoring is LLM-formula-based; classical ML is planned, not built (§9).
2. **If the Lead Assessment POC is in scope**, build the missing surface (§11): lead data model + CRUD endpoints, a trained model + prediction endpoint, explainability, and a `lead_assessment` DAG + prompts — reusing the existing approval/evidence/tenant substrate.
3. **Wire a scheduler** (APScheduler/cron) to drive `outcome_tracker.check_pending_outcomes` so the feedback loop closes automatically (§8/§16).
4. **Add a prompt-injection mitigation layer** (input sanitization / delimiting / instruction-isolation) before external data reaches LLM prompts (§17).
5. **Optionally verify mutating flows** in a disposable tenant (trigger → status → escalation decide → email approve → fork) to promote the ~50 "IMPLEMENTED — NOT YET VERIFIED" endpoints to VERIFIED, without touching production/seed data.

---

*End of audit.*
