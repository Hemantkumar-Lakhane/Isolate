"""
tests/test_meeting_intelligence_registration.py
================================================
Automated verification for 'Meeting Intelligence & Follow-up' workflow registration,
cross-industry global scope eligibility, plan entitlements, and organization assignments.
"""

import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select

from api.main import app
from api.dependencies import get_db
from core.workflow_catalog_sync import _dag_to_catalog_entry, _DAGS_DIR
from db.models.core import (
    Base, Organization, WorkflowCatalog, BillingPlan,
    PlanWorkflowEntitlement, OrganizationSubscription, OrganizationWorkflowAssignment,
)
import api.crud as crud

from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return compiler.visit_JSON(JSON(), **kw)

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture
async def test_db():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.mark.anyio
async def test_dag_file_and_catalog_entry():
    """Verify that meeting_intelligence_followup.json exists and resolves to GLOBAL productivity workflow."""
    dag_path = _DAGS_DIR / "meeting_intelligence_followup.json"
    assert dag_path.exists(), "DAG file meeting_intelligence_followup.json must exist in workflows/dags"

    entry = _dag_to_catalog_entry(dag_path)
    assert entry is not None
    assert entry["key"] == "meeting_intelligence_followup"
    assert entry["name"] == "Meeting Intelligence & Follow-up"
    assert entry["category"] == "productivity"
    assert entry["scope"] == "GLOBAL"
    assert entry["industry"] is None
    assert entry["active"] is True


@pytest.mark.anyio
async def test_cross_industry_eligibility_and_filtering(test_db: AsyncSession):
    """
    Verify that Meeting Intelligence & Follow-up is applicable across multiple industries
    (SaaS, Healthcare, Finance) while industry-specific workflows remain properly restricted.
    """
    # 1. Create catalog entries
    global_wf = WorkflowCatalog(
        id=uuid.uuid4(),
        name="Meeting Intelligence & Follow-up",
        key="meeting_intelligence_followup",
        description="Converts conversations into structured memory",
        category="productivity",
        scope="GLOBAL",
        industry=None,
        active=True,
    )
    healthcare_wf = WorkflowCatalog(
        id=uuid.uuid4(),
        name="Patient Intake Triage",
        key="patient_intake_triage",
        description="Healthcare patient intake",
        category="healthcare",
        scope="INDUSTRY",
        industry="healthcare",
        active=True,
    )
    finance_wf = WorkflowCatalog(
        id=uuid.uuid4(),
        name="Finance Expense Monitoring",
        key="finance_expense_monitoring",
        description="Finance expense monitor",
        category="finance",
        scope="INDUSTRY",
        industry="finance",
        active=True,
    )
    test_db.add_all([global_wf, healthcare_wf, finance_wf])
    await test_db.commit()

    # 2. Create organizations in different industries
    saas_org = Organization(id=uuid.uuid4(), name="SaaS Corp", industry="saas", active=True)
    health_org = Organization(id=uuid.uuid4(), name="Metro Health", industry="healthcare", active=True)
    finance_org = Organization(id=uuid.uuid4(), name="Apex Capital", industry="finance", active=True)
    test_db.add_all([saas_org, health_org, finance_org])
    await test_db.commit()

    # 3. Test applicability for SaaS org
    saas_applicable = await crud.get_available_workflows_for_org(test_db, str(saas_org.id))
    saas_keys = {w.key for w in saas_applicable}
    assert "meeting_intelligence_followup" in saas_keys, "Meeting Intelligence must be applicable to SaaS"
    assert "patient_intake_triage" not in saas_keys, "Healthcare workflow must NOT be applicable to SaaS"
    assert "finance_expense_monitoring" not in saas_keys, "Finance workflow must NOT be applicable to SaaS"

    # 4. Test applicability for Healthcare org
    health_applicable = await crud.get_available_workflows_for_org(test_db, str(health_org.id))
    health_keys = {w.key for w in health_applicable}
    assert "meeting_intelligence_followup" in health_keys, "Meeting Intelligence must be applicable to Healthcare"
    assert "patient_intake_triage" in health_keys, "Healthcare workflow must be applicable to Healthcare"
    assert "finance_expense_monitoring" not in health_keys, "Finance workflow must NOT be applicable to Healthcare"

    # 5. Test applicability for Finance org
    finance_applicable = await crud.get_available_workflows_for_org(test_db, str(finance_org.id))
    finance_keys = {w.key for w in finance_applicable}
    assert "meeting_intelligence_followup" in finance_keys, "Meeting Intelligence must be applicable to Finance"
    assert "finance_expense_monitoring" in finance_keys, "Finance workflow must be applicable to Finance"
    assert "patient_intake_triage" not in finance_keys, "Healthcare workflow must NOT be applicable to Finance"


@pytest.mark.anyio
async def test_access_requires_subscription_entitlement_and_assignment(test_db: AsyncSession):
    """
    Verify that even though Meeting Intelligence is GLOBAL in scope, it strictly enforces:
    - Active organization
    - Active subscription
    - Plan entitlement
    - Explicit workflow assignment
    """
    # Create workflow
    wf = WorkflowCatalog(
        id=uuid.uuid4(),
        name="Meeting Intelligence & Follow-up",
        key="meeting_intelligence_followup",
        category="productivity",
        scope="GLOBAL",
        industry=None,
        active=True,
    )
    test_db.add(wf)

    # Create plan
    plan = BillingPlan(
        id=uuid.uuid4(),
        name="Growth",
        slug="growth",
        monthly_price_usd=199.0,
        status="active",
    )
    test_db.add(plan)
    await test_db.flush()

    # Create org
    org = Organization(id=uuid.uuid4(), name="Alpha Corp", industry="saas", active=True)
    test_db.add(org)
    await test_db.flush()

    # Case A: No subscription -> Access Denied
    res = await crud.check_org_workflow_access(test_db, str(org.id), "meeting_intelligence_followup")
    assert res["allowed"] is False
    assert "No active subscription" in res["reason"]

    # Add subscription
    sub = OrganizationSubscription(
        id=uuid.uuid4(),
        organization_id=org.id,
        plan_id=plan.id,
        status="active",
    )
    test_db.add(sub)
    await test_db.flush()

    # Case B: Subscription exists but Plan has no entitlement -> Access Denied
    res = await crud.check_org_workflow_access(test_db, str(org.id), "meeting_intelligence_followup")
    assert res["allowed"] is False
    assert "does not include" in res["reason"]

    # Entitle plan
    ent = PlanWorkflowEntitlement(plan_id=plan.id, workflow_id=wf.id)
    test_db.add(ent)
    await test_db.flush()

    # Case C: Plan entitles workflow but not assigned to org -> Access Denied
    res = await crud.check_org_workflow_access(test_db, str(org.id), "meeting_intelligence_followup")
    assert res["allowed"] is False
    assert "has not been assigned" in res["reason"]

    # Assign workflow to org
    assign = OrganizationWorkflowAssignment(
        id=uuid.uuid4(),
        organization_id=org.id,
        workflow_id=wf.id,
        status="active",
        assigned_by="platform_admin",
    )
    test_db.add(assign)
    await test_db.commit()

    # Case D: All checks pass -> Access Granted
    res = await crud.check_org_workflow_access(test_db, str(org.id), "meeting_intelligence_followup")
    assert res["allowed"] is True
    assert res["reason"] == "Access granted"


@pytest.mark.anyio
async def test_auto_assign_excludes_workflows_requiring_explicit_assignment(test_db: AsyncSession):
    """
    Verify that auto_assign_industry_workflows:
      1. Automatically assigns standard starter workflows (e.g. email_summarizer)
      2. Does NOT auto-assign workflows flagged with requires_explicit_assignment = True (meeting_intelligence_followup)
    """
    plan = BillingPlan(
        id=uuid.uuid4(),
        name="Enterprise",
        slug="enterprise_test",
        monthly_price_usd=499.0,
        status="active",
    )
    test_db.add(plan)

    # Global starter workflow (auto-assign eligible)
    starter_wf = WorkflowCatalog(
        id=uuid.uuid4(),
        name="AI Inbox Triage & Email Summarizer",
        key="email_summarizer",
        category="productivity",
        scope="GLOBAL",
        active=True,
        metadata_={},
    )
    test_db.add(starter_wf)

    # Meeting Intelligence (requires explicit assignment)
    meeting_wf = WorkflowCatalog(
        id=uuid.uuid4(),
        name="Meeting Intelligence & Follow-up",
        key="meeting_intelligence_followup",
        category="productivity",
        scope="GLOBAL",
        active=True,
        metadata_={"requires_explicit_assignment": True},
    )
    test_db.add(meeting_wf)
    await test_db.flush()

    # Entitle both in the plan
    test_db.add(PlanWorkflowEntitlement(plan_id=plan.id, workflow_id=starter_wf.id))
    test_db.add(PlanWorkflowEntitlement(plan_id=plan.id, workflow_id=meeting_wf.id))
    await test_db.flush()

    # Create new org in SaaS industry
    new_org = Organization(id=uuid.uuid4(), name="Beta Technologies", industry="saas", active=True)
    test_db.add(new_org)
    await test_db.flush()

    # Run auto_assign_industry_workflows
    count = await crud.auto_assign_industry_workflows(
        test_db,
        organization_id=str(new_org.id),
        industry="saas",
        assigned_by="system",
        plan_slug="enterprise_test",
    )
    assert count >= 1

    # Query assignments for new_org
    assign_res = await test_db.execute(
        select(OrganizationWorkflowAssignment.workflow_id)
        .where(OrganizationWorkflowAssignment.organization_id == new_org.id)
    )
    assigned_ids = {str(r[0]) for r in assign_res.all()}

    # starter_wf MUST be auto-assigned
    assert str(starter_wf.id) in assigned_ids, "Starter workflow email_summarizer must be auto-assigned"
    # meeting_wf MUST NOT be auto-assigned
    assert str(meeting_wf.id) not in assigned_ids, "meeting_intelligence_followup must NOT be auto-assigned"


@pytest.mark.anyio
async def test_multi_tenant_three_org_isolation_and_dynamic_assignment(test_db: AsyncSession):
    """
    Multi-tenant isolation verification across 3 organizations:
      Org A (Healthcare): Explicitly assigned -> Visible, Active, Execution Allowed
      Org B (Finance):    Not assigned        -> Inactive/Not Assigned, Execution 403 Forbidden
      Org C (SaaS):       Not assigned        -> Inactive/Not Assigned, Execution 403 Forbidden

    Then assign Org B:
      Org B -> Becomes Active, Execution Allowed
      Org A -> Unaffected (Active)
      Org C -> Unaffected (Still Blocked)
    """
    from fastapi import HTTPException

    # 1. Setup meeting intelligence workflow
    meeting_wf = WorkflowCatalog(
        id=uuid.uuid4(),
        name="Meeting Intelligence & Follow-up",
        key="meeting_intelligence_followup",
        category="productivity",
        scope="GLOBAL",
        industry=None,
        active=True,
        metadata_={"requires_explicit_assignment": True},
    )
    test_db.add(meeting_wf)

    # 2. Setup shared Growth plan with entitlement
    plan = BillingPlan(
        id=uuid.uuid4(),
        name="Growth",
        slug="growth_multi",
        monthly_price_usd=199.0,
        status="active",
    )
    test_db.add(plan)
    await test_db.flush()

    test_db.add(PlanWorkflowEntitlement(plan_id=plan.id, workflow_id=meeting_wf.id))

    # 3. Create Org A (Healthcare), Org B (Finance), Org C (SaaS)
    org_a = Organization(id=uuid.uuid4(), name="Hospital System A", industry="healthcare", active=True)
    org_b = Organization(id=uuid.uuid4(), name="FinTech Capital B", industry="finance", active=True)
    org_c = Organization(id=uuid.uuid4(), name="Cloud SaaS C", industry="saas", active=True)
    test_db.add_all([org_a, org_b, org_c])
    await test_db.flush()

    # Active subscriptions for all 3
    for org in (org_a, org_b, org_c):
        test_db.add(OrganizationSubscription(
            id=uuid.uuid4(),
            organization_id=org.id,
            plan_id=plan.id,
            status="active",
        ))
    await test_db.flush()

    # 4. Explicitly assign meeting_intelligence_followup ONLY to Org A
    test_db.add(OrganizationWorkflowAssignment(
        id=uuid.uuid4(),
        organization_id=org_a.id,
        workflow_id=meeting_wf.id,
        status="active",
        assigned_by="admin@smbflow.com",
    ))
    await test_db.commit()

    # ── Phase 1 Verification ──────────────────────────────────────────────────
    # Org A: Allowed
    res_a = await crud.check_org_workflow_access(test_db, str(org_a.id), "meeting_intelligence_followup")
    assert res_a["allowed"] is True
    assert res_a["reason"] == "Access granted"
    assert (await crud.assert_workflow_access(test_db, str(org_a.id), "meeting_intelligence_followup"))["allowed"] is True

    # Org B: Blocked
    res_b = await crud.check_org_workflow_access(test_db, str(org_b.id), "meeting_intelligence_followup")
    assert res_b["allowed"] is False
    assert "has not been assigned" in res_b["reason"]
    with pytest.raises(HTTPException) as exc_b:
        await crud.assert_workflow_access(test_db, str(org_b.id), "meeting_intelligence_followup")
    assert exc_b.value.status_code == 403

    # Org C: Blocked
    res_c = await crud.check_org_workflow_access(test_db, str(org_c.id), "meeting_intelligence_followup")
    assert res_c["allowed"] is False
    assert "has not been assigned" in res_c["reason"]
    with pytest.raises(HTTPException) as exc_c:
        await crud.assert_workflow_access(test_db, str(org_c.id), "meeting_intelligence_followup")
    assert exc_c.value.status_code == 403

    # ── Phase 2: Explicitly assign Org B ──────────────────────────────────────
    test_db.add(OrganizationWorkflowAssignment(
        id=uuid.uuid4(),
        organization_id=org_b.id,
        workflow_id=meeting_wf.id,
        status="active",
        assigned_by="admin@smbflow.com",
    ))
    await test_db.commit()

    # Org B: Now Allowed
    res_b2 = await crud.check_org_workflow_access(test_db, str(org_b.id), "meeting_intelligence_followup")
    assert res_b2["allowed"] is True
    assert res_b2["reason"] == "Access granted"
    assert (await crud.assert_workflow_access(test_db, str(org_b.id), "meeting_intelligence_followup"))["allowed"] is True

    # Org A: Unaffected (Still Allowed)
    res_a2 = await crud.check_org_workflow_access(test_db, str(org_a.id), "meeting_intelligence_followup")
    assert res_a2["allowed"] is True

    # Org C: Unaffected (Still Denied 403)
    res_c2 = await crud.check_org_workflow_access(test_db, str(org_c.id), "meeting_intelligence_followup")
    assert res_c2["allowed"] is False
    with pytest.raises(HTTPException) as exc_c2:
        await crud.assert_workflow_access(test_db, str(org_c.id), "meeting_intelligence_followup")
    assert exc_c2.value.status_code == 403


@pytest.mark.anyio
async def test_catalog_visibility_shows_all_workflows_with_active_only_for_assigned(test_db: AsyncSession):
    """
    Verify the tenant catalog endpoint rule:
    - All workflows applicable to the organization are returned/visible.
    - Only the assigned workflows have status='active' and is_assigned=True.
    - Unassigned workflows have status='ready' and is_assigned=False.
    """
    from api.main import list_tenant_workflows
    from api.auth import TokenData

    # Create meeting workflow and standard workflow
    wf_meeting = WorkflowCatalog(
        id=uuid.uuid4(),
        name="Meeting Intelligence & Follow-up",
        key="meeting_intelligence_followup",
        category="productivity",
        scope="GLOBAL",
        active=True,
    )
    wf_standard = WorkflowCatalog(
        id=uuid.uuid4(),
        name="Email Summarizer",
        key="email_summarizer",
        category="productivity",
        scope="GLOBAL",
        active=True,
    )
    test_db.add_all([wf_meeting, wf_standard])

    plan = BillingPlan(id=uuid.uuid4(), name="Free", slug="free", monthly_price_usd=0.0, status="active")
    test_db.add(plan)
    await test_db.flush()

    test_db.add(PlanWorkflowEntitlement(plan_id=plan.id, workflow_id=wf_meeting.id))
    test_db.add(PlanWorkflowEntitlement(plan_id=plan.id, workflow_id=wf_standard.id))

    org = Organization(id=uuid.uuid4(), name="Visibility Test Org", industry="saas", active=True)
    test_db.add(org)
    await test_db.flush()

    test_db.add(OrganizationSubscription(id=uuid.uuid4(), organization_id=org.id, plan_id=plan.id, status="active"))

    # Assign ONLY meeting_intelligence_followup
    test_db.add(OrganizationWorkflowAssignment(
        id=uuid.uuid4(),
        organization_id=org.id,
        workflow_id=wf_meeting.id,
        status="active",
        assigned_by="platform_admin",
    ))
    await test_db.commit()

    user_token = TokenData(user_id=str(uuid.uuid4()), email="owner@vis.test", role="org_owner", organization_id=str(org.id), tenant_id=str(org.id))

    # Call endpoint function
    items = await list_tenant_workflows(include_unassigned=True, current_user=user_token, db=test_db)
    
    item_map = {item["key"]: item for item in items}

    # BOTH workflows must be visible
    assert "meeting_intelligence_followup" in item_map
    assert "email_summarizer" in item_map

    # meeting_intelligence_followup was assigned -> Active & can_run=True
    assert item_map["meeting_intelligence_followup"]["is_assigned"] is True
    assert item_map["meeting_intelligence_followup"]["status"] == "active"
    assert item_map["meeting_intelligence_followup"]["can_run"] is True

    # email_summarizer was NOT assigned -> Ready & can_run=False
    assert item_map["email_summarizer"]["is_assigned"] is False
    assert item_map["email_summarizer"]["status"] == "ready"
    assert item_map["email_summarizer"]["can_run"] is False


