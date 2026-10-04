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
from db.models.core import WorkflowInstance, RelationshipConversation, RelationshipMemoryItem, ApprovalItem

async def inspect():
    async with AsyncSessionLocal() as db:
        inst_id = uuid.UUID('c0eaf648-1fce-4f73-99ef-8f8e244c8659')
        stmt = select(WorkflowInstance).where(WorkflowInstance.id == inst_id)
        res = await db.execute(stmt)
        inst = res.scalar_one_or_none()
        if not inst:
            print('Instance not found!')
            return
        
        ctx = inst.context or {}
        print('=== 1. WorkflowInstance.context keys ===')
        print(list(ctx.keys()))
        
        cc = ctx.get('conversation_capture') or {}
        print('\n=== conversation_capture ===')
        print(json.dumps(cc, indent=2, default=str))

        n3 = ctx.get('node3_central_memory') or {}
        print('\n=== node3_central_memory ===')
        print(json.dumps(n3, indent=2, default=str))

        # Check RelationshipConversation
        conv_id_str = cc.get('conversation_id') or n3.get('conversation_id') or ctx.get('conversation_id')
        print(f'\n=== Conversation ID: {conv_id_str} ===')
        if conv_id_str:
            conv_id = uuid.UUID(conv_id_str)
            stmt_conv = select(RelationshipConversation).where(RelationshipConversation.id == conv_id)
            conv = (await db.execute(stmt_conv)).scalar_one_or_none()
            if conv:
                print('RelationshipConversation found:')
                print('title:', conv.title)
                print('contact_id:', conv.contact_id)
                print('structured_memory type:', type(conv.structured_memory))
                if isinstance(conv.structured_memory, dict):
                    print('structured_memory keys:', list(conv.structured_memory.keys()))
                    print('structured_memory["commitments"]:')
                    print(json.dumps(conv.structured_memory.get('commitments'), indent=2))
            
            # Check RelationshipMemoryItem for current conv
            stmt_mem = select(RelationshipMemoryItem).where(
                RelationshipMemoryItem.conversation_id == conv_id,
                RelationshipMemoryItem.category == 'commitment'
            )
            mem_items = (await db.execute(stmt_mem)).scalars().all()
            print(f'\n=== RelationshipMemoryItem (category=commitment, conv_id={conv_id}): {len(mem_items)} items ===')
            for m in mem_items:
                print(f'  ID: {m.id}')
                print(f'  content: "{m.content}"')
                print(f'  details: {m.details}')

        # Check ApprovalItems for this instance
        stmt_appr = select(ApprovalItem).where(ApprovalItem.instance_id == inst_id)
        apprs = (await db.execute(stmt_appr)).scalars().all()
        print(f'\n=== ApprovalItems for instance {inst_id}: {len(apprs)} items ===')
        for a in apprs:
            print(f'  ID: {a.id}, review_type: {a.review_type}, status: {a.status}, reason: {a.reason}, action_type: {(a.payload or {}).get("action_type")}, owner_display: {(a.payload or {}).get("owner_display")}')

        # Check node4_action_generator in ctx
        n4 = ctx.get('node4_action_generator') or {}
        print('\n=== node4_action_generator in context ===')
        print('status:', n4.get('status'))
        print('our_commitments count:', len(n4.get('our_commitments', [])))
        print('contact_commitments count:', len(n4.get('contact_commitments', [])))
        print('ai_suggestions count:', len(n4.get('ai_suggestions', [])))
        print('open_questions count:', len(n4.get('open_questions', [])))

if __name__ == '__main__':
    asyncio.run(inspect())
