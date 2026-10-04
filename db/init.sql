-- ═══════════════════════════════════════════════════════════════════════
-- OpsGrid PostgreSQL Schema v2.0
-- Full multi-tenant auth, RAG, A2A, budget governance, key vault
-- ═══════════════════════════════════════════════════════════════════════

CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";       -- pgvector for RAG

-- ── Tenants ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tenants (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(255) NOT NULL,
    industry    VARCHAR(100) NOT NULL,
    config      JSONB NOT NULL DEFAULT '{}',
    active      BOOLEAN DEFAULT true,
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now()
);

-- ── Users ─────────────────────────────────────────────────────────────────────
-- Roles: super_admin (full system), tenant_user (scoped to tenant)
CREATE TABLE IF NOT EXISTS users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email         VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name     VARCHAR(255),
    role          VARCHAR(50) NOT NULL DEFAULT 'tenant_user',
    tenant_id     UUID REFERENCES tenants(id) ON DELETE CASCADE,
    is_active     BOOLEAN DEFAULT true,
    last_login    TIMESTAMPTZ,
    created_at    TIMESTAMPTZ DEFAULT now(),
    updated_at    TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT role_tenant_check CHECK (
        (role = 'super_admin' AND tenant_id IS NULL) OR
        (role = 'tenant_user' AND tenant_id IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_tenant ON users(tenant_id);

-- Password reset tokens: single-use, expiring. Only a SHA-256 hash of the
-- token is stored (never the raw token). Matches core.state_manager
-- PasswordResetToken (auto-created at startup via Base.metadata.create_all;
-- this keeps the SQL source of truth in sync).
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(64) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at    TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pwreset_token_hash ON password_reset_tokens(token_hash);
CREATE INDEX IF NOT EXISTS idx_pwreset_user ON password_reset_tokens(user_id);

-- ── Workflow Definitions ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS workflow_definitions (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name           VARCHAR(255) NOT NULL,
    industry       VARCHAR(100) NOT NULL,
    version        VARCHAR(20) NOT NULL DEFAULT '1.0.0',
    dag_definition JSONB NOT NULL,
    prompt_refs    JSONB,
    active         BOOLEAN DEFAULT true,
    created_at     TIMESTAMPTZ DEFAULT now()
);

-- ── Workflow Instances ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS workflow_instances (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id         UUID REFERENCES tenants(id) ON DELETE CASCADE,
    definition_id     UUID REFERENCES workflow_definitions(id),
    workflow_name     VARCHAR(255) NOT NULL,
    status            VARCHAR(50) NOT NULL DEFAULT 'pending',
    trigger_signal    JSONB NOT NULL,
    current_node      VARCHAR(100),
    context           JSONB DEFAULT '{}',
    started_at        TIMESTAMPTZ DEFAULT now(),
    completed_at      TIMESTAMPTZ,
    outcome           JSONB,
    error_log         TEXT,
    total_tokens_in   INTEGER DEFAULT 0,
    total_tokens_out  INTEGER DEFAULT 0,
    total_cost_usd    FLOAT DEFAULT 0.0,
    epi_artifact_path VARCHAR(500),
    admin_signal      VARCHAR(50),    -- pause | stop | resume
    triggered_by      UUID REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_workflow_instances_tenant ON workflow_instances(tenant_id);
CREATE INDEX IF NOT EXISTS idx_workflow_instances_status ON workflow_instances(status);
CREATE INDEX IF NOT EXISTS idx_workflow_instances_started ON workflow_instances(started_at DESC);

-- ── Agent Runs ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agent_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    instance_id     UUID REFERENCES workflow_instances(id) ON DELETE CASCADE,
    agent_type      VARCHAR(100) NOT NULL,
    node_id         VARCHAR(100) NOT NULL,
    input_data      JSONB NOT NULL,
    output_data     JSONB,
    confidence      FLOAT,
    reasoning_chain TEXT,
    tokens_in       INTEGER DEFAULT 0,
    tokens_out      INTEGER DEFAULT 0,
    cost_usd        FLOAT DEFAULT 0.0,
    model_used      VARCHAR(200),
    duration_ms     INTEGER,
    status          VARCHAR(50) DEFAULT 'pending',
    a2a_triggered   BOOLEAN DEFAULT false,
    created_at      TIMESTAMPTZ DEFAULT now(),
    completed_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_agent_runs_instance ON agent_runs(instance_id);

-- ── Escalations ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS escalations (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    instance_id         UUID REFERENCES workflow_instances(id),
    tenant_id           UUID REFERENCES tenants(id),
    node_id             VARCHAR(100) NOT NULL,
    reason              TEXT NOT NULL,
    context_brief       TEXT NOT NULL,
    recommended_action  TEXT,
    options             JSONB DEFAULT '[]',
    status              VARCHAR(50) DEFAULT 'pending',
    decision            JSONB,
    decided_by          VARCHAR(255),
    decided_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_escalations_status ON escalations(status);
CREATE INDEX IF NOT EXISTS idx_escalations_tenant ON escalations(tenant_id);

-- ── Outcomes ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS outcomes (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    instance_id   UUID REFERENCES workflow_instances(id),
    tenant_id     UUID REFERENCES tenants(id),
    action_taken  VARCHAR(255) NOT NULL,
    action_detail JSONB,
    metric_name   VARCHAR(255),
    metric_value  FLOAT,
    measured_at   TIMESTAMPTZ,
    created_at    TIMESTAMPTZ DEFAULT now()
);

-- ── Pattern Memory ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pattern_memory (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id    UUID REFERENCES tenants(id) ON DELETE CASCADE,
    pattern_key  VARCHAR(255) NOT NULL,
    pattern_data JSONB NOT NULL,
    success_rate FLOAT,
    sample_size  INTEGER DEFAULT 1,
    last_updated TIMESTAMPTZ DEFAULT now(),
    UNIQUE(tenant_id, pattern_key)
);

CREATE INDEX IF NOT EXISTS idx_pattern_memory_tenant ON pattern_memory(tenant_id);
CREATE INDEX IF NOT EXISTS idx_pattern_memory_key ON pattern_memory(pattern_key);

-- ── Integration Credentials (Encrypted Key Vault) ─────────────────────────────
CREATE TABLE IF NOT EXISTS integration_credentials (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID REFERENCES tenants(id) ON DELETE CASCADE,
    tool_name       VARCHAR(100) NOT NULL,
    display_name    VARCHAR(255),
    credentials     JSONB NOT NULL,          -- <-- Changed from encrypted_data TEXT
    expires_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE(tenant_id, tool_name)
);

CREATE INDEX IF NOT EXISTS idx_credentials_tenant ON integration_credentials(tenant_id);

-- ── Custom Tool Registry (per tenant) ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS custom_tools (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID REFERENCES tenants(id) ON DELETE CASCADE,
    tool_name           VARCHAR(255) NOT NULL,
    display_name        VARCHAR(255),
    description         TEXT,
    base_url            VARCHAR(500),
    http_method         VARCHAR(10) DEFAULT 'GET',
    headers_template    JSONB DEFAULT '{}',
    body_template       JSONB DEFAULT '{}',
    query_params        JSONB DEFAULT '{}',
    auth_type           VARCHAR(50) DEFAULT 'api_key',   -- api_key | bearer | basic | none
    credential_id       UUID REFERENCES integration_credentials(id),
    response_path       VARCHAR(255),        -- JSONPath to extract result
    schema_definition   JSONB,               -- OpenAI tool schema
    is_active           BOOLEAN DEFAULT true,
    created_at          TIMESTAMPTZ DEFAULT now(),
    UNIQUE(tenant_id, tool_name)
);

CREATE INDEX IF NOT EXISTS idx_custom_tools_tenant ON custom_tools(tenant_id);

-- ── RAG Embeddings (pgvector) ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS rag_embeddings (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id      UUID REFERENCES tenants(id) ON DELETE CASCADE,
    content_type   VARCHAR(100) NOT NULL,  -- outcome | error | tool_schema | correction;
    content_text   TEXT NOT NULL,
    embedding      vector(384),           -- OpenAI ada-002 / text-embedding-3-small
    metadata       JSONB DEFAULT '{}',
    workflow_name  VARCHAR(255),
    run_id         UUID REFERENCES workflow_instances(id),
    created_at     TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rag_tenant ON rag_embeddings(tenant_id);
CREATE INDEX IF NOT EXISTS idx_rag_content_type ON rag_embeddings(content_type);
-- IVFFlat index for approximate nearest neighbor search
CREATE INDEX IF NOT EXISTS idx_rag_embedding_cosine
    ON rag_embeddings USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 50);

-- ── A2A (Agent-to-Agent) Requests ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS a2a_requests (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    instance_id         UUID REFERENCES workflow_instances(id),
    tenant_id           UUID REFERENCES tenants(id),
    requesting_agent    VARCHAR(100) NOT NULL,
    target_agent        VARCHAR(100) NOT NULL,
    reason              TEXT NOT NULL,
    refinement_note     TEXT,
    estimated_cost_usd  FLOAT DEFAULT 0.001,
    status              VARCHAR(50) DEFAULT 'pending_permission',
    -- pending_permission | approved | rejected | executing | completed
    client_decision     VARCHAR(50),    -- approved | rejected
    decided_at          TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_a2a_instance ON a2a_requests(instance_id);
CREATE INDEX IF NOT EXISTS idx_a2a_tenant ON a2a_requests(tenant_id);
CREATE INDEX IF NOT EXISTS idx_a2a_status ON a2a_requests(status);

-- ── Budget Governor Settings (per tenant) ────────────────────────────────────
CREATE TABLE IF NOT EXISTS budget_settings (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id            UUID REFERENCES tenants(id) ON DELETE CASCADE UNIQUE,
    optimization_level   INTEGER DEFAULT 1 CHECK (optimization_level BETWEEN 0 AND 3),
    strategy             VARCHAR(50) DEFAULT 'balanced',
    -- 0=max_accuracy | 1=balanced | 2=aggressive | 3=budget_first
    max_context_tokens   INTEGER DEFAULT 10000,
    enable_caching       BOOLEAN DEFAULT true,
    cache_ttl_seconds    INTEGER DEFAULT 3600,
    a2a_enabled          BOOLEAN DEFAULT false,  -- client allows A2A
    auto_retry_on_low_confidence BOOLEAN DEFAULT true,
    confidence_retry_threshold   FLOAT DEFAULT 0.6,
    created_at           TIMESTAMPTZ DEFAULT now(),
    updated_at           TIMESTAMPTZ DEFAULT now()
);

-- ── WebSocket Session Tracking ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ws_sessions (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID REFERENCES users(id) ON DELETE CASCADE,
    session_id VARCHAR(255) UNIQUE NOT NULL,
    role       VARCHAR(50),
    tenant_id  UUID REFERENCES tenants(id),
    connected_at TIMESTAMPTZ DEFAULT now(),
    last_ping    TIMESTAMPTZ DEFAULT now()
);

-- ── System Events Log (for admin god view) ───────────────────────────────────
CREATE TABLE IF NOT EXISTS system_events (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type   VARCHAR(100) NOT NULL,
    tenant_id    UUID REFERENCES tenants(id),
    instance_id  UUID REFERENCES workflow_instances(id),
    agent_type   VARCHAR(100),
    message      TEXT NOT NULL,
    metadata     JSONB DEFAULT '{}',
    cost_usd     FLOAT DEFAULT 0.0,
    created_at   TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_system_events_created ON system_events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_system_events_tenant ON system_events(tenant_id);

-- ── Triggers for updated_at ───────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END;
$$ language 'plpgsql';

CREATE TRIGGER update_tenants_updated_at
    BEFORE UPDATE ON tenants FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();

CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();

CREATE TRIGGER update_credentials_updated_at
    BEFORE UPDATE ON integration_credentials FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();

CREATE TRIGGER update_budget_settings_updated_at
    BEFORE UPDATE ON budget_settings FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();

-- ── Seed: Default super admin ─────────────────────────────────────────────────
-- Password: admin123 (bcrypt hash) — CHANGE IN PRODUCTION
INSERT INTO users (email, password_hash, full_name, role)
VALUES (
    'admin@smbflow.com',
    '$2b$12$kJBJTdvgvGbM98YN.UCWauIkWDUOoKcxuXjtBCXzMH9QdpxB6P/.e',
    'OpsGrid Admin',
    'super_admin'
) ON CONFLICT (email) DO NOTHING;


-- ═══════════════════════════════════════════════════════════════════════
-- OpsGrid Migration 001 — Architectural Evolution
-- Run once against the existing schema produced by db/init.sql
-- ═══════════════════════════════════════════════════════════════════════

-- ── WorkflowStatus: add pending_a2a ────────────────────────────────────────
-- (status is VARCHAR so no enum change needed; just document the value)
-- Valid: pending | running | paused | escalated | pending_a2a | completed | failed | stopped

-- ── workflow_instances: add suspension columns ────────────────────────────
ALTER TABLE workflow_instances
  ADD COLUMN IF NOT EXISTS suspension_data   JSONB,
  ADD COLUMN IF NOT EXISTS tenant_config     JSONB;

COMMENT ON COLUMN workflow_instances.suspension_data IS
  'Set when a workflow is suspended: {resume_from_node, escalation_id, a2a_id, ...}';
COMMENT ON COLUMN workflow_instances.tenant_config IS
  'Snapshot of tenant config at trigger time, required for workflow resumption.';

-- ── escalations: multi-step approval ─────────────────────────────────────
ALTER TABLE escalations
  ADD COLUMN IF NOT EXISTS required_signatures INTEGER NOT NULL DEFAULT 1,
  ADD COLUMN IF NOT EXISTS signatures          JSONB   NOT NULL DEFAULT '[]';

COMMENT ON COLUMN escalations.required_signatures IS
  'Number of approvals needed before the workflow is auto-resumed.';
COMMENT ON COLUMN escalations.signatures IS
  'Array of {user_id, user_email, action_chosen, decision, signed_at}.';

-- ── integration_credentials: relax unique constraint for dev ─────────────
-- (original init.sql has UNIQUE(tenant_id, tool_name) — keep as is, fine)

-- ── Index additions ───────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_workflow_instances_status_tenant
  ON workflow_instances(status, tenant_id);

CREATE INDEX IF NOT EXISTS idx_escalations_instance
  ON escalations(instance_id);

CREATE INDEX IF NOT EXISTS idx_a2a_run ON a2a_requests(instance_id, status);

-- ── budget_settings: add missing columns ─────────────────────────────────
ALTER TABLE budget_settings
  ADD COLUMN IF NOT EXISTS auto_retry_on_low_confidence BOOLEAN NOT NULL DEFAULT true,
  ADD COLUMN IF NOT EXISTS confidence_retry_threshold   FLOAT   NOT NULL DEFAULT 0.6;

ALTER TABLE a2a_requests ADD COLUMN target_node_id VARCHAR(100);

ALTER TABLE workflow_instances ADD COLUMN agent_runs JSONB DEFAULT '[]';

ALTER TABLE budget_settings
  ADD COLUMN IF NOT EXISTS enable_map_reduce_summarization BOOLEAN NOT NULL DEFAULT false;




-- ═══════════════════════════════════════════════════════════════════════
-- OpsGrid Migration 002 — A2A Dynamic Tools + Human Correction RAG Type
-- Run once against the schema produced by db/init.sql + migration 001.
-- ═══════════════════════════════════════════════════════════════════════

-- ── a2a_requests: add new_tools column ───────────────────────────────────────
-- Allows the Reasoning agent to request tools that were NOT in the original
-- DAG node definition.  Empty array = no extra tools (backwards compatible).
ALTER TABLE a2a_requests
  ADD COLUMN IF NOT EXISTS new_tools JSONB NOT NULL DEFAULT '[]'; -- 'Tool names (strings) the requesting agent wants injected into the target node '
  --'on re-run.  These are tools not present in the original DAG node definition.';


ALTER TABLE escalations ADD COLUMN IF NOT EXISTS action_chosen VARCHAR(255);
ALTER TABLE escalations ADD COLUMN IF NOT EXISTS required_signatures INTEGER NOT NULL DEFAULT 1;
ALTER TABLE escalations ADD COLUMN IF NOT EXISTS signatures JSONB NOT NULL DEFAULT '[]';




-- ═══════════════════════════════════════════════════════════════════════
-- OpsGrid Migration 003 — Pattern Sandbox + Loop Count + Streaming EPI
-- ═══════════════════════════════════════════════════════════════════════
 
ALTER TABLE workflow_instances
  ADD COLUMN IF NOT EXISTS loop_count INTEGER NOT NULL DEFAULT 0;
 
COMMENT ON COLUMN workflow_instances.loop_count IS
  'Counts A2A re-run loops. Enforces max_a2a_attempts from DAG meta.';
 
ALTER TABLE pattern_memory
  ADD COLUMN IF NOT EXISTS pattern_status VARCHAR(50) NOT NULL DEFAULT 'active';
 
COMMENT ON COLUMN pattern_memory.pattern_status IS
  'active = injected into RAG context. pending_review = sandboxed until admin promotes.';
 
CREATE INDEX IF NOT EXISTS idx_pattern_memory_status
  ON pattern_memory(tenant_id, pattern_status);

ALTER TABLE rag_embeddings ALTER COLUMN run_id DROP NOT NULL;


-- Email Queue table
CREATE TABLE IF NOT EXISTS email_queue (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        UUID REFERENCES tenants(id) ON DELETE CASCADE,
    run_id           UUID REFERENCES workflow_instances(id),
    account_id       VARCHAR(255),
    recipient_email  VARCHAR(255) NOT NULL,
    recipient_name   VARCHAR(255),
    subject          TEXT NOT NULL,
    body             TEXT NOT NULL,
    email_type       VARCHAR(50),
    csm_name         VARCHAR(255),
    workflow_name    VARCHAR(255),
    status           VARCHAR(50) NOT NULL DEFAULT 'pending',
    rejection_reason TEXT,
    reviewed_at      TIMESTAMPTZ,
    reviewed_by      VARCHAR(255),
    created_at       TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_email_queue_tenant  ON email_queue(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_email_queue_run     ON email_queue(run_id);


-- ═══════════════════════════════════════════════════════════════════════
-- OpsGrid Migration 004 — Performance, Normalization & Security
-- Run: psql $DATABASE_URL -f db/migrations/004_improvements.sql
-- ═══════════════════════════════════════════════════════════════════════

-- ── 1. Agent Run Records table (BUG-002: replaces unbounded JSONB array) ──
CREATE TABLE IF NOT EXISTS agent_run_records (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    instance_id       UUID REFERENCES workflow_instances(id) ON DELETE CASCADE,
    node_id           VARCHAR(100) NOT NULL,
    agent_type        VARCHAR(100),
    status            VARCHAR(50),
    cost_usd          FLOAT   DEFAULT 0.0,
    tokens_in         INTEGER DEFAULT 0,
    tokens_out        INTEGER DEFAULT 0,
    model_used        VARCHAR(200),
    confidence        FLOAT,
    duration_ms       INTEGER,
    error             TEXT,
    tools_used        JSONB   DEFAULT '[]',
    node_description  TEXT,
    -- Verification-specific audit fields
    prosecutor_issues INTEGER,
    judge_verdict     VARCHAR(20),
    prosecutor_faults JSONB DEFAULT '[]',
    -- Memory-specific delta fields
    delta_vs_history  VARCHAR(50),
    delta_trend       VARCHAR(50),
    delta_analysis    JSONB,
    -- Full structured output of the node (business result the UI renders),
    -- tied to (instance_id, node_id). Secrets redacted / size-capped by the app.
    output_data       JSONB,
    completed_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_agent_run_records_instance
    ON agent_run_records(instance_id);
CREATE INDEX IF NOT EXISTS idx_agent_run_records_node
    ON agent_run_records(instance_id, node_id);

-- Migrate existing data from JSONB array (run once, then the app uses new table)
INSERT INTO agent_run_records (
    instance_id, node_id, agent_type, status, cost_usd,
    tokens_in, tokens_out, model_used, confidence, duration_ms,
    error, tools_used, completed_at
)
SELECT
    id AS instance_id,
    run->>'node_id'   AS node_id,
    run->>'agent_type' AS agent_type,
    run->>'status'    AS status,
    (run->>'cost_usd')::FLOAT AS cost_usd,
    (run->>'tokens_in')::INTEGER AS tokens_in,
    (run->>'tokens_out')::INTEGER AS tokens_out,
    run->>'model_used' AS model_used,
    (run->>'confidence')::FLOAT AS confidence,
    (run->>'duration_ms')::INTEGER AS duration_ms,
    run->>'error'     AS error,
    COALESCE(run->'tools_used', '[]'::jsonb) AS tools_used,
    COALESCE(
        (run->>'completed_at')::TIMESTAMPTZ,
        now()
    ) AS completed_at
FROM workflow_instances,
     jsonb_array_elements(COALESCE(agent_runs, '[]'::jsonb)) AS run
WHERE jsonb_array_length(COALESCE(agent_runs, '[]'::jsonb)) > 0
  AND run->>'node_id' IS NOT NULL
ON CONFLICT DO NOTHING;

-- ── 2. Performance indexes ────────────────────────────────────────────────

-- Partial index for active workflow dashboard queries (avoids full table scan)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_wi_status_active
    ON workflow_instances(status, tenant_id, started_at DESC)
    WHERE status IN ('running', 'paused', 'escalated', 'pending_a2a');

-- Pattern store lookup by tenant + status
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pattern_memory_tenant_status
    ON pattern_memory(tenant_id, pattern_status, last_updated DESC);

-- RAG: composite index for content_type + tenant filtering (used before vector search)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_rag_tenant_type
    ON rag_embeddings(tenant_id, content_type, created_at DESC);

-- Email queue: tenant + status lookup
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_email_queue_tenant_status
    ON email_queue(tenant_id, status, created_at DESC);

-- ── 3. Tenant prompt storage (SEC-005: replaces filesystem-based prompts) ──
CREATE TABLE IF NOT EXISTS tenant_prompts (
    id          UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID    REFERENCES tenants(id) ON DELETE CASCADE,
    prompt_path VARCHAR(500) NOT NULL,   -- e.g. "saas/reasoning_churn.txt"
    content     TEXT    NOT NULL,
    is_system   BOOLEAN DEFAULT false,   -- true = read-only for non-admins
    created_by  UUID    REFERENCES users(id),
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE(tenant_id, prompt_path)
);
CREATE INDEX IF NOT EXISTS idx_tenant_prompts_lookup
    ON tenant_prompts(tenant_id, prompt_path);

-- ── 4. Connector health tracking ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS connector_health (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        UUID REFERENCES tenants(id) ON DELETE CASCADE,
    connector_name   VARCHAR(100) NOT NULL,
    last_checked_at  TIMESTAMPTZ DEFAULT now(),
    is_healthy       BOOLEAN DEFAULT true,
    error_message    TEXT,
    UNIQUE(tenant_id, connector_name)
);

-- ── 5. Keep agent_runs JSONB as last-10 summary only (trim via trigger) ──
-- After migration, keep only last 10 entries for dashboard overview.
-- Full history lives in agent_run_records.
CREATE OR REPLACE FUNCTION trim_agent_runs_jsonb()
RETURNS TRIGGER AS $$
BEGIN
    IF jsonb_array_length(COALESCE(NEW.agent_runs, '[]'::jsonb)) > 10 THEN
        NEW.agent_runs = (
            SELECT jsonb_agg(elem)
            FROM (
                SELECT elem
                FROM jsonb_array_elements(NEW.agent_runs) AS elem
                ORDER BY (elem->>'completed_at') DESC NULLS LAST
                LIMIT 10
            ) sub
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_trim_agent_runs ON workflow_instances;
CREATE TRIGGER trg_trim_agent_runs
    BEFORE UPDATE OF agent_runs ON workflow_instances
    FOR EACH ROW EXECUTE FUNCTION trim_agent_runs_jsonb();

-- ── 6. Add learning_mode column to tenants (MemoryAgent fix) ─────────────
ALTER TABLE tenants
    ADD COLUMN IF NOT EXISTS learning_mode VARCHAR(20) DEFAULT 'supervised';

COMMENT ON COLUMN tenants.learning_mode IS
    'autonomous = auto-promote patterns; supervised = require human review';

-- Update existing tenants that already have autonomous in config
UPDATE tenants
SET learning_mode = 'autonomous'
WHERE config->>'learning_mode' = 'autonomous';

ALTER TABLE budget_settings ADD COLUMN IF NOT EXISTS max_spend_per_run_usd FLOAT;