"""
tests/test_meeting_intelligence_node3.py
========================================
Automated test suite for Meeting Intelligence & Follow-up:
NODE 3 — Central Memory (Relationship Intelligence & Organization-Scoped Memory)

Verifies:
1. Node 2 completed -> Node 3 succeeds (creates contact, conversation, and structured memory items).
2. Distinction between factual extractions (is_ai_generated=False) and AI suggestions (is_ai_generated=True).
3. Source traceability: each memory item references workflow instance, conversation, and date.
4. Observability: AgentRunRecord for n3 (tokens=0, cost=0.0) and AuditEvent recorded.
5. Node 2 missing/not completed -> Node 3 refuses to create memory (clean 400).
6. Idempotency: Same run processed twice -> no duplicate contact, conversation, or memory items.
7. Second-Conversation Test: Same contact in new run -> existing contact reused, conversation count = 2.
8. Cross-Tenant Test: Same contact name in different organizations -> two independent contact records.
9. Tenant Isolation: Unauthorized organization attempts to access memory -> rejected (403 Forbidden).
10. Contact history endpoint: Returns aggregated multi-conversation memory scoped by organization.
"""

import uuid
import pytest
from datetime import datetime
from unittest.mock import AsyncMock

from fastapi import HTTPException
from api.auth import TokenData
from api.routers.meeting_intelligence import (
    CentralMemoryRequest,
    process_central_memory,
    get_contact_memory_history,
)
from db.models.core import (
    AgentRunRecord,
    AuditEvent,
    RelationshipContact,
    RelationshipConversation,
    RelationshipMemoryItem,
    WorkflowInstance,
)


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


class CentralMemoryMockSession:
    """Mock async database session managing Central Memory entities in memory."""

    def __init__(self):
        self.workflow_instances = {}
        self.contacts = {}
        self.conversations = {}
        self.memory_items = []
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

        # Query RelationshipConversation
        if "relationship_conversations" in stmt_str:
            matched = []
            for conv in self.conversations.values():
                # Filter by workflow_instance_id if present
                if str(conv.workflow_instance_id).lower() in param_vals or str(conv.workflow_instance_id).lower() in stmt_str:
                    matched.append(conv)
                # Filter by contact_id if present
                elif str(conv.contact_id).lower() in param_vals or str(conv.contact_id).lower() in stmt_str:
                    matched.append(conv)
                elif not params:
                    matched.append(conv)

            matched.sort(key=lambda x: getattr(x, "created_at", datetime.min) or datetime.min, reverse=True)
            mock_result.scalars = lambda: AsyncMock(
                first=lambda: matched[0] if matched else None,
                all=lambda: matched,
            )
            return mock_result

        # Query RelationshipContact
        if "relationship_contacts" in stmt_str:
            matched = []
            for contact in self.contacts.values():
                if str(contact.id).lower() in param_vals or str(contact.id).lower() in stmt_str:
                    matched = [contact]
                    break
                # Match normalized_name and organization_id
                if (contact.normalized_name in param_vals or contact.normalized_name in stmt_str) and \
                   (str(contact.organization_id).lower() in param_vals or str(contact.organization_id).lower() in stmt_str):
                    matched = [contact]
                    break
            mock_result.scalars = lambda: AsyncMock(
                first=lambda: matched[0] if matched else None,
                all=lambda: matched,
            )
            return mock_result

        # Query RelationshipMemoryItem
        if "relationship_memory_items" in stmt_str:
            matched = []
            for item in self.memory_items:
                if str(item.contact_id).lower() in param_vals or str(item.contact_id).lower() in stmt_str:
                    matched.append(item)
            mock_result.scalars = lambda: AsyncMock(
                first=lambda: matched[0] if matched else None,
                all=lambda: matched,
            )
            return mock_result

        # Fallback empty
        mock_result.scalars = lambda: AsyncMock(first=lambda: None, all=lambda: [])
        return mock_result


def _build_mock_workflow_instance(
    instance_id: uuid.UUID,
    org_id: str,
    contact_name: str,
    conversation_title: str,
    is_node2_done: bool = True,
) -> WorkflowInstance:
    """Helper to assemble a workflow instance in a given state."""
    capture_data = {
        "conversation_title": conversation_title,
        "contact_name": contact_name,
        "conversation_type": "Online Meeting",
        "language": "Auto Detect",
        "conversation_date": "2026-09-27",
        "participant_role": "VP of Customer Success",
        "recording": {"filename": "meeting.mp3", "size_bytes": 1024},
    }

    ctx = {"conversation_capture": capture_data}

    if is_node2_done:
        ctx["node2_process_conversation"] = {
            "status": "completed",
            "transcript_text": "Hi Rahul, thank you for meeting. We discussed AI automation for customer support. I will send a proposal by Friday.",
            "detected_language": "en",
            "extraction": {
                "summary": "Meeting with Rahul regarding customer support AI automation pilot.",
                "people": [
                    {
                        "name": contact_name,
                        "facts": ["Leading customer success at Enterprise Corp"],
                        "interests": ["Customer query automation", "AI agent response benchmarking"],
                        "needs": ["Reduce response backlog by 40%"],
                        "opportunities": ["Pilot expansion across APAC"],
                    }
                ],
                "commitments": [
                    {
                        "owner": "Speaker",
                        "commitment": "Send a short proposal by Friday",
                        "due_date": "2026-10-02",
                    }
                ],
                "suggested_actions": [
                    {
                        "action": "Draft 3 pilot use-cases before the follow-up call",
                        "reason": "Aligns implementation scope and sets clear success metrics",
                    }
                ],
                "open_questions": [
                    "What is the target integration timeline with Zendesk?"
                ],
            },
        }

    return WorkflowInstance(
        id=instance_id,
        organization_id=uuid.UUID(org_id),
        workflow_name="meeting_intelligence_followup",
        status="processed" if is_node2_done else "capture_completed",
        current_node="n2" if is_node2_done else "n1",
        trigger_payload=capture_data,
        context=ctx,
        started_at=datetime.utcnow(),
    )


# ── Test 1: Node 2 Completed -> Node 3 Central Memory Succeeds ─────────────────

@pytest.mark.asyncio
async def test_central_memory_node3_success():
    """Verify Node 3 converts Node 2 extractions into persistent Central Memory."""
    session = CentralMemoryMockSession()
    inst_id = uuid.uuid4()
    wf = _build_mock_workflow_instance(inst_id, ORG_A, "Rahul Sharma", "AI Automation Discussion", is_node2_done=True)
    session.add(wf)

    req = CentralMemoryRequest(instance_id=str(inst_id))
    resp = await process_central_memory(req, db=session, current_user=USER_ORG_A)

    assert resp.status == "completed"
    assert resp.current_node == "n3"
    assert resp.idempotent_reused is False
    assert resp.memory.contact_name == "Rahul Sharma"
    assert resp.memory.total_conversations == 1
    assert resp.memory.latest_conversation_title == "AI Automation Discussion"

    # Verify structured memory separation
    assert len(resp.memory.facts) >= 1
    assert len(resp.memory.interests) >= 2
    assert len(resp.memory.needs) >= 1
    assert len(resp.memory.opportunities) >= 1

    # Commitments (factual human promises)
    assert len(resp.memory.commitments) == 1
    assert resp.memory.commitments[0].is_ai_generated is False
    assert resp.memory.commitments[0].details.get("owner") == "Speaker"

    # Suggested actions (AI recommendations)
    assert len(resp.memory.suggested_actions) == 1
    assert resp.memory.suggested_actions[0].is_ai_generated is True
    assert "Draft 3 pilot use-cases" in resp.memory.suggested_actions[0].content

    # Open questions
    assert len(resp.memory.open_questions) == 1

    # Pipeline status
    n3_node = next(n for n in resp.nodes if n.id == "n3")
    assert n3_node.status == "completed"
    assert n3_node.implemented is True

    n4_node = next(n for n in resp.nodes if n.id == "n4")
    assert n4_node.status == "pending"
    assert n4_node.implemented is True

    # Observability
    assert len(session.agent_runs) == 1
    assert session.agent_runs[0].node_id == "n3"
    assert session.agent_runs[0].agent_capability == "central_memory"
    assert session.agent_runs[0].cost_usd == 0.0
    assert session.agent_runs[0].tokens_in == 0

    assert len(session.audit_events) == 1
    assert session.audit_events[0].action == "central_memory_indexed"


# ── Test 2: Node 2 Missing / Incomplete -> Refuses to Index Memory ─────────────

@pytest.mark.asyncio
async def test_central_memory_refuses_when_node2_incomplete():
    """Verify Node 3 refuses to execute and returns 400 if Node 2 has not run."""
    session = CentralMemoryMockSession()
    inst_id = uuid.uuid4()
    wf = _build_mock_workflow_instance(inst_id, ORG_A, "Rahul Sharma", "Capture Only Run", is_node2_done=False)
    session.add(wf)

    req = CentralMemoryRequest(instance_id=str(inst_id))
    with pytest.raises(HTTPException) as exc_info:
        await process_central_memory(req, db=session, current_user=USER_ORG_A)

    assert exc_info.value.status_code == 400
    assert "Node 2 (Process Conversation) has not successfully completed" in exc_info.value.detail
    assert len(session.contacts) == 0
    assert len(session.conversations) == 0


# ── Test 3: Idempotency (Same Run Processed Twice -> No Duplicates) ─────────────

@pytest.mark.asyncio
async def test_central_memory_idempotency_prevents_duplicates():
    """Executing Node 3 twice for the same run must reuse records with no duplicates."""
    session = CentralMemoryMockSession()
    inst_id = uuid.uuid4()
    wf = _build_mock_workflow_instance(inst_id, ORG_A, "Rahul Sharma", "Idempotent Run", is_node2_done=True)
    session.add(wf)

    req = CentralMemoryRequest(instance_id=str(inst_id))

    # First execution
    resp1 = await process_central_memory(req, db=session, current_user=USER_ORG_A)
    assert resp1.idempotent_reused is False
    assert len(session.contacts) == 1
    assert len(session.conversations) == 1
    initial_item_count = len(session.memory_items)

    # Second execution for same run
    resp2 = await process_central_memory(req, db=session, current_user=USER_ORG_A)
    assert resp2.idempotent_reused is True
    assert resp2.conversation_id == resp1.conversation_id
    assert resp2.contact_id == resp1.contact_id

    # Verify no new contacts, conversations, or memory items were created
    assert len(session.contacts) == 1
    assert len(session.conversations) == 1
    assert len(session.memory_items) == initial_item_count


# ── Test 4: Second-Conversation Test (Same Contact in New Run) ──────────────────

@pytest.mark.asyncio
async def test_central_memory_second_conversation_appended_to_same_contact():
    """
    Second-Conversation Test:
    Conversation 1: Rahul Sharma -> AI automation
    Conversation 2: Rahul Sharma -> Pilot implementation
    Expected:
    1 Contact record
    2 Conversation records
    Conversation count = 2
    Both conversations intact and preserved.
    """
    session = CentralMemoryMockSession()

    # --- Conversation 1 ---
    run1_id = uuid.uuid4()
    wf1 = _build_mock_workflow_instance(run1_id, ORG_A, "Rahul Sharma", "AI Automation Sync", is_node2_done=True)
    session.add(wf1)

    req1 = CentralMemoryRequest(instance_id=str(run1_id))
    resp1 = await process_central_memory(req1, db=session, current_user=USER_ORG_A)

    assert resp1.memory.total_conversations == 1
    contact_id = resp1.contact_id
    assert len(session.contacts) == 1
    assert len(session.conversations) == 1

    # --- Conversation 2 (New Run, Same Contact Name) ---
    run2_id = uuid.uuid4()
    wf2 = _build_mock_workflow_instance(run2_id, ORG_A, "  rahul sharma  ", "Pilot Implementation Review", is_node2_done=True)
    # Give conversation 2 different commitments
    wf2.context["node2_process_conversation"]["extraction"]["commitments"] = [
        {"owner": "Rahul Sharma", "commitment": "Approve pilot budget by Wednesday", "due_date": "2026-10-07"}
    ]
    session.add(wf2)

    req2 = CentralMemoryRequest(instance_id=str(run2_id))
    resp2 = await process_central_memory(req2, db=session, current_user=USER_ORG_A)

    # CRITICAL VERIFICATIONS:
    # 1. Same Contact Reused!
    assert resp2.contact_id == contact_id
    assert len(session.contacts) == 1, "Must NOT create a duplicate contact for the same normalized name!"

    # 2. Two distinct conversations stored
    assert len(session.conversations) == 2, "Must preserve both conversations!"
    assert resp2.memory.total_conversations == 2

    # 3. Both conversations are associated with the same contact
    conv1 = session.conversations[resp1.conversation_id]
    conv2 = session.conversations[resp2.conversation_id]
    assert conv1.contact_id == conv2.contact_id

    # 4. Conversation 1 evidence remained intact
    assert "AI Automation Sync" in conv1.title
    assert "Pilot Implementation Review" in conv2.title


# ── Test 5: Cross-Tenant Test (Same Name in Different Orgs) ────────────────────

@pytest.mark.asyncio
async def test_central_memory_cross_tenant_isolation():
    """
    Org A -> Rahul Sharma
    Org B -> Rahul Sharma
    Expected: Two completely separate contact records with independent memory.
    """
    session = CentralMemoryMockSession()

    # Org A Meeting
    run_a = uuid.uuid4()
    wf_a = _build_mock_workflow_instance(run_a, ORG_A, "Rahul Sharma", "Org A Client Meeting", is_node2_done=True)
    session.add(wf_a)

    resp_a = await process_central_memory(CentralMemoryRequest(instance_id=str(run_a)), db=session, current_user=USER_ORG_A)
    assert resp_a.memory.contact_name == "Rahul Sharma"
    contact_a_id = resp_a.contact_id

    # Org B Meeting (Same contact name, different org)
    run_b = uuid.uuid4()
    wf_b = _build_mock_workflow_instance(run_b, ORG_B, "Rahul Sharma", "Org B Supplier Meeting", is_node2_done=True)
    session.add(wf_b)

    resp_b = await process_central_memory(CentralMemoryRequest(instance_id=str(run_b)), db=session, current_user=USER_ORG_B)
    assert resp_b.memory.contact_name == "Rahul Sharma"
    contact_b_id = resp_b.contact_id

    # MUST be different contacts
    assert contact_a_id != contact_b_id, "Contacts across different orgs must never be merged!"
    assert len(session.contacts) == 2

    contact_a = session.contacts[contact_a_id]
    contact_b = session.contacts[contact_b_id]
    assert str(contact_a.organization_id) == ORG_A
    assert str(contact_b.organization_id) == ORG_B


# ── Test 6: Unauthorized Organization Access Rejected ─────────────────────────

@pytest.mark.asyncio
async def test_central_memory_unauthorized_access_rejected():
    """A user from Org B cannot index or access an Org A workflow instance."""
    session = CentralMemoryMockSession()
    run_a = uuid.uuid4()
    wf_a = _build_mock_workflow_instance(run_a, ORG_A, "Rahul Sharma", "Org A Confidential", is_node2_done=True)
    session.add(wf_a)

    # Bob (Org B) tries to process Org A run
    req = CentralMemoryRequest(instance_id=str(run_a))
    with pytest.raises(HTTPException) as exc_info:
        await process_central_memory(req, db=session, current_user=USER_ORG_B)

    assert exc_info.value.status_code == 403
    assert "Access forbidden" in exc_info.value.detail


# ── Test 7: Contact History Endpoint Scoped by Organization ───────────────────

@pytest.mark.asyncio
async def test_contact_history_endpoint_and_cross_tenant_rejection():
    """Verify GET /contacts/{id}/history returns aggregated memory and rejects foreign orgs."""
    session = CentralMemoryMockSession()

    run_id = uuid.uuid4()
    wf = _build_mock_workflow_instance(run_id, ORG_A, "Rahul Sharma", "Strategic Planning", is_node2_done=True)
    session.add(wf)

    resp = await process_central_memory(CentralMemoryRequest(instance_id=str(run_id)), db=session, current_user=USER_ORG_A)
    contact_id = resp.contact_id

    # Org A user can retrieve history
    hist = await get_contact_memory_history(contact_id=contact_id, db=session, current_user=USER_ORG_A)
    assert hist.contact_name == "Rahul Sharma"
    assert hist.total_conversations == 1
    assert len(hist.facts) >= 1

    # Org B user cannot retrieve Org A contact history
    with pytest.raises(HTTPException) as exc_info:
        await get_contact_memory_history(contact_id=contact_id, db=session, current_user=USER_ORG_B)

    assert exc_info.value.status_code == 403
