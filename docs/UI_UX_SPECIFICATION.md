# FRONTEND & DESIGN RULES



<!-- ==================== FROM UX_SPECIFICATION.md ==================== -->

# SMBFlow Product & UX Specification

This document serves as the foundational UX and product specification for the upcoming Figma redesign of SMBFlow. It maps the current technical capabilities into a professional B2B SaaS product structure.

## 1. Primary User Personas & Goals
- **SMB Operations Manager (Primary)**
  - *Goals:* Automate repetitive back-office tasks, prevent churn, monitor business health, and ensure AI actions are safe before they are sent to customers. Needs ROI visibility.
- **Workflow Developer / Admin (Secondary)**
  - *Goals:* Configure agent prompts, manage LLM models, set API keys, design DAG workflows, and monitor token/cost limits.
- **Platform Super Admin (OpsGrid Team)**
  - *Goals:* Manage tenants, monitor global fleet costs, oversee system-wide health and cryptographic EPI (Execution Provenance) evidence. (Accessed via `/admin` God View).

## 2. Main Daily User Journey
1. **Event Trigger:** A business event (e.g., a customer's usage drops, triggering churn risk) automatically kicks off a workflow.
2. **AI Processing:** Agents (Research, Reasoning, Drafting) process the event autonomously in the background.
3. **Intervention Request:** An agent halts and requests human permission (A2A request or Escalation) to send a drafted email or execute an API call.
4. **Human Approval:** The Ops Manager reviews the drafted action in the "Action Center," edits if necessary, and approves it.
5. **Action & Outcome:** The execution agent fires the action, completing the workflow. The Dashboard reflects the completed run and the cost/savings (ROI) incurred.

## 3. Current Routes: Core vs. Technical
**Core Business Workflows:**
- Dashboard
- Action Center (Escalations / Email Queue)
- Workflows (History & Detail)

**Technical / Configuration (Should be hidden/nested):**
- Workflow Builder, Config Studio, Model Settings, Prompt Studio, Tools, Budget, Patterns, Evidence.

**Admin Only:**
- God View, Fleet Cost, Users.

## 4. Top 5 Most Important User Tasks
1. **Quickly unblock workflows:** Approve or reject pending AI actions (Action Center).
2. **Monitor system pulse:** See active runs, success rates, and active alerts at a glance (Dashboard).
3. **Understand ROI:** See the financial impact and estimated savings of automated tasks (Dashboard / Workflows).
4. **Audit a specific run:** Drill into a completed or failed workflow to understand exactly what the AI did and why (Workflow Detail).
5. **Adjust business logic:** Easily tweak a workflow's prompt or rules without writing code (Settings/Builder).

## 5. Dashboard Needs vs. Settings/Admin Hiding
**Dashboard Needs (Business Focus):**
- Active running workflows and their progress.
- Urgent actions requiring human approval.
- High-level business impact (workflows completed, estimated time/money saved).
- High-level cost (Total API spend this week).

**Hide under Settings (Technical Focus):**
- Individual agent token usage, LLM routing (Anthropic vs Gemini), raw prompt editing, tool bindings, and API keys.

## 6. The Human-in-the-Loop (HITL) Journey
- **Alert:** User sees a centralized badge in the Action Center for a pending item.
- **Review:** User clicks the item. They see plain-english context (e.g., "Agent wants to email John Doe offering a 20% discount").
- **Edit/Reject:** User can directly edit the drafted email, outright reject the action (stopping the workflow), or hit "Approve".
- **Resolution:** Upon approval, the workflow resumes immediately.

## 7. Workflow Creation/Configuration Journey
- **Current:** Users manually piece together DAG logic, prompts, and models across 4 different pages.
- **Target Experience:** A unified "New Workflow" flow where a user selects a template (e.g., "SaaS Churn Prevention"), assigns a budget limit, reviews the plain-english business rules, and activates it. Advanced users can click "Edit Logic" to open the node builder.

## 8. Workflow Monitoring Journey
- **List View:** Users see a table of runs with status (Running, Paused, Completed, Failed), duration, and cost.
- **Detail View:** Users see a real-time progress bar (e.g., "Researching -> Reasoning -> Drafting"). They can watch the AI "think" in real-time, but the UI should abstract away the raw JSON payload in favor of conversational milestones.

## 9. Outcome / ROI Journey
- Every workflow run calculates an `estimated_cost_usd` and an `estimated_savings_pct`. 
- The UI should aggregate these metrics over time to show the user exactly how many manual hours were saved by the platform and balance it against the API cost.

## 10. Recommended Navigation & Hierarchy
- **Operations (Default)**
  - Home (Dashboard)
  - Action Center (Inbox)
  - Workflows (History)
- **Configuration**
  - Workflow Library (Templates & Builder)
  - Memory (Patterns)
- **Settings**
  - General
  - AI Engine (Models, Tools, Prompts)
  - Budget & Billing
  - Evidence Logs

## 11. Industry Expectations for B2B Operations
- **Trust & Explainability:** The system is making autonomous decisions. The UI must always explain *why* an agent made a choice (e.g., "Drafted discount because usage dropped by 40%").
- **Clear Actions:** Buttons for "Approve" and "Reject" must be prominent, unambiguous, and safe.
- **Low Cognitive Load:** Remove developer jargon. Hide JSON, LLM models, and token counts behind tooltips or "Advanced" toggles.
- **Business Impact:** Always surface value (time/money saved) to justify the product's existence.

## 12. Exact Content/Data by Page
- **Dashboard:**
  - KPI Cards: Active Runs, Tasks Completed, Pending Actions, ROI/Savings vs Cost.
  - Quick Inbox: Top 3 pending approvals.
  - Active Feed: Live ticker of currently running workflows.
- **Workflows:**
  - Table: Run ID, Name, Status, Started Ago, Duration, Cost. Filter tabs (All, Active, Completed, Failed).
- **Action Center (Inbox):**
  - List of cards: Agent Name, Intent, Plain-English Reason, Drafted Artifact (e.g., email text), Approve/Reject/Edit buttons.
- **Workflow Detail:**
  - Status Banner, Progress Pipeline, Plain-English Activity Log, Final Output/Artifact.
- **Settings:**
  - Form fields for API Keys, Model Dropdowns, Budget thresholds, User Invites.
- **Admin (Super Admin):**
  - Global KPI Dashboard, Tenant List, Global Fleet Cost Chart.

## 13. What NOT to Expose Prominently
To maintain a professional, business-first B2B interface, **hide** the following behind "Developer Mode", "Advanced Settings", or tooltips:
- Raw JSON inputs/outputs.
- Token counts (In/Out) and chunk sizes.
- The specific LLM models being used (e.g., "gemini-3.6-flash") during normal monitoring.
- The concept of "Agents" communicating via API endpoints.
- Cryptographic EPI signatures and hash chains (unless explicitly investigating an audit).


<!-- ==================== FROM UI_DESIGN_PROPOSAL.md ==================== -->

# UI Design Proposal

> [!NOTE]
> These are proposed UI/UX designs generated in Figma during Phase 2A. They have **not yet been implemented** in the React application.

## Design Goals
Our UI redesign focuses on:
- **Business-First SMB Operations UX**: Removing technical jargon and orienting the platform around business goals and results.
- **Human-in-the-Loop Action Center**: A clear, unified inbox for approving, rejecting, and editing autonomous actions safely.
- **Measurable Business Impact/ROI**: Surfacing metrics like time and money saved across the dashboard and workflows.
- **Reduced Technical Clutter**: Grouping models, API keys, and prompt engineering tools under organized settings.
- **Professional B2B SaaS Visual Language**: Moving away from noisy animations and gradients toward a high-contrast, trustworthy, data-dense interface.

---

## Current Figma Coverage

### Home Dashboard
The main entry point for the Operations Manager. It provides a high-level pulse on system health, active runs, outstanding human actions, and ROI generated by the platform.
![Home Dashboard](assets/ui-redesign/home.png)

### Action Center
The unified inbox for all Human-in-the-Loop interventions. This screen allows users to quickly review agent-generated drafts, approve API actions, and resolve escalations safely.
![Action Center](assets/ui-redesign/action_center.png)

### Workflows
A list view of all historic and active workflow runs. It allows filtering by status and provides a quick summary of duration and cost per run.
![Workflows](assets/ui-redesign/workflows.png)

### Workflow Detail
An audit view into a specific workflow run. It replaces the raw JSON WebSocket stream with a clean, plain-english progress pipeline showing exactly what the agents are thinking and doing.
![Workflow Detail](assets/ui-redesign/workflow_detail.png)

### Workflow Analysis
*(Design planned - placeholder for deep-dive metrics)*
![Workflow Analysis](assets/ui-redesign/workflow_analysis.png)

### Workflow Creation
The builder experience for launching a new workflow. It guides the user through selecting templates, configuring constraints, and setting a budget limit before activation.
![Workflow Creation](assets/ui-redesign/create_workflow.png)

### General Settings
A centralized hub consolidating system configuration, LLM model routing, API keys, and prompts, keeping technical details out of the core operations flow.
![General Settings](assets/ui-redesign/settings.png)

---

## Screens Still To Be Designed

The following screens are planned for our next design session (they are not missing implementation):
- Login / Authentication
- Workflow Library / Templates
- AI Engine Settings
- Integrations / Credentials
- Budget & Billing
- Evidence / Audit
- Tenant Management
- User / Team Management
- Fleet Cost / Platform Health
- Additional loading, empty, error and confirmation states
- Responsive/mobile layouts where useful


<!-- ==================== FROM PHASE_4_UI_IMPLEMENTATION_MAP.md ==================== -->

# Phase 4 UI Implementation Map

This document maps the approved Figma designs to the actual React components, routes, and existing backend APIs. It defines the implementation strategy and execution order for transforming the inherited OpsGrid UI into the new SMBFlow product experience.

## Implementation Principles
- **Figma is the Visual Source of Truth**: Use designs for spacing, typography, dimensions, and layout structure.
- **API is the Functional Source of Truth**: Only use real data from the backend. No hardcoded or fabricated data (ROI, savings, fake names).
- **Business-First Language**: Hide raw DAG terminology, agent LLM traces, and JSON in "Advanced" sections. Focus on business value, recommendations, and evidence.

---

## Screen Mappings & Analysis

### 1. Shared SMBFlow Application Shell
* **Figma Reference**: Persistent navigation and layout across all screens.
* **Current Route**: `/*`
* **React Component**: `components/layout/Layout.jsx`, `contexts/ThemeContext.jsx`
* **API Dependencies**: `GET /api/v1/auth/me`
* **Reusable Components Needed**: Sidebar navigation, standard Page Header, unified loading Spinners, Status Badges.
* **Exact Visual Changes**: Transition to high-contrast minimal aesthetic (Stripe/Linear style). Clean up padding.
* **Missing Backend Data**: None.

### 2. SMB Owner Home Dashboard (COMPLETED - CURRENT PHASE)
* **Role Scope**: SMB Owner / Business User (Tenant-isolated).
* **Figma Reference**: `home.png`
* **Current Route**: `/dashboard`
* **React Component**: `pages/client/Dashboard.jsx`
* **API Dependencies**: 
  - `GET /api/v1/analytics/{tenant_id}`
  - `GET /api/v1/tenants/{tenant_id}/workflows/stats`
* **Exact Visual Changes**: Clean up data density. Remove generic alerts and move human-in-the-loop tasks entirely to the Action Center. Present a high-level operational summary scoped to the logged-in user's tenant.
* **Missing Backend Data**: Figma may depict exact "hours saved" or monetary ROI. If the `/analytics` endpoint doesn't return these explicit fields, fallback to honest empty states (e.g., "-"). Do not fabricate backend data.

### 3. Workflows List
* **Figma Reference**: `workflows.png`
* **Current Route**: Missing in `App.jsx`
* **React Component**: Needs to be created (`pages/client/WorkflowsPage.jsx`)
* **API Dependencies**: 
  - `GET /api/v1/workflows` (or equivalent run history endpoint)
* **Exact Visual Changes**: Data-dense table without excessive padding for easy scanning.
* **Missing Backend Data**: None.

### 4. Action Center (Escalations)
* **Figma Reference**: `action_center.png`
* **Current Route**: `/escalations`
* **React Component**: `pages/client/EscalationsPage.jsx`
* **API Dependencies**: 
  - `GET /api/v1/escalations`
  - `POST /api/v1/escalations/{escalation_id}/decide`
* **Exact Visual Changes**: Refactor into a standard "Inbox" queue format. Focus on what SMBFlow wants to do, why it recommends it, and the risk. Primary actions: Approve, Edit, Reject.
* **Missing Backend Data**: None. The API returns full context payloads for decisions.

### 5. Workflow Detail
* **Figma Reference**: `workflow_detail.png`
* **Current Route**: `/workflows/:runId`
* **React Component**: `pages/client/WorkflowDetail.jsx`
* **API Dependencies**: 
  - `GET /api/v1/workflows/{run_id}/status`
  - `GET /api/v1/workflows/{run_id}/evidence`
  - `GET /api/v1/workflows/{run_id}/system-log` (Note: Currently returning 404 in local runtime, handle gracefully)
* **Exact Visual Changes**: Emphasize Business Summary, Progress, Recommendation, and Evidence. Move raw technical execution logs out of the default view into an "Advanced/Technical" tab.
* **Missing Backend Data**: None.

### 6. Workflow Creation
* **Figma Reference**: `create_workflow.png`
* **Current Route**: `/workflows/builder`
* **React Component**: `pages/client/WorkflowBuilder.jsx`
* **API Dependencies**: 
  - `GET /api/v1/config/workflows`
  - `POST /api/v1/config/dag`
* **Exact Visual Changes**: Replace the technical DAG node editor with a business-first wizard sequence (Choose workflow → Connect data → Set rules → Define approvals → Activate). The DAG editor will be moved to Advanced Configuration.
* **Missing Backend Data**: None.

### 7. Settings (Unified Hub)
* **Figma Reference**: `settings.png`
* **Current Routes**: `/config`, `/models`, `/tools`, `/prompts`
* **React Component**: Consolidate into a new `pages/client/SettingsHub.jsx`
* **API Dependencies**: 
  - `GET /api/v1/tenants/{tenant_id}/config-schema`
  - `PUT /api/v1/tenants/{tenant_id}/config`
  - `GET /api/v1/tools`
  - `GET /api/v1/credentials`
* **Exact Visual Changes**: Consolidate disparate configuration pages into a standard tabbed interface rather than dedicating entire routes to minor configurations.
* **Missing Backend Data**: None.

---

### 8. SMBFlow Admin / God View (PLANNED - NEXT PHASE)
* **Role Scope**: SMBFlow Admin / Super Admin (Platform-wide visibility).
* **Figma Reference**: Pending design/admin layouts.
* **Current Route**: `/admin`
* **React Component**: To be implemented under `pages/admin/`
* **API Dependencies**: Global endpoints (e.g., `/api/v1/admin/*`)
* **Exact Visual Changes**: This UI will be implemented later. Do NOT implement or redesign the Admin UI in the current phase.
* **Missing Backend Data**: To be determined.

---

## Identified Risks
1. **Missing Logs Endpoint**: The `GET /api/v1/workflows/{run_id}/logs` or system-log endpoint returned a 404 during verification. UI must handle this gracefully without crashing the detail view.
2. **Missing Query Parameters**: `GET /api/v1/workflows/estimate-cost` throws a 422. UI components utilizing this must correctly pass the required query parameters as defined by the OpenAPI schema.
3. **Fake Data Temptation**: Strictly enforce that missing analytics metrics are rendered as empty states rather than hardcoded UI mocks.
4. **Role Confusion**: Ensure strict separation between SMB Owner and SMBFlow Admin. Admin credentials should not mistakenly render the SMB Owner dashboard.

---

## Recommended Safest Implementation Order

1. **Shared Application Shell** (Layout, Nav, Theme) - Sets the design system foundation.
2. **SMB Owner Home Dashboard** - [COMPLETED] Easiest data-binding and structural implementation.
3. **Workflows List** - Straightforward table implementation establishing data density patterns.
4. **Action Center** - High value, interaction-heavy queue component.
5. **Workflow Detail** - Complex view requiring careful parsing of evidence and hiding of raw logs.
6. **Settings (Unified Hub)** - Routing consolidation and tab management.
7. **Workflow Creation** - Most complex functional change (moving from DAG editor to Wizard).
8. **SMBFlow Admin UI** - [NEXT PHASE] Implement God View for Super Admins.

*Note: Execution will proceed strictly one screen at a time with full verification before moving to the next.*
