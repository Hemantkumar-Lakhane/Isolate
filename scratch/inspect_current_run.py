import asyncio
import json
import os
from dotenv import load_dotenv
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

async def inspect():
    engine = create_async_engine(DATABASE_URL, echo=False, connect_args={"statement_cache_size": 0})
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with SessionLocal() as session:
        # Find latest workflow instances for meeting_intelligence_followup
        stmt = text("""
            SELECT id, organization_id, workflow_name, status, current_node, started_at, completed_at, context, trigger_payload
            FROM workflow_instances
            WHERE workflow_name = 'meeting_intelligence_followup'
            ORDER BY started_at DESC
            LIMIT 5;
        """)
        res = await session.execute(stmt)
        rows = res.fetchall()
        print(f"--- FOUND {len(rows)} RECENT WORKFLOW INSTANCES ---")
        for r in rows:
            inst_id = r[0]
            org_id = r[1]
            status = r[3]
            curr_node = r[4]
            started_at = r[5]
            ctx = r[7] if isinstance(r[7], dict) else json.loads(r[7] or "{}")
            trig = r[8] if isinstance(r[8], dict) else json.loads(r[8] or "{}")
            title = trig.get("conversation_title") or ctx.get("conversation_capture", {}).get("conversation_title")
            contact = trig.get("contact_name") or ctx.get("conversation_capture", {}).get("contact_name")
            print(f"\nInstance ID: {inst_id}")
            print(f"Title: {title}")
            print(f"Contact: {contact}")
            print(f"Status: {status} | Current Node: {curr_node} | Started: {started_at}")
            print(f"Context keys: {list(ctx.keys())}")
            has_node3 = "node3_central_memory" in ctx
            print(f"Has node3_central_memory in context? {has_node3}")
            if has_node3:
                print(f"Node 3 context: {ctx['node3_central_memory']}")

            # Check RelationshipConversation for this instance
            conv_stmt = text("SELECT id, title, conversation_date, contact_id FROM relationship_conversations WHERE workflow_instance_id = :iid;")
            conv_res = await session.execute(conv_stmt, {"iid": inst_id})
            convs = conv_res.fetchall()
            print(f"RelationshipConversations for this instance: {len(convs)}")
            for c in convs:
                print(f"  Conv ID: {c[0]}, Title: {c[1]}, Contact ID: {c[3]}")
                # Check memory items for this conv
                mem_stmt = text("SELECT id, category, content FROM relationship_memory_items WHERE conversation_id = :cid;")
                mem_res = await session.execute(mem_stmt, {"cid": c[0]})
                mems = mem_res.fetchall()
                print(f"  Memory items for this conv: {len(mems)}")

            # Check AgentRunRecords
            run_stmt = text("SELECT id, node_id, agent_capability, status, cost_usd, duration_ms, error FROM agent_run_records WHERE instance_id = :iid;")
            run_res = await session.execute(run_stmt, {"iid": inst_id})
            runs = run_res.fetchall()
            print(f"AgentRunRecords for this instance: {len(runs)}")
            for rn in runs:
                print(f"  Node: {rn[1]}, Capability: {rn[2]}, Status: {rn[3]}, Duration: {rn[5]}ms, Error: {rn[6]}")

            # Check ApprovalItems (Node 4)
            appr_stmt = text("SELECT id, node_id, review_type, status, reason FROM approval_items WHERE instance_id = :iid;")
            appr_res = await session.execute(appr_stmt, {"iid": inst_id})
            apprs = appr_res.fetchall()
            print(f"ApprovalItems for this instance: {len(apprs)}")

            # Also check audit events
            audit_stmt = text("SELECT id, action, entity_type, entity_id, created_at FROM audit_events WHERE entity_id = :iid OR metadata->>'workflow_instance_id' = :iid_str;")
            audit_res = await session.execute(audit_stmt, {"iid": str(inst_id), "iid_str": str(inst_id)})
            audits = audit_res.fetchall()
            print(f"AuditEvents for this instance: {len(audits)}")
            for a in audits:
                print(f"  Action: {a[1]}, EntityType: {a[2]}, EntityID: {a[3]}, Created: {a[4]}")

        # Check all contacts named Rahul
        print("\n--- CONTACTS NAMED RAHUL ---")
        c_stmt = text("SELECT id, organization_id, name, normalized_name, created_at FROM relationship_contacts WHERE normalized_name LIKE '%rahul%';")
        c_res = await session.execute(c_stmt)
        c_rows = c_res.fetchall()
        for c in c_rows:
            print(f"Contact ID: {c[0]} | Org: {c[1]} | Name: {c[2]} | Normalized: {c[3]} | Created: {c[4]}")
            # Count conversations for this contact
            cc_stmt = text("SELECT COUNT(*) FROM relationship_conversations WHERE contact_id = :cid;")
            cc_res = await session.execute(cc_stmt, {"cid": c[0]})
            print(f"  Total conversations for contact {c[0]}: {cc_res.scalar()}")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(inspect())
