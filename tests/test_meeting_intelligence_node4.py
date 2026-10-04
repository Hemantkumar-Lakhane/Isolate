"""
tests/test_meeting_intelligence_node4.py
========================================
Automated test suite for Meeting Intelligence & Follow-up:
NODE 4 — Action Generator (Deterministic Action Classification & Action Center Integration)

Verifies:
1. Our commitment -> internal pending action (owner_type="internal", owner_display="You / Internal", status="pending").
2. Contact commitment -> waiting-on-contact action (owner_type="contact", owner_display="Rahul Sharma", status="waiting").
3. AI suggestion -> suggestion, NOT confirmed task (status="suggested", clearly separated).
4. Open question -> preserved as contextual intelligence, NOT converted to task.
5. Due dates -> normalized due dates preserved, null dates display "No due date".
6. Unknown owner -> not falsely assigned to our commitments.
7. Idempotency -> running Node 4 twice creates zero duplicate ApprovalItems.
8. Second conversation -> only creates current conversation's actions; historical commitments provided as read-only context.
9. Node 3 incomplete -> Node 4 rejected with clean HTTP 400.
10. Cross-tenant access -> forbidden (HTTP 403).
11. Action Center integration -> ApprovalItems can be queried via list_approval_items and converted via approval_item_to_dict.
12. Refresh/rehydration -> get_meeting_intelligence_run restores Node 4 actions.
"""

import uuid
import pytest
from datetime import datetime
from unittest.mock import AsyncMock

from fastapi import HTTPException
from api.auth import TokenData
from api.routers.meeting_intelligence import (
    ActionGeneratorRequest,
    process_action_generator,
    get_meeting_intelligence_run,
    _classify_commitment_owner,
    _format_due_date_display,
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


class ActionGeneratorMockSession:
    """Mock async database session managing entities for Action Generator tests."""

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

        # Query RelationshipMemoryItem
        if "relationship_memory_items" in stmt_str:
            matched = list(self.memory_items)
            # Filter by contact_id if present
            for c_id in self.contacts:
                if c_id.lower() in param_vals:
                    matched = [m for m in matched if str(m.contact_id).lower() == c_id.lower()]
                    break
            # Check if query filters by conversation_id
            if "!=" in stmt_str or "<>" in stmt_str:
                for conv_id in self.conversations:
                    if conv_id.lower() in param_vals:
                        matched = [m for m in matched if str(m.conversation_id).lower() != conv_id.lower()]
                        break
            elif "conversation_id" in stmt_str:
                for conv_id in self.conversations:
                    if conv_id.lower() in param_vals:
                        matched = [m for m in matched if str(m.conversation_id).lower() == conv_id.lower()]
                        break

            mock_result.scalars = lambda: AsyncMock(
                first=lambda: matched[0] if matched else None,
                all=lambda: matched,
            )
            return mock_result

        # Query ApprovalItem
        if "approval_items" in stmt_str:
            matched = []
            for appr in self.approval_items.values():
                if "followup_email_draft" in stmt_str and getattr(appr, "review_type", None) != "followup_email_draft":
                    continue
                if "n4" in stmt_str and getattr(appr, "node_id", None) != "n4":
                    continue
                if str(appr.instance_id).lower() in param_vals or str(appr.instance_id).lower() in stmt_str:
                    matched.append(appr)
                elif str(appr.id).lower() in param_vals or str(appr.id).lower() in stmt_str:
                    matched.append(appr)
                elif not params:
                    matched.append(appr)

            mock_result.scalars = lambda: AsyncMock(
                first=lambda: matched[0] if matched else None,
                all=lambda: matched,
            )
            return mock_result

        # Fallback
        mock_result.scalars = lambda: AsyncMock(first=lambda: None, all=lambda: [])
        return mock_result


def _build_test_run(
    org_id: str,
    contact_name: str = "Rahul Sharma",
    commitments=None,
    suggested_actions=None,
    open_questions=None,
    node3_done: bool = True,
):
    """Helper to set up mock session with completed Nodes 1, 2, and optionally 3."""
    session = ActionGeneratorMockSession()
    inst_id = uuid.uuid4()
    org_uuid = uuid.UUID(org_id)
    contact_id = uuid.uuid4()
    conv_id = uuid.uuid4()

    if commitments is None:
        commitments = [
            {"owner": "Speaker", "action": "Send Rahul the proposal", "due_date": "2026-10-02"},
            {"owner": "Rahul", "action": "Share list of common customer queries", "due_date": "2026-10-01"},
        ]
    if suggested_actions is None:
        suggested_actions = [
            {"action": "Prepare evaluation criteria for the query list", "reason": "Will accelerate adoption"},
        ]
    if open_questions is None:
        open_questions = [
            "What is Rahul's budget range for the pilot?",
        ]

    # Contact
    contact = RelationshipContact(
        id=contact_id,
        organization_id=org_uuid,
        name=contact_name,
        normalized_name=contact_name.strip().lower(),
        role="VP of Operations",
        company="Apex Logistics",
        created_at=datetime.utcnow(),
    )
    session.add(contact)

    # Conversation
    conv = RelationshipConversation(
        id=conv_id,
        organization_id=org_uuid,
        contact_id=contact_id,
        workflow_instance_id=inst_id,
        title=f"Meeting with {contact_name}",
        conversation_type="sales_discovery",
        conversation_date="2026-09-27",
        transcript="Speaker: I will send Rahul the proposal by Friday. Rahul: I will share the customer queries by Wednesday.",
        summary="Discovery meeting with Rahul.",
        created_at=datetime.utcnow(),
    )
    session.add(conv)

    # WorkflowInstance context
    ctx = {
        "conversation_capture": {
            "contact_name": contact_name,
            "conversation_title": f"Meeting with {contact_name}",
            "conversation_date": "2026-09-27",
        },
        "node2_process_conversation": {
            "status": "completed",
            "extraction": {
                "summary": "Meeting with Rahul Sharma.",
                "commitments": commitments,
                "suggested_actions": suggested_actions,
                "open_questions": open_questions,
            },
        },
    }

    if node3_done:
        ctx["node3_central_memory"] = {
            "contact_id": str(contact_id),
            "contact_name": contact_name,
            "conversation_id": str(conv_id),
            "status": "completed",
        }

    instance = WorkflowInstance(
        id=inst_id,
        organization_id=org_uuid,
        workflow_name="meeting_intelligence_followup",
        status="processed",
        current_node="n3" if node3_done else "n2",
        context=ctx,
        started_at=datetime.utcnow(),
    )
    session.add(instance)

    return session, inst_id, contact_id, conv_id


# =============================================================================
# TESTS
# =============================================================================

@pytest.mark.asyncio
async def test_action_generator_our_commitment_internal_pending():
    """Verify that an internal commitment becomes our_commitment with status='pending' and creates ApprovalItem."""
    session, inst_id, contact_id, conv_id = _build_test_run(
        ORG_A,
        commitments=[{"owner": "Speaker", "action": "Send Rahul the proposal", "due_date": "2026-10-02"}]
    )

    req = ActionGeneratorRequest(instance_id=str(inst_id))
    resp = await process_action_generator(req, db=session, current_user=USER_ORG_A)

    assert resp.status == "completed"
    assert resp.current_node == "n4"
    assert len(resp.our_commitments) == 1
    assert len(resp.contact_commitments) == 0

    item = resp.our_commitments[0]
    assert item.action_type == "our_commitment"
    assert item.action == "Send Rahul the proposal"
    assert item.owner_type == "internal"
    assert item.owner_display == "You / Internal"
    assert item.due_date == "2026-10-02"
    assert item.due_date_display == "Oct 2, 2026"
    assert item.status == "pending"
    assert item.approval_id is not None

    # Check ApprovalItem in mock DB
    apprs = [a for a in session.approval_items.values() if a.payload.get("action_type") == "our_commitment"]
    assert len(apprs) == 1
    appr = apprs[0]
    assert appr.status == "pending"
    assert appr.review_type == "meeting_action"
    assert appr.reason == "Send Rahul the proposal"
    assert appr.payload["action_type"] == "our_commitment"
    assert appr.payload["owner_display"] == "You / Internal"


@pytest.mark.asyncio
async def test_action_generator_contact_commitment_waiting():
    """Verify that an external contact commitment becomes contact_commitment with status='waiting'."""
    session, inst_id, contact_id, conv_id = _build_test_run(
        ORG_A,
        contact_name="Rahul Sharma",
        commitments=[{"owner": "Rahul", "action": "Share list of common customer queries", "due_date": "2026-10-01"}]
    )

    req = ActionGeneratorRequest(instance_id=str(inst_id))
    resp = await process_action_generator(req, db=session, current_user=USER_ORG_A)

    assert len(resp.our_commitments) == 0
    assert len(resp.contact_commitments) == 1

    item = resp.contact_commitments[0]
    assert item.action_type == "contact_commitment"
    assert item.owner_type == "contact"
    assert item.owner_display == "Rahul Sharma"
    assert item.action == "Share list of common customer queries"
    assert item.status == "waiting"
    assert item.due_date == "2026-10-01"
    assert item.due_date_display == "Oct 1, 2026"

    # Verify ApprovalItem marked waiting
    apprs = [a for a in session.approval_items.values() if a.payload.get("action_type") == "contact_commitment"]
    assert len(apprs) == 1
    appr = apprs[0]
    assert appr.status == "waiting"
    assert appr.payload["action_type"] == "contact_commitment"
    assert appr.payload["owner_display"] == "Rahul Sharma"


@pytest.mark.asyncio
async def test_action_generator_ai_suggestion_not_confirmed_task():
    """Verify that AI recommendations remain suggestions (status='suggested') and are NOT confirmed tasks."""
    session, inst_id, contact_id, conv_id = _build_test_run(
        ORG_A,
        commitments=[],
        suggested_actions=[{"action": "Prepare evaluation criteria for the query list", "reason": "Accelerate onboarding"}]
    )

    req = ActionGeneratorRequest(instance_id=str(inst_id))
    resp = await process_action_generator(req, db=session, current_user=USER_ORG_A)

    assert len(resp.our_commitments) == 0
    assert len(resp.contact_commitments) == 0
    assert len(resp.ai_suggestions) == 1

    sugg = resp.ai_suggestions[0]
    assert sugg.action_type == "ai_suggestion"
    assert sugg.status == "suggested"
    assert sugg.action == "Prepare evaluation criteria for the query list"
    assert sugg.reason == "Accelerate onboarding"
    assert sugg.owner_display == "AI Suggested"
    assert sugg.due_date_display == "No due date"

    # Stored in ApprovalItem as status="suggested" (requires decision, not pending task)
    apprs = list(session.approval_items.values())
    assert len(apprs) == 1
    assert apprs[0].status == "suggested"


@pytest.mark.asyncio
async def test_action_generator_open_questions_preserved_not_tasks():
    """Verify open questions are preserved for context and not converted into ApprovalItem tasks."""
    session, inst_id, contact_id, conv_id = _build_test_run(
        ORG_A,
        commitments=[],
        suggested_actions=[],
        open_questions=["What is Rahul's budget range for the pilot?"]
    )

    req = ActionGeneratorRequest(instance_id=str(inst_id))
    resp = await process_action_generator(req, db=session, current_user=USER_ORG_A)

    assert len(resp.open_questions) == 1
    assert resp.open_questions[0].question == "What is Rahul's budget range for the pilot?"

    # Crucial: ZERO ApprovalItems should be created for open questions
    assert len(session.approval_items) == 0


@pytest.mark.asyncio
async def test_action_generator_due_dates_preserved():
    """Verify due date handling preserves valid dates and displays 'No due date' for missing dates."""
    assert _format_due_date_display("2026-10-02") == "Oct 2, 2026"
    assert _format_due_date_display(None) == "No due date"
    assert _format_due_date_display("") == "No due date"
    assert _format_due_date_display("null") == "No due date"
    assert _format_due_date_display("Wednesday") == "Wednesday"


@pytest.mark.asyncio
async def test_action_generator_unknown_owner_not_assigned_internally():
    """Verify that an ambiguous or unrecognized owner is marked 'unknown' and not forced into our commitments."""
    owner_type, owner_display = _classify_commitment_owner("Both", "Rahul Sharma", "Align on dates")
    assert owner_type == "unknown"
    assert owner_display == "Unassigned / Unknown"

    owner_type, owner_display = _classify_commitment_owner("David", "Rahul Sharma", "Review architecture")
    assert owner_type == "unknown"
    assert owner_display == "David"

    session, inst_id, contact_id, conv_id = _build_test_run(
        ORG_A,
        commitments=[{"owner": "Both", "action": "Align on dates", "due_date": None}]
    )
    req = ActionGeneratorRequest(instance_id=str(inst_id))
    resp = await process_action_generator(req, db=session, current_user=USER_ORG_A)

    # Must NOT be in our_commitments
    assert len(resp.our_commitments) == 0
    assert len(resp.contact_commitments) == 1
    assert resp.contact_commitments[0].owner_type == "unknown"


@pytest.mark.asyncio
async def test_action_generator_idempotency_prevents_duplicate_actions():
    """Verify that re-running Node 4 for the same run returns existing actions with zero new ApprovalItems."""
    session, inst_id, contact_id, conv_id = _build_test_run(ORG_A)

    req = ActionGeneratorRequest(instance_id=str(inst_id))
    resp1 = await process_action_generator(req, db=session, current_user=USER_ORG_A)
    assert resp1.idempotent_reused is False
    initial_appr_count = len(session.approval_items)
    assert initial_appr_count == 3  # 1 our, 1 contact, 1 ai_sugg

    # Second run for same instance_id
    resp2 = await process_action_generator(req, db=session, current_user=USER_ORG_A)
    assert resp2.idempotent_reused is True
    assert len(resp2.our_commitments) == len(resp1.our_commitments)
    assert len(session.approval_items) == initial_appr_count  # Zero duplicates added!


@pytest.mark.asyncio
async def test_action_generator_second_conversation_only_creates_current_actions():
    """Verify processing Conversation #2 creates only Conversation #2 actions and surfaces Conversation #1 as read-only historical context."""
    session, inst_id_1, contact_id, conv_id_1 = _build_test_run(
        ORG_A,
        commitments=[{"owner": "Speaker", "action": "Send Rahul proposal", "due_date": "2026-10-02"}]
    )

    # Run 1 generates actions
    req1 = ActionGeneratorRequest(instance_id=str(inst_id_1))
    await process_action_generator(req1, db=session, current_user=USER_ORG_A)
    assert len(session.approval_items) == 2  # 1 our commitment + 1 ai suggestion

    # Add historical memory item for Conversation 1 in Central Memory
    hist_mem = RelationshipMemoryItem(
        id=uuid.uuid4(),
        organization_id=uuid.UUID(ORG_A),
        contact_id=contact_id,
        conversation_id=conv_id_1,
        workflow_instance_id=inst_id_1,
        category="commitment",
        content="Send Rahul proposal",
        details={"owner": "Speaker", "due_date": "2026-10-02", "conversation_title": "Meeting 1"},
        source_date="2026-09-27",
        is_ai_generated=False,
    )
    session.add(hist_mem)

    # Now create Conversation 2 for the same contact
    inst_id_2 = uuid.uuid4()
    conv_id_2 = uuid.uuid4()

    conv2 = RelationshipConversation(
        id=conv_id_2,
        organization_id=uuid.UUID(ORG_A),
        contact_id=contact_id,
        workflow_instance_id=inst_id_2,
        title="Follow-up with Rahul",
        conversation_type="technical_followup",
        conversation_date="2026-09-28",
        transcript="Rahul: I will send the customer query list by Wednesday.",
        summary="Followup with Rahul.",
        created_at=datetime.utcnow(),
    )
    session.add(conv2)

    inst2 = WorkflowInstance(
        id=inst_id_2,
        organization_id=uuid.UUID(ORG_A),
        workflow_name="meeting_intelligence_followup",
        status="processed",
        current_node="n3",
        context={
            "conversation_capture": {"contact_name": "Rahul Sharma", "conversation_title": "Follow-up with Rahul"},
            "node2_process_conversation": {
                "status": "completed",
                "extraction": {
                    "summary": "Followup meeting.",
                    "commitments": [{"owner": "Rahul", "action": "Share customer query list", "due_date": "2026-10-01"}],
                    "suggested_actions": [],
                    "open_questions": [],
                },
            },
            "node3_central_memory": {
                "contact_id": str(contact_id),
                "contact_name": "Rahul Sharma",
                "conversation_id": str(conv_id_2),
                "status": "completed",
            },
        },
        started_at=datetime.utcnow(),
    )
    session.add(inst2)

    # Run Node 4 for Conversation 2
    req2 = ActionGeneratorRequest(instance_id=str(inst_id_2))
    resp2 = await process_action_generator(req2, db=session, current_user=USER_ORG_A)

    # Only 1 new action created for current conversation (waiting on contact)
    assert len(resp2.our_commitments) == 0
    assert len(resp2.contact_commitments) == 1
    assert resp2.contact_commitments[0].action == "Share customer query list"

    # Historical commitment from Conversation 1 surfaced as read-only context
    assert len(resp2.historical_commitments) == 1
    assert resp2.historical_commitments[0].action == "Send Rahul proposal"
    assert resp2.historical_commitments[0].source == "historical_conversation"


@pytest.mark.asyncio
async def test_action_generator_rejected_if_node3_incomplete():
    """Verify Node 4 refuses execution with HTTP 400 if Node 3 is not completed."""
    session, inst_id, contact_id, conv_id = _build_test_run(ORG_A, node3_done=False)

    req = ActionGeneratorRequest(instance_id=str(inst_id))
    with pytest.raises(HTTPException) as exc_info:
        await process_action_generator(req, db=session, current_user=USER_ORG_A)

    assert exc_info.value.status_code == 400
    assert "Node 3" in exc_info.value.detail


@pytest.mark.asyncio
async def test_action_generator_cross_tenant_access_rejected():
    """Verify that Org B cannot run Node 4 or access actions from Org A."""
    session, inst_id, contact_id, conv_id = _build_test_run(ORG_A)

    req = ActionGeneratorRequest(instance_id=str(inst_id))
    with pytest.raises(HTTPException) as exc_info:
        await process_action_generator(req, db=session, current_user=USER_ORG_B)

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_action_generator_action_center_integration():
    """Verify ApprovalItems created by Node 4 integrate cleanly with Action Center CRUD formatting."""
    session, inst_id, contact_id, conv_id = _build_test_run(ORG_A)

    req = ActionGeneratorRequest(instance_id=str(inst_id))
    await process_action_generator(req, db=session, current_user=USER_ORG_A)

    apprs = list(session.approval_items.values())
    our_appr = next(a for a in apprs if a.payload.get("action_type") == "our_commitment")

    # Format via crud.approval_item_to_dict
    d = await crud.approval_item_to_dict(our_appr)
    assert d["review_type"] == "meeting_action"
    assert d["workflow_name"] == "meeting_intelligence_followup"
    assert "Send Rahul the proposal" in d["payload"]["subject"]
    assert d["payload"]["recipient"] == "Rahul Sharma"
    assert d["status"] == "pending"


@pytest.mark.asyncio
async def test_action_generator_refresh_rehydration_preserves_node4():
    """Verify that get_meeting_intelligence_run rehydrates Node 4 actions and sets pipeline node n4 to completed."""
    session, inst_id, contact_id, conv_id = _build_test_run(ORG_A)

    req = ActionGeneratorRequest(instance_id=str(inst_id))
    await process_action_generator(req, db=session, current_user=USER_ORG_A)

    # Rehydrate run detail
    detail = await get_meeting_intelligence_run(str(inst_id), db=session, current_user=USER_ORG_A)

    assert detail.actions is not None
    assert len(detail.actions.our_commitments) == 1
    assert len(detail.actions.contact_commitments) == 1
    n4_node = next(n for n in detail.nodes if n.id == "n4")
    assert n4_node.status == "completed"
    assert n4_node.implemented is True
    n5_node = next(n for n in detail.nodes if n.id == "n5")
    assert n5_node.status == "pending"
    assert n5_node.implemented is False


@pytest.mark.asyncio
async def test_action_generator_persisted_node2_extraction_simultaneous():
    """
    Regression test: Persisted Node 2 extraction containing simultaneously:
    - commitments with 'commitment' field name (Speaker and Rahul Sharma)
    - suggested_actions with 'action' and 'reason'
    Expected Node 4:
    our_commitments = 1
    contact_commitments = 1
    ai_suggestions = 1
    And idempotent on 2nd run with 0 duplicates.
    """
    commitments = [
        {
            "owner": "Rahul Sharma",
            "commitment": "Share list of common customer queries",
            "due_date": "2026-09-30",
        },
        {
            "owner": "Speaker",
            "commitment": "Prepare and send pilot proposal",
            "due_date": "2026-10-02",
        },
    ]
    suggested_actions = [
        {
            "action": "Define pilot evaluation criteria",
            "reason": "Clear KPIs ensure measurable success for the pilot",
        },
    ]

    session, inst_id, contact_id, conv_id = _build_test_run(
        ORG_A,
        contact_name="Rahul Sharma",
        commitments=commitments,
        suggested_actions=suggested_actions,
    )

    req = ActionGeneratorRequest(instance_id=str(inst_id))
    resp = await process_action_generator(req, db=session, current_user=USER_ORG_A)

    assert resp.status == "completed"
    assert len(resp.our_commitments) == 1
    assert resp.our_commitments[0].action == "Prepare and send pilot proposal"
    assert resp.our_commitments[0].owner_type == "internal"
    assert resp.our_commitments[0].owner_display == "You / Internal"
    assert resp.our_commitments[0].status == "pending"
    assert resp.our_commitments[0].due_date == "2026-10-02"

    assert len(resp.contact_commitments) == 1
    assert resp.contact_commitments[0].action == "Share list of common customer queries"
    assert resp.contact_commitments[0].owner_type == "contact"
    assert resp.contact_commitments[0].owner_display == "Rahul Sharma"
    assert resp.contact_commitments[0].status == "waiting"
    assert resp.contact_commitments[0].due_date == "2026-09-30"

    assert len(resp.ai_suggestions) == 1
    assert resp.ai_suggestions[0].action == "Define pilot evaluation criteria"
    assert resp.ai_suggestions[0].status == "suggested"

    # Verify ApprovalItems persisted
    apprs = list(session.approval_items.values())
    assert len(apprs) == 3
    internal_apprs = [a for a in apprs if a.payload.get("action_type") == "our_commitment"]
    contact_apprs = [a for a in apprs if a.payload.get("action_type") == "contact_commitment"]
    suggestion_apprs = [a for a in apprs if a.payload.get("action_type") == "ai_suggestion"]
    assert len(internal_apprs) == 1
    assert len(contact_apprs) == 1
    assert len(suggestion_apprs) == 1

    # Verify IDEMPOTENCY on second execution
    resp2 = await process_action_generator(req, db=session, current_user=USER_ORG_A)
    assert resp2.idempotent_reused is True
    assert len(resp2.our_commitments) == 1
    assert len(resp2.contact_commitments) == 1
    assert len(resp2.ai_suggestions) == 1
    apprs2 = list(session.approval_items.values())
    assert len(apprs2) == 3, f"Expected exactly 3 approval items, found {len(apprs2)} (duplicates created!)"


@pytest.mark.asyncio
async def test_action_generator_schema_rehydration_from_node3_central_memory():
    """
    Regression test: Schema mismatch catch between Node 2 -> Node 3 -> Node 4.
    If Node 2 extraction commitments is empty in context, but Node 3 persisted
    RelationshipMemoryItem rows with category='commitment', Node 4 falls back to
    RelationshipMemoryItem and correctly classifies the actions.
    """
    session = ActionGeneratorMockSession()
    inst_id = uuid.uuid4()
    org_uuid = uuid.UUID(ORG_A)
    contact_id = uuid.uuid4()
    conv_id = uuid.uuid4()

    # Create contact
    contact = RelationshipContact(
        id=contact_id,
        organization_id=org_uuid,
        name="Rahul Sharma",
        normalized_name="rahul sharma",
        role="VP of Operations",
        created_at=datetime.utcnow(),
    )
    session.add(contact)

    # Create conversation with structured_memory
    conv = RelationshipConversation(
        id=conv_id,
        organization_id=org_uuid,
        contact_id=contact_id,
        workflow_instance_id=inst_id,
        title="Rahul - AI Pilot Action Planning",
        conversation_type="Online Meeting",
        conversation_date="2026-09-27",
        structured_memory={
            "commitments": [
                {"owner": "Rahul Sharma", "commitment": "Share list of common customer queries", "due_date": "2026-09-30"},
                {"owner": "Speaker", "commitment": "Prepare and send pilot proposal", "due_date": "2026-10-02"},
            ]
        },
        created_at=datetime.utcnow(),
    )
    session.add(conv)

    # Create RelationshipMemoryItem rows as Node 3 stores them (content + details)
    mem1 = RelationshipMemoryItem(
        id=uuid.uuid4(),
        organization_id=org_uuid,
        contact_id=contact_id,
        conversation_id=conv_id,
        workflow_instance_id=inst_id,
        category="commitment",
        content="Share list of common customer queries",
        details={"owner": "Rahul Sharma", "due_date": "2026-09-30"},
        source_date="2026-09-27",
        created_at=datetime.utcnow(),
    )
    mem2 = RelationshipMemoryItem(
        id=uuid.uuid4(),
        organization_id=org_uuid,
        contact_id=contact_id,
        conversation_id=conv_id,
        workflow_instance_id=inst_id,
        category="commitment",
        content="Prepare and send pilot proposal",
        details={"owner": "Speaker", "due_date": "2026-10-02"},
        source_date="2026-09-27",
        created_at=datetime.utcnow(),
    )
    session.add(mem1)
    session.add(mem2)

    # WorkflowInstance context where Node 2 extraction has commitments empty
    ctx = {
        "conversation_capture": {
            "contact_name": "Rahul Sharma",
            "conversation_title": "Rahul - AI Pilot Action Planning",
            "conversation_date": "2026-09-27",
        },
        "node2_process_conversation": {
            "status": "completed",
            "extraction": {
                "summary": "Meeting with Rahul Sharma.",
                "commitments": [],  # Empty in context (simulating Node 2 extraction gap)
                "suggested_actions": [
                    {"action": "Define pilot evaluation criteria", "reason": "KPI definition"}
                ],
                "open_questions": ["What is the expected pilot start date?"],
            },
        },
        "node3_central_memory": {
            "contact_id": str(contact_id),
            "contact_name": "Rahul Sharma",
            "conversation_id": str(conv_id),
            "status": "completed",
        },
    }

    instance = WorkflowInstance(
        id=inst_id,
        organization_id=org_uuid,
        workflow_name="meeting_intelligence_followup",
        status="processed",
        current_node="n3",
        context=ctx,
        started_at=datetime.utcnow(),
    )
    session.add(instance)

    req = ActionGeneratorRequest(instance_id=str(inst_id))
    resp = await process_action_generator(req, db=session, current_user=USER_ORG_A)

    assert resp.status == "completed"
    assert len(resp.our_commitments) == 1
    assert resp.our_commitments[0].action == "Prepare and send pilot proposal"
    assert resp.our_commitments[0].owner_type == "internal"
    assert resp.our_commitments[0].owner_display == "You / Internal"
    assert resp.our_commitments[0].status == "pending"

    assert len(resp.contact_commitments) == 1
    assert resp.contact_commitments[0].action == "Share list of common customer queries"
    assert resp.contact_commitments[0].owner_type == "contact"
    assert resp.contact_commitments[0].owner_display == "Rahul Sharma"
    assert resp.contact_commitments[0].status == "waiting"

    assert len(resp.ai_suggestions) == 1
    assert resp.ai_suggestions[0].action == "Define pilot evaluation criteria"
    assert resp.ai_suggestions[0].status == "suggested"

