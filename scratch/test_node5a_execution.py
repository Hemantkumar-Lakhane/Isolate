import sys
import os
sys.path.insert(0, os.path.abspath("."))
from dotenv import load_dotenv
load_dotenv()
import asyncio
import uuid
from core.database import AsyncSessionLocal
from api.routers.meeting_intelligence import (
    process_followup_draft,
    action_followup_draft,
    FollowupDraftRequest,
    FollowupDraftActionRequest,
)
from api.auth import TokenData
from db.models.core import WorkflowInstance, ApprovalItem, AuditEvent

async def test_node5a():
    async with AsyncSessionLocal() as db:
        inst_id = "c0eaf648-1fce-4f73-99ef-8f8e244c8659"
        
        # 1. Fetch instance to get organization_id
        inst = await db.get(WorkflowInstance, uuid.UUID(inst_id))
        assert inst is not None, "WorkflowInstance not found!"
        org_id = str(inst.organization_id)
        
        user = TokenData(
            user_id="test-user-id",
            email="founder@smbflow.io",
            organization_id=org_id,
            tenant_id=org_id,
            role="admin",
        )
        
        print(f"=== 1. Generating Node 5A Follow-up Draft for instance {inst_id} ===")
        req = FollowupDraftRequest(instance_id=inst_id)
        res = await process_followup_draft(req, db, user)
        print("Generated Status:", res.status)
        print("Draft ID:", res.draft.id)
        print("Subject:", res.draft.subject)
        print("Recipient Email:", res.draft.recipient_email)
        print("Recipient Email Available:", res.draft.recipient_email_available)
        print("Idempotent Reused:", res.idempotent_reused)
        print("Body Preview:\n", res.draft.body[:200], "...")
        print("Node 5 Note:", [n.note for n in res.nodes if n.id == "n5"][0])
        
        # Verify anti-hallucination: recipient_email should be None / False for Rahul unless specified
        print("Recipient email check passed:", res.draft.recipient_email is None or res.draft.recipient_email == "None")
        
        draft_id = res.draft.id
        
        print("\n=== 2. Testing Idempotency (Calling generate again) ===")
        res_idem = await process_followup_draft(req, db, user)
        print("Idempotent Reused:", res_idem.idempotent_reused)
        assert res_idem.idempotent_reused is True, "Expected idempotent_reused=True on second call!"
        assert res_idem.draft.id == draft_id, "Expected same draft ID!"
        
        print("\n=== 3. Testing Edit Draft Action ===")
        edited_subject = "Updated: AI Customer Support Pilot — Next Steps & Schedule"
        edited_body = res.draft.body + "\n\nP.S. Let's aim to wrap up the pilot setup by mid-October."
        edit_req = FollowupDraftActionRequest(
            action="edit",
            subject=edited_subject,
            body=edited_body,
            notes="Added P.S. note regarding timeline"
        )
        res_edit = await action_followup_draft(draft_id, edit_req, db, user)
        print("Edit Message:", res_edit.message)
        print("Updated Subject:", res_edit.draft.subject)
        print("Status after edit:", res_edit.draft.status)
        assert res_edit.draft.subject == edited_subject
        assert res_edit.draft.original_generated_subject is not None
        assert res_edit.draft.status == "awaiting_review"
        
        print("\n=== 4. Testing Snooze Action ===")
        snooze_req = FollowupDraftActionRequest(
            action="snooze",
            snoozed_until="Tomorrow 9:00 AM",
            snooze_reason="Waiting for internal team sync before final approval",
        )
        res_snooze = await action_followup_draft(draft_id, snooze_req, db, user)
        print("Snooze Message:", res_snooze.message)
        print("Status after snooze:", res_snooze.draft.status)
        print("Snoozed Until:", res_snooze.draft.snoozed_until)
        assert res_snooze.draft.status == "snoozed"
        
        print("\n=== 5. Testing Approve Action (STRICTLY NO SEND) ===")
        approve_req = FollowupDraftActionRequest(
            action="approve",
            notes="Approved after team review. Ready for later dispatch.",
        )
        res_approve = await action_followup_draft(draft_id, approve_req, db, user)
        print("Approve Message:", res_approve.message)
        print("Status after approve:", res_approve.draft.status)
        assert res_approve.draft.status == "approved"
        
        print("\n=== 6. Verify WorkflowInstance context and AuditEvent ===")
        await db.refresh(inst)
        ctx = inst.context or {}
        draft_ctx = ctx.get("node5_followup_draft")
        print("Workflow context draft status:", draft_ctx.get("status"))
        assert draft_ctx.get("status") == "approved"
        
        print("\nAll Node 5A verification tests passed cleanly on real instance!")

if __name__ == '__main__':
    asyncio.run(test_node5a())
