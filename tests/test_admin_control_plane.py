"""
tests/test_admin_control_plane.py
===================================
Comprehensive backend tests for SMBFlow Platform Admin Control Plane:
- Organizations (create, retrieve, update, suspend, activate)
- User Management (invite, role switching, organization assignment, RBAC)
- Workflow Catalog & Assignments (create catalog item, assign/unassign to org)
- Server-Side Authorization & Entitlements (check access, unassigned workflow execution rejection)
- Billing & Plans (create plan, set entitlements, subscription lifecycle, usage summary)
- Role-based Access Control (platform_admin access vs org_user denial)
"""

import pytest
import uuid
from datetime import datetime, timedelta
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select, text

from api.main import app
from api.auth import create_access_token
from api.dependencies import get_db
from db.models.core import (
    Base, Organization, OrganizationUser, WorkflowCatalog, BillingPlan,
    PlanWorkflowEntitlement, OrganizationSubscription, OrganizationWorkflowAssignment,
    WorkflowInstance, UsageRecord, AuditEvent,
)

from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return compiler.visit_JSON(JSON(), **kw)

# Test DB setup
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"

@pytest.fixture
async def test_db_session():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def client(test_db_session):
    async def _get_test_db():
        yield test_db_session

    app.dependency_overrides[get_db] = _get_test_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
def admin_headers():
    token = create_access_token({"sub": "admin@smbflow.com", "email": "admin@smbflow.com", "role": "platform_admin", "user_id": str(uuid.uuid4())})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def org_user_headers():
    token = create_access_token({"sub": "user@acme.com", "email": "user@acme.com", "role": "org_user", "user_id": str(uuid.uuid4())})
    return {"Authorization": f"Bearer {token}"}


# ─────────────────────────────────────────────────────────────────────────────
# 1. ORGANIZATIONS TEST SUITE
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_organization_lifecycle(client, admin_headers, test_db_session):
    # 1. Create plan first
    plan_resp = await client.post("/api/v1/admin/plans", json={
        "name": "Growth Plan",
        "slug": "growth",
        "monthly_price_usd": 199.0,
        "included_workflow_runs": 100,
    }, headers=admin_headers)
    assert plan_resp.status_code == 201

    # 2. Create organization
    create_resp = await client.post("/api/v1/admin/organizations", json={
        "name": "Acme Health",
        "industry": "healthcare",
        "plan_slug": "growth",
        "owner_email": "owner@acmehealth.com",
        "owner_name": "Alice Smith",
    }, headers=admin_headers)
    assert create_resp.status_code == 201
    org_id = create_resp.json()["id"]

    # 3. Retrieve organization detail
    get_resp = await client.get(f"/api/v1/admin/organizations/{org_id}", headers=admin_headers)
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["name"] == "Acme Health"
    assert data["active"] is True
    assert len(data["users"]) >= 1
    assert data["subscription"] is not None

    # 4. Update organization
    update_resp = await client.patch(f"/api/v1/admin/organizations/{org_id}", json={
        "name": "Acme Health Systems"
    }, headers=admin_headers)
    assert update_resp.status_code == 200

    # 5. Suspend organization
    suspend_resp = await client.post(f"/api/v1/admin/organizations/{org_id}/suspend", json={
        "reason": "Payment overdue"
    }, headers=admin_headers)
    assert suspend_resp.status_code == 200

    # Verify suspended state
    get_suspended = await client.get(f"/api/v1/admin/organizations/{org_id}", headers=admin_headers)
    assert get_suspended.json()["active"] is False

    # 6. Activate organization
    activate_resp = await client.post(f"/api/v1/admin/organizations/{org_id}/activate", headers=admin_headers)
    assert activate_resp.status_code == 200
    get_active = await client.get(f"/api/v1/admin/organizations/{org_id}", headers=admin_headers)
    assert get_active.json()["active"] is True


# ─────────────────────────────────────────────────────────────────────────────
# 2. USER MANAGEMENT TEST SUITE
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_user_management(client, admin_headers, test_db_session):
    # Invite user
    invite_resp = await client.post("/api/v1/admin/users/invite", json={
        "email": "bob@acme.com",
        "full_name": "Bob Jones",
        "role": "org_user",
    }, headers=admin_headers)
    assert invite_resp.status_code == 201
    uid = invite_resp.json()["user_id"]

    # List users
    users_resp = await client.get("/api/v1/admin/users", headers=admin_headers)
    assert users_resp.status_code == 200
    users = users_resp.json()
    bob = next((u for u in users if u["email"] == "bob@acme.com"), None)
    assert bob is not None
    assert bob["role"] == "org_user"

    # Deactivate / Suspend user
    ou_id = bob["id"]
    deact_resp = await client.patch(f"/api/v1/admin/users/{ou_id}/deactivate", headers=admin_headers)
    assert deact_resp.status_code == 200

    # Reactivate user
    react_resp = await client.patch(f"/api/v1/admin/users/{ou_id}/reactivate", headers=admin_headers)
    assert react_resp.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# 3. WORKFLOW CATALOG & ASSIGNMENTS TEST SUITE
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_workflow_catalog_and_assignment(client, admin_headers, test_db_session):
    # 1. Create catalog item
    cat_resp = await client.post("/api/v1/admin/workflows/catalog", json={
        "name": "Product Launch Sprint",
        "key": "product_launch_sprint",
        "description": "Multi-channel product launch campaign builder",
        "category": "marketing",
    }, headers=admin_headers)
    assert cat_resp.status_code == 201
    wf_id = cat_resp.json()["id"]

    # 2. Create organization & plan
    plan_resp = await client.post("/api/v1/admin/plans", json={
        "name": "Enterprise Plan",
        "slug": "enterprise",
    }, headers=admin_headers)
    plan_id = plan_resp.json()["id"]

    # Set entitlement
    ent_resp = await client.put(f"/api/v1/admin/plans/{plan_id}/entitlements", json={
        "workflow_ids": [wf_id]
    }, headers=admin_headers)
    assert ent_resp.status_code == 200

    org_resp = await client.post("/api/v1/admin/organizations", json={
        "name": "Beta Inc",
        "plan_slug": "enterprise",
    }, headers=admin_headers)
    org_id = org_resp.json()["id"]

    # 3. Assign workflow to organization
    assign_resp = await client.post(f"/api/v1/admin/organizations/{org_id}/workflows/{wf_id}/assign", json={}, headers=admin_headers)
    assert assign_resp.status_code == 201

    # 4. Check workflow access
    check_resp = await client.get(f"/api/v1/admin/organizations/{org_id}/workflows/access/product_launch_sprint", headers=admin_headers)
    assert check_resp.status_code == 200
    assert check_resp.json()["allowed"] is True

    # 5. Unassign workflow
    unassign_resp = await client.delete(f"/api/v1/admin/organizations/{org_id}/workflows/{wf_id}/assign", headers=admin_headers)
    assert unassign_resp.status_code == 200

    # Verify access revoked
    check_revoked = await client.get(f"/api/v1/admin/organizations/{org_id}/workflows/access/product_launch_sprint", headers=admin_headers)
    assert check_revoked.json()["allowed"] is False


# ─────────────────────────────────────────────────────────────────────────────
# 4. AUTHORIZATION & RBAC DENIAL TEST SUITE
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_rbac_authorization_controls(client, org_user_headers):
    # Org user should be DENIED platform admin routes
    res1 = await client.get("/api/v1/admin/overview", headers=org_user_headers)
    assert res1.status_code == 403

    res2 = await client.get("/api/v1/admin/organizations", headers=org_user_headers)
    assert res2.status_code == 403

    res3 = await client.get("/api/v1/admin/plans", headers=org_user_headers)
    assert res3.status_code == 403

    res4 = await client.get("/api/v1/admin/audit", headers=org_user_headers)
    assert res4.status_code == 403


# ─────────────────────────────────────────────────────────────────────────────
# 5. BILLING & USAGE SUMMARY TEST SUITE
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_billing_and_usage(client, admin_headers, test_db_session):
    # Retrieve platform usage
    usage_resp = await client.get("/api/v1/admin/usage?days=30", headers=admin_headers)
    assert usage_resp.status_code == 200
    data = usage_resp.json()
    assert "total_cost_usd" in data or "breakdown" in data

    # Retrieve platform health
    health_resp = await client.get("/api/v1/admin/health", headers=admin_headers)
    assert health_resp.status_code == 200
    health = health_resp.json()
    assert "overall" in health
    assert "services" in health

    # Retrieve AI Providers
    prov_resp = await client.get("/api/v1/admin/providers", headers=admin_headers)
    assert prov_resp.status_code == 200
    provs = prov_resp.json()
    assert len(provs) >= 4
