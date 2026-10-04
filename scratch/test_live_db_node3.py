"""
scratch/test_live_db_node3.py
=============================
Live database verification script for Node 3 (Central Memory) against the active Supabase PostgreSQL database.
"""

import asyncio
import uuid
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

from core.database import AsyncSessionLocal
from api.auth import TokenData
from api.routers.meeting_intelligence import (
    CentralMemoryRequest,
    process_central_memory,
    get_contact_memory_history,
)
from db.models.core import (
    Organization,
    WorkflowInstance,
    RelationshipContact,
    RelationshipConversation,
    RelationshipMemoryItem,
)
from sqlalchemy import select, delete


async def run_live_test():
    print("=== LIVE POSTGRESQL VERIFICATION: NODE 3 (CENTRAL MEMORY) ===")

    # Test Organizations
    org_a_id = uuid.uuid4()
    org_b_id = uuid.uuid4()

    user_a = TokenData(
        user_id=str(uuid.uuid4()),
        email="owner_a@smbflow-test.com",
        role="org_admin",
        organization_id=str(org_a_id),
        tenant_id=str(org_a_id),
    )

    user_b = TokenData(
        user_id=str(uuid.uuid4()),
        email="owner_b@smbflow-test.com",
        role="org_admin",
        organization_id=str(org_b_id),
        tenant_id=str(org_b_id),
    )

    async with AsyncSessionLocal() as session:
        # Create test organizations
        org_a = Organization(id=org_a_id, name="Test Org A", industry="saas")
        org_b = Organization(id=org_b_id, name="Test Org B", industry="saas")
        session.add(org_a)
        session.add(org_b)

        # -------------------------------------------------------------
        # Step 1: Create Workflow Run 1 for Rahul Sharma (Org A)
        # -------------------------------------------------------------
        run1_id = uuid.uuid4()
        wf1 = WorkflowInstance(
            id=run1_id,
            organization_id=org_a_id,
            workflow_name="meeting_intelligence_followup",
            status="processed",
            current_node="n2",
            trigger_payload={
                "conversation_title": "Rahul Sharma - AI Automation Discussion",
                "contact_name": "Rahul Sharma",
                "participant_role": "VP of Customer Success",
                "conversation_type": "Online Meeting",
                "language": "English",
                "conversation_date": "2026-09-27",
            },
            context={
                "conversation_capture": {
                    "conversation_title": "Rahul Sharma - AI Automation Discussion",
                    "contact_name": "Rahul Sharma",
                    "participant_role": "VP of Customer Success",
                    "conversation_type": "Online Meeting",
                    "language": "English",
                    "conversation_date": "2026-09-27",
                },
                "node2_process_conversation": {
                    "status": "completed",
                    "transcript_text": "Hi Rahul, thank you for meeting. We discussed AI automation for customer support. I agreed to send him a proposal by Friday.",
                    "detected_language": "en",
                    "extraction": {
                        "summary": "Explored pilot project automating customer support with AI agents.",
                        "people": [
                            {
                                "name": "Rahul Sharma",
                                "facts": ["Customer Success VP at Acme Corp"],
                                "interests": ["AI ticket automation", "Zendesk integration"],
                                "needs": ["Reduce escalation lag by 50%"],
                                "opportunities": ["APAC enterprise rollout"],
                            }
                        ],
                        "commitments": [
                            {"owner": "Speaker", "commitment": "Send short proposal by Friday", "due_date": "2026-10-02"}
                        ],
                        "suggested_actions": [
                            {"action": "Prepare 3 customer support ROI case studies", "reason": "Accelerate budget signoff"}
                        ],
                        "open_questions": ["What is their current monthly ticket volume?"],
                    },
                },
            },
            started_at=datetime.utcnow(),
        )
        session.add(wf1)
        await session.commit()
        print(f"Created Workflow Run 1 in DB: {run1_id}")

    # Process Node 3 for Run 1
    async with AsyncSessionLocal() as session:
        resp1 = await process_central_memory(
            CentralMemoryRequest(instance_id=str(run1_id)),
            db=session,
            current_user=user_a,
        )
        print(f"[OK] Run 1 Processed! Contact ID: {resp1.contact_id}, Conversations: {resp1.memory.total_conversations}")
        assert resp1.memory.contact_name == "Rahul Sharma"
        assert resp1.memory.total_conversations == 1
        assert len(resp1.memory.commitments) == 1
        assert resp1.memory.commitments[0].is_ai_generated is False
        assert len(resp1.memory.suggested_actions) == 1
        assert resp1.memory.suggested_actions[0].is_ai_generated is True
        contact_id_a = resp1.contact_id

    # -------------------------------------------------------------
    # Step 2: Idempotency Check on Run 1
    # -------------------------------------------------------------
    async with AsyncSessionLocal() as session:
        resp1_idem = await process_central_memory(
            CentralMemoryRequest(instance_id=str(run1_id)),
            db=session,
            current_user=user_a,
        )
        print(f"[OK] Run 1 Idempotent Re-run: Reused={resp1_idem.idempotent_reused}, Conversations: {resp1_idem.memory.total_conversations}")
        assert resp1_idem.idempotent_reused is True
        assert resp1_idem.contact_id == contact_id_a
        assert resp1_idem.memory.total_conversations == 1

    # -------------------------------------------------------------
    # Step 3: Conversation 2 with Same Contact (Rahul Sharma) in Org A
    # -------------------------------------------------------------
    run2_id = uuid.uuid4()
    async with AsyncSessionLocal() as session:
        wf2 = WorkflowInstance(
            id=run2_id,
            organization_id=org_a_id,
            workflow_name="meeting_intelligence_followup",
            status="processed",
            current_node="n2",
            trigger_payload={
                "conversation_title": "Rahul Sharma - Implementation Pilot Scope",
                "contact_name": "  rahul sharma  ",  # tests whitespace trimming & lowercase normalization
                "participant_role": "VP of Customer Success",
                "conversation_type": "Phone Call",
                "language": "English",
                "conversation_date": "2026-10-05",
            },
            context={
                "conversation_capture": {
                    "conversation_title": "Rahul Sharma - Implementation Pilot Scope",
                    "contact_name": "  rahul sharma  ",
                    "participant_role": "VP of Customer Success",
                    "conversation_type": "Phone Call",
                    "language": "English",
                    "conversation_date": "2026-10-05",
                },
                "node2_process_conversation": {
                    "status": "completed",
                    "transcript_text": "Rahul agreed to start the pilot with 200 tickets per day. He will sign off on the pilot NDA by Monday.",
                    "detected_language": "en",
                    "extraction": {
                        "summary": "Agreed to 200 ticket/day pilot volume starting next month.",
                        "people": [
                            {
                                "name": "Rahul Sharma",
                                "facts": ["Security review approved internally"],
                                "interests": ["Slack notification alerts"],
                                "needs": ["SOC2 compliance confirmation"],
                                "opportunities": ["Annual subscription conversion"],
                            }
                        ],
                        "commitments": [
                            {"owner": "Rahul Sharma", "commitment": "Sign off on pilot NDA by Monday", "due_date": "2026-10-08"}
                        ],
                        "suggested_actions": [
                            {"action": "Send SOC2 certificate to security team", "reason": "Unblock NDA signing"}
                        ],
                        "open_questions": ["Who is their primary IT administrator?"],
                    },
                },
            },
            started_at=datetime.utcnow(),
        )
        session.add(wf2)
        await session.commit()
        print(f"Created Workflow Run 2 in DB: {run2_id}")

    # Process Node 3 for Run 2
    async with AsyncSessionLocal() as session:
        resp2 = await process_central_memory(
            CentralMemoryRequest(instance_id=str(run2_id)),
            db=session,
            current_user=user_a,
        )
        print(f"[OK] Run 2 Processed! Contact ID: {resp2.contact_id}, Conversations: {resp2.memory.total_conversations}")
        # MUST reuse same contact!
        assert resp2.contact_id == contact_id_a
        assert resp2.memory.total_conversations == 2
        assert len(resp2.memory.conversations) == 2
        print("  -> Verified: Conversation 1 & Conversation 2 both intact and appended to same contact!")

    # -------------------------------------------------------------
    # Step 4: Cross-Tenant Test: Rahul Sharma in Org B
    # -------------------------------------------------------------
    run_b_id = uuid.uuid4()
    async with AsyncSessionLocal() as session:
        wf_b = WorkflowInstance(
            id=run_b_id,
            organization_id=org_b_id,
            workflow_name="meeting_intelligence_followup",
            status="processed",
            current_node="n2",
            trigger_payload={
                "conversation_title": "Org B Discussion with Rahul Sharma",
                "contact_name": "Rahul Sharma",
                "conversation_type": "Online Meeting",
                "language": "English",
                "conversation_date": "2026-09-27",
            },
            context={
                "conversation_capture": {
                    "conversation_title": "Org B Discussion with Rahul Sharma",
                    "contact_name": "Rahul Sharma",
                    "conversation_type": "Online Meeting",
                    "language": "English",
                    "conversation_date": "2026-09-27",
                },
                "node2_process_conversation": {
                    "status": "completed",
                    "transcript_text": "Meeting for Org B.",
                    "detected_language": "en",
                    "extraction": {
                        "summary": "Independent discussion for Org B.",
                        "people": [{"name": "Rahul Sharma", "facts": ["Independent contact"]}],
                        "commitments": [],
                        "suggested_actions": [],
                        "open_questions": [],
                    },
                },
            },
            started_at=datetime.utcnow(),
        )
        session.add(wf_b)
        await session.commit()

    async with AsyncSessionLocal() as session:
        resp_b = await process_central_memory(
            CentralMemoryRequest(instance_id=str(run_b_id)),
            db=session,
            current_user=user_b,
        )
        print(f"[OK] Org B Run Processed! Contact ID: {resp_b.contact_id}")
        assert resp_b.contact_id != contact_id_a, "Org A and Org B must have completely independent contacts!"
        assert resp_b.memory.total_conversations == 1
        print("  -> Verified: Org A and Org B have separate contacts despite identical name!")

    # Cleanup test records
    async with AsyncSessionLocal() as session:
        await session.execute(delete(RelationshipMemoryItem).where(RelationshipMemoryItem.organization_id.in_([org_a_id, org_b_id])))
        await session.execute(delete(RelationshipConversation).where(RelationshipConversation.organization_id.in_([org_a_id, org_b_id])))
        await session.execute(delete(RelationshipContact).where(RelationshipContact.organization_id.in_([org_a_id, org_b_id])))
        await session.execute(delete(WorkflowInstance).where(WorkflowInstance.organization_id.in_([org_a_id, org_b_id])))
        await session.execute(delete(Organization).where(Organization.id.in_([org_a_id, org_b_id])))
        await session.commit()
        print("Cleaned up test records from database.")

    print("\n>>> ALL LIVE POSTGRESQL TESTS PASSED SUCCESSFULLY! <<<")


if __name__ == "__main__":
    asyncio.run(run_live_test())
