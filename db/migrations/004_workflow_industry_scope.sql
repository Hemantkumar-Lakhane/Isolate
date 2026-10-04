-- =============================================================================
-- Migration 004: Workflow Catalog — Industry Scope columns
-- Adds `scope` and `industry` to workflow_catalog so per-vertical filtering works.
-- Safe to run multiple times (IF NOT EXISTS / DO NOTHING guards).
-- =============================================================================

-- Add scope column: GLOBAL (all orgs) or INDUSTRY (only matching orgs)
ALTER TABLE workflow_catalog
    ADD COLUMN IF NOT EXISTS scope    VARCHAR(20)  NOT NULL DEFAULT 'GLOBAL';

-- Add industry column: NULL for GLOBAL scope; org.industry value for INDUSTRY scope
ALTER TABLE workflow_catalog
    ADD COLUMN IF NOT EXISTS industry VARCHAR(100) NULL;

-- Index for fast per-industry lookups
CREATE INDEX IF NOT EXISTS idx_workflow_catalog_scope    ON workflow_catalog(scope);
CREATE INDEX IF NOT EXISTS idx_workflow_catalog_industry ON workflow_catalog(industry);

-- Back-fill known INDUSTRY workflows from the applicability map.
-- The sync code does this at runtime too, but we do it here so a fresh
-- migration run also fixes the data without needing a server restart.
UPDATE workflow_catalog SET scope = 'INDUSTRY', industry = 'healthcare'
WHERE key IN (
    'patient_intake_triage', 'provider_evidence_verification',
    'case_brief_summarization', 'coordinator_communication_copilot',
    'healthcare_patient_engagement'
);

UPDATE workflow_catalog SET scope = 'INDUSTRY', industry = 'finance'
WHERE key IN (
    'finance_expense_monitoring', 'finance_operations_pack',
    'fpa_copilot', 'quote_normalization_comparison', 'billing_agent'
);

UPDATE workflow_catalog SET scope = 'INDUSTRY', industry = 'real_estate'
WHERE key IN (
    're_listing_health_monitor', 're_tenant_flight_risk'
);

UPDATE workflow_catalog SET scope = 'INDUSTRY', industry = 'retail'
WHERE key IN ('retail_inventory_health');

UPDATE workflow_catalog SET scope = 'INDUSTRY', industry = 'saas'
WHERE key IN (
    'saas_churn_prevention', 'saas_pipeline_velocity', 'inbound_lead_to_demo',
    'lead_qualification_and_routing', 'lead_qualifier', 'demo_booker',
    'account_based_campaign_coordinator', 'campaign_orchestrator',
    'performance_engine', 'founder_content_to_demand', 'weekly_founder_growth_brief',
    'social_campaign', 'persona_builder', 'pipeline_content_operations',
    'journey_task_orchestration', 'ai_account_manager', 'account_signal_expansion',
    'marketing_to_sales_sla_monitor', 'investor_partnership_update',
    'case_study_repursposer', 'freshness_publishing_review', 'product_launch_sprint'
);

-- Explicitly mark GLOBAL workflows (no-op if they already have scope=GLOBAL default)
UPDATE workflow_catalog SET scope = 'GLOBAL', industry = NULL
WHERE key IN (
    'email_summarizer', 'compliance_monitor',
    'document_intake_extraction', 'content_factory', 'ops_playbook',
    'meeting_intelligence_followup'
);

-- Seed plan_workflow_entitlements for the FREE plan with GLOBAL workflows only.
-- (Starter/Growth/Enterprise are already seeded in Migration 003 for all workflows.)
-- This INSERT only runs if the workflow_catalog rows exist and the free plan exists.
INSERT INTO plan_workflow_entitlements (plan_id, workflow_id)
SELECT bp.id, wc.id
FROM   billing_plans bp
CROSS  JOIN workflow_catalog wc
WHERE  bp.slug = 'free'
  AND  wc.scope = 'GLOBAL'
  AND  wc.active = true
ON CONFLICT DO NOTHING;

-- Seed Starter plan with its own industry workflows too (not just productivity/sales).
-- Starter should see email_summarizer + global tools at minimum.
INSERT INTO plan_workflow_entitlements (plan_id, workflow_id)
SELECT bp.id, wc.id
FROM   billing_plans bp
CROSS  JOIN workflow_catalog wc
WHERE  bp.slug = 'starter'
  AND  wc.active = true
ON CONFLICT DO NOTHING;

-- Growth plan: all workflows
INSERT INTO plan_workflow_entitlements (plan_id, workflow_id)
SELECT bp.id, wc.id
FROM   billing_plans bp
CROSS  JOIN workflow_catalog wc
WHERE  bp.slug IN ('growth', 'enterprise')
  AND  wc.active = true
ON CONFLICT DO NOTHING;
