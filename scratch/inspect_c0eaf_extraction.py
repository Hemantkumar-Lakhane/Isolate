import asyncio
import json
import os
import uuid
from dotenv import load_dotenv
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

async def inspect():
    engine = create_async_engine(DATABASE_URL, echo=False, connect_args={"statement_cache_size": 0})
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    inst_id = uuid.UUID("c0eaf648-1fce-4f73-99ef-8f8e244c8659")

    async with SessionLocal() as db:
        # 1. Inspect WorkflowInstance.context
        stmt = text("SELECT id, status, current_node, context FROM workflow_instances WHERE id = :iid;")
        res = await db.execute(stmt, {"iid": inst_id})
        r = res.fetchone()
        if not r:
            print("Instance not found!")
            return

        ctx = r[3] if isinstance(r[3], dict) else json.loads(r[3] or "{}")
        print("=== WORKFLOW INSTANCE CONTEXT KEYS ===")
        print(list(ctx.keys()))

        node2_data = ctx.get("node2_process_conversation", {})
        print("\n=== NODE 2 DATA KEYS ===")
        print(list(node2_data.keys()))

        extraction = node2_data.get("extraction") or node2_data.get("structured_extraction") or {}
        print("\n=== EXTRACTION KEYS ===")
        print(list(extraction.keys()))

        print("\n=== EXTRACTION COMMITMENTS RAW ===")
        commitments = extraction.get("commitments")
        agreed_commitments = extraction.get("agreed_commitments")
        print(f"extraction.get('commitments'): {json.dumps(commitments, indent=2)}")
        print(f"extraction.get('agreed_commitments'): {json.dumps(agreed_commitments, indent=2)}")

        print("\n=== EXTRACTION SUGGESTED ACTIONS RAW ===")
        print(json.dumps(extraction.get("suggested_actions"), indent=2))

        # 2. Inspect RelationshipConversation
        c_stmt = text("SELECT id, title, contact_id, summary, conversation_date FROM relationship_conversations WHERE workflow_instance_id = :iid;")
        c_res = await db.execute(c_stmt, {"iid": inst_id})
        c_row = c_res.fetchone()
        if c_row:
            conv_id = c_row[0]
            print(f"\n=== RELATIONSHIP CONVERSATION ===")
            print(f"Conv ID: {conv_id} | Title: {c_row[1]} | Contact ID: {c_row[2]}")

            # 3. Inspect RelationshipMemoryItems for this conversation
            m_stmt = text("SELECT id, category, content, details, is_ai_generated FROM relationship_memory_items WHERE conversation_id = :cid;")
            m_res = await db.execute(m_stmt, {"cid": conv_id})
            m_rows = m_res.fetchall()
            print(f"\n=== RELATIONSHIP MEMORY ITEMS ({len(m_rows)} total) ===")
            for m in m_rows:
                cat = m[1]
                content = m[2]
                details = m[3]
                ai_gen = m[4]
                if cat in ["commitment", "suggested_action", "action"]:
                    print(f"ID: {m[0]} | Cat: {cat} | AI: {ai_gen} | Content: {content} | Details: {details}")

        # 4. Inspect current approval items for this instance
        a_stmt = text("SELECT id, review_type, status, reason, payload FROM approval_items WHERE instance_id = :iid;")
        a_res = await db.execute(a_stmt, {"iid": inst_id})
        a_rows = a_res.fetchall()
        print(f"\n=== APPROVAL ITEMS ({len(a_rows)} total) ===")
        for a in a_rows:
            print(f"ID: {a[0]} | Type: {a[1]} | Status: {a[2]} | Reason: {a[3]} | Payload action_type: {a[4].get('action_type') if isinstance(a[4], dict) else None}")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(inspect())
