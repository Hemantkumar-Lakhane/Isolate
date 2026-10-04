# OpsGrid — Complete Project Structure & Documentation
### Autonomous Multi-Agent Workflow Engine

---

## 📁 Full File Structure

```
opsgrid/
│
├── main.py                              # ← ROOT ENTRY POINT (manual signal here)
├── requirements.txt
├── docker-compose.yml
├── .env.example
├── Dockerfile
│
├── core/                                # ← CONSTANT — engine logic
│   ├── __init__.py
│   ├── orchestrator.py                  # DAG workflow executor
│   ├── llm_router.py                    # Multi-LLM abstraction + cost tracking
│   ├── state_manager.py                 # PostgreSQL state + admin controls
│   ├── signal_collector.py              # Scheduled polling + webhook intake
│   └── exception_router.py             # Escalation routing logic
│
├── agents/                              # ← CONSTANT — agent implementations
│   ├── __init__.py
│   ├── base_agent.py                    # Abstract base + tool-calling loop
│   └── agents.py                        # All 6 agents (Research→Memory)
│
├── integrations/                        # ← CONSTANT (add new by extending)
│   ├── __init__.py
│   ├── connectors.py                    # HubSpot, Gmail, Slack, Stripe, Generic REST
│   └── tool_registry_builder.py         # Wires connectors → ToolRegistry for agents
│
├── workflows/
│   ├── dags/                            # ← MODIFY: one JSON per workflow
│   │   ├── saas_churn_prevention.json   # Fully implemented (SaaS demo)
│   │   ├── saas_pipeline_velocity.json
│   │   ├── cpg_distributor_health.json
│   │   └── ... (one per module)
│   │
│   └── prompts/                         # ← MODIFY: AI prompt templates
│       ├── saas/
│       │   ├── research_churn.txt
│       │   ├── reasoning_churn.txt      # ← Most important prompt
│       │   ├── drafting_churn.txt
│       │   ├── verification_churn.txt
│       │   ├── execution_churn.txt
│       │   └── memory_churn.txt
│       └── cpg/
│           └── ...
│
├── config/
│   ├── templates/                       # ← MODIFY for each new client
│   │   ├── saas.json                    # Client config (fully documented)
│   │   └── llm_config.json             # Which LLM handles which task
│   └── clients/                         # ← Per-client configs (gitignored)
│       └── acme_saas.json
│
├── api/                                 # ← CONSTANT — REST API
│   ├── __init__.py
│   └── main.py                          # All FastAPI endpoints
│
├── epi/                                 # ← CONSTANT — evidence & audit
│   ├── __init__.py
│   └── epi_manager.py                   # EPI recorder integration
│
├── admin/                               # ← CONSTANT — admin control panel
│   ├── __init__.py
│   └── control_panel.py                 # Rich terminal dashboard
│
├── db/
│   ├── init.sql                         # PostgreSQL schema
│   ├── migrations/                      # Alembic migrations (add as schema evolves)
│   └── seed/
│       ├── saas_seed.py                 # 120 synthetic SaaS accounts
│       └── data/                        # Generated JSON data files
│
├── frontend/
│   └── src/
│       └── App.jsx                      # Complete React dashboard (single file)
│
└── evidence/                            # ← EPI .epi artifacts (auto-created)
```

---

## ✅ CONSTANT vs MODIFY Guide

### 🔒 CONSTANT — Do NOT modify for new clients

| File | Why Constant |
|------|-------------|
| `core/orchestrator.py` | DAG engine logic — same for all workflows |
| `core/llm_router.py` | Multi-LLM abstraction — change config, not code |
| `core/state_manager.py` | Database schema and state machine |
| `agents/base_agent.py` | Base class interface |
| `agents/agents.py` | Agent logic — prompt templates are injected |
| `integrations/connectors.py` | Tool implementations |
| `api/main.py` | REST API endpoints |
| `epi/epi_manager.py` | Evidence capture |
| `admin/control_panel.py` | Admin dashboard |

### ✏️ MODIFY — Customize per client/industry

| File | What to Change |
|------|---------------|
| `config/templates/saas.json` | All `[MODIFY]` fields |
| `config/templates/llm_config.json` | Model assignments per task tier |
| `workflows/dags/saas_churn_prevention.json` | Nodes, edges, tools used |
| `workflows/prompts/saas/*.txt` | AI prompt wording, output schemas |

---

## 📋 JSON Format Specifications

### 1. Client Config (`config/templates/saas.json`)

**Required fields:**
```json
{
  "client_id": "uuid",
  "client_name": "Company Name",
  "industry": "saas | cpg | proserv | healthcare | realestate | ...",
  "active_workflows": ["workflow_dag_id_1", "workflow_dag_id_2"],
  "learning_mode": "observe | assist | autonomous",

  "company_profile": {
    "name": "Company Name",
    "description": "What the company does",
    "products": ["Product 1", "Product 2"],
    "target_customer": "Who they sell to",
    "key_metrics": ["MRR", "Churn Rate", "NPS"]
  },

  "business_rules": {
    "confidence_threshold": 0.75,
    "operating_hours": {
      "timezone": "America/New_York",
      "days": "Mon-Fri",
      "hours": "8am-6pm",
      "respect_hours_for_outreach": true
    }
  },

  "tone_profile": {
    "brand_voice": "Professional and warm",
    "formality": "medium | high | low",
    "avoid_phrases": ["synergy", "circle back"],
    "sign_off_name": "The Team Name"
  },

  "integrations": {
    "hubspot": {
      "enabled": true,
      "credential_id": "uuid-from-db"
    }
  },

  "escalation_contacts": [
    { "name": "Jane", "email": "jane@co.com", "role": "VP Sales" }
  ],

  "llm_overrides": {
    "reasoning_agent": null,
    "drafting_agent": "anthropic/claude-sonnet-4-20250514"
  },

  "action_library": {
    "action_key": "Human-readable description of what this action does"
  }
}
```

---

### 2. LLM Config (`config/templates/llm_config.json`)

**Model tiers:**
```json
{
  "task_models": {
    "heavy":    { "model": "anthropic/claude-sonnet-4-20250514" },
    "fast":     { "model": "groq/llama-3.1-70b-versatile" },
    "mini":     { "model": "anthropic/claude-haiku-4-5-20251001" },
    "balanced": { "model": "gemini/gemini-2.0-flash" }
  },
  "agent_defaults": {
    "research_agent":     { "tier": "fast" },
    "reasoning_agent":    { "tier": "heavy" },
    "drafting_agent":     { "tier": "heavy" },
    "verification_agent": { "tier": "mini" },
    "execution_agent":    { "tier": "mini" },
    "memory_agent":       { "tier": "mini" }
  }
}
```

**To use Gemini Flash instead of Groq for fast tasks:**
```json
"fast": { "model": "gemini/gemini-2.0-flash" }
```

**To use GPT-4o instead of Claude Sonnet for heavy tasks:**
```json
"heavy": { "model": "openai/gpt-4o" }
```

---

### 3. Workflow DAG (`workflows/dags/saas_churn_prevention.json`)

```json
{
  "_meta": { "workflow_id": "...", "name": "...", "industry": "..." },
  "nodes": [
    {
      "id": "research",
      "agent": "research_agent",
      "prompt_file": "saas/research_churn.txt",
      "tools": ["hubspot_read_contacts", "stripe_read_subscriptions"],
      "timeout_seconds": 120,
      "retry_on_failure": true
    }
  ],
  "edges": [
    { "from": "research", "to": "reasoning", "condition": null },
    { "from": "reasoning", "to": "drafting", "condition": "not output.escalate" },
    { "from": "reasoning", "to": "escalation", "condition": "output.escalate" }
  ]
}
```

---

### 4. Prompt Templates (`workflows/prompts/saas/reasoning_churn.txt`)

Prompts are plain text files with `{placeholder}` variables.

**Available variables (injected by agents):**
- `{tenant_name}` — Company name from config
- `{industry}` — Industry from config
- `{company_profile}` — JSON of company_profile
- `{business_rules}` — JSON of business_rules (churn weights, thresholds, etc.)
- `{tone_profile}` — JSON of tone_profile
- `{action_library}` — JSON of available actions
- `{confidence_threshold}` — Float from business_rules
- `{relevant_patterns}` — Historical patterns from memory store
- `{research_output}` — Output from previous research node
- `{current_datetime}` — ISO timestamp

---

## 🚀 Quick Start

```bash
# 1. Clone and setup
cp .env.example .env
# Fill in: ANTHROPIC_API_KEY (minimum required), others optional

# 2. Start infrastructure
docker-compose up -d   # PostgreSQL + Redis

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Generate demo data
python db/seed/saas_seed.py

# 5. Validate your config
python main.py check-config config/templates/saas.json

# 6. LIST available workflows
python main.py list-workflows

# 7. TRIGGER A WORKFLOW (manual signal)
python main.py trigger saas_churn_prevention

# 8. Start API server (for dashboard)
python main.py api

# 9. Start frontend
cd frontend && npm install && npm run dev
```

---

## ⚡ Manual Signal — How Work Starts

**There is no automatic trigger until you configure scheduled workflows.**

Work starts in ONE of these ways:

1. **CLI** (development/admin):
   ```bash
   python main.py trigger saas_churn_prevention
   python main.py trigger saas_churn_prevention --signal '{"priority":"high"}'
   ```

2. **API** (production):
   ```bash
   curl -X POST http://localhost:8000/api/v1/workflows/trigger \
     -H "Content-Type: application/json" \
     -d '{"tenant_id":"uuid","workflow_name":"saas_churn_prevention","signal_data":{}}'
   ```

3. **Dashboard**: Click "⚡ Trigger Workflow" in the React UI

4. **Webhook** (automated external trigger):
   ```bash
   POST /api/v1/webhooks/{tenant_id}   # Stripe/HubSpot webhooks auto-trigger
   ```

5. **Scheduled** (add cron to docker-compose or use n8n):
   ```bash
   # workflow DAG has "schedule_cron": "0 8 * * 1-5"
   ```

---

## 🧠 Agent Flow (Every Workflow)

```
MANUAL SIGNAL
    │
    ▼
RESEARCH AGENT      [fast model: Groq]     → Pulls all data via tools
    │
    ▼
REASONING AGENT     [heavy model: Sonnet]  → Scores, ranks, recommends
    │
    ├── confidence < threshold → ESCALATION → Human Queue
    │
    ▼
DRAFTING AGENT      [heavy model: Sonnet]  → Writes personalized comms
    │
    ▼
VERIFICATION AGENT  [mini model: Haiku]    → Checks rules, catches errors
    │
    ├── all failed → ESCALATION
    │
    ▼
EXECUTION AGENT     [mini model: Haiku]    → Fires tools (email, CRM, Slack)
    │
    ▼
MEMORY AGENT        [mini model: Haiku]    → Stores patterns for learning
```

---

## 💰 Cost Tracking

Every LLM call is tracked automatically. View in:
- **Terminal**: Live Rich dashboard shows per-agent token/cost table
- **Dashboard**: "Tokens & Cost" page in React UI
- **API**: `GET /api/v1/analytics/{tenant_id}`
- **EPI Artifact**: Each `.epi` file contains full token usage

Cost is accumulated **per workflow run** and **per session**. Reset between runs with `llm_router.reset_session()`.

---

## 🔒 EPI Evidence

Every workflow creates a `.epi` artifact in `./evidence/`:
```bash
epi view evidence/saas_churn_*.epi    # Open in browser
epi verify evidence/saas_churn_*.epi  # Check integrity
python main.py verify-evidence --open-viewer
```

The `.epi` file contains:
- Full execution timeline (every agent step)
- All LLM inputs/outputs
- Token usage per call
- Trust state: Signed | Unsigned | Tampered

---

## 🏢 Adding a New Client

1. Copy `config/templates/saas.json` → `config/clients/yourclient.json`
2. Replace all `[MODIFY]` placeholders
3. Set `active_workflows` to the workflow names in `workflows/dags/`
4. Store credentials via `POST /api/v1/integrations/credentials`
5. Register tenant: `POST /api/v1/tenants` with the config JSON
6. Test: `python main.py check-config config/clients/yourclient.json`
7. Run: `python main.py trigger saas_churn_prevention --config config/clients/yourclient.json`

---

## 🏭 Adding a New Industry Module

1. Create `workflows/dags/myindustry_workflow1.json`
2. Create `workflows/prompts/myindustry/` with `research_*.txt`, `reasoning_*.txt`, etc.
3. Add the workflow name to the client config's `active_workflows`
4. Create `db/seed/myindustry_seed.py` for demo data
5. No Python code changes needed — the engine reads the DAG JSON

---

## 🔧 Admin Controls

**Via CLI:**
```bash
# Pause a running workflow
curl -X POST http://localhost:8000/api/v1/workflows/{run_id}/pause

# Stop immediately
curl -X POST http://localhost:8000/api/v1/workflows/{run_id}/stop

# Resume paused
curl -X POST http://localhost:8000/api/v1/workflows/{run_id}/resume
```

**Via Dashboard**: Workflow Feed page has Pause/Stop/Resume buttons per run.

**Escalation decisions**: Escalation Queue page — context brief + recommended action + approve/override buttons.
