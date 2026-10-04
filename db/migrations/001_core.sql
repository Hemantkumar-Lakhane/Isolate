-- =============================================================================
-- Migration 001: Core Platform DDL & Row-Level Security (RLS)
-- Target: Supabase Managed PostgreSQL
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Organizations (Tenants)
CREATE TABLE IF NOT EXISTS organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    industry VARCHAR(100) NOT NULL DEFAULT 'saas',
    enabled_modules JSONB NOT NULL DEFAULT '["medical_tourism"]'::jsonb,
    profile_config JSONB NOT NULL DEFAULT '{}'::jsonb,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Organization Users (Mapping Supabase auth.users to Organizations and Roles)
CREATE TABLE IF NOT EXISTS organization_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL, -- FK to auth.users
    email VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(50) NOT NULL DEFAULT 'org_user', -- platform_admin, org_admin, org_user
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(organization_id, user_id)
);

-- Tool Connections (First-Class Integrations)
CREATE TABLE IF NOT EXISTS tool_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    tool_name VARCHAR(100) NOT NULL,
    display_name VARCHAR(255),
    status VARCHAR(50) NOT NULL DEFAULT 'not_connected', -- not_connected, connected, error
    encrypted_credentials TEXT,
    config JSONB DEFAULT '{}'::jsonb,
    last_tested_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Workflow Definitions
CREATE TABLE IF NOT EXISTS workflow_definitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    industry VARCHAR(100) NOT NULL DEFAULT 'general',
    version VARCHAR(20) NOT NULL DEFAULT '1.0.0',
    dag_definition JSONB NOT NULL,
    is_template BOOLEAN DEFAULT FALSE,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Workflow Instances (Runs)
CREATE TABLE IF NOT EXISTS workflow_instances (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    definition_id UUID REFERENCES workflow_definitions(id),
    workflow_name VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    trigger_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    current_node VARCHAR(100),
    context JSONB DEFAULT '{}'::jsonb,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    outcome JSONB,
    error_log TEXT,
    total_tokens_in INT DEFAULT 0,
    total_tokens_out INT DEFAULT 0,
    total_cost_usd DOUBLE PRECISION DEFAULT 0.0
);

-- Agent Run Records (Per-node execution log)
CREATE TABLE IF NOT EXISTS agent_run_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    instance_id UUID NOT NULL REFERENCES workflow_instances(id) ON DELETE CASCADE,
    node_id VARCHAR(100) NOT NULL,
    agent_capability VARCHAR(100) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    cost_usd DOUBLE PRECISION DEFAULT 0.0,
    tokens_in INT DEFAULT 0,
    tokens_out INT DEFAULT 0,
    model_used VARCHAR(200),
    confidence DOUBLE PRECISION,
    duration_ms INT,
    error TEXT,
    tools_used JSONB DEFAULT '[]'::jsonb,
    -- Full structured output of the node (business result the UI renders),
    -- tied to (instance_id, node_id). Secrets redacted / size-capped by the app.
    output_data JSONB,
    completed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Approval Items (Review Queue / Action Center)
CREATE TABLE IF NOT EXISTS approval_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    instance_id UUID REFERENCES workflow_instances(id) ON DELETE CASCADE,
    node_id VARCHAR(100),
    review_type VARCHAR(100) NOT NULL,
    reason TEXT NOT NULL,
    context_brief TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    required_signatures INT DEFAULT 1,
    signatures JSONB DEFAULT '[]'::jsonb,
    decided_by VARCHAR(255),
    decided_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Evidence Records (Immutable Ledger)
CREATE TABLE IF NOT EXISTS evidence_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    instance_id UUID NOT NULL REFERENCES workflow_instances(id) ON DELETE CASCADE,
    evidence_json_path VARCHAR(500) NOT NULL,
    checksum VARCHAR(64),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Audit Events
CREATE TABLE IF NOT EXISTS audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    actor_id VARCHAR(255) NOT NULL,
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(100) NOT NULL,
    entity_id VARCHAR(255),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================================================
-- Row-Level Security (RLS) Policies
-- =============================================================================

ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE tool_connections ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_instances ENABLE ROW LEVEL SECURITY;
ALTER TABLE approval_items ENABLE ROW LEVEL SECURITY;

-- Helper function to extract user's organization_id from Supabase JWT app_metadata / user_metadata
CREATE OR REPLACE FUNCTION current_organization_id() RETURNS UUID AS $$
  SELECT COALESCE(
    (current_setting('request.jwt.claims', true)::json->'user_metadata'->>'organization_id')::UUID,
    (current_setting('request.jwt.claims', true)::json->'app_metadata'->>'organization_id')::UUID
  );
$$ LANGUAGE SQL STABLE;

-- RLS Policy: Organizations
CREATE POLICY org_isolation_policy ON organizations
    FOR ALL USING (id = current_organization_id());

-- RLS Policy: Tool Connections
CREATE POLICY tool_conn_isolation_policy ON tool_connections
    FOR ALL USING (organization_id = current_organization_id());

-- RLS Policy: Workflow Instances
CREATE POLICY workflow_instances_isolation_policy ON workflow_instances
    FOR ALL USING (organization_id = current_organization_id());

-- RLS Policy: Approval Items
CREATE POLICY approval_items_isolation_policy ON approval_items
    FOR ALL USING (organization_id = current_organization_id());
