# SMBFlow — Architecture Specification

## 1. High-Level Stack
- **Frontend**: React 18 + Vite + TanStack React Query + Supabase JS Client (`@supabase/supabase-js`).
- **Backend API**: FastAPI (`api/main.py` & `api/routers/`).
- **Database & Auth**: Supabase Managed PostgreSQL with Row-Level Security (RLS) & Supabase Auth.
- **Cache & Pub/Sub**: Redis 7 (Multi-worker WebSocket event relay & LLM semantic caching).
- **LLM Layer**: LiteLLM Multi-Provider Router (`core/llm_router.py`) with Budget Governor.

## 2. Authentication & Roles
- **Provider**: Supabase Auth (Email/Password, Google OAuth, Reset Password, Sessions).
- **FastAPI Token Dependency**: `api/deps/auth.py` validates Supabase JWTs (`SUPABASE_JWT_SECRET`) and maps identity to:
  - `user_id`
  - `organization_id`
  - `role` (`platform_admin` | `org_admin` | `org_user`)

## 3. Tool Connection Architecture
Connectors implement `BaseConnector` (`integrations/connectors.py`).
States: `NOT CONNECTED` | `CONNECTED` | `CONNECTION ERROR`.
Credentials encrypted at rest via `MultiFernet` (`integrations/key_vault.py`).

## 4. Reusable Agent Capabilities
Eight Agent Capabilities registered in Agent Registry (`agents/agents.py`):
1. Customer Outreach
2. Customer Support
3. Marketing Outreach
4. Summarizer
5. Recommendation (Operational)
6. Comparison (Quote/Data)
7. HR
8. Operations
