# SMBFlow — Next Phase Implementation & Integration Plan

## Baseline

The completed audit reports 80 HTTP operations + 1 WebSocket, 30 live read endpoints verified, JWT/RBAC/tenant isolation verified, existing workflow/orchestration/LLM/RAG/integration infrastructure working, and the Lead Assessment ML surface missing. fileciteturn11file0

## Target architecture

Keep one SMBFlow repository:

```text
SMBFlow/
├── frontend/      # approved SMBFlow React/Vite UI
├── api/            # existing FastAPI backend
├── core/           # orchestration/services
├── agents/
├── integrations/
├── workflows/
├── ml/             # new Lead Assessment ML POC
├── db/
├── scripts/
└── docs/
```

Runtime:

```text
React
  ↓
frontend API service layer
  ↓
FastAPI /api/v1
  ↓
services
  ↓
PostgreSQL / Redis / AI providers / integrations / ML
```

Never connect the browser directly to PostgreSQL or Redis.

## 1. Preserve before changing

Preserve the existing:

- FastAPI backend
- `/api/v1` contract
- JWT authentication
- RBAC
- tenant isolation
- PostgreSQL schema
- Redis event infrastructure
- workflow engine
- agents
- LLM router
- RAG
- integration connectors
- encrypted credential vault
- evidence/audit machinery
- WebSocket design

Do not rewrite working infrastructure just because the frontend changed.

## 2. Frontend migration strategy

The legacy frontend is no longer the UX source of truth. The approved SMBFlow Figma design becomes the product UI direction.

Do NOT delete the old frontend wholesale.

First preserve/reuse useful infrastructure:

- API client
- auth/token handling
- WebSocket client
- React Query setup
- useful hooks
- state management
- route guards
- tested workflow logic
- error normalization

Replace/refactor the legacy presentation:

- layouts
- navigation
- pages
- dashboard
- Admin console
- settings
- action/review surfaces
- workflow presentation where needed

Target:

```text
existing backend
+
reusable frontend infrastructure
+
approved SMBFlow UI
=
one application
```

## 3. Central API service layer

Create or consolidate:

```text
frontend/src/services/
├── apiClient.js
├── authApi.js
├── dashboardApi.js
├── workflowApi.js
├── runApi.js
├── reviewApi.js
├── organizationApi.js
├── userApi.js
├── adminApi.js
├── aiProviderApi.js
├── modelApi.js
├── integrationApi.js
├── healthApi.js
├── usageApi.js
└── auditApi.js
```

Every method must map to a confirmed backend endpoint.

Do not invent endpoint URLs.

## 4. Environment configuration

Use:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

Do not scatter `localhost:8000` through components.

## 5. API classification

For every frontend requirement, classify the backend as:

- REUSE — existing endpoint is sufficient
- EXTEND — endpoint exists but lacks required fields/filtering/behavior
- NEW — capability genuinely does not exist

Do not replace a working API just because the UI changed.

## 6. Integration order

### Phase A — Foundation
1. API client
2. auth/login
3. `/auth/me`
4. token handling
5. role routing
6. global 401/403/422/5xx handling

### Phase B — SMB Owner
1. Dashboard
2. Workflows
3. Workflow detail
4. Review/action surfaces
5. Evidence
6. Integrations
7. Settings
8. Budget

### Phase C — Admin
1. Platform Overview
2. Organizations
3. Users
4. Workflows
5. Workflow Runs
6. Review Queue
7. AI Services
8. Provider Connections
9. Models
10. Routing/Assignments
11. System Health
12. Usage & Cost
13. Audit
14. Platform Settings

### Phase D — Lead Assessment
Build the missing ML/lead domain on top of the existing orchestration substrate.

## 7. Admin AI architecture

Use:

```text
Provider Connection
    ↓
Model Catalog
    ↓
Capability
    ↓
Task Routing
    ↓
Agent Assignment
    ↓
Workflow Override
    ↓
Fallback Policy
    ↓
Execution
    ↓
Monitoring / Audit
```

API credentials belong to provider connections, not models.

Never show raw secrets.

## 8. Lead Assessment backend additions

The audit found no classical predictive ML and no Lead Assessment surface. fileciteturn11file0

Add a separate domain, for example:

```text
ml/lead_assessment/
├── data.py
├── features.py
├── train.py
├── evaluate.py
├── predict.py
├── explain.py
├── schemas.py
└── artifacts/
```

Keep UCI Bank Marketing training data separate from SaaS tenant data.

Conceptual API surface:

```text
lead list/get
lead create/ingest
assessment request
prediction result
explanation
assessment history
outcome/feedback
```

These are design candidates only; first align them with existing backend conventions before implementation.

## 9. Lead Assessment workflow

```text
Lead Data
→ Validation
→ ML Lead Scoring
→ Explainability
→ LLM Business Reasoning
→ Follow-up Recommendation
→ Risk / Policy Gate
→ Human Review
→ Action
→ Outcome Tracking
→ Feedback
```

Reuse:

- DAG engine
- agents
- HITL/escalation machinery
- evidence
- integrations
- tenant isolation

Add only lead-specific nodes/services/prompts.

## 10. ML correctness

Do not describe current LLM-based formula scoring as classical ML.

The audit found:

- no sklearn/xgboost/lightgbm predictive implementation
- no prediction endpoint
- no predictive model artifacts
- current churn/risk scoring is prompt-driven LLM reasoning/formula application

Only call the system ML-integrated after the new predictive model is actually trained, evaluated, integrated and tested. fileciteturn11file0

## 11. Explainability

Prediction responses should provide:

- probability/score
- class/decision where applicable
- top contributing features
- contribution direction
- explanation metadata

Do not ask an LLM to fabricate feature attribution.

## 12. Scheduler

Outcome tracking is partially implemented because it lacks an internal scheduler. fileciteturn11file0

Later add:

```text
Scheduler
→ pending outcome check
→ evaluate
→ persist outcome
→ evidence/memory update
```

Make it retry-safe and observable.

## 13. Safe mutation verification

The audit deliberately avoided most mutating endpoints. fileciteturn11file0

Verify them in a disposable/test tenant:

- tenant creation
- user creation/deactivation
- workflow trigger
- pause/resume/stop/fork
- escalation decisions
- A2A decisions
- email approval/rejection
- tools create/delete/test
- credentials create/delete
- budget update
- DAG/config/prompt writes

For each verify:

```text
request
→ auth/RBAC
→ validation
→ DB change
→ response
→ side effect
→ audit/evidence
→ retry/idempotency behavior
```

## 14. UI state contract

Every data-driven screen must distinguish:

- Loading
- Empty
- Unavailable
- Authentication expired
- Permission denied
- Validation error
- Network error
- Server error
- Partial failure

Do not collapse all failures into "No data".

## 15. Security

Maintain and verify:

- no secrets in frontend
- secure credential handling
- RBAC
- tenant isolation
- confirmation for sensitive actions
- prompt-injection mitigation before external data reaches LLMs
- no unsafe provider/model disable/delete flows

The audit explicitly flags prompt-injection exposure as an architectural risk to address. fileciteturn11file0

## 16. Testing

### Backend
- unit tests
- API integration tests
- auth/RBAC
- tenant isolation
- workflow lifecycle
- provider connection
- ML prediction
- explainability

### Frontend
- route guards
- API service methods
- loading/empty/error states
- forms
- confirmation flows
- role-specific navigation

### End-to-end
Owner:
```text
login
→ dashboard
→ workflows
→ workflow detail
→ trigger
→ status
→ evidence
```

Admin:
```text
login
→ overview
→ organizations
→ users
→ AI provider/model management
→ runs
→ review queue
→ audit
```

## 17. Change management

Before each phase:

```text
git status
git diff
```

Checkpoint after stable phases.

Suggested commits:

```text
feat: establish frontend api service layer
feat: integrate authentication and role routing
feat: integrate owner core screens
feat: integrate admin console
feat: add lead assessment ml poc
feat: connect lead assessment workflow
test: verify end-to-end workflow
```

Do not mix unrelated UI, backend refactor, and ML work in one giant change.

## 18. Definition of done

A feature is complete only when:

- UI exists
- route works
- API exists
- contract matches
- authorization works
- tenant isolation works
- loading/empty/error states work
- mutation is tested where applicable
- audit/evidence behavior is verified where relevant
- no fake data
- no exposed secrets
- regression tests pass

## 19. Immediate execution plan

1. Freeze the Figma Admin/Owner design.
2. Keep the current backend as the foundation.
3. Inspect the existing frontend and identify reusable infrastructure.
4. Build/standardize the frontend API service layer.
5. Connect authentication and role routing.
6. Replace legacy pages incrementally with approved SMBFlow pages.
7. Connect Owner screens one by one.
8. Connect Admin screens one by one.
9. Safely verify mutating APIs in a disposable tenant.
10. Implement Lead Assessment ML + explainability.
11. Add the Lead Assessment DAG.
12. Connect LLM reasoning + HITL + action.
13. Add outcome scheduling.
14. Run complete security/regression/E2E validation.

## 20. Final target

```text
Professional SMB Owner UX
        +
Professional Platform Admin Console
        +
Existing workflow/agent infrastructure
        +
Real API integration
        +
Real predictive ML Lead Assessment
        +
LLM reasoning
        +
Human-in-the-loop
        +
Evidence / auditability
        +
Outcome tracking
```

The objective is to evolve the existing platform safely into SMBFlow, not to discard working infrastructure and rebuild everything.
