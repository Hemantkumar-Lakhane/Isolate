# SMBFlow Security & Credential Vault Architecture

## 1. Zero Credential Exposure
- Client secrets, access tokens, refresh tokens, and API keys are **NEVER** returned in frontend API responses.
- API endpoints return only connection metadata: `status`, `capabilities`, `granted_scopes`, `provider_account_name`, and latency diagnostics.

---

## 2. MultiFernet AES Credential Vault
- Stored credentials in PostgreSQL `tool_connections.credentials` column are encrypted using AES-128-CBC + HMAC-SHA256 via cryptography's `MultiFernet`.
- Master encryption keys are configured via `VAULT_ENCRYPTION_KEY` in `.env`.
- Supports seamless key rotation by providing comma-separated keys (`VAULT_ENCRYPTION_KEY="primary_key,fallback_key"`).

---

## 3. HMAC OAuth State Integrity
- OAuth authorization requests generate HMAC-SHA256 signed state tokens encoding `org_id`, `user_id`, `capabilities`, `return_to`, and a 10-minute expiry timestamp.
- Protects against CSRF, replay attacks, and tenant state tampering.

---

## 4. Multi-Tenant & Scope Isolation
- Organization connections (e.g. Slack, Google Workspace) are scoped to `organization_id`.
- Personal connections (e.g. LinkedIn personal feed) are bound to `(organization_id, user_id)` and are invisible to other users in the organization.
