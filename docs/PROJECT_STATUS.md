# SMBFlow Project Status — Current Checkpoint

## Milestone Status Overview

### DONE
- **Backend API Audit:** Comprehensive inventory of 80 FastAPI HTTP endpoints + 1 WebSocket endpoint completed.
- **Frontend Migration Analysis:** Integration strategy defined (retaining legacy client/auth infrastructure while adopting Figma presentation UI).
- **API Service Foundation:** Modular API service layer created in `src/api/client.js` and `src/api/services/`.
- **Login & Auth Shell:** Figma login, signup, forgot password, and reset password UI integrated with real backend auth.
- **Real Auth Verification:** Login verified against live backend JWT endpoints (`/api/v1/auth/login`, `/api/v1/auth/me`).
- **Role Routing:** Enforced automatic routing (`super_admin` → `/admin`, `tenant_user` → `/dashboard`).
- **Protected Routes:** Enforced `ProtectedRoute` guard across Figma shell components (`AppShell`, `Sidebar`, `TopHeader`).
- **Auth Input Visibility:** Explicit readable input text color and lighter placeholder styling fixed across all auth pages.
- **Build Verification:** Production frontend build passed with exit code 0.

### IN PROGRESS
- Remaining authentication verification / edge-case testing
- Screen-by-screen frontend migration preparation

### NEXT
- Dashboard migration & backend wiring
- Owner screens integration
- Admin screens integration
- API integration for remaining domain endpoints
- Lead Assessment ML integration

---

# Changelog

## [Phase 0 - Baseline] - 2026-08-24
### Milestones
- **Environment Stabilized**: Docker, PostgreSQL (pgvector), and Redis correctly configured and running.
- **Full Stack Verified**: Backend API, frontend UI, and WebSocket connections tested and functioning.
- **Tenant Flow**: Test tenant onboarded (`TechFlow SaaS Inc.`).
- **Workflow Verification**: `saas_churn_prevention` workflow successfully triggered via frontend UI and executed end-to-end.
- **EPI Evidence**: Cryptographically signed Execution Provenance Records successfully generated for the workflow execution.
- **Feature Freeze**: No new application features have been added yet. This marks the stabilized baseline of the inherited repository.


<!-- ==================== FROM FEATURE_STATUS.md ==================== -->

# FEATURE STATUS

## 1. Backend / Core Engine
- **Status:** Mostly Complete
- **Details:** The orchestrator, LLM router, and state manager are fully fleshed out in Python.

## 2. Agent Framework
- **Status:** Mostly Complete
- **Details:** The 6-agent chain is implemented. They use Litellm to communicate with models.

## 3. Workflow Engine
- **Status:** Complete (for JSON DAGs)
- **Details:** Configured to read JSON files and follow edges and conditions.

## 4. AI / ML
- **Status:** Prototype (LLM only)
- **Details:** See `EXISTING_SYSTEM_AUDIT.md`. There is no classical ML. It entirely relies on prompting LLMs to perform "reasoning".

## 5. Database
- **Status:** Mostly Complete
- **Details:** `db/init.sql` defines a very comprehensive schema (multi-tenant, RAG pgvector, budget settings, escalations).

## 6. Integrations
- **Status:** Partial
- **Details:** Framework exists. HubSpot, Slack, Gmail, Stripe have basic connector classes. 

## 7. API
- **Status:** Mostly Complete
- **Details:** 78 endpoints implemented for auth, tenant management, workflow control, and admin views.

## 8. Frontend
- **Status:** MVP-Ready
- **Details:** React SPA with standard pages built (Dashboard, Config, Workflows). 

## 9. Human-in-the-Loop
- **Status:** Mostly Complete
- **Details:** Escalation logic exists in the DAG and DB schemas. The API exposes endpoints for human review.

## 10. Audit / Evidence
- **Status:** Complete
- **Details:** `epi_manager.py` successfully implemented to record cryptographic evidence of execution.

## 11. Testing
- **Status:** Missing / Unknown
- **Details:** Pytest is in requirements, but no robust unit test suite was identified during the initial scan.

## 12. Deployment
- **Status:** MVP-Ready
- **Details:** `Dockerfile` and `docker-compose.yml` are present and configured for Postgres + Redis.


<!-- ==================== FROM UI_STATUS.md ==================== -->

# UI Status

The current frontend User Interface (React/Vite) is fully functional and correctly integrates with the backend API and WebSockets for real-time workflow monitoring.

## Phase 2A: UI Design Proposal (Figma)
- **Figma redesign v1 completed.**
- These designs are reference/prototype assets only. See `docs/UI_DESIGN_PROPOSAL.md`.
- **React implementation has NOT started.** No application logic or frontend code was changed during this task.
- Remaining screens (Login, Builder templates, Billing, etc.) are planned for the next design session.

## Next Steps
While the current UI is functionally verified, the next major development phase will be implementing the approved Figma redesign to meet professional B2B SaaS standards.

> [!NOTE]
> No modifications to styling, components, layout, routing, or frontend architecture have been made during Phase 0 or Phase 2A.


<!-- ==================== FROM RUNTIME_BASELINE.md ==================== -->

# Runtime Baseline

This document records the baseline state of the SMBFlow platform after completing Phase 0 end-to-end verification.

## Infrastructure
The backend is powered by Docker-based infrastructure running locally:
- **PostgreSQL**: Serving as the relational database.
- **pgvector**: Enabled for vector embeddings and search.
- **Redis**: Running for pub/sub (used by the WebSocket broadcast).

## Application Stack
- **Backend API**: FastAPI / Uvicorn server running on `localhost:8000`. Connects to Postgres and Redis.
- **Frontend**: React application running on Vite (`localhost:5173`). UI relies on the real backend API.
- **WebSocket**: Successfully authenticates with a JWT token parameter (`/ws/{session_id}?token={token}`) and broadcasts real-time events (`workflow_triggered`, `workflow_running`, `agent_started`, `agent_live_output`, `agent_completed`).

## Workflow Execution State
The system was verified by running the existing `saas_churn_prevention` workflow for the `TechFlow SaaS Inc.` tenant from the UI.

- **Trigger Flow**: The UI successfully established a WebSocket connection and dispatched the trigger event to the backend API.
- **Agent Execution**: `research_agent`, `reasoning_agent`, `drafting_agent`, and `verification_agent` all successfully ran sequentially.
- **EPI Evidence**: A cryptographically signed EPI (Execution Provenance Record) artifact was successfully generated and stored.

### LLM Provider Behavior
- **Default Models**: By default, the `research_agent` and `verification_agent` use Anthropic (`claude-haiku-4-5-20251001`).
- **Overrides**: In our local tests, we explicitly configured the `reasoning_agent`, `drafting_agent`, and `memory_agent` to use `gemini-3.6-flash` via temporary overrides in `config/clients/saas_demo.json`.
- **Fallback / Retry Engine**: The `LLMRouter` flawlessly fell back to OpenRouter when direct Anthropic requests failed. The Orchestrator engine correctly caught OpenRouter limits and degraded/retried across models without crashing the application.
- **Known Limitations**: The primary Anthropic account and OpenRouter fallback accounts both hit credit limits (`400 BadRequest` on Anthropic, `402 Payment Required` on OpenRouter), which necessitated the Gemini overrides.
- **EPI Heuristic Flags**: The EPI validation flagged the litellm fallback exceptions as `ERROR_CONTINUATION`, which is expected given the graceful retry behavior of the architecture.

## Temporary Local Configuration
The following model overrides exist exclusively in `config/clients/saas_demo.json` to bypass paid credit limits:
- `reasoning_agent` -> `gemini/gemini-3.6-flash`
- `drafting_agent` -> `gemini/gemini-3.6-flash`
- `memory_agent` -> `gemini/gemini-3.6-flash`

> [!WARNING]
> These overrides are specific to the local demo tenant configuration (`saas_demo.json`) and must NOT be integrated into the global templates (`llm_config.json`).


<!-- ==================== FROM RUNTIME_TEST_REPORT.md ==================== -->

# RUNTIME TEST REPORT

## Environment Verification
- **Python Version:** 3.13.0
- **Node Version:** 20.19.0
- **Docker:** NOT FOUND in the current local test environment.

## Execution Attempts

### 1. Database & Cache
- **Command:** `docker-compose up -d postgres redis`
- **Result:** Failed. `docker` command not recognized in the environment.
- **Impact:** The backend API and Workflow Orchestrator cannot run because they strictly require PostgreSQL and Redis connections at startup.

### 2. Dependency Installation
- **Command:** `pip install -r requirements.txt`
- **Result:** Partially successful, but since DB cannot be started, the backend cannot be fully tested.

### 3. API Startup
- **Command:** `python main.py api`
- **Result:** Will fail on DB connection if forced, but the API has a `system_integrity_check` middleware that returns `503 System Not Initialized` if `DATABASE_URL` is missing.

### 4. Code Checks
- `audit_script.py` successfully traversed the directory, parsed JSON workflows, and verified the presence of Python classes and React files.

## Summary of Runtime State
The code is syntactically sound and well-structured, but the project is currently untestable in environments lacking Docker. 
**Next Steps for Runtime:** Provision a PostgreSQL database and a Redis instance (either locally natively, or remotely) and configure the `.env` file to point to them.

## Frontend Runtime Verification
- **Mismatch**: CLI runs completed successfully in Lite Mode (no DB), but Frontend UI is strictly DB-driven. Thus, Admin dashboard shows 0 runs and 0 cost.
- **UI Blocking**: The "Trigger Workflow" UI is broken due to a missing fallback when the `tenants` DB table is empty. Most client-facing pages require a tenant context.
- **WebSocket Verification**: Blocked until a workflow can be successfully triggered from the UI.
- **Fix**: Require Database Seeding with a mock tenant (e.g., `TechFlow SaaS Inc.`).


<!-- ==================== FROM GAPS_AND_BLOCKERS.md ==================== -->

# GAPS AND BLOCKERS

## Ranked Blockers

### P0 — Prevents Running the System
- **Missing Infrastructure (Docker):** The project relies entirely on PostgreSQL and Redis. The current environment lacks Docker, making it impossible to bring up the database or cache.
- **Impact:** Backend API fails to start. Workflows cannot be executed or tested end-to-end.
- **Evidence:** `docker --version` returns command not found.
- **Recommended Action:** Install Docker locally or provision a managed PostgreSQL/Redis instance (e.g., Supabase, Upstash) and update the `.env` file.

### P1 — Prevents Demonstrating the Project for Academic Credit
- **No Classical Machine Learning:** This is an ML course project, but the codebase uses 0 classical ML. It relies entirely on LLM prompting.
- **Impact:** Will not meet academic requirements for training/evaluating an ML model.
- **Evidence:** Codebase grep for `sklearn`, `torch`, `xgboost` returns 0 hits (excluding the audit script itself).
- **Recommended Action:** Build a classical predictive model (e.g., a churn prediction classifier) and pipe its predictions into the DAG orchestration.

### P2 — Major Functionality Gaps
- **Missing Tests:** There are no apparent unit or integration test suites covering the core orchestrator or APIs.
- **Impact:** High risk of regressions during future development.
- **Evidence:** Lack of a populated `tests/` directory.

### P3 — Improvement / Polish
- **Prompt Injection Vulnerability:** Raw data from third-party tools is injected directly into LLM prompts without sanitization.
- **Impact:** Potential for unintended agent actions.
- **Recommended Action:** Add a prompt sanitization or validation layer.
