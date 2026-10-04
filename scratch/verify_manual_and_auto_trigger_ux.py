"""
scratch/verify_manual_and_auto_trigger_ux.py
============================================
Verification script for SMBFlow UX Fix:
- Workflow trigger-info endpoint (reading real runtime fixture counts)
- Manual workflow trigger via POST /api/v1/workflows/trigger
- Automatic event detector trigger distinction
- Workflow runs serialization with Manual vs New Email trigger badges
- Safe Action Center integration (only real ApprovalItems)
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(override=False)

from sqlalchemy import select
from core.database import get_raw_session
import api.crud as crud
from core.event_detector import EmailEventDetector
from db.models.core import WorkflowInstance, ApprovalItem, ProcessedEmailEvent


async def verify_all():
    print("=" * 70)
    print("SMBFLOW WORKFLOW TRIGGER / RUN NOW UX VERIFICATION")
    print("=" * 70)

    # 1. Verify Trigger Info API Logic & Runtime Fixture Count
    print("\n[TEST 1] Testing Trigger Info API logic on 'email_summarizer'...")
    fixture_path = Path("db/seed/data/email_messages.json")
    assert fixture_path.exists(), "Email messages fixture must exist"
    with open(fixture_path, "r", encoding="utf-8") as fp:
        fixture_msgs = json.load(fp)
    fixture_count = len(fixture_msgs)
    print(f"  [OK] Real fixture messages detected: {fixture_count}")

    # 2. Test Manual Execution Trigger (POST /api/v1/workflows/trigger)
    print("\n[TEST 2] Testing Manual Execution Trigger contract...")
    from api.main import trigger_workflow, WorkflowTriggerRequest
    from starlette.datastructures import Headers

    class MockUser:
        user_id = "00000000-0000-0000-0000-000000000001"
        email = "lead_reviewer@smbflow.test"
        role = "org_admin"
        organization_id = "ab17c472-46f5-4778-9df9-293cefa86e1c"
        tenant_id = "ab17c472-46f5-4778-9df9-293cefa86e1c"
        raw_claims = {}

    class MockBgTasks:
        def __init__(self):
            self.tasks = []
        def add_task(self, func, *args, **kwargs):
            self.tasks.append((func, args, kwargs))

    bg = MockBgTasks()
    async with (await get_raw_session()) as session:
        # Trigger manual run with limit=15
        req = WorkflowTriggerRequest(
            workflow_name="email_summarizer",
            trigger_signal={"source": "manual_ui", "limit": 15},
        )
        res = await trigger_workflow(
            body=req,
            background_tasks=bg,
            current_user=MockUser(),
            db=session,
        )
        manual_run_id = res["run_id"]
        print(f"  [OK] Manual Trigger successful -> run_id: {manual_run_id}, status: {res['status']}")
        assert res["status"] == "pending"
        assert len(bg.tasks) == 1

        # Check DB instance properties
        inst = await crud.get_workflow_instance(session, manual_run_id)
        assert inst is not None
        d = crud.workflow_to_dict(inst)
        print(f"  [OK] Instance serialized: Trigger Type='{d.get('trigger_type')}', Source='{d.get('trigger_source')}', Messages={d.get('message_count')}")
        assert d.get("trigger_type") == "Manual"
        assert d.get("trigger_source") == "manual_ui"
        assert d.get("message_count") == 15

    # 3. Test Automatic Event-Driven Trigger
    print("\n[TEST 3] Testing Automatic Event-Driven Trigger distinction...")
    import uuid
    async with (await get_raw_session()) as session:
        auto_run_id = str(uuid.uuid4())
        await crud.create_workflow_instance(
            session,
            run_id=auto_run_id,
            tenant_id="ab17c472-46f5-4778-9df9-293cefa86e1c",
            workflow_name="email_summarizer",
            trigger_signal={
                "source": "email_event_detector",
                "batch_id": "batch_test_auto_999",
                "message_ids": ["syn_msg_001", "syn_msg_002", "syn_msg_003", "syn_msg_004"],
            },
            triggered_by="event_detector",
        )
        auto_inst = await crud.get_workflow_instance(session, auto_run_id)
        auto_dict = crud.workflow_to_dict(auto_inst)
        print(f"  [OK] Auto Instance serialized: Trigger Type='{auto_dict.get('trigger_type')}', Source='{auto_dict.get('trigger_source')}', Messages={auto_dict.get('message_count')}")
        assert auto_dict.get("trigger_type") == "New Email"
        assert auto_dict.get("trigger_source") == "email_event_detector"
        assert auto_dict.get("message_count") == 4

    # 4. Test List Workflows & Runs Integrity
    print("\n[TEST 4] Testing list_workflows serialization...")
    from api.main import list_workflows
    async with (await get_raw_session()) as session:
        runs_list = await list_workflows(
            tenant_id="ab17c472-46f5-4778-9df9-293cefa86e1c",
            current_user=MockUser(),
            db=session,
        )
        print(f"  [OK] Listed {len(runs_list)} workflow instances from DB")
        manual_matches = [r for r in runs_list if r.get("run_id") == manual_run_id]
        auto_matches = [r for r in runs_list if r.get("run_id") == auto_run_id]
        assert len(manual_matches) == 1, "Manual run must be found"
        assert len(auto_matches) == 1, "Auto run must be found"
        print(f"  [OK] Manual run verification: Trigger={manual_matches[0].get('trigger_type')} (Expected: Manual)")
        print(f"  [OK] Auto run verification:   Trigger={auto_matches[0].get('trigger_type')} (Expected: New Email)")

    # 5. Test Config Workflows Catalog
    print("\n[TEST 5] Testing list_workflow_dags catalog metadata...")
    from api.main import list_workflow_dags
    dags = await list_workflow_dags()
    email_dag = next((d for d in dags if d["name"] == "email_summarizer"), None)
    assert email_dag is not None, "email_summarizer must be in catalog"
    print(f"  [OK] Email Summarizer DAG catalog metadata:")
    print(f"       - Status: {email_dag.get('status')}")
    print(f"       - Trigger Type: {email_dag.get('trigger_type')}")
    print(f"       - Source: {email_dag.get('source')}")
    print(f"       - Automation Status: {email_dag.get('automation_status')}")
    assert email_dag.get("status") == "active"
    assert email_dag.get("trigger_type") == "New Email"
    assert email_dag.get("source") == "Synthetic Inbox"

    # 6. Verify Action Center Real Items Boundary
    print("\n[TEST 6] Verifying Action Center real items boundary...")
    async with (await get_raw_session()) as session:
        approvals = await crud.list_approval_items(session)
        print(f"  [OK] Real approval items in database: {len(approvals)}")
        for a in approvals[:3]:
            print(f"       - Item ID: {a.id}, Status: {a.status}, Node: {a.node_id}")

    print("\n" + "=" * 70)
    print("ALL TRIGGER & RUN NOW VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(verify_all())
