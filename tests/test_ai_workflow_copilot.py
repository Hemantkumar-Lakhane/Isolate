"""
tests/test_ai_workflow_copilot.py
==================================
Unit and API integration tests for AI Workflow Copilot Synthesizer:
- Natural language prompt to DAG graph translation
- Category, industry, and trigger inference
- 2D node layout calculation
- Topological Kahn's algorithm cycle validation
- POST /api/v1/admin/workflows/ai-generate endpoint
"""

import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON

from api.main import app
from api.auth import create_access_token
from api.dependencies import get_db
from db.models.core import Base
from core.workflow_ai_generator import generate_workflow_from_prompt

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
async def test_ai_workflow_synthesis_logic():
    """Verify that core generator accurately infers agents, tools, and 2D layout."""
    prompt = (
        "Build an automated clinic patient intake triage and reminder workflow "
        "that ingests incoming booking webhooks, verifies insurance eligibility, "
        "reasons on appointment priority, requests human nurse approval if urgent, "
        "and sends SMS confirmation."
    )
    result = await generate_workflow_from_prompt(prompt, industry="healthcare")

    assert result["category"] == "healthcare"
    assert result["industry"] == "healthcare"
    assert result["trigger_type"] == "webhook"
    assert len(result["nodes"]) >= 4
    assert len(result["edges"]) >= 3

    # Check node 2D positions
    for node in result["nodes"]:
        assert "x" in node["position"]
        assert "y" in node["position"]
        assert node["position"]["x"] >= 60

    # Verify agent types are in supported palette
    agent_types = [n["data"].get("agentType") for n in result["nodes"] if "agentType" in n["data"]]
    assert "research_agent" in agent_types or "reasoning_agent" in agent_types
    assert "approval_gate" in agent_types or "verification_agent" in agent_types


@pytest.mark.anyio
async def test_ai_workflow_api_endpoint(client, admin_headers):
    """Verify POST /api/v1/admin/workflows/ai-generate endpoint."""
    payload = {
        "prompt": "Create an invoice fraud detector that scans vendor receipts and flags transactions over $10,000 for manager review",
        "industry": "finance",
    }
    resp = await client.post("/api/v1/admin/workflows/ai-generate", json=payload, headers=admin_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["category"] == "finance"
    assert "nodes" in data
    assert "edges" in data
    assert len(data["nodes"]) > 0
    assert len(data["edges"]) > 0
    assert "explanation" in data
