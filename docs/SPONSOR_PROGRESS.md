# SMBFlow — Project Progress Update

## 1. Project Understanding

SMBFlow is being developed as a reusable AI workflow automation platform for small and medium businesses. The platform is intended to automate repetitive business workflows while keeping humans in control of important decisions.

The broader goal is to enable businesses to create and deploy workflow-specific AI automation rather than using a generic chatbot or automation tool.

## 2. Progress Completed

### Existing System Study & Runtime Validation

The inherited codebase was comprehensively studied and successfully brought to a working local state.

The following were verified:

- Backend and API functionality
- PostgreSQL and Redis infrastructure
- Frontend-to-backend connectivity
- Tenant and workspace onboarding flow
- Existing workflow execution end-to-end
- WebSocket-based live workflow monitoring
- Multi-agent workflow execution
- Fallback and recovery behaviour
- Workflow outcome and audit/evidence generation

An existing `saas_churn_prevention` workflow was successfully executed through the platform and verified through both the backend and frontend flow.

### UI/UX Redesign

The existing interface was reviewed and found to be too technical and developer-oriented for a typical SMB business user.

A new professional B2B SaaS direction was therefore designed in Figma with a business-first approach.

The redesign focuses on:

- A business-oriented operations dashboard
- A dedicated Human-in-the-Loop Action Center
- Clear workflow monitoring and status
- Business impact and ROI visibility
- Explainability and trust
- Reduced technical clutter
- Clear separation between business operations and advanced technical configuration

The initial design covers:

- Home Dashboard
- Action Center
- Workflows
- Workflow Detail
- Workflow Analysis
- Workflow Creation
- General Settings

The redesigned experience follows:

**Business event → AI analysis → recommendation → human review when needed → action → outcome and business impact**

Technical information such as model names, agents, prompts, tokens and raw execution data is intended to remain within advanced or administrative areas rather than the primary business workflow.

## 3. UI/UX Improvements Planned

The next design iteration will strengthen the current direction further.

### Explainability

Workflow Detail will clearly show **why SMBFlow recommended an action**, using understandable business evidence such as customer activity, support behaviour, business rules and historical patterns.

### Human-in-the-Loop Decisions

The Action Center will show:

- Risk if the action is approved
- Expected business impact
- Why human approval is required

Approve, Edit and Reject will remain the primary actions.

### Business-First Workflow Creation

Workflow creation will follow:

**Choose business workflow → Connect data → Set business rules → Define approval requirements → Review → Activate**

Advanced technical workflow configuration will remain optional.

### Remaining UI Screens

The remaining design work includes:

- Login / Authentication
- Workflow Library / Templates
- AI Engine
- Integrations / Credentials
- Budget & Billing
- Evidence / Audit
- Tenant Management
- User / Team Management
- Fleet Cost / Platform Health
- Loading, empty, error and confirmation states

## 4. Next Phase

The next phase will focus on product and innovation research before major implementation begins.

Planned sequence:

1. Research existing AI workflow and automation platforms.
2. Study SMB operational problems and existing solutions.
3. Identify gaps and opportunities for differentiation.
4. Evaluate candidate SMB workflows and select one representative workflow.
5. Define the unique ML/AI contribution.
6. Identify data requirements and suitable algorithms.
7. Define evaluation and ROI metrics.
8. Finalize the proposed system architecture.
9. Complete the remaining UI/UX design.
10. Implement the redesigned frontend and new capabilities phase-wise.

## 5. Current Status

| Area                              | Status      |
| --------------------------------- | ----------- |
| Existing system study             | Complete    |
| Runtime and end-to-end validation | Complete    |
| Initial UI/UX redesign            | Complete    |
| UI/UX refinement                  | Planned     |
| Remaining UI screens              | Planned     |
| Innovation / ML research          | Next        |
| New feature development           | Not started |

> **Current milestone:** The team has completed the study and validation of the inherited platform and established a new business-focused product direction. The next phase will focus on research, differentiation, ML planning and final product architecture before implementation.
