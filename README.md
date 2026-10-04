# ⚡ SMBFLOW

**Autonomous Multi-Agent Workflow Engine for Mid-Market Businesses**

SMBFlow runs entire business processes end-to-end — without a human at every step. It monitors signals, makes decisions, drafts communications, executes actions across your tools, and learns from every outcome. One platform, any industry, configured entirely through JSON — no new code per client.

---

## Table of Contents

1. [What SMBFlow Does](#1-what-opsgrid-does)
2. [How It Works](#2-how-it-works)
3. [Architecture Overview](#3-architecture-overview)
4. [Project Structure](#4-project-structure)
5. [Prerequisites](#5-prerequisites)
6. [Installation &amp; Setup](#6-installation--setup)
7. [Configuration Guide](#7-configuration-guide)
8. [Running Your First Workflow](#8-running-your-first-workflow)
9. [Admin Control Panel](#9-admin-control-panel)
10. [Multi-LLM Setup](#10-multi-llm-setup)
11. [Token &amp; Cost Tracking](#11-token--cost-tracking)
12. [EPI Evidence &amp; Audit Trail](#12-epi-evidence--audit-trail)
13. [API Reference](#13-api-reference)
14. [React Dashboard](#14-react-dashboard)
15. [Adding a New Client](#15-adding-a-new-client)
16. [Adding a New Industry Module](#16-adding-a-new-industry-module)
17. [Integrations Reference](#17-integrations-reference)
18. [JSON Schema Reference](#18-json-schema-reference)
19. [Troubleshooting](#19-troubleshooting)
20. [Environment Variables](#20-environment-variables)

---

## 1. What SMBFlow Does

Most business automation tools do one thing: if X happens, do Y. SMBFlow does something fundamentally different — it handles the full decision-making loop:

```
Monitor data  →  Understand situation  →  Draft response  →  Execute action  →  Learn from outcome
```

A concrete example for a B2B SaaS company:

> Every morning at 8 AM, SMBFlow pulls usage data, NPS scores, and support ticket volume for all 120 customers. It scores each account for churn risk using your weighted model. For the 8 accounts it flags as critical, it drafts a personalised CSM outreach email for each one — referencing their specific usage drop and renewal date. It checks each draft against your business rules (no duplicates, correct tone, factual accuracy). It queues the approved emails for one-click send, creates HubSpot tasks for the CSM team, and posts a risk digest to #cs-alerts in Slack. It logs what it did. Next week, it checks whether the accounts that got outreach recovered — and gets smarter.

That entire process — from pulling data to Slack alert — runs in under 5 minutes, automatically, with a full tamper-evident audit trail.

---

## 2. How It Works

### The Agent Chain

Every workflow runs through the same 6-agent pipeline. The agents share context — each one passes its output forward to the next:

```
RESEARCH AGENT
  └─ Pulls all relevant data from connected tools (HubSpot, Stripe, product DB, etc.)
  └─ Returns: structured data object

REASONING AGENT
  └─ Applies your business rules to the data
  └─ Scores, ranks, and recommends actions with confidence scores
  └─ Returns: ranked action list + escalation flag

DRAFTING AGENT
  └─ Writes personalised communications in your brand voice
  └─ Reads communication history to avoid duplicates
  └─ Returns: email drafts + executive briefs

VERIFICATION AGENT
  └─ Checks every draft against your rules (tone, facts, duplicates, compliance)
  └─ Returns: approved drafts + rejection reasons

EXECUTION AGENT
  └─ Fires approved actions: sends emails, creates CRM tasks, posts to Slack
  └─ Returns: confirmation of every action taken

MEMORY AGENT
  └─ Extracts patterns from this run and updates the memory store
  └─ This is what makes SMBFlow improve over time
```

If confidence drops below your threshold at any step, the workflow pauses and sends the context to your human review queue — with a pre-written brief and recommended action ready.

### What Makes It Configurable

The engine code is identical across every client and industry. What changes is:

- **Client config JSON** — your company profile, business rules, tone, integrations
- **Workflow DAG JSON** — the sequence of agents and tools for each process
- **Prompt template files** — the AI instructions specific to your workflow

New client = new JSON config file. New industry = new DAG + prompt folder. Zero Python changes.

---

## 3. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         MANUAL SIGNAL                           │
│          CLI / API / Dashboard / Webhook / Schedule             │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    WORKFLOW ORCHESTRATOR                        │
│   Reads DAG JSON → Spawns agents → Passes context forward       │
│   Handles: escalation routing, admin pause/stop, EPI recording  │
└──────┬──────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────┐
│                        AGENT LIBRARY                            │
│  Research → Reasoning → Drafting → Verification → Execution     │
│                        → Memory                                 │
│  All agents share: LLM Router, Tool Registry, State Manager     │
└──────┬──────────────────────────────────────────────────────────┘
       │
       ├──── LLM ROUTER ─────────────────────────────────────────┐
       │     LiteLLM → Anthropic / OpenAI / Gemini / Groq        │
       │     Per-task tier assignment, fallback chains            │
       │     Real-time token + cost tracking                     │
       └─────────────────────────────────────────────────────────┘
       │
       ├──── INTEGRATION HUB ────────────────────────────────────┐
       │     HubSpot · Gmail · Slack · Stripe · Generic REST      │
       │     Every connector: authenticate / read / write         │
       └─────────────────────────────────────────────────────────┘
       │
       ├──── STATE MANAGER ──────────────────────────────────────┐
       │     PostgreSQL · Workflow instances · Agent runs         │
       │     Pattern memory · Escalation queue · Admin controls   │
       └─────────────────────────────────────────────────────────┘
       │
       └──── EPI RECORDER ───────────────────────────────────────┐
             Tamper-evident .epi artifact per workflow run        │
             Every LLM call captured via LiteLLM callback        │
             Verify with: epi verify evidence/filename.epi        │
             └─────────────────────────────────────────────────────┘
```

### Technology Stack

| Layer                | Technology                  | Purpose                                          |
| -------------------- | --------------------------- | ------------------------------------------------ |
| Workflow Engine      | Python + LangGraph concepts | DAG execution and state routing                  |
| Multi-LLM            | LiteLLM                     | Abstraction over Anthropic, OpenAI, Gemini, Groq |
| API                  | FastAPI + Pydantic          | REST API with full type safety                   |
| Database             | PostgreSQL + SQLAlchemy     | Workflow state, patterns, credentials            |
| Cache                | Redis                       | Hot data caching                                 |
| Evidence             | EPI Recorder (≥ v2.8.6)    | Tamper-evident audit trails                      |
| Dashboard (Terminal) | Rich + Click                | Live admin control panel                         |
| Dashboard (Web)      | React 18 + Tailwind         | Full workflow monitoring UI                      |
| Containerisation     | Docker + Docker Compose     | One-command infrastructure                       |

---

## 4. Project Structure

```
SMBFlow/
│
├── main.py                          ← ROOT ENTRY POINT — start here
├── requirements.txt
├── docker-compose.yml
├── Dockerfile
├── .env.example                     ← Copy to .env and fill in
│
├── core/                            ← ENGINE (CONSTANT — don't modify)
│   ├── orchestrator.py              ← DAG executor, escalation routing
│   ├── llm_router.py                ← Multi-LLM with cost tracking
│   └── state_manager.py             ← PostgreSQL ORM + admin controls
│
├── agents/                          ← AGENTS (CONSTANT)
│   ├── base_agent.py                ← Base class, tool-call loop, JSON parser
│   └── agents.py                    ← All 6 agents
│
├── integrations/                    ← CONNECTORS (CONSTANT + extensible)
│   ├── connectors.py                ← HubSpot, Gmail, Slack, Stripe, Generic REST
│   └── tool_registry_builder.py     ← Wires connectors → tools for agents
│
├── api/
│   └── main.py                      ← All FastAPI endpoints
│
├── epi/
│   └── epi_manager.py               ← EPI Recorder integration
│
├── admin/
│   └── control_panel.py             ← Rich terminal dashboard + CLI
│
├── workflows/
│   ├── dags/                        ← MODIFY: one JSON file per workflow
│   │   └── saas_churn_prevention.json
│   └── prompts/                     ← MODIFY: AI prompt templates
│       └── saas/
│           ├── research_churn.txt
│           ├── reasoning_churn.txt  ← Most important — tune this first
│           ├── drafting_churn.txt
│           ├── verification_churn.txt
│           ├── execution_churn.txt
│           └── memory_churn.txt
│
├── config/
│   ├── templates/                   ← MODIFY: per-client configuration
│   │   ├── saas.json                ← Full SaaS client config (demo-ready)
│   │   └── llm_config.json          ← Model assignments and cost rates
│   └── clients/                     ← GITIGNORED: your actual client configs
│
├── db/
│   ├── init.sql                     ← Full PostgreSQL schema
│   └── seed/
│       └── saas_seed.py             ← Generates 120 synthetic SaaS accounts
│
├── frontend/
│   └── src/
│       └── App.jsx                  ← Complete React dashboard (single file)
│
└── evidence/                        ← Auto-created: .epi audit files
```

### The CONSTANT vs MODIFY Principle

This distinction is the key to SMBFlow's multi-tenant model:

**CONSTANT** — the engine, agents, connectors, API, admin panel. Identical for every client. You never touch these for business customisation.

**MODIFY** — the config JSON files and prompt templates. A new client is a new config file. A new industry is a new DAG and prompt folder. All business logic lives in JSON and `.txt` files, not Python.

---

## 5. Prerequisites

### Required

| Tool           | Minimum Version | Install                           |
| -------------- | --------------- | --------------------------------- |
| Python         | 3.11+           | [python.org](https://python.org)   |
| Docker Desktop | Latest          | [docker.com](https://docker.com)   |
| Node.js        | 18+             | [nodejs.org](https://nodejs.org)   |
| Git            | Any             | [git-scm.com](https://git-scm.com) |

### API Keys (at least one LLM required)

| Provider  | Key Name              | Where to Get                                          | Used For                           |
| --------- | --------------------- | ----------------------------------------------------- | ---------------------------------- |
| Anthropic | `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) | Reasoning + Drafting (heavy tasks) |
| Groq      | `GROQ_API_KEY`      | [console.groq.com](https://console.groq.com)           | Research + fast tasks (very cheap) |
| OpenAI    | `OPENAI_API_KEY`    | [platform.openai.com](https://platform.openai.com)     | Alternative heavy model            |
| Google    | `GOOGLE_API_KEY`    | [aistudio.google.com](https://aistudio.google.com)     | Gemini Flash (balanced tier)       |

> **Minimum to get started:** just `ANTHROPIC_API_KEY`. The system will use Claude for all tasks. Add other providers to unlock model routing.

---

## 6. Installation & Setup

We have provided automated scripts for local development setup.

### Step 1 — One-Time Setup

Run the setup script from the project root (or **drag & drop `setup.ps1`** into your PowerShell terminal window):

```powershell
.\setup.ps1
# Or if execution policy is restricted:
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

This will automatically:

- Verify prerequisites (Python, Node, Docker)
- Create and activate a Python virtual environment
- Ensure `.env` is created and safely generate a `VAULT_ENCRYPTION_KEY`
- Start PostgreSQL (port 5434) and Redis (port 6379) via Docker Compose
- Install backend and frontend dependencies
- Generate local JSON seed data

### Step 2 — Daily Startup

To start the application, run (or **drag & drop `start.ps1`** into your PowerShell terminal window):

```powershell
.\start.ps1
```

This will launch the backend API and the Vite frontend in separate windows.

### Step 3 — Access the Application & API Testing URLs

- **Frontend Dashboard:** [http://localhost:5173](http://localhost:5173)
- **API Base Endpoint:** [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **Interactive API Testing Docs (Swagger UI):** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **API Health Check Endpoint:** [http://127.0.0.1:8000/api/v1/health](http://127.0.0.1:8000/api/v1/health)
- **API ReDoc Documentation:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **OpenAPI JSON Schema:** [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json)

**Test Logins:**

- *SMB Owner (Business User):* `demo@tenant.com` / `demo123`
- *SMBFlow Admin (Super Admin):* `admin@smbflow.com` / `admin123`

### Step 4 — Shutdown

When you are done developing, shut everything down safely:

```powershell
.\stop.ps1
```

This will gracefully stop the local backend/frontend processes and run `docker-compose stop` to pause the infrastructure without losing your database state.

---

## 7. Configuration Guide

SMBFlow is configured entirely through two JSON files per client. No Python code changes.

### 7.1 Client Config (`config/templates/saas.json`)

This is the most important file. It defines everything about a specific client:

```json
{
  "client_id": "uuid",
  "client_name": "TechFlow SaaS Inc.",
  "industry": "saas",

  "active_workflows": [
    "saas_churn_prevention",
    "saas_pipeline_velocity"
  ],

  "company_profile": {
    "name": "TechFlow SaaS Inc.",
    "description": "B2B project management SaaS for SMBs",
    "products": ["Project Management Platform"],
    "target_customer": "SMB and mid-market operations teams",
    "avg_contract_value": "$15,000/yr"
  },

  "business_rules": {
    "confidence_threshold": 0.75,
    "churn_risk": {
      "usage_drop_weight": 0.40,
      "support_spike_weight": 0.25,
      "nps_weight": 0.20,
      "engagement_recency_weight": 0.15,
      "critical_score_threshold": 70,
      "at_risk_score_threshold": 45,
      "usage_drop_days_to_flag": 14
    },
    "operating_hours": {
      "timezone": "America/New_York",
      "days": "Mon-Fri",
      "hours": "8am-6pm",
      "respect_hours_for_outreach": true
    }
  },

  "tone_profile": {
    "brand_voice": "Professional, empathetic, data-driven",
    "formality": "medium",
    "avoid_phrases": ["synergy", "circle back"],
    "sign_off_name": "The TechFlow Customer Success Team"
  },

  "integrations": {
    "hubspot": {
      "enabled": true,
      "credential_id": "stored-in-db"
    },
    "gmail": {
      "enabled": true,
      "credential_id": "stored-in-db",
      "sender_alias": "cs@yourcompany.com",
      "queue_for_approval": true
    },
    "slack": {
      "enabled": true,
      "credential_id": "stored-in-db",
      "cs_alerts_channel": "#cs-alerts"
    }
  },

  "escalation_contacts": [
    {
      "name": "Jane Smith",
      "email": "jane@company.com",
      "role": "VP Customer Success",
      "escalation_types": ["critical_churn"]
    }
  ],

  "llm_overrides": {
    "reasoning_agent": null,
    "drafting_agent": "anthropic/claude-sonnet-4-20250514"
  },

  "action_library": {
    "send_csm_outreach_email": "Draft and queue a CSM check-in email",
    "create_hubspot_task": "Create task in HubSpot for account owner",
    "post_slack_alert": "Post risk alert to CS Slack channel"
  }
}
```

**Fields marked `[MODIFY]` in the template** must be updated for each real client. Fields not marked are safe defaults.

### 7.2 LLM Config (`config/templates/llm_config.json`)

Controls which model handles which type of task:

```json
{
  "task_models": {
    "heavy":    { "model": "anthropic/claude-sonnet-4-20250514" },
    "fast":     { "model": "groq/llama-3.1-70b-versatile" },
    "mini":     { "model": "anthropic/claude-haiku-4-5-20251001" },
    "balanced": { "model": "gemini/gemini-2.0-flash" }
  },
  "agent_defaults": {
    "research_agent":     { "tier": "fast"  },
    "reasoning_agent":    { "tier": "heavy" },
    "drafting_agent":     { "tier": "heavy" },
    "verification_agent": { "tier": "mini"  },
    "execution_agent":    { "tier": "mini"  },
    "memory_agent":       { "tier": "mini"  }
  }
}
```

To switch a model, change the `"model"` string in `task_models`. The value must be a valid [LiteLLM model string](https://docs.litellm.ai/docs/providers) in `provider/model-name` format.

### 7.3 Prompt Templates (`workflows/prompts/saas/`)

Prompts are plain `.txt` files with `{placeholder}` variables. The variables are injected by the agents at runtime from the client config. You never hardcode company names or business rules into prompts — they come from the JSON.

Available placeholders in every prompt:

| Placeholder                | Source                                  |
| -------------------------- | --------------------------------------- |
| `{tenant_name}`          | `client_name` from config             |
| `{industry}`             | `industry` from config                |
| `{company_profile}`      | `company_profile` block as JSON       |
| `{business_rules}`       | `business_rules` block as JSON        |
| `{tone_profile}`         | `tone_profile` block as JSON          |
| `{action_library}`       | `action_library` block as JSON        |
| `{confidence_threshold}` | `business_rules.confidence_threshold` |
| `{relevant_patterns}`    | Historical patterns from memory store   |
| `{research_output}`      | Output from the Research Agent          |
| `{current_datetime}`     | UTC timestamp at time of execution      |

---

## 8. Running Your First Workflow

### The Manual Signal

SMBFlow does not start automatically. Work begins when you explicitly trigger it. This is intentional — you control when it runs.

```bash
# Basic trigger — uses default config
python main.py trigger saas_churn_prevention

# With specific client config
python main.py trigger saas_churn_prevention --config config/templates/saas.json

# With custom trigger signal (passed to all agents as context)
python main.py trigger saas_churn_prevention \
  --signal '{"type":"manual","priority":"high","triggered_by":"weekly_review"}'

# Dry run — validates without executing
python main.py trigger saas_churn_prevention --dry-run
```

### What Happens When You Trigger

1. The CLI loads your client config JSON
2. It loads `workflows/dags/saas_churn_prevention.json` — the DAG definition
3. The orchestrator starts executing nodes in order
4. A live Rich terminal dashboard appears showing:
   - Current node executing
   - Per-agent token usage (live-updating)
   - Running cost in USD
   - Any escalations triggered
5. When complete, a session summary prints with total tokens, total cost, and EPI artifact path

### Triggering via the API

```bash
# First register your tenant
curl -X POST http://localhost:8000/api/v1/tenants \
  -H "Content-Type: application/json" \
  -d @config/templates/saas.json

# Then trigger a workflow (use the tenant_id from the response above)
curl -X POST http://localhost:8000/api/v1/workflows/trigger \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "your-tenant-uuid",
    "workflow_name": "saas_churn_prevention",
    "signal_data": {"type": "manual", "source": "api"}
  }'
```

### Triggering via the Dashboard

1. Open `http://localhost:5173`
2. Click **⚡ Trigger Workflow**
3. Select tenant, workflow, and enter signal JSON
4. Click **Start Workflow**
5. Watch status update in real-time on the Workflows page

### Checking Results

```bash
# Via API
curl http://localhost:8000/api/v1/workflows/{run_id}/status

# View the EPI evidence artifact
python main.py verify-evidence --open-viewer

# Via terminal dashboard
python main.py dashboard
```

---

## 9. Admin Control Panel

The terminal dashboard gives you live visibility and control during execution.

### Starting the Dashboard

```bash
python main.py dashboard
```

### What You See

```
⚡ SMBFlow  ● LIVE    2026-03-24 08:14:22    Session Cost: $0.0043
┌──────────────────────────────────────────────────────────────────┐
│ Active Workflows                                                  │
│ Run ID   │ Workflow                │ Status  │ Node       │ Cost  │
│ a3f8b1   │ saas_churn_prevention   │ ● run   │ reasoning  │$0.003 │
│ 9c2d44   │ saas_pipeline_velocity  │ ● run   │ drafting   │$0.001 │
├──────────────────────────────────────────────────────────────────┤
│ ⚡ LLM Token Usage & Cost (Live)                                  │
│ Agent         │ Model           │ Calls │ In      │ Out  │ Cost  │
│ research      │ groq/llama-70b  │  3    │ 2,840   │ 512  │$0.001 │
│ reasoning     │ claude-sonnet   │  1    │ 4,200   │ 890  │$0.022 │
│ drafting      │ claude-sonnet   │  1    │ 3,100   │ 1200 │$0.019 │
│ TOTAL         │                 │  5    │ 10,140  │ 2602 │$0.042 │
└──────────────────────────────────────────────────────────────────┘
[T] Trigger  [P] Pause  [R] Resume  [S] Stop  [E] Evidence  [Q] Quit
```

### Admin Controls

**Pause a workflow** — stops at the next node boundary, preserving all accumulated context. The workflow can be resumed exactly where it left off.

```bash
# Via API
curl -X POST http://localhost:8000/api/v1/workflows/{run_id}/pause

# Via dashboard: press [P] then enter the run ID
```

**Stop a workflow** — immediately terminates execution. Status set to `stopped`. Cannot be resumed.

```bash
curl -X POST http://localhost:8000/api/v1/workflows/{run_id}/stop
```

**Resume a paused workflow**

```bash
curl -X POST http://localhost:8000/api/v1/workflows/{run_id}/resume
```

### Handling Escalations

When an agent's confidence drops below your threshold, the workflow pauses and creates an escalation. You'll see a `🔔` in the dashboard and a notification in the configured Slack channel.

To resolve an escalation:

```bash
# Via API
curl -X POST http://localhost:8000/api/v1/escalations/{escalation_id}/decide \
  -H "Content-Type: application/json" \
  -d '{
    "decision": {"notes": "Reviewed — proceed with outreach"},
    "action_chosen": "send_csm_outreach_email",
    "decided_by": "Jane Smith"
  }'
```

Or use the **Escalation Queue** page in the React dashboard — it shows the full context brief, the agent's recommended action, and approve/override buttons.

---

## 10. Multi-LLM Setup

SMBFlow uses [LiteLLM](https://docs.litellm.ai) as its LLM abstraction layer. This means you can use any provider with the same interface.

### Model Tiers

| Tier         | Default Model      | Best Used For                           | Approx Cost/1M tokens |
| ------------ | ------------------ | --------------------------------------- | --------------------- |
| `heavy`    | Claude Sonnet 4    | Reasoning, drafting (quality critical)  | $3 in / $15 out       |
| `fast`     | Groq Llama-3.1-70B | Research, tool calls (speed critical)   | $0.59 in / $0.79 out  |
| `mini`     | Claude Haiku 4.5   | Verification, execution (deterministic) | $0.80 in / $4.00 out  |
| `balanced` | Gemini 2.0 Flash   | Orchestration decisions                 | $0.075 in / $0.30 out |

### Switching Models

Edit `config/templates/llm_config.json`:

```json
"task_models": {
  "heavy":    { "model": "openai/gpt-4o" },
  "fast":     { "model": "gemini/gemini-2.0-flash" },
  "mini":     { "model": "openai/gpt-4o-mini" },
  "balanced": { "model": "groq/llama-3.1-70b-versatile" }
}
```

### Per-Client Model Overrides

In a client config JSON:

```json
"llm_overrides": {
  "reasoning_agent": "anthropic/claude-sonnet-4-20250514",
  "drafting_agent":  "openai/gpt-4o",
  "research_agent":  null
}
```

`null` means use the system default from `llm_config.json`.

### Supported Providers (LiteLLM model string format)

| Provider       | Model String Example                    |
| -------------- | --------------------------------------- |
| Anthropic      | `anthropic/claude-sonnet-4-20250514`  |
| Anthropic      | `anthropic/claude-haiku-4-5-20251001` |
| OpenAI         | `openai/gpt-4o`                       |
| OpenAI         | `openai/gpt-4o-mini`                  |
| Google         | `gemini/gemini-2.0-flash`             |
| Google         | `gemini/gemini-2.0-pro`               |
| Groq           | `groq/llama-3.1-70b-versatile`        |
| Groq           | `groq/llama-3.1-8b-instant`           |
| Groq           | `groq/mixtral-8x7b-32768`             |
| Ollama (local) | `ollama/llama3.2`                     |

For Ollama, also set `OPENAI_API_BASE=http://localhost:11434/v1` in your `.env`.

### Fallback Chains

If a model fails (rate limit, timeout, API error), SMBFlow automatically tries the next model in the fallback chain. Configure in `llm_config.json`:

```json
"fallback_chain": {
  "heavy": ["anthropic/claude-sonnet-4-20250514", "openai/gpt-4o", "gemini/gemini-2.0-pro"],
  "fast":  ["groq/llama-3.1-70b-versatile", "groq/mixtral-8x7b-32768", "anthropic/claude-haiku-4-5-20251001"]
}
```

---

## 11. Token & Cost Tracking

Every single LLM call is tracked automatically. You always know exactly what was sent, what was received, and what it cost.

### What Is Tracked Per Call

- Agent name
- Model used
- Tokens sent (input)
- Tokens received (output)
- Cost in USD (calculated from `cost_rates` in `llm_config.json`)
- Duration in milliseconds
- Success / failure

### Where to See It

**1. Terminal (live during execution)**

The dashboard table updates in real-time as each agent runs.

**2. Session summary (after completion)**

```
╔══════════════════════════════════════════════╗
║ ✓ Workflow Complete: saas_churn_prevention    ║
║                                              ║
║ Total Tokens In:   14,820                    ║
║ Total Tokens Out:   3,540                    ║
║ Total Cost:        $0.0842                   ║
║ Total LLM Calls:   8                         ║
╚══════════════════════════════════════════════╝
```

**3. React Dashboard → Tokens & Cost page**

Full table broken down by workflow, plus cost-per-run average.

**4. EPI Evidence Artifact**

Every `.epi` file contains the complete token log for that workflow run. Immutable and cryptographically signed.

**5. API**

```bash
curl http://localhost:8000/api/v1/analytics/{tenant_id}
# Returns: total_cost_usd, total_tokens, breakdown by workflow
```

### Updating Cost Rates

When providers change their pricing, update `cost_rates` in `config/templates/llm_config.json`:

```json
"cost_rates": {
  "anthropic/claude-sonnet-4-20250514": { "input": 3.00, "output": 15.00 },
  "groq/llama-3.1-70b-versatile":       { "input": 0.59, "output": 0.79  }
}
```

All values are per million tokens in USD.

---

## 12. EPI Evidence & Audit Trail

SMBFlow uses [EPI Recorder](https://github.com/mohdibrahimaiml/epi-recorder) (v2.8.6+) to create a tamper-evident `.epi` artifact for every workflow run. This gives you an immutable, cryptographically signed audit trail of every decision made.

### What Each `.epi` File Contains

- Complete execution timeline (every agent step in order)
- All LLM inputs and outputs
- Token usage per call
- Confidence scores at each decision point
- Tool calls and results
- Any escalation events
- Trust state: **Signed** | **Unsigned** | **Tampered**

### Viewing Evidence

```bash
# List all artifacts
python main.py verify-evidence

# Open the latest artifact in browser (no login required, fully offline)
python main.py verify-evidence --open-viewer

# Direct EPI commands
epi view evidence/saas_churn_prevention_abc123_20260324.epi
epi verify evidence/saas_churn_prevention_abc123_20260324.epi
```

The browser viewer opens the timeline, shows each agent's reasoning, and displays the trust badge.

### Evidence in the Dashboard

The **Evidence** page in the React dashboard lists all `.epi` files with their trust state. Click any row to open the offline viewer.

### How EPI Is Integrated

EPI captures data at two levels:

1. **LiteLLM callback** (`EPICallback`) — automatically records every LLM call (model, tokens, cost, response) without any manual instrumentation
2. **Workflow context manager** (`record()` + `agent_run()`) — records the structured workflow timeline including agent decisions, tool calls, and confidence scores

You do not need to add any EPI code to your agents or prompts. It's all handled in `epi/epi_manager.py`.

---

## 13. API Reference

Start the API server:

```bash
python main.py api
# Or: uvicorn api.main:app --reload
# Docs at: http://localhost:8000/docs
```

### Endpoints

#### System

| Method  | Endpoint           | Description                                    |
| ------- | ------------------ | ---------------------------------------------- |
| `GET` | `/api/v1/health` | System health — DB, Redis, LLM providers, EPI |

#### Tenants

| Method   | Endpoint                           | Description                                     |
| -------- | ---------------------------------- | ----------------------------------------------- |
| `GET`  | `/api/v1/tenants`                | List all tenants                                |
| `POST` | `/api/v1/tenants`                | Create tenant — body is the client config JSON |
| `GET`  | `/api/v1/tenants/{id}`           | Get tenant including full config                |
| `PUT`  | `/api/v1/tenants/{id}/config`    | Update tenant config                            |
| `GET`  | `/api/v1/tenants/{id}/workflows` | List workflow runs for a tenant                 |

#### Workflows

| Method   | Endpoint                              | Description                           |
| -------- | ------------------------------------- | ------------------------------------- |
| `POST` | `/api/v1/workflows/trigger`         | Manually trigger a workflow           |
| `GET`  | `/api/v1/workflows/{run_id}/status` | Get full workflow status + agent runs |
| `POST` | `/api/v1/workflows/{run_id}/pause`  | Pause at next node boundary           |
| `POST` | `/api/v1/workflows/{run_id}/stop`   | Immediately stop                      |
| `POST` | `/api/v1/workflows/{run_id}/resume` | Resume from pause                     |

#### Escalations

| Method   | Endpoint                            | Description                               |
| -------- | ----------------------------------- | ----------------------------------------- |
| `GET`  | `/api/v1/escalations`             | List pending escalations                  |
| `POST` | `/api/v1/escalations/{id}/decide` | Submit human decision — resumes workflow |

#### Analytics

| Method  | Endpoint                          | Description                      |
| ------- | --------------------------------- | -------------------------------- |
| `GET` | `/api/v1/analytics/{tenant_id}` | Performance metrics for a tenant |

#### Webhooks

| Method   | Endpoint                         | Description                                          |
| -------- | -------------------------------- | ---------------------------------------------------- |
| `POST` | `/api/v1/webhooks/{tenant_id}` | Receive inbound webhook — may auto-trigger workflow |

#### Evidence

| Method  | Endpoint             | Description                     |
| ------- | -------------------- | ------------------------------- |
| `GET` | `/api/v1/evidence` | List all`.epi` artifact files |

---

## 14. React Dashboard

```bash
cd frontend
npm install
npm run dev
# http://localhost:5173
```

### Pages

| Page                    | What It Shows                                                       |
| ----------------------- | ------------------------------------------------------------------- |
| **Dashboard**     | Live workflow feed, system status, stats, one-click trigger         |
| **Workflows**     | All runs with status, current node, cost, pause/stop/resume buttons |
| **Escalations**   | Human review queue with context brief and decision form             |
| **Tokens & Cost** | Breakdown by workflow — runs, tokens in/out, cost, cost-per-run    |
| **Evidence**      | List of`.epi` artifacts with trust state                          |

The dashboard polls the API every 3 seconds. All data is fetched from `http://localhost:8000/api/v1`.

To point the dashboard at a different API host, change `API_BASE` at the top of `frontend/src/App.jsx`.

---

## 15. Adding a New Client

A new client requires only JSON configuration — no Python code.

**Step 1** — Copy the template

```bash
cp config/templates/saas.json config/clients/acme_saas.json
```

**Step 2** — Edit the config

Replace every `[MODIFY]` placeholder with real values. The `check-config` command will tell you what's missing:

```bash
python main.py check-config config/clients/acme_saas.json
```

**Step 3** — Store credentials

Credentials (API keys, OAuth tokens) are stored in the database and referenced by UUID in the config. Add them:

```bash
curl -X POST http://localhost:8000/api/v1/integrations/credentials \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "your-tenant-uuid",
    "tool_name": "hubspot",
    "credentials": { "api_key": "your-hubspot-key" }
  }'
```

Update the `credential_id` in your client config with the returned UUID.

**Step 4** — Register the tenant

```bash
curl -X POST http://localhost:8000/api/v1/tenants \
  -H "Content-Type: application/json" \
  -d @config/clients/acme_saas.json
```

**Step 5** — Run a workflow

```bash
python main.py trigger saas_churn_prevention \
  --config config/clients/acme_saas.json
```

---

## 16. Adding a New Industry Module

A new industry module requires one new DAG JSON file and one new prompt folder. No Python changes.

**Step 1** — Create the workflow DAG

```bash
cp workflows/dags/saas_churn_prevention.json workflows/dags/legal_matter_intake.json
```

Edit the DAG:

- Set `_meta.workflow_id`, `_meta.industry`, `_meta.name`
- Update `nodes[*].prompt_file` to point to your new prompt folder
- Update `nodes[*].tools` to list the integration tools needed
- Set edge conditions appropriate for your workflow logic

**Step 2** — Create the prompt folder

```bash
mkdir -p workflows/prompts/legal
```

Create one `.txt` file per agent node. At minimum:

- `research_intake.txt`
- `reasoning_intake.txt`
- `drafting_intake.txt`

Use `{tenant_name}`, `{business_rules}`, `{research_output}` and other standard placeholders. The agent injects these automatically.

**Step 3** — Create a seed data generator

```bash
cp db/seed/saas_seed.py db/seed/legal_seed.py
# Edit to generate realistic legal matter data
python db/seed/legal_seed.py
```

**Step 4** — Add workflow to client config

In `config/templates/legal.json`:

```json
"active_workflows": ["legal_matter_intake", "legal_deadline_enforcement"]
```

**Step 5** — Run it

```bash
python main.py trigger legal_matter_intake --config config/clients/mylaw.json
```

---

## 17. Integrations Reference

All connectors are in `integrations/connectors.py`. They are wired to agent tools in `integrations/tool_registry_builder.py`.

### Available Connectors

| Connector    | Class                    | Auth Method      | Available Tools                                                                                                                        |
| ------------ | ------------------------ | ---------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| HubSpot CRM  | `HubSpotConnector`     | API Key / OAuth2 | `hubspot_read_contacts`, `hubspot_read_deals`, `hubspot_create_task`, `hubspot_update_property`, `hubspot_read_activity_log` |
| Gmail        | `GmailConnector`       | OAuth2           | `gmail_queue_email`, `gmail_read_recent_threads`                                                                                   |
| Slack        | `SlackConnector`       | Bot Token        | `slack_post_message`, `slack_post_risk_alert`                                                                                      |
| Stripe       | `StripeConnector`      | Secret Key       | `stripe_read_subscriptions`, `stripe_read_customers`                                                                               |
| Generic REST | `GenericRESTConnector` | API Key          | Configurable per endpoint                                                                                                              |
| Database     | (built-in)               | Internal         | `db_write_outcome`, `db_update_pattern`                                                                                            |

### Adding a New Connector

1. Extend `BaseConnector` in `integrations/connectors.py`:

```python
class MyToolConnector(BaseConnector):
    async def authenticate(self) -> bool: ...
    async def read(self, resource: str, filters: dict = None) -> list[dict]: ...
    async def write(self, resource: str, data: dict) -> dict: ...
    async def health_check(self) -> bool: ...
```

2. Register tools in `integrations/tool_registry_builder.py` inside `build_registry()`:

```python
if integrations.get("mytool", {}).get("enabled") and "mytool" in credentials:
    my_conn = MyToolConnector(credentials["mytool"], integrations["mytool"])
    _register_mytool_tools(registry, my_conn)
```

3. Add the tool to the DAG node's `"tools"` list in the workflow JSON.
4. Enable it in the client config:

```json
"integrations": {
  "mytool": {
    "enabled": true,
    "credential_id": "stored-uuid"
  }
}
```

---

## 18. JSON Schema Reference

### Workflow DAG (`workflows/dags/*.json`)

```json
{
  "_meta": {
    "workflow_id": "unique_snake_case_id",
    "name": "Human-readable name",
    "industry": "saas | cpg | proserv | ...",
    "version": "1.0.0",
    "description": "What this workflow does",
    "trigger_types": ["scheduled", "manual", "webhook"],
    "schedule_cron": "0 8 * * 1-5",
    "estimated_duration_minutes": 5
  },

  "nodes": [
    {
      "id": "research",
      "agent": "research_agent | reasoning_agent | drafting_agent | verification_agent | execution_agent | memory_agent",
      "name": "Display name",
      "description": "What this node does",
      "prompt_file": "saas/research_churn.txt",
      "tools": ["hubspot_read_contacts", "stripe_read_subscriptions"],
      "timeout_seconds": 120,
      "retry_on_failure": true,
      "max_retries": 2
    }
  ],

  "edges": [
    {
      "from": "source_node_id",
      "to": "target_node_id",
      "condition": null
    },
    {
      "from": "reasoning",
      "to": "drafting",
      "condition": "not output.escalate"
    },
    {
      "from": "reasoning",
      "to": "escalation",
      "condition": "output.escalate"
    }
  ],

  "escalation_config": {
    "notify_channel": "slack",
    "notify_email": true,
    "sla_hours": 4,
    "resume_after_decision": true
  }
}
```

### Reasoning Agent Output (expected JSON from your prompt)

Your reasoning prompt must return this exact structure:

```json
{
  "situation_summary": "2-3 sentence summary",
  "urgency": "critical | high | medium | low",
  "reasoning_confidence": 0.85,
  "recommended_actions": [
    {
      "action_id": "send_csm_outreach_email",
      "confidence": 0.91,
      "reasoning": "Account shows 42% DAU drop over 14 days and NPS dropped from 8 to 4",
      "expected_outcome": "CSM re-engagement should stabilise usage within 30 days"
    }
  ],
  "escalate": false,
  "escalation_reason": ""
}
```

### Verification Agent Output

```json
{
  "passed": true,
  "approved_drafts": [...],
  "rejected_drafts": [
    { "account_id": "...", "rejection_reason": "Duplicate email sent 3 days ago" }
  ],
  "issues": ["Draft for AccountX rejected: duplicate outreach"]
}
```

---

## 19. Troubleshooting

### "DAG not found"

```
❌ Workflow DAG not found: workflows/dags/your_workflow.json
```

Run `python main.py list-workflows` to see available DAGs. Make sure you're running from the project root.

### "LLM config not found"

```
FileNotFoundError: LLM config not found: config/templates/llm_config.json
```

Make sure you're in the `opsgrid/` directory. Run `ls config/templates/` to verify the file exists.

### "All models failed"

```
RuntimeError: All models failed for agent research_agent. Last error: ...
```

Check your API keys in `.env`. Run `curl http://localhost:8000/api/v1/health` — the `llm_providers` field shows which are configured.

### EPI recorder not found

```
WARNING: EPI recorder not installed — evidence capture disabled
```

```bash
pip install epi-recorder
```

Evidence capture is optional — workflows run without it. Install to get `.epi` audit files.

### Database connection refused

```
asyncpg.exceptions.ConnectionRefusedError
```

```bash
docker-compose up -d postgres
docker-compose ps   # Should show postgres as healthy
```

### Frontend can't reach API

The dashboard shows "API unreachable". Verify the API is running:

```bash
python main.py api
# Check: http://localhost:8000/docs should load
```

If the API is on a different host, update `API_BASE` at the top of `frontend/src/App.jsx`.

### Agent produces invalid JSON

All agents include a JSON parser with fallback logic. If an agent's LLM output can't be parsed, the raw text is stored in `output_data.raw_output` and the workflow continues where possible.

To diagnose: check `reasoning_chain` in the agent run — it contains the full LLM response. Usually caused by a prompt that isn't strict enough about output format.

---

## 20. Environment Variables

Copy `.env.example` to `.env` and fill in these values:

### Required

| Variable              | Description                                             |
| --------------------- | ------------------------------------------------------- |
| `ANTHROPIC_API_KEY` | Anthropic API key — minimum required for any LLM calls |

### Recommended

| Variable           | Description                                                 | Default                                                                      |
| ------------------ | ----------------------------------------------------------- | ---------------------------------------------------------------------------- |
| `GROQ_API_KEY`   | Groq API key — enables fast/cheap research tier            | —                                                                           |
| `GOOGLE_API_KEY` | Google AI Studio key — enables Gemini balanced tier        | —                                                                           |
| `OPENAI_API_KEY` | OpenAI API key — enables GPT-4o as alternative heavy model | —                                                                           |
| `DATABASE_URL`   | PostgreSQL connection string                                | `postgresql+asyncpg://opsgrid:opsgrid_dev_password@localhost:5432/opsgrid` |
| `REDIS_URL`      | Redis connection string                                     | `redis://:opsgrid_redis_dev@localhost:6379/0`                              |

### Optional

| Variable               | Description                             | Default                                 |
| ---------------------- | --------------------------------------- | --------------------------------------- |
| `ENVIRONMENT`        | `development` or `production`       | `development`                         |
| `SECRET_KEY`         | JWT signing key — change in production | `dev_secret_key_...`                  |
| `EPI_EVIDENCE_DIR`   | Where`.epi` files are saved           | `./evidence`                          |
| `EPI_AUTO_RECORD`    | Auto-record all LLM calls               | `true`                                |
| `ADMIN_REFRESH_RATE` | Dashboard refresh rate in seconds       | `2`                                   |
| `LOG_LEVEL`          | Logging level                           | `INFO`                                |
| `LLM_HEAVY_MODEL`    | Override the heavy tier model           | `anthropic/claude-sonnet-4-20250514`  |
| `LLM_FAST_MODEL`     | Override the fast tier model            | `groq/llama-3.1-70b-versatile`        |
| `LLM_MINI_MODEL`     | Override the mini tier model            | `anthropic/claude-haiku-4-5-20251001` |

---

## Quick Reference Card

```bash
# Setup
cp .env.example .env && docker-compose up -d

# First run
python db/seed/saas_seed.py
python main.py check-config config/templates/saas.json

# Trigger work (manual signal)
python main.py trigger saas_churn_prevention

# With specific config
python main.py trigger saas_churn_prevention --config config/clients/acme.json

# Admin dashboard
python main.py dashboard

# API server
python main.py api                          # http://localhost:8000/docs

# Frontend
cd frontend && npm run dev                  # http://localhost:5173

# View evidence
python main.py verify-evidence --open-viewer

# List workflows
python main.py list-workflows

# Validate config
python main.py check-config config/templates/saas.json

# Admin controls (via API)
curl -X POST localhost:8000/api/v1/workflows/{run_id}/pause
curl -X POST localhost:8000/api/v1/workflows/{run_id}/stop
curl -X POST localhost:8000/api/v1/workflows/{run_id}/resume
```

---

*Built by FracsNet · SMBFlow Intern Build Program*
