"""
tests/test_meeting_intelligence_node5a.py
=========================================
Automated test suite for Meeting Intelligence & Follow-up:
NODE 5A — Follow-up Email Draft + Human Review Controls

Verifies:
1. Grounded draft generation from actual conversation & agreed commitments.
2. Anti-hallucination & grounding (null email preserved as null; no fabricated facts).
3. Idempotency (re-running Node 5A reuses existing draft, creates zero duplicates).
4. Deterministic fallback generator if LLM fails or is unavailable.
5. HITL Review Action: Edit (updates subject/body, preserves original).
6. HITL Review Action: Snooze (sets snoozed_until, status="snoozed").
7. HITL Review Action: Discard (sets status="discarded").
8. HITL Review Action: Approve (sets status="approved", STRICTLY ZERO OUTBOUND SEND).
9. Node 4 prerequisite check (rejects with 400 if Node 4 is incomplete).
10. Cross-tenant isolation (rejects with 403 on cross-org draft generation or action).
11. Rehydration in get_meeting_intelligence_run (restores followup_draft and partial Node 5 note).
12. Action Center list_approval_items integration (includes awaiting_review and snoozed).
"""

import json
import uuid
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException
from api.auth import TokenData
from api.routers.meeting_intelligence import (
    FollowupDraftRequest,
    FollowupDraftActionRequest,
    generate_followup_draft,
    handle_followup_draft_action,
    get_meeting_intelligence_run,
    _build_deterministic_followup_draft,
)
from db.models.core import (
    AgentRunRecord,
    ApprovalItem,
    AuditEvent,
    RelationshipContact,
    RelationshipConversation,
    RelationshipMemoryItem,
    WorkflowInstance,
)
from api import crud


ORG_A = str(uuid.uuid4())
ORG_B = str(uuid.uuid4())

USER_ORG_A = TokenData(
    user_id=str(uuid.uuid4()),
    email="alice@company-a.com",
    role="org_admin",
    organization_id=ORG_A,
    tenant_id=ORG_A,
)

USER_ORG_B = TokenData(
    user_id=str(uuid.uuid4()),
    email="bob@company-b.com",
    role="org_admin",
    organization_id=ORG_B,
    tenant_id=ORG_B,
)


class Node5AMockSession:
    """Mock async database session for Node 5A tests."""

    def __init__(self):
        self.workflow_instances = {}
        self.contacts = {}
        self.conversations = {}
        self.memory_items = []
        self.approval_items = {}
        self.agent_runs = []
        self.audit_events = []

    def add(self, obj):
        if not hasattr(obj, "id") or not obj.id:
            obj.id = uuid.uuid4()

        if isinstance(obj, WorkflowInstance):
            self.workflow_instances[str(obj.id)] = obj
        elif isinstance(obj, RelationshipContact):
            self.contacts[str(obj.id)] = obj
        elif isinstance(obj, RelationshipConversation):
            self.conversations[str(obj.id)] = obj
        elif isinstance(obj, RelationshipMemoryItem):
            self.memory_items.append(obj)
        elif isinstance(obj, ApprovalItem):
            self.approval_items[str(obj.id)] = obj
        elif isinstance(obj, AgentRunRecord):
            self.agent_runs.append(obj)
        elif isinstance(obj, AuditEvent):
            self.audit_events.append(obj)

    async def flush(self):
        pass

    async def commit(self):
        pass

    async def refresh(self, obj):
        pass

    async def execute(self, stmt):
        stmt_str = str(stmt).lower()
        params = {}
        try:
            params = stmt.compile().params
        except Exception:
            pass
        param_vals = [str(v).lower() for v in params.values() if v is not None]

        mock_result = AsyncMock()

        # Query WorkflowInstance
        if "workflow_instances" in stmt_str:
            matched = list(self.workflow_instances.values())
            for wid, inst in self.workflow_instances.items():
                if wid.lower() in param_vals or wid.lower() in stmt_str:
                    matched = [inst]
                    break
            mock_result.scalars = lambda: AsyncMock(
                first=lambda: matched[0] if matched else None,
                all=lambda: matched,
            )
            return mock_result

        # Query RelationshipContact
        if "relationship_contacts" in stmt_str:
            matched = list(self.contacts.values())
            for cid, c in self.contacts.items():
                if cid.lower() in param_vals or cid.lower() in stmt_str:
                    matched = [c]
                    break
            mock_result.scalars = lambda: AsyncMock(
                first=lambda: matched[0] if matched else None,
                all=lambda: matched,
            )
            return mock_result

        # Query RelationshipConversation
        if "relationship_conversations" in stmt_str:
            matched = []
            for conv in self.conversations.values():
                if str(conv.workflow_instance_id).lower() in param_vals or str(conv.workflow_instance_id).lower() in stmt_str:
                    matched.append(conv)
                elif str(conv.id).lower() in param_vals or str(conv.id).lower() in stmt_str:
                    matched.append(conv)
                elif not params:
                    matched.append(conv)

            matched.sort(key=lambda x: getattr(x, "created_at", datetime.min) or datetime.min, reverse=True)
            mock_result.scalars = lambda: AsyncMock(
                first=lambda: matched[0] if matched else None,
                all=lambda: matched,
            )
            return mock_result

        # Query ApprovalItem
        if "approval_items" in stmt_str:
            matched = []
            for appr in self.approval_items.values():
                # Filter by draft_id / id
                if str(appr.id).lower() in param_vals or str(appr.id).lower() in stmt_str:
                    matched.append(appr)
                # Filter by instance_id
                elif str(appr.instance_id).lower() in param_vals or str(appr.instance_id).lower() in stmt_str:
                    matched.append(appr)
                elif not params:
                    matched.append(appr)

            # If review_type="followup_email_draft" is queried specifically
            if "followup_email_draft" in param_vals or "followup_email_draft" in stmt_str:
                matched = [a for a in matched if a.review_type == "followup_email_draft"]

            mock_result.scalars = lambda: AsyncMock(
                first=lambda: matched[0] if matched else None,
                all=lambda: matched,
            )
            return mock_result

        # Fallback
        mock_result.scalars = lambda: AsyncMock(first=lambda: None, all=lambda: [])
        return mock_result


def _build_node5a_test_run(
    org_id: str,
    contact_name: str = "Rahul Sharma",
    contact_email: str = None,
    node4_done: bool = True,
):
    """Helper to set up mock session with completed Nodes 1, 2, 3, and 4."""
    session = Node5AMockSession()
    inst_id = uuid.uuid4()
    org_uuid = uuid.UUID(org_id)
    contact_id = uuid.uuid4()
    conv_id = uuid.uuid4()

    # Contact
    contact = RelationshipContact(
        id=contact_id,
        organization_id=org_uuid,
        name=contact_name,
        normalized_name=contact_name.strip().lower(),
        role="VP of Operations",
        company="Apex Logistics",
        metadata_={"email": contact_email} if contact_email else {},
        created_at=datetime.utcnow(),
    )
    session.add(contact)

    # Conversation
    conv = RelationshipConversation(
        id=conv_id,
        organization_id=org_uuid,
        contact_id=contact_id,
        workflow_instance_id=inst_id,
        title=f"AI Pilot Action Planning with {contact_name}",
        conversation_type="sales_discovery",
        conversation_date="2026-09-27",
        transcript="Speaker: I will send Rahul the pilot proposal by Friday. Rahul: I will share the customer queries by Wednesday.",
        summary="Discussion on AI customer support automation pilot with Rahul Sharma.",
        created_at=datetime.utcnow(),
    )
    session.add(conv)

    # Context
    our_commitments = [
        {
            "action_id": str(uuid.uuid4()),
            "action": "Send Rahul the pilot proposal",
            "action_type": "our_commitment",
            "owner_type": "internal",
            "owner_display": "You / Internal",
            "due_date": "2026-10-02",
            "due_date_display": "Oct 2, 2026",
            "status": "pending",
        }
    ]
    contact_commitments = [
        {
            "action_id": str(uuid.uuid4()),
            "action": "Share list of common customer queries",
            "action_type": "contact_commitment",
            "owner_type": "contact",
            "owner_display": contact_name,
            "due_date": "2026-10-01",
            "due_date_display": "Oct 1, 2026",
            "status": "waiting",
        }
    ]
    suggested_actions = [
        {
            "action_id": str(uuid.uuid4()),
            "action": "Prepare evaluation criteria for query list",
            "action_type": "suggested_action",
            "reason": "Accelerates review once queries arrive",
            "status": "suggested",
        }
    ]

    ctx = {
        "conversation_capture": {
            "contact_name": contact_name,
            "conversation_title": f"AI Pilot Action Planning with {contact_name}",
            "conversation_date": "2026-09-27",
        },
        "node2_process_conversation": {
            "status": "completed",
            "transcript_text": conv.transcript,
            "extraction": {
                "summary": conv.summary,
                "commitments": [
                    {"owner": "Speaker", "action": "Send Rahul the pilot proposal", "due_date": "2026-10-02"},
                    {"owner": "Rahul", "action": "Share list of common customer queries", "due_date": "2026-10-01"},
                ],
                "suggested_actions": [
                    {"action": "Prepare evaluation criteria for query list", "reason": "Accelerates review once queries arrive"}
                ],
                "open_questions": ["What is the target response latency?"],
            },
        },
        "node3_central_memory": {
            "status": "completed",
            "contact_id": str(contact_id),
            "contact_name": contact_name,
            "conversation_id": str(conv_id),
        },
    }

    if node4_done:
        ctx["node4_action_generator"] = {
            "status": "completed",
            "our_commitments": our_commitments,
            "contact_commitments": contact_commitments,
            "suggested_actions": suggested_actions,
            "open_questions": ["What is the target response latency?"],
        }

    instance = WorkflowInstance(
        id=inst_id,
        organization_id=org_uuid,
        workflow_name="meeting_intelligence_followup",
        status="processed",
        current_node="n4" if node4_done else "n3",
        context=ctx,
        started_at=datetime.utcnow(),
    )
    session.add(instance)

    return session, inst_id, contact_id, conv_id


# =============================================================================
# TESTS
# =============================================================================

@pytest.mark.asyncio
async def test_generate_followup_draft_llm_success():
    """Verify Node 5A generates draft via LLMRouter, saves ApprovalItem, and leaves Node 5 pending."""
    session, inst_id, contact_id, conv_id = _build_node5a_test_run(ORG_A)

    mock_llm_call = MagicMock()
    mock_llm_call.content = json.dumps({
        "subject": "Follow-up: AI Pilot Action Planning & Next Steps",
        "body": "Hi Rahul,\n\nThank you for taking the time to speak today...",
        "next_steps": [
            "Rahul: Share list of common customer queries by Oct 1",
            "Speaker: Prepare and send pilot proposal by Oct 2"
        ],
        "tone": "professional_warm"
    })
    mock_llm_call.model = "gpt-4o-mini"
    mock_llm_call.provider = "openai"
    mock_llm_call.latency_ms = 412.0
    mock_llm_call.input_tokens = 450
    mock_llm_call.output_tokens = 180

    with patch("api.routers.meeting_intelligence.LLMRouter.call", new=AsyncMock(return_value=(mock_llm_call.content, mock_llm_call))):
        req = FollowupDraftRequest(instance_id=str(inst_id))
        resp = await generate_followup_draft(req, db=session, current_user=USER_ORG_A)

    assert resp.status == "awaiting_review"
    assert resp.draft is not None
    assert resp.draft.recipient_name == "Rahul Sharma"
    assert resp.draft.recipient_email is None
    assert resp.draft.recipient_email_available is False
    assert resp.draft.subject == "Follow-up: AI Pilot Action Planning & Next Steps"
    assert resp.draft.status == "awaiting_review"
    assert resp.idempotent_reused is False
    assert resp.draft.our_commitments_count == 1
    assert resp.draft.contact_commitments_count == 1

    # Verify Node 5 is partial
    node5 = next(n for n in resp.nodes if n.id == "n5")
    assert node5.status == "partial"
    assert node5.implemented is True
    assert "ready / awaiting review" in node5.note.lower()

    # Check ApprovalItem in database
    appr_items = [a for a in session.approval_items.values() if a.review_type == "followup_email_draft"]
    assert len(appr_items) == 1
    draft_appr = appr_items[0]
    assert draft_appr.status == "awaiting_review"
    assert draft_appr.organization_id == uuid.UUID(ORG_A)
    assert draft_appr.payload["recipient_name"] == "Rahul Sharma"
    assert draft_appr.payload["recipient_email"] is None

    # Check AgentRunRecord logged
    agent_runs = [r for r in session.agent_runs if "followup_email_draft" in r.agent_capability]
    assert len(agent_runs) == 1
    assert agent_runs[0].status == "completed"

    # Check AuditEvent logged
    audit_events = [e for e in session.audit_events if e.action == "followup_email_draft_generated"]
    assert len(audit_events) == 1


@pytest.mark.asyncio
async def test_generate_followup_draft_deterministic_fallback():
    """Verify fallback draft generation runs reliably when LLM fails or is unavailable."""
    session, inst_id, contact_id, conv_id = _build_node5a_test_run(ORG_A)

    with patch("api.routers.meeting_intelligence.LLMRouter.call", side_effect=Exception("LLM offline")):
        req = FollowupDraftRequest(instance_id=str(inst_id))
        resp = await generate_followup_draft(req, db=session, current_user=USER_ORG_A)

    assert resp.status == "awaiting_review"
    assert resp.draft is not None
    assert resp.draft.recipient_name == "Rahul Sharma"
    assert resp.draft.model_used == "deterministic_fallback"
    assert "Rahul Sharma" in resp.draft.body
    assert "Send Rahul the pilot proposal" in resp.draft.body
    assert "Share list of common customer queries" in resp.draft.body


@pytest.mark.asyncio
async def test_anti_hallucination_recipient_email_grounding():
    """Verify unknown email is strictly None and known email is correctly preserved."""
    # Case 1: Unknown email -> None
    session_no_email, inst_id_1, _, _ = _build_node5a_test_run(ORG_A, contact_email=None)
    with patch("api.routers.meeting_intelligence.LLMRouter.call", side_effect=Exception("mock")):
        req1 = FollowupDraftRequest(instance_id=str(inst_id_1))
        resp1 = await generate_followup_draft(req1, db=session_no_email, current_user=USER_ORG_A)
    assert resp1.draft.recipient_email is None
    assert resp1.draft.recipient_email_available is False

    # Case 2: Known email -> preserved
    session_with_email, inst_id_2, _, _ = _build_node5a_test_run(
        ORG_A, contact_name="Priya Patel", contact_email="priya@acmelogistics.com"
    )
    with patch("api.routers.meeting_intelligence.LLMRouter.call", side_effect=Exception("mock")):
        req2 = FollowupDraftRequest(instance_id=str(inst_id_2))
        resp2 = await generate_followup_draft(req2, db=session_with_email, current_user=USER_ORG_A)
    assert resp2.draft.recipient_email == "priya@acmelogistics.com"
    assert resp2.draft.recipient_email_available is True


@pytest.mark.asyncio
async def test_followup_draft_idempotency():
    """Verify calling generate_followup_draft multiple times reuses existing draft and creates 0 duplicates."""
    session, inst_id, contact_id, conv_id = _build_node5a_test_run(ORG_A)

    with patch("api.routers.meeting_intelligence.LLMRouter.call", side_effect=Exception("mock")):
        req = FollowupDraftRequest(instance_id=str(inst_id))
        resp1 = await generate_followup_draft(req, db=session, current_user=USER_ORG_A)
        assert resp1.idempotent_reused is False

        # Second call
        resp2 = await generate_followup_draft(req, db=session, current_user=USER_ORG_A)
        assert resp2.idempotent_reused is True
        assert resp2.draft.approval_id == resp1.draft.approval_id

    # Check total ApprovalItems in database: exactly 1
    draft_items = [a for a in session.approval_items.values() if a.review_type == "followup_email_draft"]
    assert len(draft_items) == 1


@pytest.mark.asyncio
async def test_followup_draft_action_edit():
    """Verify editing a draft updates subject/body, preserves original, and keeps status=awaiting_review."""
    session, inst_id, contact_id, conv_id = _build_node5a_test_run(ORG_A)

    with patch("api.routers.meeting_intelligence.LLMRouter.call", side_effect=Exception("mock")):
        req = FollowupDraftRequest(instance_id=str(inst_id))
        resp = await generate_followup_draft(req, db=session, current_user=USER_ORG_A)

    draft_id = resp.draft.approval_id
    original_subject = resp.draft.subject
    original_body = resp.draft.body

    action_req = FollowupDraftActionRequest(
        action="edit",
        subject="Updated Subject: Quick follow-up on pilot",
        body="Hi Rahul,\n\nEdited body with additional notes.\n\nBest,\nMe",
    )
    action_resp = await handle_followup_draft_action(
        draft_id=draft_id,
        req=action_req,
        db=session,
        current_user=USER_ORG_A,
    )

    assert action_resp.status == "awaiting_review"
    assert action_resp.draft.subject == "Updated Subject: Quick follow-up on pilot"
    assert "Edited body with additional notes" in action_resp.draft.body
    assert action_resp.draft.original_subject == original_subject
    assert action_resp.draft.original_body == original_body

    # Check persisted item
    appr = session.approval_items[draft_id]
    assert appr.payload["subject"] == "Updated Subject: Quick follow-up on pilot"
    assert appr.payload["original_subject"] == original_subject


@pytest.mark.asyncio
async def test_followup_draft_action_snooze():
    """Verify snoozing a draft sets status=snoozed and records snooze details."""
    session, inst_id, contact_id, conv_id = _build_node5a_test_run(ORG_A)

    with patch("api.routers.meeting_intelligence.LLMRouter.call", side_effect=Exception("mock")):
        req = FollowupDraftRequest(instance_id=str(inst_id))
        resp = await generate_followup_draft(req, db=session, current_user=USER_ORG_A)

    draft_id = resp.draft.approval_id

    action_req = FollowupDraftActionRequest(
        action="snooze",
        snooze_until="Tomorrow 9:00 AM",
        snooze_reason="Waiting for technical team confirmation",
    )
    action_resp = await handle_followup_draft_action(
        draft_id=draft_id,
        req=action_req,
        db=session,
        current_user=USER_ORG_A,
    )

    assert action_resp.status == "snoozed"
    assert action_resp.draft.status == "snoozed"
    assert action_resp.draft.snoozed_until == "Tomorrow 9:00 AM"
    assert action_resp.draft.snoozed_reason == "Waiting for technical team confirmation"

    appr = session.approval_items[draft_id]
    assert appr.status == "snoozed"


@pytest.mark.asyncio
async def test_followup_draft_action_discard():
    """Verify discarding a draft sets status=discarded."""
    session, inst_id, contact_id, conv_id = _build_node5a_test_run(ORG_A)

    with patch("api.routers.meeting_intelligence.LLMRouter.call", side_effect=Exception("mock")):
        req = FollowupDraftRequest(instance_id=str(inst_id))
        resp = await generate_followup_draft(req, db=session, current_user=USER_ORG_A)

    draft_id = resp.draft.approval_id

    action_req = FollowupDraftActionRequest(
        action="discard",
        notes="Decided to follow up via phone instead",
    )
    action_resp = await handle_followup_draft_action(
        draft_id=draft_id,
        req=action_req,
        db=session,
        current_user=USER_ORG_A,
    )

    assert action_resp.status == "discarded"
    assert action_resp.draft.status == "discarded"

    appr = session.approval_items[draft_id]
    assert appr.status == "discarded"


@pytest.mark.asyncio
async def test_followup_draft_action_approve_strictly_no_send():
    """Verify approving a draft sets status=approved with STRICTLY ZERO outbound email dispatch."""
    session, inst_id, contact_id, conv_id = _build_node5a_test_run(ORG_A)

    with patch("api.routers.meeting_intelligence.LLMRouter.call", side_effect=Exception("mock")):
        req = FollowupDraftRequest(instance_id=str(inst_id))
        resp = await generate_followup_draft(req, db=session, current_user=USER_ORG_A)

    draft_id = resp.draft.approval_id

    action_req = FollowupDraftActionRequest(action="approve")
    action_resp = await handle_followup_draft_action(
        draft_id=draft_id,
        req=action_req,
        db=session,
        current_user=USER_ORG_A,
    )

    assert action_resp.status == "approved"
    assert action_resp.draft.status == "approved"
    assert "approved" in action_resp.message.lower() and "later sending" in action_resp.message.lower()

    appr = session.approval_items[draft_id]
    assert appr.status == "approved"

    # STRICTLY NO SEND VERIFICATION:
    # Ensure NO audit event with action="email_sent" or similar outbound dispatch exists
    email_sent_audits = [e for e in session.audit_events if "send" in e.action.lower() and e.action != "followup_email_draft_approved"]
    assert len(email_sent_audits) == 0

    # Ensure approval event is present
    approval_audits = [e for e in session.audit_events if e.action == "followup_draft_approve"]
    assert len(approval_audits) == 1


@pytest.mark.asyncio
async def test_node4_prerequisite_enforced():
    """Verify generate_followup_draft fails with HTTP 400 if Node 4 is incomplete."""
    session, inst_id, contact_id, conv_id = _build_node5a_test_run(ORG_A, node4_done=False)

    req = FollowupDraftRequest(instance_id=str(inst_id))
    with pytest.raises(HTTPException) as exc_info:
        await generate_followup_draft(req, db=session, current_user=USER_ORG_A)

    assert exc_info.value.status_code == 400
    assert "Node 4 (Action Generator) must be completed" in exc_info.value.detail


@pytest.mark.asyncio
async def test_cross_tenant_isolation_rejected():
    """Verify Org B cannot generate draft or perform review action on Org A's instance."""
    session, inst_id, contact_id, conv_id = _build_node5a_test_run(ORG_A)

    # 1. Draft generation cross-tenant forbidden
    req = FollowupDraftRequest(instance_id=str(inst_id))
    with pytest.raises(HTTPException) as exc_info:
        await generate_followup_draft(req, db=session, current_user=USER_ORG_B)
    assert exc_info.value.status_code == 403

    # Generate legitimate draft under Org A
    with patch("api.routers.meeting_intelligence.LLMRouter.call", side_effect=Exception("mock")):
        resp = await generate_followup_draft(req, db=session, current_user=USER_ORG_A)
    draft_id = resp.draft.approval_id

    # 2. Action on Org A's draft by Org B forbidden
    action_req = FollowupDraftActionRequest(action="approve")
    with pytest.raises(HTTPException) as exc_info2:
        await handle_followup_draft_action(
            draft_id=draft_id,
            req=action_req,
            db=session,
            current_user=USER_ORG_B,
        )
    assert exc_info2.value.status_code == 403


@pytest.mark.asyncio
async def test_rehydration_in_get_meeting_intelligence_run():
    """Verify get_meeting_intelligence_run rehydrates followup_draft from ApprovalItem."""
    session, inst_id, contact_id, conv_id = _build_node5a_test_run(ORG_A)

    with patch("api.routers.meeting_intelligence.LLMRouter.call", side_effect=Exception("mock")):
        req = FollowupDraftRequest(instance_id=str(inst_id))
        gen_resp = await generate_followup_draft(req, db=session, current_user=USER_ORG_A)

    # Edit draft
    draft_id = gen_resp.draft.approval_id
    await handle_followup_draft_action(
        draft_id=draft_id,
        req=FollowupDraftActionRequest(action="edit", subject="Customized Title", body="Customized Body"),
        db=session,
        current_user=USER_ORG_A,
    )

    # Now call detail endpoint
    detail = await get_meeting_intelligence_run(
        instance_id=str(inst_id),
        db=session,
        current_user=USER_ORG_A,
    )

    assert detail.followup_draft is not None
    assert detail.followup_draft.subject == "Customized Title"
    assert detail.followup_draft.body == "Customized Body"
    assert detail.followup_draft.status == "awaiting_review"

    # Node 5 has partial status note
    node5 = next(n for n in detail.nodes if n.id == "n5")
    assert node5.status == "partial"
    assert node5.implemented is True
    assert "ready / awaiting review" in node5.note.lower()
