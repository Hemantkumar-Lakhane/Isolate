import asyncio
import os
import uuid
from dotenv import load_dotenv
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from api.auth import TokenData
from api.routers.meeting_intelligence import (
    CentralMemoryRequest,
    process_central_memory,
    ActionGeneratorRequest,
    process_action_generator,
)
from db.models.core import WorkflowInstance, RelationshipConversation, RelationshipMemoryItem, ApprovalItem

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

async def recover():
    engine = create_async_engine(DATABASE_URL, echo=False, connect_args={"statement_cache_size": 0})
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    target_instance_id = "c0eaf648-1fce-4f73-99ef-8f8e244c8659"
    inst_uuid = uuid.UUID(target_instance_id)

    async with SessionLocal() as db:
        # Check initial state
        wf = (await db.execute(select(WorkflowInstance).where(WorkflowInstance.id == inst_uuid))).scalars().first()
        if not wf:
            print("Workflow instance not found!")
            return

        org_uuid = wf.organization_id
        user = TokenData(
            user_id="manual_test_recovery",
            email="developer@smbflow.io",
            organization_id=str(org_uuid),
            org_id=str(org_uuid),
            role="admin",
        )

        # Check existing conversations & items
        stmt_conv = select(RelationshipConversation).where(RelationshipConversation.workflow_instance_id == inst_uuid)
        initial_convs = list((await db.execute(stmt_conv)).scalars().all())
        print(f"Pre-recovery conversations for {inst_uuid}: {len(initial_convs)}")

        stmt_mem = select(RelationshipMemoryItem).where(RelationshipMemoryItem.workflow_instance_id == inst_uuid)
        initial_mems = list((await db.execute(stmt_mem)).scalars().all())
        print(f"Pre-recovery memory items for {inst_uuid}: {len(initial_mems)}")

        # 1. Run process_central_memory (idempotent recovery)
        print("\n--- Invoking process_central_memory (Idempotent Recovery) ---")
        cm_req = CentralMemoryRequest(instance_id=target_instance_id)
        cm_resp = await process_central_memory(cm_req, db=db, current_user=user)
        print(f"Central Memory Status: {cm_resp.status}")
        print(f"Idempotent Reused: {cm_resp.idempotent_reused}")
        print(f"Contact Name: {cm_resp.memory.contact_name}")
        print(f"Total Conversations: {cm_resp.memory.total_conversations}")

        # Check that NO duplicate conversations or memory items were added
        post_convs = list((await db.execute(stmt_conv)).scalars().all())
        post_mems = list((await db.execute(stmt_mem)).scalars().all())
        print(f"Post-recovery conversations: {len(post_convs)} (Change: +{len(post_convs) - len(initial_convs)})")
        print(f"Post-recovery memory items: {len(post_mems)} (Change: +{len(post_mems) - len(initial_mems)})")
        assert len(post_convs) == len(initial_convs), "DUPLICATE CONVERSATION CREATED!"
        assert len(post_mems) == len(initial_mems), "DUPLICATE MEMORY ITEMS CREATED!"

        # Verify context now has node3_central_memory
        wf_refreshed = (await db.execute(select(WorkflowInstance).where(WorkflowInstance.id == inst_uuid))).scalars().first()
        print(f"WorkflowInstance Current Node: {wf_refreshed.current_node}")
        print(f"Has node3_central_memory in context? {'node3_central_memory' in (wf_refreshed.context or {})}")

        # 2. Run process_action_generator (Node 4)
        print("\n--- Invoking process_action_generator (Node 4) ---")
        act_req = ActionGeneratorRequest(instance_id=target_instance_id)
        act_resp = await process_action_generator(act_req, db=db, current_user=user)
        print(f"Action Generator Status: {act_resp.status}")
        print(f"Current Node: {act_resp.current_node}")
        print(f"Our Commitments: {len(act_resp.our_commitments)}")
        for c in act_resp.our_commitments:
            print(f"  [Our Commitment] {c.action} (Due: {c.due_date_display}, Status: {c.status})")
        print(f"Contact Commitments: {len(act_resp.contact_commitments)}")
        for c in act_resp.contact_commitments:
            print(f"  [Waiting on Contact] {c.action} (Owner: {c.owner_display}, Due: {c.due_date_display}, Status: {c.status})")
        print(f"AI Suggestions: {len(act_resp.ai_suggestions)}")
        for s in act_resp.ai_suggestions:
            print(f"  [AI Suggestion] {s.action} (Reason: {s.reason})")
        print(f"Historical Commitments from prior meetings: {len(act_resp.historical_commitments)}")
        for h in act_resp.historical_commitments:
            print(f"  [Historical] {h.action} (Source: {h.source_title})")

        # Check ApprovalItems created
        stmt_appr = select(ApprovalItem).where(ApprovalItem.instance_id == inst_uuid)
        apprs = list((await db.execute(stmt_appr)).scalars().all())
        print(f"\nTotal ApprovalItems created for run: {len(apprs)}")

        print("\nRECOVERY OF RUN c0eaf648-1fce-4f73-99ef-8f8e244c8659 SUCCESSFUL!")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(recover())
