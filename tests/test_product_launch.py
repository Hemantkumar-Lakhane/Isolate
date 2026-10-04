"""
tests/test_product_launch.py
=============================
Automated test suite for SMBFlow Product Launch Sprint backend integration:
- Quick Fill AI brief extraction & JSON structuring
- Validation & error handling (502 Gateway on LLM provider error)
- Draft save and load persistence via WorkflowInstance
- Campaign creation (WorkflowInstance status='escalated', ApprovalItem records pending)
- Human post approval gating & audit logging without external publishing
- Tenant & Organization isolation
"""

import json
import uuid
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException

from api.auth import TokenData
from api.routers.product_launch import (
    ExtractBriefRequest, SaveDraftRequest, CreateCampaignRequest, UpdatePostRequest,
    extract_brief_with_ai, save_product_launch_draft,
    load_product_launch_draft, create_product_launch_campaign,
    approve_product_launch_post, reject_product_launch_post,
    update_product_launch_post, export_product_launch_campaign
)
from db.models.core import AgentRunRecord, ApprovalItem, AuditEvent, EvidenceRecord, ToolConnection, WorkflowInstance
from core.state_manager import WorkflowStatus


# Mock user tokens
TEST_ORG_ID = str(uuid.uuid4())
MOCK_USER = TokenData(
    user_id=str(uuid.uuid4()),
    email="owner@smallbusiness.com",
    role="org_admin",
    organization_id=TEST_ORG_ID,
    tenant_id=TEST_ORG_ID,
)


# In-memory mock AsyncSession for fast unit testing
class MockAsyncSession:
    def __init__(self):
        self.store = {}
        self.added = []

    def add(self, obj):
        if not hasattr(obj, 'id') or not obj.id:
            obj.id = uuid.uuid4()
        self.added.append(obj)
        self.store[str(obj.id)] = obj

    async def commit(self):
        pass

    async def refresh(self, obj):
        pass

    async def get(self, model, obj_id):
        return self.store.get(str(obj_id))

    async def execute(self, stmt):
        mock_res = MagicMock()
        items = list(self.store.values())

        target_model = None
        if hasattr(stmt, "column_descriptions") and stmt.column_descriptions:
            target_model = stmt.column_descriptions[0].get("type")

        if target_model and isinstance(target_model, type):
            items = [x for x in items if isinstance(x, target_model)]

        # Filter items by SQLAlchemy _where_criteria if present
        if hasattr(stmt, "_where_criteria") and stmt._where_criteria:
            for crit in stmt._where_criteria:
                try:
                    if hasattr(crit, "right") and hasattr(crit.right, "value"):
                        val = crit.right.value
                        if hasattr(crit, "left") and hasattr(crit.left, "key"):
                            key = crit.left.key
                            items = [x for x in items if hasattr(x, key) and getattr(x, key) == val]
                except Exception:
                    pass

        scalars_mock = MagicMock()
        scalars_mock.all.return_value = items
        scalars_mock.first.return_value = items[0] if items else None

        mock_res.scalars.return_value = scalars_mock
        mock_res.scalar_one_or_none.return_value = items[0] if items else None
        return mock_res


@pytest.fixture
def mock_db():
    return MockAsyncSession()


@pytest.mark.asyncio
async def test_extract_brief_empty_input():
    """Validates that empty brief text returns 400 Bad Request."""
    req = ExtractBriefRequest(launch_brief="   ")
    with pytest.raises(HTTPException) as exc_info:
        await extract_brief_with_ai(req, current_user=MOCK_USER)
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_extract_brief_ai_success():
    """Test AI Brief Quick-Fill returns structured JSON from LLMRouter response."""
    sample_brief = "We are launching TaskFlow Pro, project management built for small teams of 5-50 people. Saves 5+ hours/week. Launch date Oct 1, 2026. CTA: Try it free."
    
    mock_llm_output = json.dumps({
        "productName": "TaskFlow Pro",
        "shortDescription": "Project management built for small teams of 5-50 people",
        "launchDate": "Oct 1, 2026",
        "desiredCta": "Try it free",
        "targetAudience": "Small teams of 5-50 people",
        "customerType": "B2B",
        "valueProposition": "Project management built for small teams",
        "topBenefit1": "Saves 5+ hours/week",
        "toneOfVoice": "Professional",
        "launchObjective": "Product adoption"
    })

    with patch("api.routers.product_launch.LLMRouter") as mock_router_cls:
        mock_router_inst = AsyncMock()
        mock_router_inst.call.return_value = (mock_llm_output, MagicMock())
        mock_router_cls.return_value = mock_router_inst

        req = ExtractBriefRequest(launch_brief=sample_brief)
        resp = await extract_brief_with_ai(req, current_user=MOCK_USER)

        assert resp["productName"] == "TaskFlow Pro"
        assert resp["shortDescription"] == "Project management built for small teams of 5-50 people"
        assert resp["launchDate"] == "Oct 1, 2026"
        assert resp["desiredCta"] == "Try it free"
        assert resp["is_ai_generated"] is True


@pytest.mark.asyncio
async def test_extract_brief_provider_failure():
    """Test that LLM provider failure produces explicit 502 Bad Gateway response."""
    sample_brief = "Launching a new product."

    with patch("api.routers.product_launch.LLMRouter") as mock_router_cls:
        mock_router_inst = AsyncMock()
        mock_router_inst.call.side_effect = Exception("Anthropic API 500 Provider Unavailable")
        mock_router_cls.return_value = mock_router_inst

        req = ExtractBriefRequest(launch_brief=sample_brief)
        with pytest.raises(HTTPException) as exc_info:
            await extract_brief_with_ai(req, current_user=MOCK_USER)
        assert exc_info.value.status_code == 502
        assert "AI Provider unavailable" in exc_info.value.detail


@pytest.mark.asyncio
async def test_extract_brief_with_document_and_provenance():
    """Test AI extraction with user brief + uploaded document text and additionalContext."""
    user_brief = "Launch TaskFlow Pro on Oct 1. CTA: Book a demo."
    doc_name = "taskflow_spec.txt"
    doc_text = """TaskFlow Pro Product Brief:
Target Audience: Small accounting firms and tax consultants in India.
Value Proposition: Reduces weekly bookkeeping labor by 5+ hours using smart AI reconciliation.
Key Features: GST invoice import, bank reconciliation, automated tax reminders.
Competitor Note: Built for SMBs, 50% cheaper than QuickBooks.
Pricing: $29/month flat rate.
"""

    mock_llm_output = json.dumps({
        "productName": "TaskFlow Pro",
        "shortDescription": "Accounting software for Indian SMBs",
        "launchDate": "Oct 1, 2026",
        "desiredCta": "Book a demo",
        "targetAudience": "Small accounting firms and tax consultants in India",
        "customerType": "B2B",
        "valueProposition": "Reduces weekly bookkeeping labor by 5+ hours using smart AI reconciliation",
        "topBenefit1": "Reduces weekly bookkeeping labor by 5+ hours",
        "keyFeatures": "GST invoice import, bank reconciliation, automated tax reminders",
        "additionalContext": "Competitor Note: Built for SMBs, 50% cheaper than QuickBooks. Pricing: $29/month flat rate.",
        "provenance": {
            "productName": "user_message",
            "desiredCta": "user_message",
            "targetAudience": "uploaded_document",
            "valueProposition": "uploaded_document",
            "keyFeatures": "uploaded_document"
        }
    })

    with patch("api.routers.product_launch.LLMRouter") as mock_router_cls:
        mock_router_inst = AsyncMock()
        mock_router_inst.call.return_value = (mock_llm_output, MagicMock())
        mock_router_cls.return_value = mock_router_inst

        req = ExtractBriefRequest(
            launch_brief=user_brief,
            document_text=doc_text,
            document_name=doc_name
        )
        resp = await extract_brief_with_ai(req, current_user=MOCK_USER)

        assert resp["productName"] == "TaskFlow Pro"
        assert resp["desiredCta"] == "Book a demo"
        assert resp["targetAudience"] == "Small accounting firms and tax consultants in India"
        assert "50% cheaper than QuickBooks" in resp["additionalContext"]
        assert resp["provenance"]["targetAudience"] == "uploaded_document"


@pytest.mark.asyncio
async def test_extract_brief_null_product_name_and_null_provenance():
    """Regression test: verify that null productName and null values in provenance map cleanly without 500 ResponseValidationError."""
    user_brief = "Focus on saving time and reducing bookkeeping effort."
    
    mock_llm_output = json.dumps({
        "productName": None,
        "shortDescription": "Focus on saving time and reducing bookkeeping effort",
        "launchDate": None,
        "desiredCta": None,
        "targetAudience": "SMB owners",
        "provenance": {
            "productName": None,
            "shortDescription": "user_message",
            "launchDate": None,
            "targetAudience": "user_message"
        }
    })

    with patch("api.routers.product_launch.LLMRouter") as mock_router_cls:
        mock_router_inst = AsyncMock()
        mock_router_inst.call.return_value = (mock_llm_output, MagicMock())
        mock_router_cls.return_value = mock_router_inst

        req = ExtractBriefRequest(launch_brief=user_brief)
        resp = await extract_brief_with_ai(req, current_user=MOCK_USER)

        assert resp["productName"] is None
        assert resp["provenance"]["productName"] is None
        assert resp["provenance"]["targetAudience"] == "user_message"


@pytest.mark.asyncio
async def test_draft_persistence_and_org_isolation(mock_db):
    """Verify that Product Launch drafts save and load via WorkflowInstance with tenant isolation."""
    brief_data = {
        "productName": "TaskFlow Pro",
        "shortDescription": "SMB Project Tool",
        "launchDate": "Oct 1, 2026"
    }

    req = SaveDraftRequest(brief_data=brief_data)
    save_resp = await save_product_launch_draft(req, db=mock_db, current_user=MOCK_USER)
    assert save_resp["status"] == "draft_saved"
    assert save_resp["organization_id"] == TEST_ORG_ID

    # Load draft for same org
    load_resp = await load_product_launch_draft(db=mock_db, current_user=MOCK_USER)
    assert load_resp["brief_data"]["productName"] == "TaskFlow Pro"


@pytest.mark.asyncio
async def test_create_campaign_validation(mock_db):
    """Test that missing required brief fields raises 400 Error."""
    req = CreateCampaignRequest(brief_data={"productName": ""})
    with pytest.raises(HTTPException) as exc_info:
        await create_product_launch_campaign(req, db=mock_db, current_user=MOCK_USER)
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_create_campaign_execution_and_hitl(mock_db):
    """Verify campaign creation creates WorkflowInstance in 'escalated' status, EvidenceRecord, AgentRunRecord & ApprovalItem records."""
    brief_data = {
        "productName": "TaskFlow Pro",
        "shortDescription": "SMB project management",
        "desiredCta": "Try it free",
        "platforms": ["LinkedIn", "X"]
    }

    mock_llm_posts = json.dumps([
        {
            "platform": "LinkedIn",
            "category": "LAUNCH ANNOUNCEMENT",
            "scheduledTime": "Oct 1 - 9:00 AM",
            "caption": "Excited to launch TaskFlow Pro today!",
            "hashtags": ["#ProductLaunch"],
            "visualPrompt": "Minimalist blue hero banner for TaskFlow Pro"
        },
        {
            "platform": "X",
            "category": "LAUNCH ANNOUNCEMENT",
            "scheduledTime": "Oct 1 - 9:00 AM",
            "caption": "TaskFlow Pro is live on X!",
            "hashtags": ["#TaskFlowPro"],
            "visualPrompt": "Dark mode hero banner for X"
        }
    ])

    with patch("api.routers.product_launch.LLMRouter") as mock_router_cls:
        mock_router_inst = AsyncMock()
        mock_router_inst.call.return_value = (mock_llm_posts, MagicMock())
        mock_router_cls.return_value = mock_router_inst

        req = CreateCampaignRequest(brief_data=brief_data)
        resp = await create_product_launch_campaign(req, db=mock_db, current_user=MOCK_USER)

        assert resp["status"] == WorkflowStatus.ESCALATED.value
        assert len(resp["posts"]) == 2

        # Verify WorkflowInstance in added objects
        wf_inst = next((o for o in mock_db.added if isinstance(o, WorkflowInstance)), None)
        assert wf_inst is not None
        assert wf_inst.status == WorkflowStatus.ESCALATED.value

        # Verify AgentRunRecord in added objects
        agent_run = next((o for o in mock_db.added if isinstance(o, AgentRunRecord)), None)
        assert agent_run is not None
        assert agent_run.node_id == "draft_assets"

        # Verify EvidenceRecord in added objects
        ev_rec = next((o for o in mock_db.added if isinstance(o, EvidenceRecord)), None)
        assert ev_rec is not None
        assert "product_launch_" in ev_rec.evidence_json_path

        # Verify ApprovalItems in added objects
        apprs = [o for o in mock_db.added if isinstance(o, ApprovalItem)]
        assert len(apprs) == 2
        for a in apprs:
            assert a.status == "pending"
            assert a.review_type == "product_launch_post"
            assert a.payload["visual_status"] == "pending_generation"
            assert "visual_prompt" in a.payload


@pytest.mark.asyncio
async def test_human_approval_gating(mock_db):
    """Verify that approving a post updates ApprovalItem status & logs AuditEvent without external publishing."""
    org_uuid = uuid.UUID(TEST_ORG_ID)
    approval_id = uuid.uuid4()
    
    appr = ApprovalItem(
        id=approval_id,
        organization_id=org_uuid,
        review_type="product_launch_post",
        reason="Campaign post requires human approval",
        context_brief="TaskFlow Pro - LinkedIn",
        payload={"post_id": "li-1", "platform": "LinkedIn"},
        status="pending",
        created_at=datetime.utcnow(),
    )
    mock_db.add(appr)

    resp = await approve_product_launch_post(str(approval_id), db=mock_db, current_user=MOCK_USER)
    assert resp["status"] == "approved"
    assert resp["decided_by"] == MOCK_USER.email
    assert resp["external_publishing_executed"] is False  # Explicit check: No auto-publishing!

    # Verify ApprovalItem status updated to approved
    assert appr.status == "approved"
    assert appr.decided_by == MOCK_USER.email

    # Verify AuditEvent written to DB
    audit_evt = next((o for o in mock_db.added if isinstance(o, AuditEvent)), None)
    assert audit_evt is not None
    assert audit_evt.action == "product_launch_post_approved"


@pytest.mark.asyncio
async def test_human_rejection_gating(mock_db):
    """Verify that rejecting a post updates ApprovalItem status & logs AuditEvent."""
    org_uuid = uuid.UUID(TEST_ORG_ID)
    approval_id = uuid.uuid4()
    
    appr = ApprovalItem(
        id=approval_id,
        organization_id=org_uuid,
        review_type="product_launch_post",
        reason="Campaign post requires human approval",
        context_brief="TaskFlow Pro - LinkedIn",
        payload={"post_id": "li-1", "platform": "LinkedIn"},
        status="pending",
        created_at=datetime.utcnow(),
    )
    mock_db.add(appr)

    resp = await reject_product_launch_post(str(approval_id), db=mock_db, current_user=MOCK_USER)
    assert resp["status"] == "rejected"
    assert resp["decided_by"] == MOCK_USER.email

    assert appr.status == "rejected"
    audit_evt = next((o for o in mock_db.added if isinstance(o, AuditEvent)), None)
    assert audit_evt is not None
    assert audit_evt.action == "product_launch_post_rejected"


@pytest.mark.asyncio
async def test_update_product_launch_post(mock_db):
    """Verify that updating a pending post modifies its payload and logs AuditEvent."""
    org_uuid = uuid.UUID(TEST_ORG_ID)
    approval_id = uuid.uuid4()
    
    appr = ApprovalItem(
        id=approval_id,
        organization_id=org_uuid,
        review_type="product_launch_post",
        reason="Campaign post requires human approval",
        context_brief="TaskFlow Pro - LinkedIn",
        payload={"post_id": "li-1", "platform": "LinkedIn", "caption": "Old caption"},
        status="pending",
        created_at=datetime.utcnow(),
    )
    mock_db.add(appr)

    upd_req = UpdatePostRequest(caption="Updated new caption", hashtags=["#NewTag"])
    resp = await update_product_launch_post(str(approval_id), upd_req, db=mock_db, current_user=MOCK_USER)
    assert resp["payload"]["caption"] == "Updated new caption"
    assert resp["payload"]["hashtags"] == ["#NewTag"]

    audit_evt = next((o for o in mock_db.added if isinstance(o, AuditEvent)), None)
    assert audit_evt is not None
    assert audit_evt.action == "product_launch_post_updated"


@pytest.mark.asyncio
async def test_export_product_launch_campaign(mock_db):
    """Verify exporting campaign schedule logs AuditEvent and returns formatted posts schedule."""
    org_uuid = uuid.UUID(TEST_ORG_ID)
    inst_id = uuid.uuid4()

    wf_inst = WorkflowInstance(
        id=inst_id,
        organization_id=org_uuid,
        workflow_name="product_launch_sprint",
        status=WorkflowStatus.ESCALATED.value,
        context={
            "brief": {"productName": "TaskFlow Pro", "shortDescription": "SMB Project Tool"},
            "posts": [
                {"id": "li-1", "platform": "LinkedIn", "caption": "Launch post", "scheduledTime": "Oct 1 - 9:00 AM"}
            ]
        },
        started_at=datetime.utcnow()
    )
    mock_db.add(wf_inst)

    resp = await export_product_launch_campaign(str(inst_id), db=mock_db, current_user=MOCK_USER)
    assert resp["instance_id"] == str(inst_id)
    assert resp["product_name"] == "TaskFlow Pro"
    assert resp["posts_count"] == 1

    audit_evt = next((o for o in mock_db.added if isinstance(o, AuditEvent)), None)
    assert audit_evt is not None
    assert audit_evt.action == "product_launch_campaign_exported"


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_campaign_visual_sharing_and_generation(mock_db):
    """Test that campaign creates core visual assets shared across posts and ImageRouter generates visual assets."""
    from api.routers.product_launch import generate_campaign_visual, approve_campaign_visual

    org_uuid = uuid.UUID(TEST_ORG_ID)
    inst_id = uuid.uuid4()

    core_vis = [
        {
            "visual_id": "vis-hero-1",
            "visual_role": "Product Hero",
            "visual_prompt": "Hero graphic for TaskFlow Pro",
            "aspect_ratio": "16:9",
            "status": "pending_generation",
            "generated_asset_url": None,
        },
        {
            "visual_id": "vis-workflow-1",
            "visual_role": "Product / Workflow / Feature",
            "visual_prompt": "Workflow graphic for TaskFlow Pro",
            "aspect_ratio": "16:9",
            "status": "pending_generation",
            "generated_asset_url": None,
        }
    ]

    posts = [
        {
            "id": "li-1",
            "platform": "LinkedIn",
            "category": "LAUNCH ANNOUNCEMENT",
            "visual_id": "vis-hero-1",
            "visual_status": "pending_generation",
            "generated_asset_url": None,
        },
        {
            "id": "li-2",
            "platform": "LinkedIn",
            "category": "PRODUCT BENEFIT",
            "visual_id": "vis-hero-1",
            "visual_status": "pending_generation",
            "generated_asset_url": None,
        }
    ]

    wf_inst = WorkflowInstance(
        id=inst_id,
        organization_id=org_uuid,
        workflow_name="product_launch_sprint",
        status=WorkflowStatus.ESCALATED.value,
        context={
            "brief": {"productName": "TaskFlow Pro"},
            "visuals": core_vis,
            "posts": posts
        },
        started_at=datetime.utcnow()
    )
    mock_db.add(wf_inst)

    mock_gen_result = {
        "status": "generated",
        "generated_asset_url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
        "generation_model": "gemini-3.1-flash-image",
        "provider": "google_genai"
    }

    with patch("core.image_router.ImageRouter.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_gen_result

        # Generate visual for vis-hero-1
        gen_resp = await generate_campaign_visual(str(inst_id), "vis-hero-1", db=mock_db, current_user=MOCK_USER)
        assert gen_resp["visual_id"] == "vis-hero-1"
        assert gen_resp["visual"]["status"] == "generated"
        assert gen_resp["visual"]["generated_asset_url"].startswith("data:image/png;base64,")

        # Check both posts referencing vis-hero-1 were updated
        assert gen_resp["posts"][0]["generated_asset_url"] == gen_resp["visual"]["generated_asset_url"]
        assert gen_resp["posts"][1]["generated_asset_url"] == gen_resp["visual"]["generated_asset_url"]

    # Approve visual
    appr_resp = await approve_campaign_visual(str(inst_id), "vis-hero-1", db=mock_db, current_user=MOCK_USER)
    assert appr_resp["status"] == "approved"
    assert appr_resp["visual"]["status"] == "approved"


@pytest.mark.asyncio
async def test_campaign_visual_failed_generation(mock_db):
    """Test that Gemini API failure produces status='failed' and error details, not fake success."""
    from api.routers.product_launch import generate_campaign_visual

    org_uuid = uuid.UUID(TEST_ORG_ID)
    inst_id = uuid.uuid4()

    wf_inst = WorkflowInstance(
        id=inst_id,
        organization_id=org_uuid,
        workflow_name="product_launch_sprint",
        status=WorkflowStatus.ESCALATED.value,
        context={
            "brief": {"productName": "TaskFlow Pro"},
            "visuals": [{"visual_id": "vis-hero-1", "visual_role": "Product Hero", "status": "pending_generation"}],
            "posts": [{"id": "li-1", "visual_id": "vis-hero-1", "visual_status": "pending_generation"}]
        },
        started_at=datetime.utcnow()
    )
    mock_db.add(wf_inst)

    mock_failed_result = {
        "status": "failed",
        "generated_asset_url": None,
        "error": "Gemini API 404 NOT_FOUND",
        "generation_model": "gemini-3.1-flash-image",
        "provider": "google_genai"
    }

    with patch("core.image_router.ImageRouter.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_failed_result

        gen_resp = await generate_campaign_visual(str(inst_id), "vis-hero-1", db=mock_db, current_user=MOCK_USER)
        assert gen_resp["visual"]["status"] == "failed"
        assert gen_resp["visual"]["generated_asset_url"] is None
        assert "Gemini API 404" in gen_resp["visual"]["error"]
        assert gen_resp["posts"][0]["visual_status"] == "failed"
        assert gen_resp["posts"][0]["generated_asset_url"] is None


@pytest.mark.asyncio
async def test_schedule_product_launch_post(mock_db):
    """Verify scheduling a post updates payload to status='Scheduled', updates date/time/timezone, and logs AuditEvent."""
    from api.routers.product_launch import schedule_product_launch_post, SchedulePostRequest

    org_uuid = uuid.UUID(TEST_ORG_ID)
    approval_id = uuid.uuid4()
    inst_id = uuid.uuid4()

    appr = ApprovalItem(
        id=approval_id,
        instance_id=inst_id,
        organization_id=org_uuid,
        review_type="product_launch_post",
        reason="Campaign post requires scheduling",
        context_brief="TaskFlow Pro - LinkedIn",
        payload={
            "post_id": "li-1",
            "platform": "LinkedIn",
            "dateStr": "Wed 1",
            "timeStr": "9:00 AM",
            "timezone": "America/New_York",
            "post_status": "Approved"
        },
        status="approved",
        created_at=datetime.utcnow(),
    )
    mock_db.add(appr)

    wf_inst = WorkflowInstance(
        id=inst_id,
        organization_id=org_uuid,
        workflow_name="product_launch_sprint",
        status=WorkflowStatus.ESCALATED.value,
        context={
            "brief": {"productName": "TaskFlow Pro"},
            "posts": [
                {"id": "li-1", "approval_id": str(approval_id), "platform": "LinkedIn", "status": "Approved"}
            ]
        },
        started_at=datetime.utcnow()
    )
    mock_db.add(wf_inst)

    sched_req = SchedulePostRequest(
        scheduled_date="2026-10-05",
        scheduled_time="10:30 AM",
        timezone="America/Los_Angeles",
        platform="LinkedIn"
    )

    resp = await schedule_product_launch_post(str(approval_id), req=sched_req, db=mock_db, current_user=MOCK_USER)
    assert resp["status"] == "Scheduled"
    assert resp["post_status"] == "Scheduled"
    assert resp["payload"]["dateStr"] == "2026-10-05"
    assert resp["payload"]["timeStr"] == "10:30 AM"
    assert resp["payload"]["timezone"] == "America/Los_Angeles"

    # Verify AuditEvent written to DB
    audit_evt = next((o for o in mock_db.added if isinstance(o, AuditEvent) and o.action == "product_launch_post_scheduled"), None)
    assert audit_evt is not None
    assert audit_evt.metadata_["internal_scheduling_only"] is True


@pytest.mark.asyncio
async def test_get_product_launch_campaign_rehydration_and_usage(mock_db):
    """Verify fetching campaign re-hydrates post status from ApprovalItem and computes usage summary from AgentRunRecords."""
    from api.routers.product_launch import get_product_launch_campaign

    org_uuid = uuid.UUID(TEST_ORG_ID)
    inst_id = uuid.uuid4()
    appr_id_1 = uuid.uuid4()
    appr_id_2 = uuid.uuid4()

    # 2 ApprovalItems: 1 Approved, 1 Scheduled
    appr1 = ApprovalItem(
        id=appr_id_1,
        instance_id=inst_id,
        organization_id=org_uuid,
        review_type="product_launch_post",
        payload={"post_id": "li-1", "platform": "LinkedIn", "post_status": "Approved"},
        status="approved",
        created_at=datetime.utcnow(),
    )
    appr2 = ApprovalItem(
        id=appr_id_2,
        instance_id=inst_id,
        organization_id=org_uuid,
        review_type="product_launch_post",
        payload={"post_id": "x-1", "platform": "X", "post_status": "Scheduled", "dateStr": "2026-10-02", "timeStr": "2:00 PM"},
        status="approved",
        created_at=datetime.utcnow(),
    )
    mock_db.add(appr1)
    mock_db.add(appr2)

    wf_inst = WorkflowInstance(
        id=inst_id,
        organization_id=org_uuid,
        workflow_name="product_launch_sprint",
        status=WorkflowStatus.ESCALATED.value,
        context={
            "brief": {"productName": "TaskFlow Pro"},
            "posts": [
                {"id": "li-1", "approval_id": str(appr_id_1), "platform": "LinkedIn", "status": "Draft"},
                {"id": "x-1", "approval_id": str(appr_id_2), "platform": "X", "status": "Draft"}
            ]
        },
        started_at=datetime.utcnow()
    )
    mock_db.add(wf_inst)

    # 2 AgentRunRecords: 1 LLM drafting, 1 Image router
    run1 = AgentRunRecord(
        id=uuid.uuid4(),
        instance_id=inst_id,
        node_id="draft_assets",
        agent_capability="drafting_agent",
        status="success",
        tokens_in=1200,
        tokens_out=800,
        cost_usd=0.005,
        completed_at=datetime.utcnow()
    )
    run2 = AgentRunRecord(
        id=uuid.uuid4(),
        instance_id=inst_id,
        node_id="image_generation",
        agent_capability="image_router",
        status="success",
        tokens_in=50,
        tokens_out=100,
        cost_usd=0.02,
        completed_at=datetime.utcnow()
    )
    mock_db.add(run1)
    mock_db.add(run2)

    resp = await get_product_launch_campaign(str(inst_id), db=mock_db, current_user=MOCK_USER)
    assert resp["instance_id"] == str(inst_id)
    assert len(resp["posts"]) == 2

    # Verify post status rehydrated correctly
    post_li = next(p for p in resp["posts"] if p["id"] == "li-1")
    post_x = next(p for p in resp["posts"] if p["id"] == "x-1")
    assert post_li["status"] == "Approved"
    assert post_x["status"] == "Scheduled"
    assert post_x["dateStr"] == "2026-10-02"

    # Verify usage summary computation
    usage = resp["usage_summary"]
    assert usage["tokens_in"] == 1250
    assert usage["tokens_out"] == 900
    assert usage["total_tokens"] == 2150
    assert usage["llm_calls_count"] == 1
    assert usage["image_generations_count"] == 1
    assert usage["total_cost_usd"] == 0.025


@pytest.mark.asyncio
async def test_get_campaign_org_isolation(mock_db):
    """Verify attempting to fetch campaign from another organization raises 404/Access Denied."""
    from api.routers.product_launch import get_product_launch_campaign

    other_org_uuid = uuid.uuid4()
    inst_id = uuid.uuid4()

    wf_inst = WorkflowInstance(
        id=inst_id,
        organization_id=other_org_uuid, # Different org!
        workflow_name="product_launch_sprint",
        status=WorkflowStatus.ESCALATED.value,
        context={"brief": {"productName": "Secret Competitor Product"}},
        started_at=datetime.utcnow()
    )
    mock_db.add(wf_inst)

    with pytest.raises(HTTPException) as exc_info:
        await get_product_launch_campaign(str(inst_id), db=mock_db, current_user=MOCK_USER)
    assert exc_info.value.status_code == 404
    assert "not found or access denied" in exc_info.value.detail


@pytest.mark.asyncio
async def test_image_router_gemini_success_no_fallback():
    """Verify that when Gemini succeeds, Pollinations fallback is NOT called."""
    from core.image_router import ImageRouter

    router = ImageRouter()

    mock_gemini_success = {
        "status": "generated",
        "generated_asset_url": "data:image/png;base64,gemini_image_data",
        "storage_path": "/path/to/gemini.png",
        "generation_model": "gemini-3.1-flash-image",
        "provider": "google_genai"
    }

    with patch.object(router, "_generate_gemini", new_callable=AsyncMock) as mock_gem, \
         patch.object(router, "_generate_pollinations", new_callable=AsyncMock) as mock_poll:
        
        mock_gem.return_value = mock_gemini_success

        res = await router.generate(
            prompt="Product hero graphic",
            visual_role="Product Hero",
            aspect_ratio="16:9"
        )

        assert res["status"] == "generated"
        assert res["provider"] == "google_genai"
        assert res["generated_asset_url"] == "data:image/png;base64,gemini_image_data"
        mock_gem.assert_called_once()
        mock_poll.assert_not_called()


@pytest.mark.asyncio
async def test_image_router_gemini_quota_error_pollinations_fallback_success():
    """Verify that when Gemini returns 429 / quota error, Pollinations fallback is called ONCE and succeeds."""
    from core.image_router import ImageRouter

    router = ImageRouter()

    mock_gemini_failure = {
        "status": "failed",
        "generated_asset_url": None,
        "error": "Gemini 429 Quota Exceeded",
        "generation_model": "gemini-3.1-flash-image",
        "provider": "google_genai"
    }

    mock_pollinations_success = {
        "status": "generated",
        "generated_asset_url": "data:image/png;base64,pollinations_image_data",
        "storage_path": "/path/to/pollinations.png",
        "generation_model": "flux",
        "provider": "pollinations"
    }

    with patch.object(router, "_generate_gemini", new_callable=AsyncMock) as mock_gem, \
         patch.object(router, "_generate_pollinations", new_callable=AsyncMock) as mock_poll, \
         patch.dict("os.environ", {"GEMINI_API_KEY": "test_gemini_key", "POLLINATIONS_API_KEY": "test_poll_key"}):
        
        mock_gem.return_value = mock_gemini_failure
        mock_poll.return_value = mock_pollinations_success

        res = await router.generate(
            prompt="Product hero graphic",
            visual_role="Product Hero",
            aspect_ratio="16:9"
        )

        assert res["status"] == "generated"
        assert res["provider"] == "pollinations"
        assert res["generated_asset_url"] == "data:image/png;base64,pollinations_image_data"
        assert res.get("fallback_used") is True
        mock_gem.assert_called_once()
        mock_poll.assert_called_once()


@pytest.mark.asyncio
async def test_image_router_both_providers_fail():
    """Verify that when both Gemini and Pollinations fail, correct generation_unavailable/failed status is returned."""
    from core.image_router import ImageRouter

    router = ImageRouter()

    mock_gemini_failure = {
        "status": "failed",
        "generated_asset_url": None,
        "error": "Gemini 429 Quota Exceeded",
        "provider": "google_genai"
    }

    mock_pollinations_failure = {
        "status": "failed",
        "generated_asset_url": None,
        "error": "Pollinations HTTP 503 Provider Unavailable",
        "provider": "pollinations"
    }

    with patch.object(router, "_generate_gemini", new_callable=AsyncMock) as mock_gem, \
         patch.object(router, "_generate_pollinations", new_callable=AsyncMock) as mock_poll, \
         patch.dict("os.environ", {"GEMINI_API_KEY": "test_gemini_key", "POLLINATIONS_API_KEY": "test_poll_key"}):

        mock_gem.return_value = mock_gemini_failure
        mock_poll.return_value = mock_pollinations_failure

        res = await router.generate(
            prompt="Product hero graphic",
            visual_role="Product Hero",
            aspect_ratio="16:9"
        )

        assert res["status"] == "failed"
        assert res["generated_asset_url"] is None
        assert "Gemini" in res["error"] and "Pollinations" in res["error"]
        assert "test_poll_key" not in res["error"]  # Key Privacy Check!
        assert "test_gemini_key" not in res["error"]
        mock_gem.assert_called_once()
        mock_poll.assert_called_once()


@pytest.mark.asyncio
async def test_visual_brief_builder_verbatim_product_name():
    """Verify that VisualBriefBuilder preserves exact product name verbatim without paraphrasing."""
    from core.visual_brief_builder import VisualBriefBuilder

    product_brief = {
        "productName": "NovaBooks AI Enterprise",
        "shortDescription": "Autonomous bookkeeping for enterprise accounting firms",
        "keyFeatures": ["Bank Reconciliation", "GST Audit Helper"],
        "topBenefit1": "Saves 10+ hours per week",
        "targetAudience": "Enterprise CFOs"
    }

    brief = VisualBriefBuilder.build_brief(
        product_brief=product_brief,
        visual_role="Product Hero",
        platform="LinkedIn",
        aspect_ratio="16:9"
    )

    assert brief["product"]["name"] == "NovaBooks AI Enterprise"
    assert brief["grounded_facts"]["exact_text"] == ["NovaBooks AI Enterprise"]
    assert "NovaBooks AI Enterprise" in brief["formatted_grounded_prompt"]
    assert "Do not misspell, alter, or paraphrase product name 'NovaBooks AI Enterprise'" in brief["negative_constraints"][0]


@pytest.mark.asyncio
async def test_visual_brief_builder_source_priority():
    """Verify source priority: approved user input -> document facts -> visual direction."""
    from core.visual_brief_builder import VisualBriefBuilder

    product_brief = {
        "productName": "TaskFlow Pro",
        "shortDescription": "User approved description",
        "keyFeatures": ["User Feature 1"],
        "document_text": "Extracted Document Fact 1: Reduces accounting overhead by 40%.\nExtracted Document Fact 2: Multi-currency support."
    }

    brief = VisualBriefBuilder.build_brief(
        product_brief=product_brief,
        visual_role="Workflow / Feature",
        platform="X",
        aspect_ratio="16:9",
        visual_prompt="Generated visual prompt direction"
    )

    assert brief["product"]["name"] == "TaskFlow Pro"
    assert brief["product"]["short_description"] == "User approved description"
    assert "uploaded_document" in brief["source_fields"]
    assert len(brief["grounded_facts"]["document_facts"]) == 2
    assert "Extracted Document Fact 1" in brief["grounded_facts"]["document_facts"][0]
    assert brief["visual_direction"]["raw_direction"] == "Generated visual prompt direction"


@pytest.mark.asyncio
async def test_visual_brief_builder_role_and_platform_composition():
    """Verify visual role and platform influence visual composition instructions."""
    from core.visual_brief_builder import VisualBriefBuilder

    brief = VisualBriefBuilder.build_brief(
        product_brief={"productName": "CloudScale Engine"},
        visual_role="Workflow / Feature",
        platform="Instagram",
        aspect_ratio="1:1"
    )

    assert brief["visual_meta"]["platform"] == "Instagram"
    assert brief["visual_meta"]["aspect_ratio"] == "1:1"
    assert "Clean modern UI interface graphic for Instagram (1:1)" in brief["visual_direction"]["composition"]







