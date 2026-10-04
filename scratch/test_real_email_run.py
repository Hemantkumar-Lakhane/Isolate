import asyncio
import json
import os
import sys
import uuid
import traceback
from dotenv import load_dotenv

load_dotenv(r"c:\Users\lakha\ml_cp\SMBFlow\.env")
os.environ["MOCK_LLM"] = "false"
sys.path.insert(0, r"c:\Users\lakha\ml_cp\SMBFlow")

from sqlalchemy import select
from db.models.core import Organization
from core.database import AsyncSessionLocal
from core.state_manager import StateManager
from core.orchestrator import WorkflowOrchestrator
from core.llm_router import LLMRouter
from integrations.tool_registry_builder import build_registry
from epi.epi_manager import EPIManager
import api.crud as crud

async def test_run():
    print("Testing real Email Summarizer workflow execution...")
    async with AsyncSessionLocal() as db:
        stmt = select(Organization).limit(1)
        org = (await db.execute(stmt)).scalar_one_or_none()
        if not org:
            print("No organization found.")
            return

        org_id = str(org.id)
        run_id = str(uuid.uuid4())

        _resolved_tid, tenant_config = await crud.resolve_tenant_config_bridge(db, org_id)

        state_mgr = StateManager(session=db)
        llm_router = LLMRouter()
        tool_registry = build_registry(tenant_config, credentials={})
        epi_mgr = EPIManager()

        inst = await crud.create_workflow_instance(
            db,
            run_id=run_id,
            tenant_id=org_id,
            workflow_name="email_summarizer",
            trigger_signal={"source": "real_verification"},
            tenant_config=tenant_config,
        )

        orchestrator = WorkflowOrchestrator(
            state_manager=state_mgr,
            llm_router=llm_router,
            tool_registry=tool_registry,
            epi_manager=epi_mgr,
        )

        try:
            run_result = await orchestrator.run_workflow(
                tenant_config=tenant_config,
                workflow_name="email_summarizer",
                trigger_signal={"source": "real_verification"},
                instance_id=run_id,
            )
            print("Run result:", json.dumps(run_result, default=str, indent=2))
        except Exception as e:
            print("WORKFLOW EXCEPTION CAUGHT:")
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_run())
