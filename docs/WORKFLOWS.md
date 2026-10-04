# SMBFlow Workflow Architecture & Runtime

## 1. Overview
SMBFlow executes multi-step Directed Acyclic Graph (DAG) workflows to automate business operations (e.g. Lead Enrichment, Medical Tourism Operations, Product Launch Sprints, Meeting Intelligence & Email Follow-up).

---

## 2. Dynamic Capability Resolution
When a workflow node requires access to an external tool (e.g. `google.gmail.send` or `google.meet.transcript.read`):
1. **Capability Check**: The runtime calls `resolve_capability_requirement(db, org_id, user_id, capability_id)`.
2. **Reusability**: If an active organization-level connection exists (e.g., Google Workspace connected once), it is immediately utilized.
3. **Missing Connection Handling**: If no active connection or missing scopes, the runtime halts safely and emits:
```json
{
  "status": "connection_required",
  "provider": "google_workspace",
  "capability": "google.gmail.send",
  "message": "Google Workspace must be connected before this workflow can continue.",
  "connect_url": "/integrations?connect=google_workspace"
}
```
4. **Human-In-The-Loop (HITL)**: Actions with `requires_hitl: true` create an `ApprovalItem` review record and require explicit operator confirmation before executing external writes.
