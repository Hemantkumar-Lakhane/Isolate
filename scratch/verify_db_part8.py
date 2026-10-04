import asyncio
import dotenv
dotenv.load_dotenv()
from sqlalchemy import select, func
from core.database import AsyncSessionLocal
from db.models.core import Organization, OrganizationUser

async def main():
    async with AsyncSessionLocal() as db:
        print("=== PART 8 — READ-ONLY DATABASE VERIFICATION ===")
        
        # 1. Check organization_users
        res_ou = await db.execute(select(OrganizationUser).order_by(OrganizationUser.created_at.desc()))
        ous = res_ou.scalars().all()
        print(f"Total OrganizationUser records: {len(ous)}")
        for ou in ous[:5]:
            print(f"  - User ID: {ou.user_id} | Email: {ou.email} | Role: {ou.role} | Org ID: {ou.organization_id}")
            
        # 2. Check organizations
        res_o = await db.execute(select(Organization))
        orgs = res_o.scalars().all()
        print(f"\nTotal Organization records: {len(orgs)}")
        for o in orgs[:5]:
            cfg = o.profile_config or {}
            print(f"  - Org ID: {o.id} | Name: {o.name} | Industry: {o.industry} | Onboarding: {cfg.get('requires_onboarding', False)}")

        # 3. Duplicate prevention check: Group by email
        res_dups = await db.execute(select(OrganizationUser.email, func.count(OrganizationUser.id)).group_by(OrganizationUser.email))
        dups = res_dups.all()
        dup_found = [d for d in dups if d[1] > 1]
        print(f"\nDuplicate email mappings in organization_users: {len(dup_found)}")

if __name__ == "__main__":
    asyncio.run(main())
