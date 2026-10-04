import asyncio
import json
import os
import sys
from dotenv import load_dotenv

load_dotenv(r"c:\Users\lakha\ml_cp\SMBFlow\.env")
sys.path.insert(0, os.path.abspath("."))

from sqlalchemy import select
from core.database import AsyncSessionLocal
from core.state_manager import WorkflowInstance, AgentRunRecord

async def check_runs():
    async with AsyncSessionLocal() as db:
        stmt = select(WorkflowInstance).order_by(WorkflowInstance.started_at.desc()).limit(5)
        res = await db.execute(stmt)
        instances = res.scalars().all()
        
        print("\n==========================================")
        print("LATEST WORKFLOW INSTANCES IN DATABASE")
        print("==========================================")
        for inst in instances:
            print(f"Run ID: {inst.id}")
            print(f"Status: {inst.status}")
            print(f"Current Node: {inst.current_node}")
            print(f"Started At: {inst.started_at}")
            print(f"Completed At: {inst.completed_at}")
            if inst.outcome and "llm_stats" in inst.outcome:
                stats = inst.outcome["llm_stats"]
                print(f"  LLM Stats: Calls={stats.get('total_calls')}, In={stats.get('total_tokens_in')}, Out={stats.get('total_tokens_out')}, Cost=${stats.get('total_cost_usd')}")
            
            stmt_runs = select(AgentRunRecord).where(AgentRunRecord.instance_id == inst.id).order_by(AgentRunRecord.completed_at.asc())
            runs_res = await db.execute(stmt_runs)
            agent_runs = runs_res.scalars().all()
            print(f"  Agent Runs ({len(agent_runs)}):")
            for ar in agent_runs:
                print(f"    - Node: {ar.node_id} ({ar.agent_type}): status={ar.status} | tokens_in={ar.tokens_in} tokens_out={ar.tokens_out} cost=${ar.cost_usd} model={ar.model_used}")
            print("-" * 50)

if __name__ == "__main__":
    asyncio.run(check_runs())
