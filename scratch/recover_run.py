import sys
import os
sys.path.insert(0, os.path.abspath("."))

from dotenv import load_dotenv
load_dotenv()

import asyncio
import json
import uuid
from sqlalchemy import select
from core.database import AsyncSessionLocal
from db.models.core import WorkflowInstance, ApprovalItem
from api.routers.meeting_intelligence import process_action_generator, ActionGeneratorRequest
from api.auth import TokenData

async def recover():
    async with AsyncSessionLocal() as db:
        inst_id = uuid.UUID('c0eaf648-1fce-4f73-99ef-8f8e244c8659')
        stmt = select(WorkflowInstance).where(WorkflowInstance.id == inst_id)
        res = await db.execute(stmt)
        inst = res.scalar_one_or_none()
        if not inst:
            print('WorkflowInstance not found!')
            return

        print(f"WorkflowInstance {inst_id} found. Org: {inst.organization_id}")
        user = TokenData(
            user_id="recovery_agent",
            organization_id=str(inst.organization_id),
            tenant_id=str(inst.organization_id),
            email="admin@smbflow.internal",
            role="super_admin"
        )
        
        # 1. Execute recovery via process_action_generator
        req = ActionGeneratorRequest(instance_id=str(inst_id))
        print("Invoking process_action_generator...")
        resp = await process_action_generator(request=req, db=db, current_user=user)
        
        print("\n=== Result of process_action_generator ===")
        print("Status:", resp.status)
        print("Idempotent Reused:", resp.idempotent_reused)
        print("Message:", resp.message)
        print(f"Our Commitments ({len(resp.our_commitments)}):")
        for c in resp.our_commitments:
            print(f"  - [{c.status}] {c.action} (owner_display: {c.owner_display}, due: {c.due_date_display})")
        print(f"Waiting on Contact ({len(resp.contact_commitments)}):")
        for c in resp.contact_commitments:
            print(f"  - [{c.status}] {c.action} (owner_display: {c.owner_display}, due: {c.due_date_display})")
        print(f"AI Suggestions ({len(resp.ai_suggestions)}):")
        for s in resp.ai_suggestions:
            print(f"  - [{s.status}] {s.action} (reason: {s.reason})")
        print(f"Open Questions ({len(resp.open_questions)}):")
        for q in resp.open_questions:
            print(f"  - {q.question}")
        print(f"Historical Commitments ({len(resp.historical_commitments)}):")
        for h in resp.historical_commitments:
            print(f"  - [{h.status}] {h.action} (owner: {h.owner_display})")

        # 2. Check ApprovalItems in database
        stmt_appr = select(ApprovalItem).where(ApprovalItem.instance_id == inst_id)
        apprs = (await db.execute(stmt_appr)).scalars().all()
        print(f"\n=== Total ApprovalItems in database for this instance: {len(apprs)} ===")
        for a in apprs:
            p = a.payload or {}
            print(f"  ID: {a.id}, action_type: {p.get('action_type')}, status: {a.status}, reason: {a.reason}")

        # 3. Test IDEMPOTENCY: Run process_action_generator a second time!
        print("\n=== Testing IDEMPOTENCY: running process_action_generator a second time ===")
        resp2 = await process_action_generator(request=req, db=db, current_user=user)
        print("Status:", resp2.status)
        print("Idempotent Reused:", resp2.idempotent_reused)
        print("Message:", resp2.message)
        print(f"Our Commitments count: {len(resp2.our_commitments)}")
        print(f"Waiting on Contact count: {len(resp2.contact_commitments)}")
        print(f"AI Suggestions count: {len(resp2.ai_suggestions)}")

        stmt_appr2 = select(ApprovalItem).where(ApprovalItem.instance_id == inst_id)
        apprs2 = (await db.execute(stmt_appr2)).scalars().all()
        print(f"Total ApprovalItems after 2nd execution: {len(apprs2)} (expected: {len(apprs)})")
        assert len(apprs2) == len(apprs), f"Duplicate approval items detected! {len(apprs2)} vs {len(apprs)}"
        print("IDEMPOTENCY VERIFIED: 0 duplicates created!")

if __name__ == '__main__':
    asyncio.run(recover())
