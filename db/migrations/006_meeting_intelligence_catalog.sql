-- Migration 006: Seed meeting_intelligence_followup into workflow_catalog
-- ============================================================================
-- Root cause: the workflow was missing from the catalog seed in migration 003,
-- causing check_org_workflow_access to return
--   { allowed: false, reason: "Workflow 'meeting_intelligence_followup' not found in catalog" }
-- which rendered the "Workflow Access Restricted" wall (blank page) on the
-- /workflows/meeting_intelligence_followup route for all non-admin users.
--
-- This migration is idempotent (ON CONFLICT DO NOTHING / DO UPDATE) and safe
-- to run against any database state — fresh or already-migrated.
-- ============================================================================

-- ── 1. Insert the catalog row (no-op if it already exists) ───────────────────
INSERT INTO workflow_catalog (
    name,
    key,
    description,
    category,
    status,
    version,
    pricing_model,
    required_integrations,
    supported_modules
)
VALUES (
    'Meeting Intelligence & Follow-up',
    'meeting_intelligence_followup',
    'Autonomous pipeline: audio transcription via Whisper, relationship memory in PostgreSQL, action item classification, and grounded follow-up email drafting with human-in-the-loop review.',
    'productivity',
    'active',
    '1.0.0',
    'included',
    '[]',
    '["meeting_intelligence"]'
)
ON CONFLICT (key) DO UPDATE
    SET
        name        = EXCLUDED.name,
        description = EXCLUDED.description,
        status      = 'active',
        version     = EXCLUDED.version
    WHERE workflow_catalog.status != 'active'
       OR workflow_catalog.name != EXCLUDED.name;

-- ── 2. Ensure scope = GLOBAL (no-op if already set) ─────────────────────────
--    Migration 004 sets this via UPDATE, but only works if the row already
--    existed at that point. This makes it unconditional.
UPDATE workflow_catalog
SET    scope    = 'GLOBAL',
       industry = NULL
WHERE  key = 'meeting_intelligence_followup';

-- ── 3. Backfill plan_workflow_entitlements for all billing plans ─────────────
--    meeting_intelligence_followup is GLOBAL so it belongs on every plan.
--    ON CONFLICT DO NOTHING makes this safe to re-run.
INSERT INTO plan_workflow_entitlements (plan_id, workflow_id)
SELECT bp.id, wc.id
FROM   billing_plans    bp
JOIN   workflow_catalog wc ON wc.key = 'meeting_intelligence_followup'
WHERE  wc.active = true
ON CONFLICT DO NOTHING;

-- ── 4. Backfill org_workflow_assignments for any org that already has an
--    active subscription but is missing an explicit assignment.
--    This covers orgs created before this migration ran.
--    Uses the same "active subscription → assign all GLOBAL workflows" pattern
--    the admin panel uses when a subscription is activated.
INSERT INTO org_workflow_assignments (organization_id, workflow_id, status, assigned_at)
SELECT
    os.organization_id,
    wc.id,
    'active',
    now()
FROM   org_subscriptions    os
JOIN   workflow_catalog      wc  ON wc.key = 'meeting_intelligence_followup'
WHERE  os.status IN ('active', 'trialing')
  AND  wc.active = true
  AND  NOT EXISTS (
           SELECT 1
           FROM   org_workflow_assignments owa
           WHERE  owa.organization_id = os.organization_id
             AND  owa.workflow_id     = wc.id
       )
ON CONFLICT DO NOTHING;
