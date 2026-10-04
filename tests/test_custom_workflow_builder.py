"""
tests/test_custom_workflow_builder.py
======================================
Tests for Custom Workflow Builder API and Engine:
- DAG cycle detection & validation
- Custom workflow creation, compiling to disk, and database catalog upsert
- Auto-assignment to organizations and billing plan entitlements
- Sandbox dry-run test simulation
- Tools library endpoint
"""

import pytest
import uuid
import json
from pathlib import Path
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select

from api.main import app
from api.auth import create_access_token
from api.dependencies import get_db
from db.models.core import (
    Base, Organization, WorkflowCatalog, BillingPlan,
    PlanWorkflowEntitlement, OrganizationWorkflowAssignment,
)
from api.routers.admin import _validate_dag_graph

from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from fastapi import HTTPException

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return compiler.visit_JSON(JSON(), **kw)

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


@pytest.mark.anyio
async def test_dag_cycle_detection():
    """Verify that acyclic DAG passes validation and cyclical graphs raise HTTP 400."""
    valid_dag = {
        "nodes": [
            {"id": "node_1", "agent": "research_agent"},
            {"id": "node_2", "agent": "reasoning_agent"},
            {"id": "node_3", "agent": "execution_agent"},
        ],
        "edges": [
            {"source": "node_1", "target": "node_2"},
            {"source": "node_2", "target": "node_3"},
        ]
    }
    # Should not raise
    _validate_dag_graph(valid_dag)

    cyclic_dag = {
        "nodes": [
            {"id": "node_a", "agent": "research_agent"},
            {"id": "node_b", "agent": "reasoning_agent"},
        ],
        "edges": [
            {"source": "node_a", "target": "node_b"},
            {"source": "node_b", "target": "node_a"},
        ]
    }
    with pytest.raises(HTTPException) as exc_info:
        _validate_dag_graph(cyclic_dag)
    assert exc_info.value.status_code == 400
    assert "Cycle detected" in exc_info.value.detail


@pytest.mark.anyio
async def test_custom_workflow_creation_and_auto_assignment(client, admin_headers, test_db_session):
    """Verify that POST /api/v1/admin/workflows/custom validates, saves to disk & DB, and auto-assigns."""
    # 1. Create Org & Plan to test assignment
    org_id = uuid.uuid4()
    org = Organization(id=org_id, name="Auto Assign Test Org", industry="saas", active=True)
    test_db_session.add(org)

    plan = BillingPlan(
        id=uuid.uuid4(),
        name="Starter Plan",
        slug="starter",
        monthly_price_usd=49.0,
        status="active"
    )
    test_db_session.add(plan)
    await test_db_session.commit()

    # 2. Publish Custom Workflow
    custom_key = "customer_lead_enricher"
    payload = {
        "name": "Customer Lead Enricher",
        "key": custom_key,
        "description": "Enriches inbound sales leads with AI reasoning",
        "category": "sales",
        "industry": "saas",
        "scope": "GLOBAL",
        "trigger_type": "webhook",
        "sla_hours": 3,
        "dag": {
            "nodes": [
                {"id": "trig_in", "agent": "trigger_webhook", "name": "Inbound Lead Webhook"},
                {"id": "agent_res", "agent": "research_agent", "name": "Company Research"},
                {"id": "agent_draft", "agent": "drafting_agent", "name": "Outreach Draft"},
            ],
            "edges": [
                {"source": "trig_in", "target": "agent_res"},
                {"source": "agent_res", "target": "agent_draft"},
            ]
        },
        "assign_to_org_ids": [str(org_id)],
        "assign_to_plan_slugs": ["starter"],
    }

    resp = await client.post("/api/v1/admin/workflows/custom", json=payload, headers=admin_headers)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["workflow"]["key"] == custom_key
    assert data["assigned_orgs_count"] == 1
    assert "starter" in data["entitled_plans"]

    # 3. Verify file written to workflows/dags/
    dag_file = Path("workflows/dags") / f"{custom_key}.json"
    assert dag_file.exists()

    # 4. Verify test-run sandbox endpoint
    test_run_resp = await client.post(
        f"/api/v1/admin/workflows/{custom_key}/test-run",
        json={"input_payload": {"email": "ceo@testcorp.com"}, "mock_mode": True},
        headers=admin_headers,
    )
    assert test_run_resp.status_code == 200, test_run_resp.text
    tr_data = test_run_resp.json()
    assert tr_data["status"] == "completed"
    assert tr_data["total_nodes_executed"] == 3
    assert len(tr_data["steps"]) == 3

    # 5. Verify tools library endpoint
    tools_resp = await client.get("/api/v1/admin/tools/library", headers=admin_headers)
    assert tools_resp.status_code == 200
    t_data = tools_resp.json()
    assert "triggers" in t_data
    assert "agents" in t_data
    assert "logic" in t_data
    assert "tools" in t_data
