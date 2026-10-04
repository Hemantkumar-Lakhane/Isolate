import asyncio
import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, ".")
load_dotenv()

from core.database import AsyncSessionLocal
from sqlalchemy import select
from db.models.core import WorkflowInstance, ApprovalItem, AgentRunRecord, AuditEvent

async def inspect():
    async with AsyncSessionLocal() as session:
        stmt = (
            select(WorkflowInstance)
            .where(WorkflowInstance.workflow_name.like("%meeting%"))
            .order_by(WorkflowInstance.started_at.desc())
            .limit(5)
        )
        res = await session.execute(stmt)
        insts = res.scalars().all()
        print(f"Found {len(insts)} recent meeting runs:")
        for inst in insts:
            title = (inst.context or {}).get("conversation_capture", {}).get("conversation_title")
            contact = (inst.context or {}).get("conversation_capture", {}).get("contact_name")
            print(f"\n--- Run {inst.id} ---")
            print(f"Title: {title} | Contact: {contact}")
            print(f"Status: {inst.status} | Current Node: {inst.current_node}")
            print(f"Started at: {inst.started_at}")
            
            # Check ApprovalItems
            appr_stmt = select(ApprovalItem).where(ApprovalItem.instance_id == inst.id)
            apprs = (await session.execute(appr_stmt)).scalars().all()
            print(f"ApprovalItems ({len(apprs)}):")
            for a in apprs:
                print(f"  - [{a.review_type}] status={a.status}, reason={a.reason[:40] if a.reason else ''}")
            
            # Check AgentRunRecords
            arr_stmt = select(AgentRunRecord).where(AgentRunRecord.instance_id == inst.id).order_by(AgentRunRecord.completed_at.asc())
            runs = (await session.execute(arr_stmt)).scalars().all()
            print(f"AgentRunRecords ({len(runs)}):")
            for r in runs:
                print(f"  - Node {r.node_id}: {r.agent_capability} (status={r.status})")

            # Check context keys
            print(f"Context keys: {list((inst.context or {}).keys())}")
            if "node5_followup_draft" in (inst.context or {}):
                print(f"node5_followup_draft: {inst.context['node5_followup_draft']}")

if __name__ == "__main__":
    asyncio.run(inspect())
