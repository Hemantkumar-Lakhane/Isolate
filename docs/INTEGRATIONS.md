# SMBFlow Tool Connections & Integrations Architecture

## 1. Core Architecture Principles

1. **Authentication vs. Tool Connections Separation**:
   - **SMBFlow Authentication**: How a user logs into the platform (Email/Password, Supabase Auth).
   - **Tool Connections**: Third-party service authorizations (Google Workspace, LinkedIn, Slack, HubSpot, Stripe) that workflows consume.
2. **Persistent Provider Marketplace**:
   - The integration marketplace always renders all supported providers regardless of whether 0 or 10 tools are connected.
   - Provider definitions are stored in the canonical `PROVIDER_CATALOG` (`integrations/registry.py`).
   - Counts are calculated and clamped:
     - `all = total_registered_providers`
     - `connected = active_connections_count`
     - `available = max(0, all - connected)`
3. **Unified Google Workspace**:
   - Single external connection exposes 16 independent capabilities with granular scope mappings across Gmail, Calendar, Google Meet REST API v2, Drive, Docs, Sheets, and Slides.
   - Connecting Google Workspace once enables all workflows in the organization to utilize authorized Google capabilities without re-authentication.
4. **Multi-Tenant & Scope Isolation**:
   - **Organization Scope**: (e.g. Slack, HubSpot, Stripe, Google Workspace) Shared across the organization.
   - **Personal Scope**: (e.g. Personal LinkedIn Profile) Isolated to the individual user.
5. **Capability-Level Access & Workflow Runtime Resolution**:
   - Workflows declare required capabilities (e.g. `google.gmail.send`, `google.meet.transcript.read`, `linkedin.post.create`).
   - `resolve_capability_requirement(db, org_id, user_id, capability_id)` verifies if an active connection exists.
   - If missing, returns structured `{ "status": "connection_required", "provider": "google_workspace", "message": "...", "connect_url": "..." }`.

---

## 2. Supported Providers & Capabilities

| Provider Key | Display Name | Auth Type | Scope Level | Capabilities Count |
| :--- | :--- | :--- | :--- | :--- |
| `google_workspace` | Google Workspace | OAuth 2.0 | Organization | 16 Capabilities |
| `linkedin` | LinkedIn | OAuth 2.0 | Personal | 3 Capabilities |
| `slack` | Slack Notifications | Bot Token / API Key | Organization | 3 Capabilities |
| `hubspot` | HubSpot CRM | API Key | Organization | 3 Capabilities |
| `stripe` | Stripe Payments & Billing | API Key | Organization | 3 Capabilities |
| `rest_api` | Custom REST Connector | API Key / Bearer | Organization | 2 Capabilities |

---

## 3. Canonical OAuth 2.0 Lifecycle

```mermaid
sequenceDiagram
    autonumber
    actor User as User / Admin
    participant UI as SMBFlow Frontend
    participant API as FastAPI Backend (/api/v1/connections)
    participant OAuth as OAuth Provider (Google / LinkedIn)
    participant Vault as MultiFernet Vault
    participant DB as PostgreSQL (tool_connections)
    participant WS as WebSocket / Redis PubSub

    User->>UI: Click "Connect with OAuth"
    UI->>API: GET /oauth/{provider}/authorize?return_to=...
    API->>API: Build HMAC-signed state token (org_id, user_id, scopes)
    API-->>UI: Return OAuth authorization URL
    UI->>OAuth: Redirect user to Consent Screen
    User->>OAuth: Grant permissions
    OAuth->>API: Redirect to GET /oauth/{provider}/callback?code=...&state=...
    API->>API: Verify HMAC state signature & expiration
    API->>OAuth: Exchange code for Access & Refresh Tokens
    API->>Vault: Encrypt tokens via MultiFernet AES-128-CBC
    API->>DB: Store encrypted ToolConnection record
    API->>WS: Broadcast 'connection_status_changed' event
    API-->>UI: Redirect back to /integrations?connected={provider}&status=success
    UI->>UI: Show Toast Notification & Update Marketplace Card
```

---

## 4. Workflow Capability Check

Before running any node requiring external tools:
```python
from integrations.registry import resolve_capability_requirement

res = await resolve_capability_requirement(
    db=db,
    org_id=org_id,
    user_id=user_id,
    capability_id="google.gmail.send",
)

if res["status"] == "connection_required":
    return {
        "status": "connection_required",
        "provider": res["provider"],
        "capability": "google.gmail.send",
        "message": res["message"],
        "connect_url": res["connect_url"],
    }
```
