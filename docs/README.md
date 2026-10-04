# SMBFlow Documentation

Welcome to the central technical documentation for **SMBFlow**, the enterprise-grade AI workflow orchestration and integration platform.

---

## Documentation Map

| Document | Purpose |
| :--- | :--- |
| [**Architecture**](file:///c:/Users/lakha/ml_cp/SMBFlow/docs/ARCHITECTURE.md) | Complete system architecture: Frontend, Backend, Database, Auth, Execution Runtime, Realtime. |
| [**Theme & UI Design System**](file:///c:/Users/lakha/ml_cp/SMBFlow/docs/THEME.md) | Single authoritative source of truth for SMBFlow UI tokens, colors, typography, components, and states. |
| [**Integrations & Tool Connections**](file:///c:/Users/lakha/ml_cp/SMBFlow/docs/INTEGRATIONS.md) | Provider registry, capability model, OAuth 2.0 lifecycle, MultiFernet vault, and scope isolation. |
| [**Workflows**](file:///c:/Users/lakha/ml_cp/SMBFlow/docs/WORKFLOWS.md) | Workflow DAG execution engine, capability resolution, nodes, human-in-the-loop (HITL), and scheduling. |
| [**Security**](file:///c:/Users/lakha/ml_cp/SMBFlow/docs/SECURITY.md) | Credential encryption, MultiFernet key rotation, multi-tenant isolation, RBAC authorization, and audit logs. |
| [**Development Guide**](file:///c:/Users/lakha/ml_cp/SMBFlow/docs/DEVELOPMENT.md) | Local environment setup, PowerShell scripts (`start.ps1`, `setup.ps1`), testing with pytest, and frontend builds. |

---

## Integration Providers

- [**Google Workspace Integration**](file:///c:/Users/lakha/ml_cp/SMBFlow/docs/integrations/google.md): 16 capabilities across Gmail, Calendar, Meet REST API v2, Drive, Docs, Sheets, Slides.
- [**LinkedIn Integration**](file:///c:/Users/lakha/ml_cp/SMBFlow/docs/integrations/linkedin.md): OpenID userinfo, Profile resolution, and Posts REST API v2 publishing.
- [**Slack Integration**](file:///c:/Users/lakha/ml_cp/SMBFlow/docs/integrations/slack.md): Bot Token / Webhook alerts, channel messaging, and HITL approval links.
- [**HubSpot Integration**](file:///c:/Users/lakha/ml_cp/SMBFlow/docs/integrations/hubspot.md): CRM contact sync, lead triage, and deal pipeline management.
