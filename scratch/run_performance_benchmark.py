import asyncio
import json
import os
import sys
import uuid
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(r"c:\Users\lakha\ml_cp\SMBFlow\.env")
sys.path.insert(0, os.path.abspath("."))

from sqlalchemy import select
from db.models.core import Organization
from core.database import AsyncSessionLocal
from core.state_manager import StateManager, AgentRunRecord
from core.orchestrator import WorkflowOrchestrator
from core.llm_router import LLMRouter
from integrations.tool_registry_builder import build_registry
from epi.epi_manager import EPIManager
import api.crud as crud

async def run_benchmark(batch_size: int):
    print(f"\n==========================================")
    print(f"STARTING BENCHMARK FOR {batch_size} SYNTHETIC EMAILS")
    print(f"==========================================")
    
    start_time = datetime.now()
    run_id = str(uuid.uuid4())
    
    async with AsyncSessionLocal() as db:
        stmt = select(Organization).limit(1)
        org = (await db.execute(stmt)).scalar_one_or_none()
        org_id = str(org.id) if org else str(uuid.uuid4())
        
        state_mgr = StateManager(session=db)
        llm_router = LLMRouter()
        
        tenant_config = {
            "client_id": org_id,
            "client_name": org.name if org else "Deconstruct",
            "organization_id": org_id,
            "industry": org.industry if org else "technology",
            "tone_profile": {"style": "professional"},
            "business_rules": {
                "priority_threshold": 0.7,
            },
            "action_library": [
                {
                    "action_id": "summarize_email",
                    "description": "Summarize operational emails",
                }
            ],
            "integrations": {},
        }
        
        tool_registry = build_registry(tenant_config, credentials={})
        epi_mgr = EPIManager()
        
        trigger_payload = {
            "data_source": "synthetic_demo",
            "source": "synthetic_inbox",
            "limit": batch_size,
        }
        
        await crud.create_workflow_instance(
            db,
            run_id=run_id,
            tenant_id=org_id,
            workflow_name="email_summarizer",
            trigger_signal=trigger_payload,
            tenant_config=tenant_config,
        )
        
        orchestrator = WorkflowOrchestrator(
            state_manager=state_mgr,
            llm_router=llm_router,
            tool_registry=tool_registry,
            epi_manager=epi_mgr,
        )
        
        res = await orchestrator.run_workflow(
            tenant_config=tenant_config,
            workflow_name="email_summarizer",
            trigger_signal=trigger_payload,
            instance_id=run_id,
        )
        
        elapsed = (datetime.now() - start_time).total_seconds()
        
        stmt_runs = select(AgentRunRecord).where(AgentRunRecord.instance_id == uuid.UUID(run_id)).order_by(AgentRunRecord.completed_at.asc())
        runs_res = await db.execute(stmt_runs)
        agent_runs = runs_res.scalars().all()
        
        tot_in = sum(r.tokens_in or 0 for r in agent_runs)
        tot_out = sum(r.tokens_out or 0 for r in agent_runs)
        tot_cost = sum(r.cost_usd or 0.0 for r in agent_runs)
        
        print(f"\n--- BENCHMARK RESULTS ({batch_size} EMAILS) ---")
        print(f"Run ID: {run_id}")
        print(f"Status: {res.get('status')}")
        print(f"Total Execution Time: {elapsed:.2f} seconds")
        print(f"Total LLM Calls: {len(agent_runs)}")
        print(f"Total Tokens In: {tot_in}")
        print(f"Total Tokens Out: {tot_out}")
        print(f"Total Cost USD: ${tot_cost:.6f}")
        print("\nNode Breakdown:")
        for ar in agent_runs:
            print(f"  - Node: {ar.node_id} ({ar.agent_type})")
            print(f"    Status: {ar.status}")
            print(f"    Tokens In: {ar.tokens_in}, Tokens Out: {ar.tokens_out}, Cost: ${ar.cost_usd:.6f}, Model: {ar.model_used}")
        
        return {
            "batch_size": batch_size,
            "elapsed": elapsed,
            "total_calls": len(agent_runs),
            "tokens_in": tot_in,
            "tokens_out": tot_out,
            "cost_usd": tot_cost,
            "agent_runs": agent_runs
        }

async def main():
    bench10 = await run_benchmark(10)
    bench40 = await run_benchmark(40)
    
    print("\n==========================================")
    print("FINAL PERFORMANCE COMPARISON SUMMARY")
    print("==========================================")
    print(f"10 Emails:  Calls={bench10['total_calls']}, TokensIn={bench10['tokens_in']}, TokensOut={bench10['tokens_out']}, Cost=${bench10['cost_usd']:.6f}, Time={bench10['elapsed']:.2f}s")
    print(f"40 Emails:  Calls={bench40['total_calls']}, TokensIn={bench40['tokens_in']}, TokensOut={bench40['tokens_out']}, Cost=${bench40['cost_usd']:.6f}, Time={bench40['elapsed']:.2f}s")

if __name__ == "__main__":
    asyncio.run(main())
