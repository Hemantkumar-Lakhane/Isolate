import asyncio
import os
import uuid
from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from api.auth import TokenData
from api.routers.meeting_intelligence import (
    ConversationCaptureRequest,
    capture_conversation,
    ProcessConversationRequest,
    process_conversation,
    CentralMemoryRequest,
    process_central_memory,
    ActionGeneratorRequest,
    process_action_generator,
)
from db.models.core import WorkflowInstance, RelationshipContact, RelationshipConversation, RelationshipMemoryItem, ApprovalItem

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

async def test_new_run_flow():
    engine = create_async_engine(DATABASE_URL, echo=False, connect_args={"statement_cache_size": 0})
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with SessionLocal() as db:
        # Get Rahul's existing contact
        c_stmt = select(RelationshipContact).where(RelationshipContact.normalized_name == "rahul sharma")
        contact = (await db.execute(c_stmt)).scalars().first()
        assert contact is not None, "Rahul Sharma contact should exist"
        org_uuid = contact.organization_id

        # Count prior conversations
        convs_before = len((await db.execute(select(RelationshipConversation).where(RelationshipConversation.contact_id == contact.id))).scalars().all())
        print(f"Prior conversations for Rahul Sharma: {convs_before}")

        user = TokenData(
            user_id="test_runner",
            email="developer@smbflow.io",
            organization_id=str(org_uuid),
            org_id=str(org_uuid),
            role="admin",
        )

        # 1. Node 1: Capture
        print("\n--- Testing Node 1: Conversation Capture ---")
        cap_req = ConversationCaptureRequest(
            conversation_title="Rahul - Automated Regression Test",
            contact_name="Rahul Sharma",
            conversation_type="Online Meeting",
            recording={"filename": "demosmb3.mp3", "file_id": "test_audio_01", "size_bytes": 10240, "stored_path": "uploads/audio/test_audio_01_demosmb3.mp3"},
            language="Auto Detect",
            conversation_date="2026-09-27",
        )
        cap_resp = await capture_conversation(cap_req, db=db, current_user=user)
        inst_id = cap_resp.instance_id
        print(f"Node 1 Completed. Instance ID: {inst_id}")
        assert cap_resp.status == "capture_completed"

        # Mock Node 2 data directly into instance context so we don't need external LLM / Whisper audio file calls
        wf = (await db.execute(select(WorkflowInstance).where(WorkflowInstance.id == uuid.UUID(inst_id)))).scalars().first()
        updated_ctx = dict(wf.context or {})
        updated_ctx["node2_process_conversation"] = {
            "status": "completed",
            "transcript_text": "Speaker: I will send Rahul the pilot agreement by Thursday. Rahul: I will review and send back signatures by next Monday.",
            "detected_language": "en",
            "model_used": "mock_whisper_test",
            "extraction": {
                "summary": "Agreement review meeting with Rahul.",
                "commitments": [
                    {"owner": "Speaker", "action": "Send Rahul the pilot agreement", "due_date": "2026-10-01"},
                    {"owner": "Rahul", "action": "Review and send back signatures", "due_date": "2026-10-05"},
                ],
                "suggested_actions": [
                    {"action": "Prepare onboarding checklist for pilot kickoff", "reason": "Ensure smooth kickoff"},
                ],
                "open_questions": [
                    "Who from Rahul's team will join the kickoff?",
                ],
                "facts": ["Pilot agreement being drafted"],
                "interests": ["Automation"],
                "needs": ["Fast deployment"],
                "opportunities": ["Full rollout in Q4"],
            }
        }
        updated_ctx["implemented_nodes"] = ["n1", "n2"]
        wf.context = updated_ctx
        wf.current_node = "n2"
        await db.commit()
        print("Node 2 extraction prepared.")

        # 2. Node 3: Central Memory
        print("\n--- Testing Node 3: Central Memory ---")
        cm_req = CentralMemoryRequest(instance_id=inst_id)
        cm_resp = await process_central_memory(cm_req, db=db, current_user=user)
        print(f"Node 3 Completed. Status: {cm_resp.status}")
        print(f"Contact Name: {cm_resp.memory.contact_name}")
        print(f"Total Conversations for Rahul: {cm_resp.memory.total_conversations} (was {convs_before})")
        assert cm_resp.status == "completed"
        assert cm_resp.memory.contact_id == str(contact.id), "Must match existing Rahul Sharma contact!"
        assert cm_resp.memory.total_conversations == convs_before + 1, "Must append conversation to same contact!"

        # Verify context now has node3_central_memory
        wf_after_n3 = (await db.execute(select(WorkflowInstance).where(WorkflowInstance.id == uuid.UUID(inst_id)))).scalars().first()
        assert "node3_central_memory" in (wf_after_n3.context or {}), "node3_central_memory must be in context!"
        print("Verified node3_central_memory successfully persisted in WorkflowInstance.context.")

        # Test Node 3 idempotency: calling it again must NOT create duplicate conversation
        print("\n--- Testing Node 3 Idempotency ---")
        cm_resp_2 = await process_central_memory(cm_req, db=db, current_user=user)
        assert cm_resp_2.idempotent_reused is True
        assert cm_resp_2.memory.total_conversations == convs_before + 1, "Idempotent call must not increment conversations count!"
        print("Node 3 Idempotency verified: 0 duplicates created.")

        # 3. Node 4: Action Generator
        print("\n--- Testing Node 4: Action Generator ---")
        act_req = ActionGeneratorRequest(instance_id=inst_id)
        act_resp = await process_action_generator(act_req, db=db, current_user=user)
        print(f"Node 4 Completed. Status: {act_resp.status}")
        print(f"Our Commitments: {len(act_resp.our_commitments)}")
        assert len(act_resp.our_commitments) == 1
        assert act_resp.our_commitments[0].action == "Send Rahul the pilot agreement"
        assert act_resp.our_commitments[0].owner_type == "internal"
        assert act_resp.our_commitments[0].status == "pending"

        print(f"Contact Commitments: {len(act_resp.contact_commitments)}")
        assert len(act_resp.contact_commitments) == 1
        assert act_resp.contact_commitments[0].action == "Review and send back signatures"
        assert act_resp.contact_commitments[0].owner_type == "contact"
        assert act_resp.contact_commitments[0].status == "waiting"

        print(f"AI Suggestions: {len(act_resp.ai_suggestions)}")
        assert len(act_resp.ai_suggestions) == 1
        assert act_resp.ai_suggestions[0].status == "suggested"

        print(f"Open Questions: {len(act_resp.open_questions)}")
        assert len(act_resp.open_questions) == 1

        print(f"Historical Commitments surfaced: {len(act_resp.historical_commitments)}")

        # Verify ApprovalItems in DB
        apprs = list((await db.execute(select(ApprovalItem).where(ApprovalItem.instance_id == uuid.UUID(inst_id)))).scalars().all())
        print(f"ApprovalItems persisted in DB: {len(apprs)}")
        assert len(apprs) == 3  # 1 internal pending + 1 contact waiting + 1 ai suggested

        # Verify Pipeline Nodes Status
        n5_node = next(n for n in act_resp.nodes if n.id == "n5")
        assert n5_node.status == "pending"
        assert n5_node.implemented is False, "Node 5 must remain pending / not implemented!"

        print("\nALL END-TO-END PIPELINE CHECKS PASSED PERFECTLY!")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test_new_run_flow())
