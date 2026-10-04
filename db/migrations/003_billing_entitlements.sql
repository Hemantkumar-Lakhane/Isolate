-- =============================================================================
-- Migration 003: Billing, Entitlements & Workflow Catalog
-- SMBFlow Platform Admin Control Plane
-- =============================================================================

-- ── Workflow Catalog ──────────────────────────────────────────────────────────
-- Platform-level catalog of all workflow products SMBFlow offers.
-- This is NOT per-org. It is the list of workflows the platform can provision.
CREATE TABLE IF NOT EXISTS workflow_catalog (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255) NOT NULL,
    key             VARCHAR(100) NOT NULL UNIQUE,   -- e.g. 'product_launch_sprint'
    description     TEXT,
    category        VARCHAR(100) NOT NULL DEFAULT 'general',
    status          VARCHAR(50)  NOT NULL DEFAULT 'active',  -- active | beta | deprecated
    version         VARCHAR(20)  NOT NULL DEFAULT '1.0.0',
    pricing_model   VARCHAR(50)  NOT NULL DEFAULT 'included', -- included | per_run | metered
    required_integrations JSONB  NOT NULL DEFAULT '[]',      -- array of tool_name strings
    supported_modules     JSONB  NOT NULL DEFAULT '[]',
    metadata        JSONB        NOT NULL DEFAULT '{}',
    active          BOOLEAN      NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_workflow_catalog_key    ON workflow_catalog(key);
CREATE INDEX IF NOT EXISTS idx_workflow_catalog_status ON workflow_catalog(status);
CREATE INDEX IF NOT EXISTS idx_workflow_catalog_active ON workflow_catalog(active);

-- ── Billing Plans ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS billing_plans (
    id                      UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    name                    VARCHAR(100) NOT NULL,           -- 'Free', 'Starter', 'Growth', 'Enterprise'
    slug                    VARCHAR(100) NOT NULL UNIQUE,    -- 'free', 'starter', 'growth', 'enterprise'
    description             TEXT,
    monthly_price_usd       NUMERIC(10,2) NOT NULL DEFAULT 0,
    annual_price_usd        NUMERIC(10,2) NOT NULL DEFAULT 0,
    -- Included quotas per billing period
    included_workflow_runs  INTEGER NOT NULL DEFAULT 0,      -- 0 = unlimited
    included_ai_tokens      BIGINT  NOT NULL DEFAULT 0,      -- 0 = unlimited
    included_image_gens     INTEGER NOT NULL DEFAULT 0,      -- 0 = unlimited
    included_users          INTEGER NOT NULL DEFAULT 1,      -- 0 = unlimited
    -- Overage pricing
    overage_run_price_usd   NUMERIC(10,6) NOT NULL DEFAULT 0,
    overage_token_price_usd NUMERIC(10,9) NOT NULL DEFAULT 0,
    overage_image_price_usd NUMERIC(10,6) NOT NULL DEFAULT 0,
    -- Caps (0 = unlimited)
    max_workflow_runs       INTEGER NOT NULL DEFAULT 0,
    max_users               INTEGER NOT NULL DEFAULT 0,
    -- Plan configuration
    status                  VARCHAR(50) NOT NULL DEFAULT 'active',  -- active | archived | hidden
    is_public               BOOLEAN     NOT NULL DEFAULT true,
    sort_order              INTEGER     NOT NULL DEFAULT 0,
    metadata                JSONB       NOT NULL DEFAULT '{}',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_billing_plans_slug   ON billing_plans(slug);
CREATE INDEX IF NOT EXISTS idx_billing_plans_status ON billing_plans(status);

-- ── Plan Workflow Entitlements ────────────────────────────────────────────────
-- Which workflow_catalog entries a plan includes.
CREATE TABLE IF NOT EXISTS plan_workflow_entitlements (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id     UUID NOT NULL REFERENCES billing_plans(id)    ON DELETE CASCADE,
    workflow_id UUID NOT NULL REFERENCES workflow_catalog(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(plan_id, workflow_id)
);

CREATE INDEX IF NOT EXISTS idx_plan_entitlements_plan     ON plan_workflow_entitlements(plan_id);
CREATE INDEX IF NOT EXISTS idx_plan_entitlements_workflow ON plan_workflow_entitlements(workflow_id);

-- ── Organization Subscriptions ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS organization_subscriptions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    plan_id             UUID NOT NULL REFERENCES billing_plans(id),
    status              VARCHAR(50) NOT NULL DEFAULT 'active',
    -- active | trialing | past_due | cancelled | paused
    billing_cycle       VARCHAR(20) NOT NULL DEFAULT 'monthly', -- monthly | annual
    current_period_start TIMESTAMPTZ NOT NULL DEFAULT now(),
    current_period_end   TIMESTAMPTZ NOT NULL DEFAULT (now() + INTERVAL '1 month'),
    trial_ends_at       TIMESTAMPTZ,
    cancelled_at        TIMESTAMPTZ,
    cancel_reason       TEXT,
    notes               TEXT,
    metadata            JSONB NOT NULL DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(organization_id)   -- one active subscription per org
);

CREATE INDEX IF NOT EXISTS idx_org_subscriptions_org    ON organization_subscriptions(organization_id);
CREATE INDEX IF NOT EXISTS idx_org_subscriptions_plan   ON organization_subscriptions(plan_id);
CREATE INDEX IF NOT EXISTS idx_org_subscriptions_status ON organization_subscriptions(status);

-- ── Organization Workflow Assignments ─────────────────────────────────────────
-- Admin explicitly assigns a workflow from the catalog to an organization.
-- Both plan entitlement AND explicit assignment are required for access.
CREATE TABLE IF NOT EXISTS organization_workflow_assignments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id)   ON DELETE CASCADE,
    workflow_id     UUID NOT NULL REFERENCES workflow_catalog(id) ON DELETE CASCADE,
    assigned_by     VARCHAR(255),   -- actor email/id who assigned this
    status          VARCHAR(50) NOT NULL DEFAULT 'active',  -- active | suspended
    config_override JSONB       NOT NULL DEFAULT '{}',      -- org-specific workflow config
    notes           TEXT,
    assigned_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(organization_id, workflow_id)
);

CREATE INDEX IF NOT EXISTS idx_workflow_assignments_org      ON organization_workflow_assignments(organization_id);
CREATE INDEX IF NOT EXISTS idx_workflow_assignments_workflow ON organization_workflow_assignments(workflow_id);
CREATE INDEX IF NOT EXISTS idx_workflow_assignments_status   ON organization_workflow_assignments(status);

-- ── Billing Periods ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS billing_periods (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    subscription_id     UUID REFERENCES organization_subscriptions(id),
    period_start        TIMESTAMPTZ NOT NULL,
    period_end          TIMESTAMPTZ NOT NULL,
    status              VARCHAR(50) NOT NULL DEFAULT 'open',   -- open | closed | invoiced
    -- Aggregated totals (populated at period close or on-demand)
    total_workflow_runs INTEGER     NOT NULL DEFAULT 0,
    total_tokens_in     BIGINT      NOT NULL DEFAULT 0,
    total_tokens_out    BIGINT      NOT NULL DEFAULT 0,
    total_token_cost_usd NUMERIC(12,6) NOT NULL DEFAULT 0,
    total_image_gens    INTEGER     NOT NULL DEFAULT 0,
    total_image_cost_usd NUMERIC(12,6) NOT NULL DEFAULT 0,
    total_cost_usd      NUMERIC(12,6) NOT NULL DEFAULT 0,
    -- Billable amounts (after plan inclusions)
    billable_runs       INTEGER     NOT NULL DEFAULT 0,
    billable_tokens     BIGINT      NOT NULL DEFAULT 0,
    billable_amount_usd NUMERIC(12,6) NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_billing_periods_org    ON billing_periods(organization_id);
CREATE INDEX IF NOT EXISTS idx_billing_periods_status ON billing_periods(status);
CREATE INDEX IF NOT EXISTS idx_billing_periods_dates  ON billing_periods(period_start, period_end);

-- ── Usage Records ─────────────────────────────────────────────────────────────
-- Granular per-event usage — one row per billable event.
CREATE TABLE IF NOT EXISTS usage_records (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    billing_period_id   UUID REFERENCES billing_periods(id),
    -- Traceable lineage
    workflow_id         UUID REFERENCES workflow_catalog(id),
    workflow_key        VARCHAR(100),         -- denormalized for fast queries
    workflow_instance_id UUID REFERENCES workflow_instances(id) ON DELETE SET NULL,
    agent_run_id        UUID,                 -- FK to agent_run_records, soft (no ON DELETE)
    -- Usage dimensions
    usage_type          VARCHAR(50) NOT NULL, -- workflow_run | llm_tokens | image_gen | tool_call
    provider            VARCHAR(100),         -- 'anthropic', 'openai', 'google', 'pollinations'
    model               VARCHAR(200),
    -- Quantities
    quantity            BIGINT      NOT NULL DEFAULT 1,  -- tokens, images, or runs
    tokens_in           BIGINT      NOT NULL DEFAULT 0,
    tokens_out          BIGINT      NOT NULL DEFAULT 0,
    -- Cost  (NULL = provider did not expose cost; 'Unavailable' shown in UI)
    cost_usd            NUMERIC(12,9),   -- NULL is meaningful: cost not reported
    -- Timestamps
    recorded_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_usage_records_org         ON usage_records(organization_id);
CREATE INDEX IF NOT EXISTS idx_usage_records_period      ON usage_records(billing_period_id);
CREATE INDEX IF NOT EXISTS idx_usage_records_workflow    ON usage_records(workflow_key);
CREATE INDEX IF NOT EXISTS idx_usage_records_instance   ON usage_records(workflow_instance_id);
CREATE INDEX IF NOT EXISTS idx_usage_records_type        ON usage_records(usage_type);
CREATE INDEX IF NOT EXISTS idx_usage_records_recorded    ON usage_records(recorded_at DESC);

-- ── Invoices ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS invoices (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    billing_period_id   UUID REFERENCES billing_periods(id),
    subscription_id     UUID REFERENCES organization_subscriptions(id),
    invoice_number      VARCHAR(50) UNIQUE,
    status              VARCHAR(50) NOT NULL DEFAULT 'draft',
    -- draft | open | paid | void | uncollectible
    subtotal_usd        NUMERIC(12,2) NOT NULL DEFAULT 0,
    tax_usd             NUMERIC(12,2) NOT NULL DEFAULT 0,
    total_usd           NUMERIC(12,2) NOT NULL DEFAULT 0,
    due_date            TIMESTAMPTZ,
    paid_at             TIMESTAMPTZ,
    voided_at           TIMESTAMPTZ,
    -- Payment provider integration (future)
    payment_provider    VARCHAR(50),    -- 'stripe', 'paddle', etc.
    external_invoice_id VARCHAR(255),   -- stripe invoice ID, etc.
    line_items          JSONB NOT NULL DEFAULT '[]',
    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_invoices_org    ON invoices(organization_id);
CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status);
CREATE INDEX IF NOT EXISTS idx_invoices_number ON invoices(invoice_number);

-- ── Platform Settings ─────────────────────────────────────────────────────────
-- Key-value store for platform-wide admin settings.
CREATE TABLE IF NOT EXISTS platform_settings (
    key         VARCHAR(255) PRIMARY KEY,
    value       JSONB        NOT NULL DEFAULT '{}',
    description TEXT,
    updated_by  VARCHAR(255),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- ── Triggers: updated_at ──────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at_column_v2()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE tbl TEXT;
BEGIN
  FOR tbl IN SELECT unnest(ARRAY[
    'workflow_catalog','billing_plans','organization_subscriptions',
    'organization_workflow_assignments','billing_periods','invoices'
  ]) LOOP
    EXECUTE format(
      'DROP TRIGGER IF EXISTS trg_%s_updated_at ON %I;
       CREATE TRIGGER trg_%s_updated_at
         BEFORE UPDATE ON %I
         FOR EACH ROW EXECUTE FUNCTION update_updated_at_column_v2();',
      tbl, tbl, tbl, tbl
    );
  END LOOP;
END;
$$;

-- ── Seed: Default Plans ───────────────────────────────────────────────────────
INSERT INTO billing_plans (name, slug, description, monthly_price_usd, annual_price_usd,
    included_workflow_runs, included_ai_tokens, included_image_gens, included_users,
    overage_run_price_usd, overage_token_price_usd, overage_image_price_usd,
    max_workflow_runs, max_users, status, is_public, sort_order)
VALUES
  ('Free',       'free',       'Free tier for evaluation',      0,     0,
   50,     500000,    10,  2, 0.00,    0.000001, 0.02, 50,   2, 'active', true, 0),
  ('Starter',    'starter',    'Small teams getting started',   49,    490,
   500,    5000000,   100, 5, 0.05,   0.000002, 0.02, 0,    5, 'active', true, 1),
  ('Growth',     'growth',     'Growing organizations',         199,   1990,
   2000,   20000000,  500, 20,0.04,   0.0000015,0.015,0,   20, 'active', true, 2),
  ('Enterprise', 'enterprise', 'Unlimited scale, custom terms', 0,     0,
   0,      0,         0,   0, 0.00,   0.000001, 0.01, 0,    0, 'active', false,3)
ON CONFLICT (slug) DO NOTHING;

-- ── Seed: Default Workflow Catalog ────────────────────────────────────────────
INSERT INTO workflow_catalog (name, key, description, category, status, version, pricing_model,
    required_integrations, supported_modules)
VALUES
  ('Email Summarizer',       'email_summarizer',      'AI-powered email triage and summarization',            'productivity',   'active', '1.0.0', 'included', '["gmail"]',              '["email"]'),
  ('Product Launch Sprint',  'product_launch_sprint', 'End-to-end product launch workflow with AI agents',    'marketing',      'active', '1.0.0', 'included', '[]',                     '["product_launch"]'),
  ('Medical Journey Ops',    'medical_journey_ops',   'Patient coordination and medical tourism workflow',    'healthcare',     'active', '1.0.0', 'included', '[]',                     '["medical_tourism"]'),
  ('Finance Operations',     'finance_operations',    'Financial reporting and reconciliation automation',    'finance',        'beta',   '0.9.0', 'included', '[]',                     '["finance"]'),
  ('CRM Intelligence',       'crm_intelligence',      'CRM data enrichment and follow-up automation',         'sales',          'beta',   '0.9.0', 'included', '["hubspot","salesforce"]','["crm"]'),
  ('Meeting Intelligence & Follow-up', 'meeting_intelligence_followup', 'Autonomous pipeline: audio transcription, relationship memory, action classification, and grounded follow-up email drafting', 'productivity', 'active', '1.0.0', 'included', '[]', '["meeting_intelligence"]')
ON CONFLICT (key) DO NOTHING;

-- ── Seed: Assign all workflows to Growth + Enterprise plans ──────────────────
-- (Free + Starter get subset only — assigned separately or by admin)
DO $$
DECLARE
  growth_id      UUID;
  enterprise_id  UUID;
  starter_id     UUID;
  wf             RECORD;
BEGIN
  SELECT id INTO growth_id     FROM billing_plans WHERE slug = 'growth'     LIMIT 1;
  SELECT id INTO enterprise_id FROM billing_plans WHERE slug = 'enterprise' LIMIT 1;
  SELECT id INTO starter_id    FROM billing_plans WHERE slug = 'starter'    LIMIT 1;

  FOR wf IN SELECT id, key FROM workflow_catalog LOOP
    -- Growth: all active workflows
    IF growth_id IS NOT NULL THEN
      INSERT INTO plan_workflow_entitlements (plan_id, workflow_id)
      VALUES (growth_id, wf.id) ON CONFLICT DO NOTHING;
    END IF;
    -- Enterprise: all workflows
    IF enterprise_id IS NOT NULL THEN
      INSERT INTO plan_workflow_entitlements (plan_id, workflow_id)
      VALUES (enterprise_id, wf.id) ON CONFLICT DO NOTHING;
    END IF;
    -- Starter: only email_summarizer and product_launch_sprint
    IF starter_id IS NOT NULL AND wf.key IN ('email_summarizer', 'product_launch_sprint') THEN
      INSERT INTO plan_workflow_entitlements (plan_id, workflow_id)
      VALUES (starter_id, wf.id) ON CONFLICT DO NOTHING;
    END IF;
  END LOOP;
END;
$$;
