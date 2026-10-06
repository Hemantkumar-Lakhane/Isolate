"""
db/seed/plans_seed.py
======================
Idempotent database seeder for canonical SMBFlow billing plans and workflow catalog entries.
Ensures Free, Starter, Growth, and Enterprise plans exist in PostgreSQL with DB-driven pricing,
included resource limits, overage policies, and default workflow entitlements.
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from core.database import DATABASE_URL
from db.models.core import BillingPlan, WorkflowCatalog, PlanWorkflowEntitlement, Base


DEFAULT_CATALOG_ITEMS = [
    {
        "name": "Product Launch Sprint",
        "key": "product_launch_sprint",
        "description": "Multi-channel product launch campaign builder with authentic copy & visual asset generation.",
        "category": "marketing",
        "version": "1.0.0",
        "pricing_model": "included",
        "supported_modules": ["marketing", "product_launch"],
        "required_integrations": ["linkedin", "x", "instagram"],
        "scope": "GLOBAL",
        "industry": None,
    },
    {
        "name": "Email Summarizer",
        "key": "email_summarizer",
        "description": "Automated email inbox digest, sentiment analysis, priority ranking, and draft response generation.",
        "category": "productivity",
        "version": "1.0.0",
        "pricing_model": "included",
        "supported_modules": ["email"],
        "required_integrations": ["gmail"],
        # GLOBAL — available to all industries
        "scope": "GLOBAL",
        "industry": None,
    },
    {
        "name": "Meeting Intelligence & Follow-up",
        "key": "meeting_intelligence_followup",
        "description": "Converts professional conversations into structured memory, follow-up actions, and meeting preparation.",
        "category": "productivity",
        "version": "1.0.0",
        "pricing_model": "included",
        "supported_modules": ["meetings", "productivity"],
        "required_integrations": ["calendar", "email"],
        "scope": "GLOBAL",
        "industry": None,
    },
    {
        "name": "Medical Journey Operations",
        "key": "medical_journey_operations",
        "description": "Patient intake coordination, medical records parsing, appointment scheduling, and care follow-up.",
        "category": "healthcare",
        "version": "1.0.0",
        "pricing_model": "included",
        "supported_modules": ["healthcare", "medical_tourism"],
        "required_integrations": ["emr", "email"],
        "scope": "INDUSTRY",
        "industry": "healthcare",
    },
    {
        "name": "Finance & Operations",
        "key": "finance_operations",
        "description": "Expense processing, invoice reconciliation, vendor tracking, and automated budget anomaly alerts.",
        "category": "finance",
        "version": "1.0.0",
        "pricing_model": "included",
        "supported_modules": ["finance", "operations"],
        "required_integrations": ["stripe", "quickbooks"],
        "scope": "INDUSTRY",
        "industry": "finance",
    },
]


DEFAULT_PLANS = [
    {
        "name": "Free",
        "slug": "free",
        "description": "For small teams testing workflow automation capabilities.",
        "monthly_price_usd": 0.0,
        "annual_price_usd": 0.0,
        "included_workflow_runs": 10,
        "included_ai_tokens": 50000,
        "included_image_gens": 5,
        "included_users": 1,
        "overage_run_price_usd": 0.50,
        "overage_token_price_usd": 0.00001,
        "overage_image_price_usd": 0.20,
        "max_workflow_runs": 20,
        "max_users": 2,
        "status": "active",
        "is_public": True,
        "sort_order": 1,
        "entitled_keys": ["email_summarizer", "product_launch_sprint", "meeting_intelligence_followup"],
    },
    {
        "name": "Starter",
        "slug": "starter",
        "description": "For growing organizations streamlining core business workflows.",
        "monthly_price_usd": 49.0,
        "annual_price_usd": 470.0,
        "included_workflow_runs": 100,
        "included_ai_tokens": 500000,
        "included_image_gens": 50,
        "included_users": 3,
        "overage_run_price_usd": 0.35,
        "overage_token_price_usd": 0.000008,
        "overage_image_price_usd": 0.15,
        "max_workflow_runs": 250,
        "max_users": 5,
        "status": "active",
        "is_public": True,
        "sort_order": 2,
        "entitled_keys": ["email_summarizer", "product_launch_sprint", "finance_operations", "meeting_intelligence_followup"],
    },
    {
        "name": "Growth",
        "slug": "growth",
        "description": "Full multi-workflow platform access with higher throughput and team seats.",
        "monthly_price_usd": 199.0,
        "annual_price_usd": 1900.0,
        "included_workflow_runs": 500,
        "included_ai_tokens": 2500000,
        "included_image_gens": 200,
        "included_users": 10,
        "overage_run_price_usd": 0.25,
        "overage_token_price_usd": 0.000005,
        "overage_image_price_usd": 0.10,
        "max_workflow_runs": 1000,
        "max_users": 25,
        "status": "active",
        "is_public": True,
        "sort_order": 3,
        "entitled_keys": ["email_summarizer", "product_launch_sprint", "medical_journey_operations", "finance_operations", "meeting_intelligence_followup"],
    },
    {
        "name": "Enterprise",
        "slug": "enterprise",
        "description": "Unlimited scale, custom SLA, dedicated AI routing, and priority support.",
        "monthly_price_usd": 499.0,
        "annual_price_usd": 4790.0,
        "included_workflow_runs": 0,  # 0 = unlimited
        "included_ai_tokens": 0,       # 0 = unlimited
        "included_image_gens": 0,      # 0 = unlimited
        "included_users": 0,           # 0 = unlimited
        "overage_run_price_usd": 0.0,
        "overage_token_price_usd": 0.0,
        "overage_image_price_usd": 0.0,
        "max_workflow_runs": 0,
        "max_users": 0,
        "status": "active",
        "is_public": True,
        "sort_order": 4,
        "entitled_keys": ["email_summarizer", "product_launch_sprint", "medical_journey_operations", "finance_operations", "meeting_intelligence_followup"],
    },
]


async def seed_plans_and_catalog(session: AsyncSession) -> None:
    """Idempotently seed default workflow catalog items, plans, and entitlements."""

    # 1. Seed Catalog Items
    catalog_by_key = {}
    for item in DEFAULT_CATALOG_ITEMS:
        key = item["key"]
        result = await session.execute(select(WorkflowCatalog).where(WorkflowCatalog.key == key))
        existing = result.scalar_one_or_none()
        if not existing:
            cat = WorkflowCatalog(
                id=uuid.uuid4(),
                name=item["name"],
                key=key,
                description=item["description"],
                category=item["category"],
                version=item["version"],
                pricing_model=item["pricing_model"],
                supported_modules=item["supported_modules"],
                required_integrations=item["required_integrations"],
                active=True,
                scope=item.get("scope", "GLOBAL"),
                industry=item.get("industry"),
            )
            session.add(cat)
            await session.flush()
            catalog_by_key[key] = cat
        else:
            catalog_by_key[key] = existing

    # 2. Seed Plans & Entitlements
    for plan_data in DEFAULT_PLANS:
        slug = plan_data["slug"]
        result = await session.execute(select(BillingPlan).where(BillingPlan.slug == slug))
        plan = result.scalar_one_or_none()

        if not plan:
            plan = BillingPlan(
                id=uuid.uuid4(),
                name=plan_data["name"],
                slug=slug,
                description=plan_data["description"],
                monthly_price_usd=plan_data["monthly_price_usd"],
                annual_price_usd=plan_data["annual_price_usd"],
                included_workflow_runs=plan_data["included_workflow_runs"],
                included_ai_tokens=plan_data["included_ai_tokens"],
                included_image_gens=plan_data["included_image_gens"],
                included_users=plan_data["included_users"],
                overage_run_price_usd=plan_data["overage_run_price_usd"],
                overage_token_price_usd=plan_data["overage_token_price_usd"],
                overage_image_price_usd=plan_data["overage_image_price_usd"],
                max_workflow_runs=plan_data["max_workflow_runs"],
                max_users=plan_data["max_users"],
                status=plan_data["status"],
                is_public=plan_data["is_public"],
                sort_order=plan_data["sort_order"],
            )
            session.add(plan)
            await session.flush()

        # Seed entitlements
        for wf_key in plan_data.get("entitled_keys", []):
            cat_entry = catalog_by_key.get(wf_key)
            if cat_entry:
                ent_res = await session.execute(
                    select(PlanWorkflowEntitlement).where(
                        PlanWorkflowEntitlement.plan_id == plan.id,
                        PlanWorkflowEntitlement.workflow_id == cat_entry.id,
                    )
                )
                if not ent_res.scalar_one_or_none():
                    session.add(PlanWorkflowEntitlement(
                        id=uuid.uuid4(),
                        plan_id=plan.id,
                        workflow_id=cat_entry.id,
                    ))

    await session.commit()
    print("[OK] Successfully seeded default billing plans and workflow catalog entitlements.")


async def main():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as session:
        await seed_plans_and_catalog(session)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
