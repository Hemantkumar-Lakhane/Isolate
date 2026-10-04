"""
db/seed/workflow_scope_seed.py
================================
Idempotent seed script: backfill scope + industry on all workflow_catalog rows.

Run this once after applying Migration 004 on an existing database, or whenever
a new workflow needs its applicability corrected.

Usage:
    python db/seed/workflow_scope_seed.py
    python db/seed/workflow_scope_seed.py --dry-run   # preview without writing

The authoritative applicability map lives here AND in
core/workflow_catalog_sync._WORKFLOW_APPLICABILITY (kept in sync).
The startup sync already calls this logic automatically, so this script is
only needed for one-off repairs or verification.

Exit codes:
  0  — success (or dry-run complete)
  1  — database error
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# ── Authoritative scope/industry map ─────────────────────────────────────────
# Must stay in sync with core/workflow_catalog_sync._WORKFLOW_APPLICABILITY.
# scope:    'GLOBAL'   — available to all industries
#           'INDUSTRY' — only for orgs whose industry matches
# industry: lowercase string matching organizations.industry values

WORKFLOW_APPLICABILITY: dict[str, dict] = {
    # ── Healthcare / Medical Tourism ─────────────────────────────────────────
    # organizations.industry = 'healthcare'
    "patient_intake_triage":               {"scope": "INDUSTRY", "industry": "healthcare"},
    "provider_evidence_verification":      {"scope": "INDUSTRY", "industry": "healthcare"},
    "case_brief_summarization":            {"scope": "INDUSTRY", "industry": "healthcare"},
    "coordinator_communication_copilot":   {"scope": "INDUSTRY", "industry": "healthcare"},
    "healthcare_patient_engagement":       {"scope": "INDUSTRY", "industry": "healthcare"},

    # ── Finance ──────────────────────────────────────────────────────────────
    # organizations.industry = 'finance'
    "finance_expense_monitoring":          {"scope": "INDUSTRY", "industry": "finance"},
    "finance_operations_pack":             {"scope": "INDUSTRY", "industry": "finance"},
    "fpa_copilot":                         {"scope": "INDUSTRY", "industry": "finance"},
    "quote_normalization_comparison":      {"scope": "INDUSTRY", "industry": "finance"},
    "billing_agent":                       {"scope": "INDUSTRY", "industry": "finance"},

    # ── Real Estate ──────────────────────────────────────────────────────────
    # organizations.industry = 'real_estate'
    "re_listing_health_monitor":           {"scope": "INDUSTRY", "industry": "real_estate"},
    "re_tenant_flight_risk":               {"scope": "INDUSTRY", "industry": "real_estate"},

    # ── Retail ───────────────────────────────────────────────────────────────
    # organizations.industry = 'retail'
    "retail_inventory_health":             {"scope": "INDUSTRY", "industry": "retail"},

    # ── SaaS / Growth ────────────────────────────────────────────────────────
    # organizations.industry = 'saas'
    "saas_churn_prevention":               {"scope": "INDUSTRY", "industry": "saas"},
    "saas_pipeline_velocity":              {"scope": "INDUSTRY", "industry": "saas"},
    "inbound_lead_to_demo":                {"scope": "INDUSTRY", "industry": "saas"},
    "lead_qualification_and_routing":      {"scope": "INDUSTRY", "industry": "saas"},
    "lead_qualifier":                      {"scope": "INDUSTRY", "industry": "saas"},
    "demo_booker":                         {"scope": "INDUSTRY", "industry": "saas"},
    "account_based_campaign_coordinator":  {"scope": "INDUSTRY", "industry": "saas"},
    "campaign_orchestrator":               {"scope": "INDUSTRY", "industry": "saas"},
    "performance_engine":                  {"scope": "INDUSTRY", "industry": "saas"},
    "founder_content_to_demand":           {"scope": "INDUSTRY", "industry": "saas"},
    "weekly_founder_growth_brief":         {"scope": "INDUSTRY", "industry": "saas"},
    "social_campaign":                     {"scope": "INDUSTRY", "industry": "saas"},
    "persona_builder":                     {"scope": "INDUSTRY", "industry": "saas"},
    "pipeline_content_operations":         {"scope": "INDUSTRY", "industry": "saas"},
    "journey_task_orchestration":          {"scope": "INDUSTRY", "industry": "saas"},
    "ai_account_manager":                  {"scope": "INDUSTRY", "industry": "saas"},
    "account_signal_expansion":            {"scope": "INDUSTRY", "industry": "saas"},
    "marketing_to_sales_sla_monitor":      {"scope": "INDUSTRY", "industry": "saas"},
    "investor_partnership_update":         {"scope": "INDUSTRY", "industry": "saas"},
    "case_study_repursposer":              {"scope": "INDUSTRY", "industry": "saas"},
    "freshness_publishing_review":         {"scope": "INDUSTRY", "industry": "saas"},
    "product_launch_sprint":               {"scope": "INDUSTRY", "industry": "saas"},

    # ── Global ────────────────────────────────────────────────────────────────
    # Available to ALL industries — subject to plan + assignment only.
    "email_summarizer":                    {"scope": "GLOBAL",   "industry": None},
    "compliance_monitor":                  {"scope": "GLOBAL",   "industry": None},
    "document_intake_extraction":          {"scope": "GLOBAL",   "industry": None},
    "content_factory":                     {"scope": "GLOBAL",   "industry": None},
    "ops_playbook":                        {"scope": "GLOBAL",   "industry": None},
    "meeting_intelligence_followup":       {"scope": "GLOBAL",   "industry": None},
}


async def seed_workflow_scope(dry_run: bool = False) -> dict:
    """
    Apply scope/industry to all matching rows in workflow_catalog.
    Returns { updated: int, skipped: int, not_found: list[str] }.
    """
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
    from core.database import DATABASE_URL
    from db.models.core import WorkflowCatalog

    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    updated    = 0
    skipped    = 0
    not_found: list[str] = []

    async with async_session() as session:
        for wf_key, applicability in WORKFLOW_APPLICABILITY.items():
            result = await session.execute(
                select(WorkflowCatalog).where(WorkflowCatalog.key == wf_key)
            )
            wf = result.scalar_one_or_none()

            if wf is None:
                not_found.append(wf_key)
                print(f"  [NOT FOUND] {wf_key}")
                continue

            desired_scope    = applicability["scope"]
            desired_industry = applicability["industry"]
            current_scope    = getattr(wf, "scope",    "GLOBAL") or "GLOBAL"
            current_industry = getattr(wf, "industry", None)

            needs_update = (current_scope != desired_scope or current_industry != desired_industry)

            if not needs_update:
                skipped += 1
                print(f"  [OK]      {wf_key:<45}  scope={current_scope}, industry={current_industry}")
                continue

            if dry_run:
                print(f"  [DRY-RUN] {wf_key:<45}  {current_scope}/{current_industry}  →  {desired_scope}/{desired_industry}")
                updated += 1
                continue

            wf.scope    = desired_scope
            wf.industry = desired_industry
            updated += 1
            print(f"  [UPDATE]  {wf_key:<45}  scope={desired_scope}, industry={desired_industry}")

        if not dry_run and updated > 0:
            await session.commit()

    await engine.dispose()

    return {
        "updated":   updated,
        "skipped":   skipped,
        "not_found": not_found,
        "dry_run":   dry_run,
    }


async def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Seed workflow scope/industry into workflow_catalog")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing to DB")
    args = parser.parse_args()

    print("=" * 60)
    print(f"SMBFlow — Workflow Scope Seed {'(DRY RUN) ' if args.dry_run else ''}")
    print("=" * 60)
    print(f"Total workflows in applicability map: {len(WORKFLOW_APPLICABILITY)}")
    global_count   = sum(1 for v in WORKFLOW_APPLICABILITY.values() if v["scope"] == "GLOBAL")
    industry_count = sum(1 for v in WORKFLOW_APPLICABILITY.values() if v["scope"] == "INDUSTRY")
    print(f"  Global:   {global_count}")
    print(f"  Industry: {industry_count}")
    print()

    try:
        result = await seed_workflow_scope(dry_run=args.dry_run)
    except Exception as e:
        print(f"[ERROR] Seed failed: {e}")
        sys.exit(1)

    print()
    print("=" * 60)
    print(f"Results:")
    print(f"  Updated:   {result['updated']}")
    print(f"  Skipped:   {result['skipped']} (already correct)")
    print(f"  Not found: {len(result['not_found'])} (not in DB yet — will sync on next startup)")
    if result["not_found"]:
        for k in result["not_found"]:
            print(f"    - {k}")
    if args.dry_run:
        print()
        print("  (Dry run — no changes written)")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
