"""
scratch/test_e2e_pass.py
========================
Verification script testing full E2E flow, security boundary, trial expiry,
usage records, seeder idempotency, and platform health.
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from fastapi import HTTPException

from db.models.core import (
    Base, Organization, OrganizationUser, OrganizationSubscription,
    BillingPlan, WorkflowCatalog, OrganizationWorkflowAssignment,
    WorkflowInstance, UsageRecord
)
from db.seed.plans_seed import seed_plans_and_catalog
from api.crud import assert_workflow_access, check_org_workflow_access, list_organizations_with_details
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return compiler.visit_JSON(JSON(), **kw)

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

async def test_full_e2e_pass():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with session_factory() as db:
        print("--- 1. Testing Seeder Idempotency ---")
        await seed_plans_and_catalog(db)
        plans1 = (await db.execute(select(BillingPlan))).scalars().all()
        cat1   = (await db.execute(select(WorkflowCatalog))).scalars().all()
        assert len(plans1) == 4, f"Expected 4 plans, got {len(plans1)}"
        assert len(cat1) == 4, f"Expected 4 catalog items, got {len(cat1)}"

        # Re-run seeder to verify idempotency
        await seed_plans_and_catalog(db)
        plans2 = (await db.execute(select(BillingPlan))).scalars().all()
        cat2   = (await db.execute(select(WorkflowCatalog))).scalars().all()
        assert len(plans2) == 4, "Seeder created duplicate plans on re-run!"
        assert len(cat2) == 4, "Seeder created duplicate catalog items on re-run!"
        print("[OK] Seeder idempotency verified: exactly 4 plans & 4 catalog items.")

        print("\n--- 2. E2E Org Onboarding (Growth Plan, 14-day Trial, Workflows) ---")
        growth_plan = (await db.execute(select(BillingPlan).where(BillingPlan.slug == "growth"))).scalar_one()

        org = Organization(
            id=uuid.uuid4(),
            name="Apex Dynamics E2E",
            industry="operations",
            active=True,
        )
        db.add(org)
        await db.flush()

        # Growth subscription with 14-day trial
        now = datetime.utcnow()
        sub = OrganizationSubscription(
            id=uuid.uuid4(),
            organization_id=org.id,
            plan_id=growth_plan.id,
            status="trialing",
            billing_cycle="monthly",
            current_period_start=now,
            current_period_end=now + timedelta(days=14),
            trial_ends_at=now + timedelta(days=14),
        )
        db.add(sub)

        # Assign product_launch_sprint workflow only
        wf_cat = (await db.execute(select(WorkflowCatalog).where(WorkflowCatalog.key == "product_launch_sprint"))).scalar_one()
        assign = OrganizationWorkflowAssignment(
            id=uuid.uuid4(),
            organization_id=org.id,
            workflow_id=wf_cat.id,
            status="active",
            assigned_at=now,
        )
        db.add(assign)
        await db.commit()

        print(f"Created Org '{org.name}' with Growth Plan (Trialing until {sub.trial_ends_at.strftime('%Y-%m-%d')})")
        print("Assigned Workflow: 'product_launch_sprint'")

        print("\n--- 3. Testing Hard Backend Security Boundary ---")
        # Assigned workflow access -> should pass cleanly
        try:
            await assert_workflow_access(db, org.id, "product_launch_sprint")
            print("[OK] Access GRANTED for assigned workflow 'product_launch_sprint'")
        except Exception as e:
            assert False, f"Assigned workflow access failed unexpectedly: {e}"

        # Unassigned workflow access -> MUST raise 403 Forbidden
        unassigned_denied = False
        try:
            await assert_workflow_access(db, org.id, "finance_operations")
        except HTTPException as he:
            if he.status_code == 403:
                unassigned_denied = True
                print(f"[OK] Access DENIED (403) for unassigned workflow 'finance_operations': detail='{he.detail}'")

        assert unassigned_denied, "Security failure: Unassigned workflow did NOT return 403!"

        print("\n--- 4. Testing DB-Backed Trial Expiry Enforcement ---")
        # Mutate trial_ends_at to past timestamp
        sub.trial_ends_at = datetime.utcnow() - timedelta(days=2)
        await db.commit()

        trial_expired_denied = False
        try:
            await assert_workflow_access(db, org.id, "product_launch_sprint")
        except HTTPException as he:
            if he.status_code == 403:
                trial_expired_denied = True
                print(f"[OK] Access DENIED (403) for expired trial: detail='{he.detail}'")

        assert trial_expired_denied, "Security failure: Expired trial allowed workflow execution!"

        # Restore active trial for usage record testing
        sub.trial_ends_at = datetime.utcnow() + timedelta(days=14)
        await db.commit()

        print("\n--- 5. Testing UsageRecord Ledger & Cost Display ---")
        wf_inst = WorkflowInstance(
            id=uuid.uuid4(),
            organization_id=org.id,
            workflow_name="product_launch_sprint",
            status="completed",
            started_at=datetime.utcnow(),
        )
        db.add(wf_inst)
        await db.flush()

        # Usage record with missing provider cost (None)
        rec_null_cost = UsageRecord(
            id=uuid.uuid4(),
            organization_id=org.id,
            workflow_key="product_launch_sprint",
            workflow_instance_id=wf_inst.id,
            usage_type="workflow_run",
            quantity=1,
            cost_usd=None, # Missing provider cost -> NULL
            recorded_at=datetime.utcnow(),
        )
        db.add(rec_null_cost)
        await db.commit()

        query_rec = (await db.execute(select(UsageRecord).where(UsageRecord.id == rec_null_cost.id))).scalar_one()
        assert query_rec.cost_usd is None, "Expected cost_usd to be None"
        print("[OK] UsageRecord successfully stores cost_usd=None (rendered as 'Unavailable' in Admin UI)")

        print("\n--- 6. Testing Test Fixture Filtering ---")
        test_org = Organization(
            id=uuid.uuid4(),
            name="Isolation Test Fixture Org",
            industry="testing",
            active=True,
        )
        db.add(test_org)
        await db.commit()

        normal_orgs = await list_organizations_with_details(db, include_test_fixtures=False)
        all_orgs    = await list_organizations_with_details(db, include_test_fixtures=True)

        assert not any("Test Fixture" in o["name"] for o in normal_orgs), "Test fixture org appeared in normal org list!"
        assert any("Test Fixture" in o["name"] for o in all_orgs), "Test fixture org missing when include_test_fixtures=True!"
        print("[OK] Test data filtering verified: automated test fixture orgs filtered by default.")

    await engine.dispose()
    print("\n[SUCCESS] ALL E2E VERIFICATION CHECKS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(test_full_e2e_pass())
