"""
tests/test_industry_workflow_access.py
========================================
Industry-aware workflow visibility, access-control, and billing tests.

Tests the core business logic layer (crud.py + models) directly,
without importing the full FastAPI application chain (which requires
litellm, asyncpg, and other heavy dependencies not available in this
test environment).

Covers all requirements from the spec:
  A. Healthcare org: sees Healthcare + Global, not Finance
  B. Finance org: sees Finance + Global, not Healthcare
  C. Real Estate org: sees Real Estate + Global only
  D. Plan entitlement: applicable workflow, plan doesn't include it → denied
  E. Admin assignment: applicable + entitled but not assigned → denied
  F. Trigger security: check_org_workflow_access rejects cross-industry access
     even when workflow is entitled + assigned
  G. Global workflow: available to multiple industries when entitled + assigned
  H. Billing: org usage summary only includes applicable/authorized workflows
  I. Multi-tenant isolation: Org A cannot access Org B's usage or workflows
  J. Existing checks preserved: org inactive, sub expired still block
"""

from __future__ import annotations

import pytest
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

# ── SQLite ↔ PostgreSQL JSONB shim ───────────────────────────────────────────
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON

@compiles(JSONB, "sqlite")
def _jsonb_sqlite(type_, compiler, **kw):
    return compiler.visit_JSON(JSON(), **kw)

# ── Project imports (models + crud only — no FastAPI app) ─────────────────────
from db.models.core import (
    Base, Organization, OrganizationUser,
    WorkflowCatalog, BillingPlan, PlanWorkflowEntitlement,
    OrganizationSubscription, OrganizationWorkflowAssignment,
    UsageRecord,
)
from api.crud import (
    check_org_workflow_access,
    get_available_workflows_for_org,
    get_org_billing_summary,
    record_usage,
)

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def db():
    """Fresh in-memory SQLite DB per test function."""
    engine = create_async_engine(TEST_DB_URL, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with Session() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


# ── DB helpers ────────────────────────────────────────────────────────────────

async def _make_org(db, name: str, industry: str) -> Organization:
    org = Organization(name=name, industry=industry, active=True)
    db.add(org)
    await db.flush()
    return org


async def _make_plan(db, slug: str = "growth") -> BillingPlan:
    plan = BillingPlan(
        name=slug.capitalize(), slug=slug + "_" + str(uuid.uuid4())[:8],
        monthly_price_usd=199, annual_price_usd=1990,
        included_workflow_runs=500, included_ai_tokens=0,
        included_image_gens=0, included_users=10,
        overage_run_price_usd=0, overage_token_price_usd=0,
        overage_image_price_usd=0, max_workflow_runs=0, max_users=0,
        status="active", is_public=True, sort_order=0,
    )
    db.add(plan)
    await db.flush()
    return plan


async def _make_sub(db, org: Organization, plan: BillingPlan,
                    status: str = "active", trial_ends_at=None) -> OrganizationSubscription:
    sub = OrganizationSubscription(
        organization_id=org.id, plan_id=plan.id, status=status,
        current_period_start=datetime.utcnow(),
        current_period_end=datetime.utcnow() + timedelta(days=30),
        trial_ends_at=trial_ends_at,
    )
    db.add(sub)
    await db.flush()
    return sub


async def _make_workflow(db, key: str, name: str, scope: str,
                         industry: str | None, category: str = "general") -> WorkflowCatalog:
    wf = WorkflowCatalog(
        name=name, key=key + "_" + str(uuid.uuid4())[:6],
        description=f"Test {key}", category=category,
        status="active", version="1.0.0", pricing_model="included",
        required_integrations=[], supported_modules=[], active=True,
        scope=scope, industry=industry,
    )
    db.add(wf)
    await db.flush()
    return wf


async def _entitle(db, plan: BillingPlan, wf: WorkflowCatalog):
    db.add(PlanWorkflowEntitlement(plan_id=plan.id, workflow_id=wf.id))
    await db.flush()


async def _assign(db, org: Organization, wf: WorkflowCatalog,
                  status: str = "active") -> OrganizationWorkflowAssignment:
    a = OrganizationWorkflowAssignment(
        organization_id=org.id, workflow_id=wf.id,
        assigned_by="admin@test.com", status=status,
    )
    db.add(a)
    await db.flush()
    return a


# ─────────────────────────────────────────────────────────────────────────────
# A. Healthcare org sees Healthcare + Global, NOT Finance
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_A_healthcare_org_sees_healthcare_and_global_not_finance(db):
    org  = await _make_org(db, "ABC Healthcare", "healthcare")
    plan = await _make_plan(db)
    await _make_sub(db, org, plan)

    wf_hc  = await _make_workflow(db, "patient_intake",    "Patient Intake",    "INDUSTRY", "healthcare")
    wf_glb = await _make_workflow(db, "email_summarizer",  "Email Summarizer",  "GLOBAL",   None)
    wf_fin = await _make_workflow(db, "expense_monitoring","Expense Monitoring","INDUSTRY", "finance")
    await db.commit()

    applicable = await get_available_workflows_for_org(db, str(org.id))
    keys = {w.key for w in applicable}

    assert wf_hc.key  in keys,  "Healthcare workflow must be applicable for healthcare org"
    assert wf_glb.key in keys,  "Global workflow must be applicable for healthcare org"
    assert wf_fin.key not in keys, "Finance workflow must NOT be applicable for healthcare org"


# ─────────────────────────────────────────────────────────────────────────────
# B. Finance org sees Finance + Global, NOT Healthcare
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_B_finance_org_sees_finance_and_global_not_healthcare(db):
    org  = await _make_org(db, "Acme Finance", "finance")
    plan = await _make_plan(db)
    await _make_sub(db, org, plan)

    wf_fin = await _make_workflow(db, "fpa_copilot",      "FP&A Copilot",     "INDUSTRY", "finance")
    wf_glb = await _make_workflow(db, "compliance_mon",   "Compliance Monitor","GLOBAL",  None)
    wf_hc  = await _make_workflow(db, "case_brief",       "Case Briefing",    "INDUSTRY", "healthcare")
    await db.commit()

    applicable = await get_available_workflows_for_org(db, str(org.id))
    keys = {w.key for w in applicable}

    assert wf_fin.key in keys
    assert wf_glb.key in keys
    assert wf_hc.key  not in keys, "Healthcare workflow must NOT appear for finance org"


# ─────────────────────────────────────────────────────────────────────────────
# C. Real Estate org sees Real Estate + Global only
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_C_real_estate_org_sees_only_its_industry_and_global(db):
    org  = await _make_org(db, "PropCo", "real_estate")
    plan = await _make_plan(db)
    await _make_sub(db, org, plan)

    wf_re     = await _make_workflow(db, "listing_health", "Listing Health", "INDUSTRY", "real_estate")
    wf_glb    = await _make_workflow(db, "doc_intake",     "Document Intake", "GLOBAL",  None)
    wf_retail = await _make_workflow(db, "inventory",      "Inventory",       "INDUSTRY","retail")
    wf_fin    = await _make_workflow(db, "billing_agt",    "Billing Agent",   "INDUSTRY","finance")
    await db.commit()

    applicable = await get_available_workflows_for_org(db, str(org.id))
    keys = {w.key for w in applicable}

    assert wf_re.key  in keys
    assert wf_glb.key in keys
    assert wf_retail.key not in keys
    assert wf_fin.key    not in keys


# ─────────────────────────────────────────────────────────────────────────────
# D. Plan entitlement check: applicable but not entitled → denied
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_D_plan_entitlement_blocks_unapproved_workflow(db):
    org  = await _make_org(db, "HC Entitlement Test", "healthcare")
    plan = await _make_plan(db, "starter")
    await _make_sub(db, org, plan)

    wf = await _make_workflow(db, "provider_verif", "Provider Verification", "INDUSTRY", "healthcare")
    # NOT entitled — but is assigned
    await _assign(db, org, wf)
    await db.commit()

    result = await check_org_workflow_access(db, str(org.id), wf.key)
    assert not result["allowed"]
    assert "plan" in result["reason"].lower(), f"Expected plan denial, got: {result['reason']}"


# ─────────────────────────────────────────────────────────────────────────────
# E. Admin assignment check: entitled but not assigned → denied
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_E_assignment_required_even_when_entitled(db):
    org  = await _make_org(db, "HC Assignment Test", "healthcare")
    plan = await _make_plan(db)
    await _make_sub(db, org, plan)

    wf = await _make_workflow(db, "coord_comms", "Coordinator Comms", "INDUSTRY", "healthcare")
    await _entitle(db, plan, wf)
    # NOT assigned
    await db.commit()

    result = await check_org_workflow_access(db, str(org.id), wf.key)
    assert not result["allowed"]
    assert "assigned" in result["reason"].lower(), f"Expected assignment denial, got: {result['reason']}"


# ─────────────────────────────────────────────────────────────────────────────
# F. Trigger security: industry check blocks cross-industry even if assigned+entitled
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_F_industry_check_blocks_cross_industry_even_when_entitled_and_assigned(db):
    """
    Healthcare org has a finance workflow both entitled and assigned.
    The industry check (step 3) must fire before plan/assignment checks and deny it.
    """
    org  = await _make_org(db, "HC Trigger Security", "healthcare")
    plan = await _make_plan(db)
    await _make_sub(db, org, plan)

    wf_finance = await _make_workflow(db, "finance_trigger_sec", "Finance Workflow", "INDUSTRY", "finance")
    await _entitle(db, plan, wf_finance)
    await _assign(db, org, wf_finance)
    await db.commit()

    result = await check_org_workflow_access(db, str(org.id), wf_finance.key)
    assert not result["allowed"], "Cross-industry workflow must be denied"
    reason = result["reason"].lower()
    assert "industry" in reason or "finance" in reason or "healthcare" in reason, \
        f"Expected industry-related denial reason, got: {result['reason']}"


# ─────────────────────────────────────────────────────────────────────────────
# G. Global workflow: accessible to multiple industries
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_G_global_workflow_applicable_to_multiple_industries(db):
    hc_org  = await _make_org(db, "Global HC",  "healthcare")
    fin_org = await _make_org(db, "Global Fin", "finance")
    plan    = await _make_plan(db)
    await _make_sub(db, hc_org,  plan)
    await _make_sub(db, fin_org, plan)

    wf_global = await _make_workflow(db, "email_global", "Email Summarizer", "GLOBAL", None)
    await db.commit()

    hc_applicable  = await get_available_workflows_for_org(db, str(hc_org.id))
    fin_applicable = await get_available_workflows_for_org(db, str(fin_org.id))

    assert any(w.key == wf_global.key for w in hc_applicable),  "GLOBAL must appear for healthcare"
    assert any(w.key == wf_global.key for w in fin_applicable), "GLOBAL must appear for finance"


@pytest.mark.anyio
async def test_G_global_workflow_full_access_granted(db):
    """GLOBAL + entitled + assigned = allowed for any industry."""
    org  = await _make_org(db, "Retail Global Access", "retail")
    plan = await _make_plan(db)
    await _make_sub(db, org, plan)

    wf = await _make_workflow(db, "ops_playbook_g", "Ops Playbook", "GLOBAL", None)
    await _entitle(db, plan, wf)
    await _assign(db, org, wf)
    await db.commit()

    result = await check_org_workflow_access(db, str(org.id), wf.key)
    assert result["allowed"], f"Expected access granted, got: {result['reason']}"
    assert result.get("scope") == "GLOBAL"


# ─────────────────────────────────────────────────────────────────────────────
# H. Billing: org usage only includes applicable workflows
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_H_billing_summary_excludes_cross_industry_usage(db):
    """
    Healthcare org has usage for healthcare WF + finance WF + global WF.
    Billing summary must exclude the finance usage.
    """
    org  = await _make_org(db, "HC Billing", "healthcare")
    plan = await _make_plan(db)
    await _make_sub(db, org, plan)

    wf_hc  = await _make_workflow(db, "patient_billing", "Patient Billing WF", "INDUSTRY", "healthcare")
    wf_fin = await _make_workflow(db, "expense_billing", "Expense Billing WF", "INDUSTRY", "finance")
    wf_glb = await _make_workflow(db, "email_billing",   "Email Billing WF",   "GLOBAL",   None)
    await db.commit()

    await record_usage(db, str(org.id), "workflow_run", workflow_key=wf_hc.key,  quantity=10, cost_usd=1.00)
    await record_usage(db, str(org.id), "workflow_run", workflow_key=wf_fin.key, quantity=5,  cost_usd=0.50)
    await record_usage(db, str(org.id), "workflow_run", workflow_key=wf_glb.key, quantity=3,  cost_usd=0.30)
    await db.commit()

    summary = await get_org_billing_summary(db, str(org.id), days=30)
    assert "error" not in summary

    billing_keys = {row["workflow_key"] for row in summary["workflow_breakdown"]}
    assert wf_hc.key  in billing_keys,  "Healthcare WF usage must be included"
    assert wf_glb.key in billing_keys,  "Global WF usage must be included"
    assert wf_fin.key not in billing_keys, "Finance WF usage must be EXCLUDED from healthcare billing"

    total = summary["total_cost_usd"]
    assert total is not None
    assert abs(total - 1.30) < 0.01, f"Total should be ~1.30 (HC+Global), got {total}"


# ─────────────────────────────────────────────────────────────────────────────
# I. Multi-tenant isolation
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_I_billing_tenant_isolation(db):
    """Org A's billing must never contain Org B's usage."""
    org_a = await _make_org(db, "Org A HC",  "healthcare")
    org_b = await _make_org(db, "Org B Fin", "finance")
    plan  = await _make_plan(db)
    await _make_sub(db, org_a, plan)
    await _make_sub(db, org_b, plan)

    wf_hc  = await _make_workflow(db, "hc_iso",  "HC Iso",  "INDUSTRY", "healthcare")
    wf_fin = await _make_workflow(db, "fin_iso", "Fin Iso", "INDUSTRY", "finance")
    await db.commit()

    await record_usage(db, str(org_a.id), "workflow_run", workflow_key=wf_hc.key,  quantity=7, cost_usd=0.70)
    await record_usage(db, str(org_b.id), "workflow_run", workflow_key=wf_fin.key, quantity=4, cost_usd=0.40)
    await db.commit()

    summary_a = await get_org_billing_summary(db, str(org_a.id), days=30)
    summary_b = await get_org_billing_summary(db, str(org_b.id), days=30)

    keys_a = {r["workflow_key"] for r in summary_a["workflow_breakdown"]}
    keys_b = {r["workflow_key"] for r in summary_b["workflow_breakdown"]}

    assert wf_hc.key  in keys_a
    assert wf_fin.key not in keys_a, "Org B finance usage leaked into Org A!"
    assert wf_fin.key in keys_b
    assert wf_hc.key  not in keys_b, "Org A healthcare usage leaked into Org B!"


@pytest.mark.anyio
async def test_I_workflow_access_isolation_between_tenants(db):
    """Assignment for Org B must NOT grant access to Org A."""
    org_a = await _make_org(db, "Isolated A", "healthcare")
    org_b = await _make_org(db, "Isolated B", "healthcare")
    plan  = await _make_plan(db)
    await _make_sub(db, org_a, plan)
    await _make_sub(db, org_b, plan)

    wf = await _make_workflow(db, "shared_iso_wf", "Shared Isolation WF", "INDUSTRY", "healthcare")
    await _entitle(db, plan, wf)
    await _assign(db, org_b, wf)  # assigned to B only
    await db.commit()

    result_a = await check_org_workflow_access(db, str(org_a.id), wf.key)
    result_b = await check_org_workflow_access(db, str(org_b.id), wf.key)

    assert not result_a["allowed"], "Org A must not gain access via Org B's assignment"
    assert result_b["allowed"],     "Org B must have access"


# ─────────────────────────────────────────────────────────────────────────────
# J. Existing checks preserved
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_J_inactive_org_blocked(db):
    org  = await _make_org(db, "Inactive HC", "healthcare")
    org.active = False
    plan = await _make_plan(db)
    await _make_sub(db, org, plan)
    wf = await _make_workflow(db, "inactive_wf", "Inactive WF", "INDUSTRY", "healthcare")
    await _entitle(db, plan, wf)
    await _assign(db, org, wf)
    await db.commit()

    result = await check_org_workflow_access(db, str(org.id), wf.key)
    assert not result["allowed"]
    assert "active" in result["reason"].lower()


@pytest.mark.anyio
async def test_J_trial_expired_blocks_access(db):
    org  = await _make_org(db, "Trial Expired HC", "healthcare")
    plan = await _make_plan(db)
    await _make_sub(db, org, plan, status="trialing",
                    trial_ends_at=datetime.utcnow() - timedelta(days=1))
    wf = await _make_workflow(db, "trial_expired_wf", "Trial Expired WF", "INDUSTRY", "healthcare")
    await _entitle(db, plan, wf)
    await _assign(db, org, wf)
    await db.commit()

    result = await check_org_workflow_access(db, str(org.id), wf.key)
    assert not result["allowed"]
    assert "trial_expired" in result["reason"].lower() or "subscription" in result["reason"].lower()


@pytest.mark.anyio
async def test_J_happy_path_all_checks_pass(db):
    """Active org + active sub + industry match + entitled + assigned = allowed."""
    org  = await _make_org(db, "Happy Path HC", "healthcare")
    plan = await _make_plan(db)
    await _make_sub(db, org, plan)
    wf = await _make_workflow(db, "happy_path_wf", "Happy Path WF", "INDUSTRY", "healthcare")
    await _entitle(db, plan, wf)
    await _assign(db, org, wf)
    await db.commit()

    result = await check_org_workflow_access(db, str(org.id), wf.key)
    assert result["allowed"], f"Expected access granted, got: {result['reason']}"
    assert result.get("scope")    == "INDUSTRY"
    assert result.get("industry") == "healthcare"


# ─────────────────────────────────────────────────────────────────────────────
# Industry check ordering: fires BEFORE plan and assignment checks
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_industry_check_fires_before_plan_check(db):
    """
    Finance org tries healthcare workflow (even entitled + assigned).
    Denial reason must mention industry/healthcare, NOT plan.
    """
    org  = await _make_org(db, "Finance Tries HC", "finance")
    plan = await _make_plan(db)
    await _make_sub(db, org, plan)

    wf = await _make_workflow(db, "hc_only_order", "HC Order Test", "INDUSTRY", "healthcare")
    await _entitle(db, plan, wf)
    await _assign(db, org, wf)
    await db.commit()

    result = await check_org_workflow_access(db, str(org.id), wf.key)
    assert not result["allowed"]
    reason = result["reason"].lower()
    # Industry check must have fired — NOT plan check
    assert "industry" in reason or "healthcare" in reason or "finance" in reason, \
        f"Expected industry denial, got: {result['reason']}"
    assert "plan" not in reason, \
        f"Industry check should fire before plan check, got: {result['reason']}"


# ─────────────────────────────────────────────────────────────────────────────
# Billing summary response shape
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_billing_summary_response_shape(db):
    """get_org_billing_summary returns expected keys including industry."""
    org  = await _make_org(db, "Shape Test HC", "healthcare")
    plan = await _make_plan(db)
    await _make_sub(db, org, plan)
    await db.commit()

    summary = await get_org_billing_summary(db, str(org.id), days=30)
    assert "error"                  not in summary
    assert summary["industry"]      == "healthcare"
    assert "workflow_breakdown"     in summary
    assert "total_run_count"        in summary
    assert "period_days"            in summary
    assert summary["period_days"]   == 30
    assert isinstance(summary["workflow_breakdown"], list)
