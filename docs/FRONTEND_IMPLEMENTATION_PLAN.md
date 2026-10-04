# Frontend Implementation Plan - Phase 2

## Overview

This document outlines the systematic plan to build the complete SMBFlow product UI based on the Figma design system. The goal is to implement the full business-facing product shell, connecting real functionality where available, and utilizing polished "In Progress" or "Coming Soon" states for unimplemented features.

## Implementation Strategy

- **Visual Consistency:** All screens must use the new sidebar layout, identical typography, spacing, cards, tables, and status badges.
- **No Fake Data:** If an API endpoint doesn't exist, the UI will clearly indicate the feature is unavailable.
- **Process:** One screen at a time: Inspect -> Compare -> Implement UI -> Connect API -> Verify.

---

## 1. Core Operations (Priority 1)

### Home (Dashboard)

- **Component:** `src/pages/client/Dashboard.jsx`
- **Figma Reference:** `home.png`
- **Backend Dependency:** `GET /api/v1/analytics/{tenant_id}`, `GET /api/v1/tenants/{tenant_id}/workflows/stats` (Available)
- **Status:** **Partially Implemented (Requires UI Overhaul)**
- **Required UI Work:** Implement metric cards (Active Runs, Completion Rate, Issues), active run table, and ROI metrics layout. Ensure no fake metrics are used; if specific ROI data is missing, mark as "In Progress" or map existing metrics.
- **Risk:** Low. Data largely exists in analytics endpoints.

### Action Center

- **Component:** `src/pages/client/EscalationsPage.jsx` (and potentially merging A2A requests)
- **Figma Reference:** `action_center.png`
- **Backend Dependency:** `GET /api/v1/escalations`, `POST /api/v1/escalations/{id}/decide`, `GET /api/v1/a2a/requests` (Available)
- **Status:** **Partially Implemented (Requires UI Overhaul)**
- **Required UI Work:** Convert to the split pane or list-detail view shown in Figma. Implement business-friendly human-in-the-loop decision cards.
- **Risk:** Medium. Requires merging multiple request types (escalations, a2a, emails) into a unified inbox experience.

### Workflows

- **Component:** `src/pages/client/WorkflowsPage.jsx`
- **Figma Reference:** `workflows.png`
- **Backend Dependency:** `GET /api/v1/workflows`
- **Status:** **✅ Complete (Phase 2A)**

### Workflow Detail

- **Component:** `src/pages/client/WorkflowDetail.jsx`
- **Figma Reference:** `workflow_detail.png`
- **Backend Dependency:** `GET /api/v1/workflows/{run_id}/status`, `GET /api/v1/workflows/{run_id}/system-log`, `GET /api/v1/workflows/{run_id}/evidence` (Available)
- **Status:** **Partially Implemented (Requires UI Overhaul)**
- **Required UI Work:** Replace developer-centric JSON views with a business-friendly step-by-step progress tracker, visual logs, and clear outcome presentations.
- **Risk:** High. Mapping the raw agent/system logs to the clean, step-based UI in Figma requires careful data transformation.

---

## 2. Configuration (Priority 2)

### Workflow Library

- **Component:** TBD / `ConfigStudio.jsx`
- **Figma Reference:** TBD (Part of workflow creation/management)
- **Backend Dependency:** `GET /api/v1/config/workflows` (Available)
- **Status:** **UI-Only / Not Yet Implemented**
- **Required UI Work:** Card grid showing available templates and custom workflows.

### Workflow Creation (Wizard)

- **Component:** `src/pages/client/WorkflowBuilder.jsx`
- **Figma Reference:** `create_workflow.png`
- **Backend Dependency:** `POST /api/v1/config/dag` (Available)
- **Status:** **Partially Implemented (Requires UI Overhaul)**
- **Required UI Work:** Build the multi-step form wizard (Details -> Triggers -> Steps). If complex step configurations aren't fully supported by the API yet, use polished "Coming Soon" disabled states for those specific trigger/step types.
- **Risk:** Medium. The current builder is likely technical; needs translation to the business-first wizard UI.

### General Settings

- **Component:** `src/pages/client/ConfigStudio.jsx` (to be repurposed as Settings > General)
- **Figma Reference:** `settings.png`
- **Backend Dependency:** `GET /api/v1/tenants/{tenant_id}` (Available)
- **Status:** **Partially Implemented (Requires UI Overhaul)**
- **Required UI Work:** Layout the settings shell (left nav for settings sections, main content area for form). Implement tenant profile settings.
- **Risk:** Low.

---

## 3. Settings & Shell (Priority 3)

### AI Engine

- **Component:** `src/pages/client/ModelSettings.jsx`
- **Figma Reference:** Settings Sub-page
- **Backend Dependency:** `GET /api/v1/config/models` (Available)
- **Status:** **Partially Implemented**
- **Required UI Work:** Apply settings shell layout. If fine-grained model controls are missing, add "Advanced AI controls coming soon" state.

### Integrations

- **Component:** `src/pages/client/ToolsPage.jsx`
- **Figma Reference:** Settings Sub-page
- **Backend Dependency:** `GET /api/v1/tools`, `GET /api/v1/credentials` (Available)
- **Status:** **Partially Implemented**
- **Required UI Work:** Card layout for connected apps (Slack, Gmail, etc.) vs available apps. Use "Coming Soon" for unimplemented integrations.

### Budget & Billing

- **Component:** `src/pages/client/BudgetPage.jsx`
- **Figma Reference:** Settings Sub-page
- **Backend Dependency:** `GET /api/v1/tenants/{tenant_id}/budget` (Available)
- **Status:** **Partially Implemented**
- **Required UI Work:** Apply settings shell layout. Clean up budget charts and alerts.

### Evidence

- **Component:** `src/pages/client/EvidencePage.jsx`
- **Figma Reference:** Settings Sub-page
- **Backend Dependency:** `GET /api/v1/evidence` (Available)
- **Status:** **Partially Implemented**
- **Required UI Work:** Convert to the standard data table layout matching the new Workflows table.

---

## 4. Admin (Priority 3)

### Tenants, Users, Health, Fleet Cost

- **Components:** `GodView.jsx`, `UsersPage.jsx`, `FleetCost.jsx`
- **Backend Dependency:** Admin endpoints (Available)
- **Status:** **Partially Implemented**
- **Required UI Work:** Align all admin tables and metric cards with the new visual system. Use consistent headers and spacing.

---

## Execution Checklist

- [X] Create Frontend Implementation Plan
- [ ] Implement Home (Dashboard)
- [ ] Implement Action Center
- [ ] Implement Workflow Detail
- [ ] Implement Workflow Creation
- [ ] Implement Settings Shell (General, AI Engine, Integrations, Budget, Evidence)
- [ ] Implement Admin Screens
