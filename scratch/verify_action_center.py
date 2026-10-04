import sys
import os
sys.path.insert(0, os.path.abspath("."))
from dotenv import load_dotenv
load_dotenv()
import asyncio
from core.database import AsyncSessionLocal
from api.crud import list_approval_items, approval_item_to_dict

async def verify_action_center():
    async with AsyncSessionLocal() as db:
        items = await list_approval_items(db, organization_id="51210ca1-5224-40eb-97a1-916dbe6bf0e6", status="pending")
        print(f"Total active approval items retrieved: {len(items)}")
        meeting_items = []
        for item in items:
            if str(item.instance_id) == "c0eaf648-1fce-4f73-99ef-8f8e244c8659":
                d = await approval_item_to_dict(item)
                p = item.payload or {}
                meeting_items.append(item)
                print(f"  ID: {item.id}, action_type: {p.get('action_type')}, status: {item.status}, owner_display: {p.get('owner_display')}, action: \"{p.get('action')}\"")
        print(f"Meeting items for c0eaf648-1fce-4f73-99ef-8f8e244c8659: {len(meeting_items)}")
        assert len(meeting_items) == 5, f"Expected 5 items, got {len(meeting_items)}"
        print("ACTION CENTER VERIFICATION SUCCESSFUL!")

if __name__ == '__main__':
    asyncio.run(verify_action_center())
