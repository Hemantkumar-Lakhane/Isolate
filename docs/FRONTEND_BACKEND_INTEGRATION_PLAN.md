# SMBFlow — Frontend ↔ Backend Integration & Migration Plan

**Document type:** Migration analysis (discovery only — no code changed)
**Repository:** `C:\Users\lakha\ml_cp\SMBFlow` (single repo — backend + frontend)
**Inputs:**
- Legacy frontend: `frontend/` (JavaScript, React 18, Vite 5) — the current backend-wired app
- New UI: Figma Make export at `C:\Users\lakha\Downloads\smbflow` (TypeScript, React 19, Vite 8) — approved product direction
- Backend truth: [docs/TECHNICAL_AUDITS_AND_APIS.md](TECHNICAL_AUDITS_AND_APIS.md)
- Phase plan: [docs/SMBFLOW_NEXT_PHASE_IMPLEMENTATION_PLAN.md](SMBFLOW_NEXT_PHASE_IMPLEMENTATION_PLAN.md)

> **Governing finding.** The **legacy frontend already works against the real backend** — in-memory JWT auth, a bound API client with FastAPI-422 handling, a WebSocket client with heartbeat/reconnect, Zustand stores, and rich workflow components — and every path it calls exists and was verified in the API audit. The **Figma export is presentation-only**: its login is faked (`setTimeout` + a role toggle), its auth store is never populated, its `ProtectedRoute` is never mounted, its entire `api/*` service layer is unused dead code targeting **invented endpoints**, and every page renders static/mock data. **Therefore the migration is: keep the legacy infrastructure layer, adopt the Figma presentation, and wire the new screens to the already-verified API client — not a rewrite.**

---

## 0. Executive Status & Progress Checkpoint

- **Phase 1 (API Service Foundation):** **COMPLETED.** Modular API service layer created (`src/api/client.js`, `src/api/services/auth.service.js`, and domain services) wrapping legacy HTTP client with full FastAPI error handling and token injection.
- **Phase 2 (Auth & Shell Integration):** **COMPLETED.** Figma presentation layer (`LoginPage`, `SignupPage`, `ForgotPasswordPage`, `ResetPasswordPage`, `AppShell`, `Sidebar`, `TopHeader`) fully integrated with existing backend auth endpoints. Real login verified end-to-end. Role-based routing enforced (`super_admin` → `/admin`, `tenant_user` → `/dashboard`). Input text visibility bugs fixed across all auth pages.
- **Current Frontend Migration Status:** 
  - Legacy frontend infrastructure (in-memory JWT, WebSocket context, API client, error handling) **retained as core foundation**.
  - Backend API (`FastAPI`) **retained as existing, unchanged foundation**.
  - Figma UI design **adopted as new presentation layer**.
  - Production frontend build passed with exit code 0.
- **Next Phase:** Screen-by-screen frontend/backend integration starting with Dashboard, Owner screens, Admin screens, and Lead Assessment ML integration.

---

## Table of Contents
1. Current Architecture
2. Target Architecture
3. Legacy Frontend Modules (inventory)
4. Figma Frontend Modules (inventory)
5. Keep / Refactor / Replace / Remove / New Matrix
6. Route Migration Table
7. API Mapping (REUSE / EXTEND / NEW / REMOVE)
8. Auth Migration
9. WebSocket Migration
10. Admin Migration
11. Owner Migration
12. Dependency Migration
13. Backend Extensions Required
14. Lead Assessment Integration Plan
15. Testing Strategy
16. Rollback Strategy
17. Recommended Implementation Order

---

## 1. Current Architecture

**Legacy `frontend/` (JS, React 18, Vite 5) — real, working:**
- Routing in `App.jsx`: `HomeRedirect`, `ProtectedRoute({adminOnly})`, `Wrap` guards; unauth → `/auth`, non-admin on admin route → `/dashboard`.
- API client `api/client.js`: `API_BASE = VITE_API_BASE || http://127.0.0.1:8000/api/v1`, `WS_BASE = VITE_WS_BASE || http://127.0.0.1:8000/ws`; `apiCall()` injects `Authorization: Bearer`, maps FastAPI 422 arrays, throws typed errors; `createApiClient(token)` → `{get,post,put,patch,delete}`.
- Auth `contexts/AuthContext.jsx`: **token in memory only** (XSS mitigation); only non-sensitive user profile persisted to localStorage (`opsgrid_user_profile`); `isAdmin = role === 'super_admin'`; exposes bound `api`.
- WebSocket `contexts/WSContext.jsx`: connects `${WS_BASE}/${sid}?token=`, 25s ping heartbeat, 3s auto-reconnect, 500-event ring buffer, `subscribe(type, handler)`, `useWorkflowEvents(runId)`.
- State: React Context (Auth/WS/Theme) + Zustand (`utils/appStore.js`: streaming, badges, UI, builder stores) + React Query (configured; used only by `WorkflowDetail.jsx`).
- Pages: 3 admin (`GodView`, `FleetCost`, `UsersPage`), 12 client, `AuthPage`. Mostly `useState`+`setInterval` polling; all call real endpoints.

**Backend (unchanged):** FastAPI, 80 HTTP ops + 1 WS, JWT/RBAC, PostgreSQL + Redis, verified in the audit.

## 2. Target Architecture

One repo, one backend, one frontend. Evolve `frontend/` in place. Proposed structure (adapt, don't force):

```text
frontend/src/
  api/            # KEEP client.js (the proven bound client) + add per-domain service modules
  contexts/       # KEEP AuthContext, WSContext, ThemeContext (proven)
  stores/         # KEEP Zustand stores (appStore.js)
  layouts/        # NEW AppShell/Sidebar/TopHeader ported from Figma (presentation)
  pages/          # REPLACE presentation with Figma pages, wired to api/
    owner/
    admin/
  components/     # MERGE Figma primitives + keep workflow/* business components
  utils/          # KEEP helpers.js
  routes/         # route table (react-router-dom v6 — keep legacy version)
```

Data flow stays: **React → api client (bearer JWT) → FastAPI /api/v1 → services → PG/Redis/LLM.** Browser never touches PG/Redis directly.

**Language decision:** legacy is `.jsx`; Figma is `.tsx`. Recommend adopting **TypeScript incrementally** (Vite supports mixed JS/TS) rather than a big-bang rewrite — port Figma pages as `.tsx`, leave proven `.jsx` infra until touched. This avoids destabilizing verified code.

## 3. Legacy Frontend Modules (inventory)

| Module | Type | Notes |
|---|---|---|
| `api/client.js` | Business | Bound client, 422 handling, bearer injection — **crown jewel** |
| `contexts/AuthContext.jsx` | Business | In-memory token, role, bound `api` |
| `contexts/WSContext.jsx` | Business | WS heartbeat/reconnect, subscribe, `useWorkflowEvents` |
| `contexts/ThemeContext.jsx` | Business | dark/light, localStorage |
| `utils/appStore.js` | Business | Zustand: streaming/badges/UI/builder |
| `utils/helpers.js` | Business | formatters + display maps (`fmtCost`, `STATUS_COLORS`, agent icon/label maps, `BUDGET_LEVELS`) |
| `components/workflow/*` | Business+UI | `NodePipeline` (dagre+xyflow), `DecisionPortal`, `A2APermissionModal`, `LogTerminal`, `CostRibbon`, `WorkflowSummary`, `TrendIndicator` |
| `components/ui/*`, `components/layout/*` | Presentation | replaceable by Figma design |
| 3 admin + 12 client pages + `AuthPage` | Mixed | logic reusable, presentation replaceable |

## 4. Figma Frontend Modules (inventory)

| Module | Reality |
|---|---|
| `api/client.ts` | `API_BASE = VITE_API_URL ?? '/api'`; **no token injection**, no `.env` |
| `api/services.ts`, `api/adminServices.ts` | Full typed spec — **unused dead code**; endpoint paths self-described "intentional placeholders" |
| `api/queryKeys.ts` + TanStack Query | configured but **zero** `useQuery`/`useMutation` in any page |
| `stores/authStore.ts` | Zustand+persist(`smbflow-auth`); `setAuth` **never called** |
| `LoginPage.tsx` | **FAKE**: real call commented out; `setTimeout(800)` then navigate by role toggle |
| `components/ProtectedRoute.tsx` | defined but **never mounted** → no route protection |
| `layouts/*`, `components/*` | Clean, reusable **presentation** (AppShell, Sidebar, TopHeader, MetricCard, StatusBadge, ConfidenceBadge, AdminTable, EmptyState, ErrorState, LoadingState, SkeletonTable, Toast, ConfirmModal, FilterBar, SearchBar) |
| ~40 pages | Presentation + pervasive **mock/static data** (see §5 remove-list) |
| `types/index.ts` vs admin-local interfaces | two divergent type systems; tenant/organization + role-enum mismatch |

**Must NOT be copied to production (mock/unsafe):** fake `LoginPage`; unpopulated `authStore`; unused `ProtectedRoute`; "Sarah Adams"/"SA" hardcoded identity; fabricated model IDs (`claude-opus-5`, `claude-sonnet-5`, `claude-haiku-4-5`, `gpt-4o`, `gemini-pro`…); `setTimeout` fake connect/test/create in `IntegrationsPage`/`AdminProvidersPage`/`AdminAIModelsPage`/`AdminUsersPage`; credential inputs that discard input; `DEMO_WORKFLOWS` and all static fixture arrays; hardcoded `ConfidenceBadge value={0.87}`; default base URL `/api` with no host; unused `recharts`.

## 5. Keep / Refactor / Replace / Remove / New Matrix

| Area | Legacy | Figma | Verdict |
|---|---|---|---|
| API client | `client.js` (bearer, 422) | `client.ts` (no auth) | **KEEP legacy**; port to TS later; discard Figma client |
| Auth | in-memory token + role | fake login | **KEEP legacy**; graft Figma login *presentation* onto legacy logic |
| Route guards | working `ProtectedRoute`/`Wrap` | unused `ProtectedRoute` | **KEEP legacy** guards; adopt Figma role→home mapping |
| WebSocket | full client | none | **KEEP legacy** (only WS client) |
| State mgmt | Zustand + Context + RQ | Zustand + RQ (unused) | **KEEP legacy** stores; **REFACTOR** to actually use React Query per page |
| Workflow components | `NodePipeline` etc. | none (static pipeline UI) | **KEEP legacy** business components; restyle to Figma |
| UI primitives | `components/ui` | richer Figma set | **REPLACE** with Figma primitives |
| Layout/nav | `Layout/Sidebar` | `AppShell/Sidebar/TopHeader` | **REPLACE** with Figma layout |
| Owner pages | functional | designed | **REFACTOR**: Figma presentation + legacy data wiring |
| Admin pages | 3 functional | ~20 designed shells | **REPLACE presentation + wire** to real endpoints (many EXTEND/NEW) |
| Service spec | none | `services.ts`/`adminServices.ts` | **NEW** (rebuild against real endpoints; reuse only names/shapes) |
| Mock data / fake auth | — | pervasive | **REMOVE** entirely |
| `helpers.js` maps | present | — | **KEEP** |

## 6. Route Migration Table

| Legacy route | New (Figma) route | Backend | Migration action |
|---|---|---|---|
| `/auth` | `/auth` | `/auth/login`,`/auth/signup`,`/auth/me` | KEEP logic; adopt Figma `LoginPage` UI; **delete fake auth**, call real login |
| `/dashboard` | `/dashboard` | `GET /dashboard/{tenant_id}` ✓ | Replace UI; reuse legacy data wiring |
| — | `/action-center` | `GET /escalations`, `/a2a/*`, `/email-queue` | NEW UI = merge of legacy Escalations + EmailQueue |
| — | `/workflows` | `GET /workflows`, `/config/workflows` | NEW list UI; wire real; drop `DEMO_WORKFLOWS` |
| `/workflows/builder` | `/workflows/create` | `GET/PUT/POST/DELETE /config/dag*` | Keep legacy `WorkflowBuilder` logic; adopt Figma wizard shell |
| `/workflows/:runId` | `/workflows/:workflowId` | `GET /workflows/{run_id}/status|evidence|system-log` | Reuse legacy `WorkflowDetail` (RQ+WS); restyle; **note id semantics** (run_id vs workflow) |
| — | `/workflows/lead-assessment` | none yet | NEW — blocked on Lead Assessment backend (§14) |
| — | `/workflow-library` | `GET /config/workflows` | NEW; map DAGs to templates (no `/templates` endpoint) |
| `/models` | `/ai-engine`, `/settings/ai-engine` | `GET /config/models`, `/health` | Reuse legacy `ModelSettings` logic |
| `/tools` | `/integrations`, `/settings/integrations` | `/credentials`,`/tools*`,`/connectors/health` | Reuse legacy `ToolsPage` logic; restyle |
| `/config` | `/settings/general` | `/tenants/{id}/config*`,`validate-config` | Reuse legacy `ConfigStudio` logic |
| `/budget` | `/settings/billing` (partial) | `GET/PUT /tenants/{id}/budget` | Reuse legacy `BudgetPage`; billing/invoicing is NEW/missing |
| `/evidence` | `/settings/evidence` | `GET /evidence`, `/evidence/{f}/content` | Reuse legacy `EvidencePage` |
| `/escalations` | folded into `/action-center` | `/escalations*` | Merge |
| `/email-queue` | folded into `/action-center` | `/email-queue*` | Merge |
| `/patterns` | (no Figma page) | `/tenants/{id}/patterns*` | KEEP legacy page or add nav; do not lose capability |
| `/prompts` | (no Figma page) | `/config/prompt*`,`auto-eval*` | KEEP legacy `PromptStudio`; admin-gated |
| `/admin` | `/admin` | `GET /admin/god-view`,`live-stats` | Replace UI; wire to god-view |
| `/admin/users` | `/admin/users` | `GET/POST /users`,`PATCH deactivate` | Reuse legacy `UsersPage` logic |
| `/admin/fleet` | `/admin/usage`,`/admin/analytics` | `GET /analytics/admin/fleet` | Reuse legacy `FleetCost` logic |
| — | `/admin/organizations` | `GET/POST /tenants` | Wire (rename tenant→organization in UI copy) |
| — | `/admin/runs`,`/admin/workflows` | `GET /workflows`,`stats`,`god-view` | Wire (EXTEND for fleet-wide filters) |
| — | `/admin/reviews` | `/escalations`,`/a2a/pending` | Wire |
| — | `/admin/providers`,`/admin/models`,`/admin/routing`,`/admin/ai-services`,`/admin/ai-models` | `/config/models`,`/health` (partial) | Partial wire; provider/model **management** is NEW backend (§13) |
| — | `/admin/health` | `GET /health`,`live-stats`,`system-events` | Wire |
| — | `/admin/integrations` | `/connectors/health` per tenant | Partial; platform-level integrations NEW |
| — | `/admin/audit` | `GET /admin/system-events` (partial) | Partial; full audit log EXTEND |
| — | `/admin/settings` | none | NEW backend (platform settings) — keep honest "not connected" until built |
| — | `*` | — | Adopt Figma `NotFoundPage` |

## 7. API Mapping (REUSE / EXTEND / NEW / REMOVE)

**Figma calls that map to REAL endpoints (rewire to these; REUSE):**
| Figma placeholder | Real backend | Class |
|---|---|---|
| `POST /auth/login`, `GET /auth/me` | same ✓ | REUSE |
| `POST /auth/logout` | *none* (JWT is stateless) | REMOVE (client-side clear only) |
| `GET /dashboard/kpis`,`/dashboard/activity` | `GET /dashboard/{tenant_id}` (returns both) ✓ | REUSE (transform) |
| `GET /workflows`, `/workflows/{id}` | `GET /workflows`, `/workflows/{run_id}/status` ✓ | REUSE |
| `GET /workflows/{id}/runs` | via `god-view`/`/workflows` filter | EXTEND |
| `POST /workflows`,`PATCH`,`DELETE`,`activate/deactivate` | DAG lives in `/config/dag*`; runtime `trigger/pause/stop/resume` | REUSE (remap verbs) |
| `GET /actions`, approve/reject | `/escalations*` + `/email-queue*` (two real queues) | REUSE (merge model) |
| `GET /agents`,`/agents/{id}` | *none* (agents are code, not a resource) | NEW or derive from `/config/models` |
| `GET /integrations`, connect/disconnect/test | `/credentials*`,`/tools*`,`/connectors/health`,`/tools/{id}/test` | REUSE (remap) |
| `GET /templates` | `GET /config/workflows` (DAG list) | EXTEND (no template metadata) |
| `GET /settings/organization`, `/settings/billing` | `/tenants/{id}/config`; budget only | EXTEND / NEW (no billing) |
| `GET /admin/stats` | `GET /admin/god-view`,`live-stats` ✓ | REUSE (transform) |
| `GET /admin/tenants`,`/admin/tenants/{id}` | `GET /tenants`,`/tenants/{id}` ✓ | REUSE (rename) |
| `GET/POST /admin/users`,`PATCH status` | `GET/POST /users`,`PATCH deactivate` ✓ | REUSE (remap) |
| `GET /admin/workflows`,`/admin/runs` | `GET /workflows`,`god-view` | EXTEND (fleet filters) |
| `GET /admin/escalations`, resolve | `GET /escalations`,`POST /escalations/{id}/decide` ✓ | REUSE (remap) |
| `GET /admin/health` | `GET /health`,`live-stats`,`system-events` ✓ | REUSE (transform) |
| `GET /admin/usage/stats`,`/by-tenant` | `GET /analytics/admin/fleet`,`/analytics/{id}` | REUSE/EXTEND |
| `GET /admin/audit` | `GET /admin/system-events` | EXTEND |
| `GET /admin/ai-providers`,`/agent-assignments`, update/test | `GET /config/models`,`/health` (read only) | NEW (management is not implemented) |
| `GET /admin/settings`, update | *none* | NEW |

**REMOVE (Figma-invented, no backend equivalent, drop from client):** `/auth/logout` (stateless), standalone `/agents` resource (unless NEW), `/templates` as a store (use DAGs).

**Rule:** do not invent endpoints. Where the Figma spec has no real backend, the screen must show honest **Loading / Empty / Not-configured / Error** states (the Figma pages already do this — preserve that honesty) until §13 backend work lands.

## 8. Auth Migration

Target behavior (backend remains the authority):
- `/auth` → real `POST /auth/login` → `{access_token, user}` → store token **in memory** (keep legacy in-memory model, not the Figma localStorage-persisted token) → `GET /auth/me` to hydrate.
- `super_admin` → `/admin`; `tenant_user` → `/dashboard` (adopt Figma's role→home map, enforce with legacy `ProtectedRoute`).
- Protected routes require a token; admin routes require `role === 'super_admin'`.
- Keep Admin and Owner navigation **separate** (distinct sidebars per role).

Actions:
1. Adopt Figma `LoginPage` **presentation**; delete its fake `setTimeout`/role-toggle logic and the commented-out call.
2. Reconcile role enums: backend uses `super_admin` / `tenant_user`. Figma uses `platform_admin`/`smb_owner`/`smb_admin`. **Backend wins** — map in one place (`AuthContext`), do not spread new role strings.
3. Mount a real guard on every route (legacy already has one; Figma's is unused).
4. Keep token out of localStorage (retain legacy XSS mitigation); persist only the non-sensitive profile if desired.

## 9. WebSocket Migration

- **Only the legacy WS client exists** (Figma has none). KEEP `contexts/WSContext.jsx` verbatim: `${WS_BASE}/{sid}?token=`, 25s ping, 3s reconnect, `subscribe(type)`, `useWorkflowEvents(runId)`.
- Do **not** create a second WS client. New Figma pages that need live data (dashboard, action center, workflow detail, admin god-view) subscribe via the existing `useWebSocket()` / `useWorkflowEvents()` hooks.
- Preserve consumed event types (`escalation_created`, `a2a_permission_requested`, `workflow_completed`, `agent_live_output`, `email_draft_approved`, …).

## 10. Admin Migration

| Approved Admin screen | Backend support | Status |
|---|---|---|
| Platform Overview (`/admin`) | `god-view`, `live-stats` | **READY** |
| Organizations | `GET/POST /tenants`,`/tenants/{id}` | **READY** (UI copy: tenant→org) |
| Users | `GET/POST /users`,`PATCH deactivate` | **READY** |
| Workflows (fleet) | `GET /workflows`,`config/workflows`,`god-view` | **PARTIALLY READY** (fleet-wide filters → EXTEND) |
| Workflow Runs | `GET /workflows`,`{run_id}/status`,`god-view` | **PARTIALLY READY** (cross-tenant run list → EXTEND) |
| Review Queue | `GET /escalations`,`/a2a/pending`,`decide` | **READY** |
| AI Services | `GET /config/models`,`/health` | **PARTIALLY READY** (read only) |
| Provider Connections | `/health` shows presence only | **BACKEND EXTENSION REQUIRED** (no provider CRUD) |
| Models | `GET /config/models` | **PARTIALLY READY** (catalog read; no per-model mgmt) |
| Routing & Assignments | `llm_overrides` in tenant config | **BACKEND EXTENSION REQUIRED** (no fleet routing API) |
| System Health | `GET /health`,`live-stats`,`system-events` | **READY** |
| Integrations (platform) | per-tenant `/connectors/health` | **PARTIALLY READY** (platform-level → NEW) |
| Usage & Cost | `GET /analytics/admin/fleet`,`/analytics/{id}` | **READY** (charts NEW) |
| Audit Log | `GET /admin/system-events` | **PARTIALLY READY** (full audit → EXTEND) |
| Platform Settings | none | **NEW BACKEND CAPABILITY REQUIRED** |

## 11. Owner Migration

| Approved Owner screen | Backend support | Status |
|---|---|---|
| Dashboard | `GET /dashboard/{tenant_id}` | **READY** |
| Action Center | `/escalations*`,`/a2a/*`,`/email-queue*` | **READY** (merge two queues) |
| Workflows | `GET /workflows`,`config/workflows` | **READY** |
| Workflow Library | `GET /config/workflows` | **PARTIALLY READY** (template metadata → EXTEND) |
| Workflow Detail | `{run_id}/status|evidence|system-log`, lifecycle | **READY** (legacy already implements) |
| Create Workflow | `config/dag*`,`tools/available`,`prompt-tree` | **READY** (legacy `WorkflowBuilder`) |
| AI Engine | `GET /config/models`,`/health` | **PARTIALLY READY** (read/config only) |
| Integrations | `/credentials*`,`/tools*`,`/connectors/health`,`test` | **READY** |
| Settings (general/config) | `/tenants/{id}/config*`,`validate-config` | **READY** |
| Evidence | `/evidence`,`/evidence/{f}/content` | **READY** |
| Billing | budget only (`/tenants/{id}/budget`) | **PARTIALLY READY** (invoicing/plans → NEW) |

No screen may fabricate data; unsupported panels show honest empty/not-configured states.

## 12. Dependency Migration

| Dependency | Legacy | Figma | Action |
|---|---|---|---|
| react / react-dom | 18 | 19 | Decide one; **stay on 18** short-term (legacy infra tested on it), plan 19 upgrade separately |
| react-router(-dom) | v6 (`react-router-dom`) | v8 (`react-router`) | **Keep v6** initially; v8 is a separate migration (API differs) |
| @tanstack/react-query | 5.28 | 5.102 | Align to one 5.x |
| zustand | 4.5 | 5.0 | Align (v5 has minor API changes) |
| tailwindcss | 3.4 (postcss) | 4.0 (`@tailwindcss/vite`) | **Significant** — v4 config differs; decide before porting styles |
| typescript | none | 5.7 | Adopt incrementally |
| lucide-react | 0.400 | 1.41 | Align |
| recharts | 2.12 (used) | 3.10 (**unused**) | Keep legacy 2.x; don't add 3.x until charts built |
| @monaco-editor, @xyflow, dagre, framer-motion, dompurify, react-virtuoso, cva, clsx | legacy only | — | **KEEP** (used by workflow/prompt/builder features) |
| oxfmt | — | figma dev | ignore |

**Do not change `package.json` yet.** Biggest decisions: React 18↔19, react-router v6↔v8, Tailwind 3↔4. Recommend: **freeze on legacy majors**, port Figma pages to those versions, schedule framework upgrades as isolated follow-ups.

## 13. Backend Extensions Required

Ordered by UI need:
1. **Provider/Model management API** (`/admin/ai-providers*`, `/admin/models*`, `/admin/agent-assignments*`): today only read-only `GET /config/models` + `/health` key-presence exist. Admin AI screens need CRUD + connection test + routing assignment. *(EXTEND/NEW)*
2. **Platform Settings API** (`/admin/settings` GET/PATCH): none today. *(NEW)*
3. **Full Audit Log** (`/admin/audit` with filters/actor/resource): `system-events` is the seed; needs structured audit records. *(EXTEND)*
4. **Fleet-wide workflow/run list filters** (cross-tenant search/status/date): `god-view` returns broad data; needs paginated filterable endpoints. *(EXTEND)*
5. **Workflow Library/template metadata**: DAGs exist; add category/description/primary flags. *(EXTEND)*
6. **Billing/invoicing** (beyond budget): *(NEW, optional)*
7. **Outcome scheduler** (from audit §16): wire APScheduler/cron to `check_pending_outcomes`. *(NEW)*
8. **Lead Assessment domain** — see §14. *(NEW, largest)*

## 14. Lead Assessment Integration Plan

**Backend truth:** no classical/predictive ML exists (audit §9); all current "scoring" is LLM-formula. Lead Assessment is a **genuinely new backend capability**. The Figma `LeadAssessmentDetailPage` is a static 12-stage pipeline mock referencing the **UCI Bank Marketing dataset** (research-only, separate from SaaS tenant data). **Do not present current churn scoring as ML.**

Required backend (new `ml/lead_assessment/` domain per the phase plan): `data.py`, `features.py`, `train.py`, `evaluate.py`, `predict.py`, `explain.py`, `schemas.py`, `artifacts/`. API surface (align to existing conventions before building): lead list/get, lead create/ingest, assessment request, prediction result, explanation, assessment history, outcome/feedback. Workflow: Lead → Validation → **ML scoring** → Explainability → LLM reasoning → Recommendation → Risk gate → Human review → Action → Outcome → Feedback (reuse DAG engine, agents, escalation/email HITL, evidence, tenant isolation; add only lead-specific nodes/prompts/services).

**Frontend plan:** keep the Figma `LeadAssessmentDetailPage` presentation, but bind each stage to real prediction/explanation responses once endpoints exist. Explainability must show real feature attributions (probability/score, decision, top contributing features + direction) — **never ask the LLM to fabricate attributions**. Until the backend lands, the page stays in honest "POC / not activated" state.

**Sequencing:** this is the **last** integration phase — it depends on new ML work and must not block the frontend migration of already-supported screens.

## 15. Testing Strategy

**Backend:** promote the ~50 "IMPLEMENTED — NOT YET VERIFIED" mutating endpoints to VERIFIED in a disposable tenant (trigger→status→escalation decide→email approve→fork); add unit/integration tests for auth/RBAC, tenant isolation, workflow lifecycle, and any new provider/settings/lead endpoints.
**Frontend:** route guards (auth required, admin gate); each API service method against a live dev backend; Loading/Empty/Unavailable/AuthExpired/PermissionDenied/Validation/Network/Server/Partial states per screen; forms and confirmation flows; role-specific navigation separation.
**E2E:** Owner (login→dashboard→workflows→detail→trigger→status→evidence); Admin (login→overview→organizations→users→provider/model mgmt→runs→review queue→audit).
Every mutating flow tested in a disposable tenant; never mutate business/seed data.

## 16. Rollback Strategy

- Work on a branch; **do not delete legacy `frontend/`** until the new UI is verified screen-by-screen.
- Migrate incrementally behind the existing router: land one screen at a time, keeping legacy pages reachable until their replacement is verified.
- Checkpoint (commit) after each stable screen; keep commits scoped (no mixing UI + backend + ML in one change).
- Because token stays in memory and endpoints are unchanged, a bad screen can be reverted by pointing the route back at the legacy page.
- Keep `openapi.json`/backend untouched during pure-frontend phases so any regression is isolated to the frontend diff.

## 17. Recommended Implementation Order

1. **Foundation:** create branch; establish the API service layer **on top of the legacy `client.js`** (per-domain modules mapping only to real endpoints); adopt env `VITE_API_BASE`. No page changes yet.
2. **Auth + shell:** port Figma `LoginPage`/`AppShell`/`Sidebar`/`TopHeader`; wire real login + `/auth/me`; enforce legacy guards; role→home routing; delete all fake auth. **This is the first implementation step.**
3. **Owner core (READY screens):** Dashboard → Action Center (merge escalations+email) → Workflows → Workflow Detail (reuse RQ+WS) → Evidence → Integrations → Settings/Config → Budget.
4. **Admin core (READY screens):** Platform Overview → Organizations → Users → Review Queue → System Health → Usage & Cost.
5. **Admin partial screens:** wire read-only AI Services/Models to `/config/models`; show honest states where management APIs are missing.
6. **Backend extensions (§13):** provider/model mgmt, platform settings, audit, fleet filters, outcome scheduler — then wire the corresponding admin screens.
7. **Lead Assessment (§14):** build ML domain + endpoints, then bind the Figma pipeline UI.
8. **Framework upgrades** (React 19, react-router v8, Tailwind 4) as isolated follow-ups.
9. **Full E2E + security/regression** pass; then retire legacy pages.

---

*End of migration plan. No application code, dependencies, DB schema, or seed data were modified in producing this document.*
