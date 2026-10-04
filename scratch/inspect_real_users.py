import asyncio
import os
import sys
import json
from pathlib import Path
from sqlalchemy import text

try:
    from dotenv import load_dotenv
    load_dotenv(override=False)
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import get_raw_session

async def inspect_real_users():
    session = await get_raw_session()
    async with session:
        print("==================================================")
        print("1. INSPECTING SUPABASE AUTH USERS (auth.users)")
        print("==================================================")
        
        supabase_auth_users = []
        has_auth_schema = False
        
        try:
            auth_res = await session.execute(text("""
                SELECT 
                    id::text, 
                    email, 
                    created_at, 
                    last_sign_in_at,
                    raw_app_meta_data,
                    raw_user_meta_data,
                    email_confirmed_at
                FROM auth.users
                ORDER BY created_at DESC
            """))
            has_auth_schema = True
            for row in auth_res.mappings():
                app_meta = row["raw_app_meta_data"] or {}
                user_meta = row["raw_user_meta_data"] or {}
                provider = app_meta.get("provider") or (app_meta.get("providers") or ["email"])[0]
                full_name = user_meta.get("full_name") or user_meta.get("name") or "-"
                confirmed = "Confirmed" if row["email_confirmed_at"] else "Unconfirmed"
                
                supabase_auth_users.append({
                    "user_id": row["id"],
                    "email": row["email"],
                    "created_at": str(row["created_at"]) if row["created_at"] else "-",
                    "last_sign_in_at": str(row["last_sign_in_at"]) if row["last_sign_in_at"] else "-",
                    "provider": provider,
                    "full_name": full_name,
                    "confirmed": confirmed,
                })
        except Exception as e:
            print(f"Notice: auth.users query error or schema not present: {e}")

        # Also check local users table if present
        local_users = []
        try:
            local_res = await session.execute(text("""
                SELECT id::text, email, full_name, role, is_active, created_at, last_login
                SELECT_STAMP
                FROM users
                ORDER BY created_at DESC
            """.replace("SELECT_STAMP", "")))
        except Exception:
            try:
                local_res = await session.execute(text("""
                    SELECT id::text, email, full_name, role, is_active, created_at, last_login
                    FROM users
                    ORDER BY created_at DESC
                """))
                for row in local_res.mappings():
                    local_users.append({
                        "user_id": row["id"],
                        "email": row["email"],
                        "full_name": row["full_name"] or "-",
                        "role": row["role"],
                        "is_active": row["is_active"],
                        "created_at": str(row["created_at"]) if row["created_at"] else "-",
                        "last_login": str(row["last_login"]) if row["last_login"] else "-",
                    })
            except Exception as e2:
                print(f"Notice: local users table query error: {e2}")

        print(f"Found {len(supabase_auth_users)} Supabase Auth users.")
        print(f"Found {len(local_users)} local users table entries.")

        print("\n==================================================")
        print("2. INSPECTING SMBFLOW ORGANIZATION MEMBERS (organization_users & organizations)")
        print("==================================================")
        
        org_members = []
        try:
            org_res = await session.execute(text("""
                SELECT 
                    ou.id::text as membership_id,
                    ou.user_id::text as user_id,
                    ou.email as member_email,
                    ou.full_name as member_full_name,
                    ou.role as member_role,
                    ou.created_at as member_created_at,
                    ou.organization_id::text as organization_id,
                    o.name as org_name,
                    o.industry as org_industry,
                    o.profile_config as org_profile_config
                FROM organization_users ou
                LEFT JOIN organizations o ON ou.organization_id = o.id
                ORDER BY ou.created_at DESC
            """))
            for row in org_res.mappings():
                p_cfg = row["org_profile_config"] or {}
                org_name = row["org_name"] or "Unknown Org"
                requires_onboarding = (
                    org_name == "Pending Workspace Setup" or 
                    p_cfg.get("requires_onboarding") is True
                )
                onboarding_status = "Incomplete (Pending)" if requires_onboarding else "Complete"
                
                org_members.append({
                    "membership_id": row["membership_id"],
                    "user_id": row["user_id"],
                    "email": row["member_email"],
                    "full_name": row["member_full_name"] or "-",
                    "role": row["member_role"],
                    "organization_id": row["organization_id"],
                    "organization_name": org_name,
                    "onboarding_status": onboarding_status,
                    "created_at": str(row["member_created_at"]) if row["member_created_at"] else "-",
                })
        except Exception as e:
            print(f"Error querying organization_users: {e}")

        print(f"Found {len(org_members)} organization_users records.")

        # Query total distinct organizations
        orgs = []
        try:
            o_res = await session.execute(text("""
                SELECT id::text, name, industry, profile_config, active, created_at
                FROM organizations
                ORDER BY created_at DESC
            """))
            for row in o_res.mappings():
                p_cfg = row["profile_config"] or {}
                requires_onboarding = (
                    row["name"] == "Pending Workspace Setup" or 
                    p_cfg.get("requires_onboarding") is True
                )
                orgs.append({
                    "organization_id": row["id"],
                    "name": row["name"],
                    "industry": row["industry"],
                    "requires_onboarding": requires_onboarding,
                    "active": row["active"],
                    "created_at": str(row["created_at"]) if row["created_at"] else "-",
                })
        except Exception as e:
            print(f"Error querying organizations: {e}")

        print(f"Found {len(orgs)} distinct organizations.")

        print("\n==================================================")
        print("3. RECONCILIATION & JOIN DATA")
        print("==================================================")

        # Build combined list for reporting table
        reconciled = []
        
        # Map Supabase users by user_id and by email
        auth_by_id = {u["user_id"]: u for u in supabase_auth_users}
        auth_by_email = {u["email"].lower(): u for u in supabase_auth_users if u.get("email")}

        # Map Org Members by user_id
        org_by_user_id = {}
        for m in org_members:
            org_by_user_id.setdefault(m["user_id"], []).append(m)

        all_user_ids = set(auth_by_id.keys()).union(set(org_by_user_id.keys()))

        for uid in sorted(all_user_ids):
            auth_u = auth_by_id.get(uid)
            m_list = org_by_user_id.get(uid, [])

            if not auth_u and m_list:
                # Try fallback matching by email if auth record not found by UUID
                m_email = m_list[0]["email"].lower() if m_list[0].get("email") else ""
                auth_u = auth_by_email.get(m_email)

            if auth_u and m_list:
                for m in m_list:
                    reconciled.append({
                        "email": auth_u["email"],
                        "user_id": uid,
                        "organization": m["organization_name"],
                        "role": m["role"],
                        "provider": auth_u["provider"],
                        "onboarding": m["onboarding_status"],
                        "created": auth_u["created_at"][:10],
                        "auth_found": True,
                        "has_org": True,
                        "requires_onboarding": m["onboarding_status"] == "Incomplete (Pending)"
                    })
            elif auth_u and not m_list:
                reconciled.append({
                    "email": auth_u["email"],
                    "user_id": uid,
                    "organization": "None (Unassigned)",
                    "role": "None",
                    "provider": auth_u["provider"],
                    "onboarding": "No Workspace",
                    "created": auth_u["created_at"][:10],
                    "auth_found": True,
                    "has_org": False,
                    "requires_onboarding": True
                })
            elif not auth_u and m_list:
                for m in m_list:
                    reconciled.append({
                        "email": m["email"],
                        "user_id": uid,
                        "organization": m["organization_name"],
                        "role": m["role"],
                        "provider": "Unknown (Local/DB)",
                        "onboarding": m["onboarding_status"],
                        "created": m["created_at"][:10],
                        "auth_found": False,
                        "has_org": True,
                        "requires_onboarding": m["onboarding_status"] == "Incomplete (Pending)"
                    })

        # Save structured report for exact JSON output
        report = {
            "supabase_auth_users": supabase_auth_users,
            "local_users": local_users,
            "org_members": org_members,
            "organizations": orgs,
            "reconciled": reconciled,
        }

        with open("scratch/inspection_results.json", "w") as f:
            json.dump(report, f, indent=2)

        print("\nInspection results saved to scratch/inspection_results.json")

if __name__ == "__main__":
    asyncio.run(inspect_real_users())
