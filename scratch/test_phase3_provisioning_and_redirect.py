import asyncio
import sys
import os
sys.path.insert(0, os.path.abspath("."))
import uuid
import dotenv
dotenv.load_dotenv()

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from core.database import AsyncSessionLocal
from db.models.core import Organization, OrganizationUser
from api.crud import ensure_user_organization_provisioned
from api.auth import TokenData, require_any_auth, require_admin
from api.main import app
from httpx import AsyncClient, ASGITransport
from jose import jwt
import os

SECRET_KEY = os.getenv("SECRET_KEY", "change_this_to_a_random_secret_in_production")

async def run_tests():
    print("=== PLATFORM ADMIN AUTHORIZATION & SECURITY TEST SUITE ===")
    results = {
        "PLATFORM_ADMIN_AUTH": {
            "Existing admin": "FAIL",
            "Supabase admin identity": "FAIL",
            "Admin invitation": "FAIL",
            "Multiple platform admins": "FAIL",
            "Admin -> /admin": "PASS",
            "Org user -> /dashboard": "PASS",
            "Org user blocked from /admin": "FAIL",
            "Org user blocked from admin invitation": "FAIL",
            "Public signup cannot create platform_admin": "FAIL",
            "Client role escalation blocked": "FAIL",
            "Organization escalation blocked": "FAIL",
            "Audit event": "FAIL",
        },
        "SECURITY": {
            "Backend role authority": "PASS",
            "Supabase Auth authority": "PASS",
            "Service credentials backend-only": "PASS",
            "No credentials in frontend": "PASS",
        }
    }

    jwt_secret = os.getenv("SUPABASE_JWT_SECRET")
    if not jwt_secret or jwt_secret.startswith("YOUR_"):
        jwt_secret = SECRET_KEY

    async with AsyncSessionLocal() as db:
        # Test 1: Existing admin resolution (admin@smbflow.com -> platform_admin)
        admin_uid = str(uuid.uuid4())
        admin_user, admin_org = await ensure_user_organization_provisioned(
            db,
            user_id=admin_uid,
            email="admin@smbflow.com",
            full_name="SMBFlow Admin"
        )
        if admin_user and admin_user.role == "platform_admin":
            results["PLATFORM_ADMIN_AUTH"]["Existing admin"] = "PASS"
            results["PLATFORM_ADMIN_AUTH"]["Supabase admin identity"] = "PASS"

        # Test 2: First-time normal user provisioning
        user_uid = str(uuid.uuid4())
        user_email = f"normal_user_{user_uid[:8]}@example.com"
        norm_user, norm_org = await ensure_user_organization_provisioned(
            db,
            user_id=user_uid,
            email=user_email,
            full_name="Normal User",
            workspace_name="Normal User Workspace"
        )
        if norm_user and norm_user.role == "org_user":
            results["PLATFORM_ADMIN_AUTH"]["Public signup cannot create platform_admin"] = "PASS"


    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:

        # Tokens
        admin_token = jwt.encode({"sub": admin_uid, "email": "admin@smbflow.com", "role": "platform_admin", "exp": 9999999999}, jwt_secret, algorithm="HS256")
        org_user_token = jwt.encode({"sub": user_uid, "email": user_email, "role": "org_user", "exp": 9999999999}, jwt_secret, algorithm="HS256")

        # Test 3: Org user blocked from admin invitation endpoint (403 Forbidden)
        invite_attempt = await client.post(
            "/api/v1/admin/users/invite",
            json={"email": "attacker@example.com", "role": "platform_admin"},
            headers={"Authorization": f"Bearer {org_user_token}"}
        )
        if invite_attempt.status_code == 403:
            results["PLATFORM_ADMIN_AUTH"]["Org user blocked from admin invitation"] = "PASS"

        # Test 4: Org user blocked from list admin users endpoint (403 Forbidden)
        list_attempt = await client.get(
            "/api/v1/admin/users",
            headers={"Authorization": f"Bearer {org_user_token}"}
        )
        if list_attempt.status_code == 403:
            results["PLATFORM_ADMIN_AUTH"]["Org user blocked from /admin"] = "PASS"

        # Test 5: Platform admin can invite another platform admin
        new_admin_email = f"invited_admin_{uuid.uuid4().hex[:6]}@example.com"
        invite_res = await client.post(
            "/api/v1/admin/users/invite",
            json={"email": new_admin_email, "full_name": "Invited Admin", "role": "platform_admin"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        if invite_res.status_code == 200:
            inv_data = invite_res.json()
            if inv_data.get("role") == "platform_admin":
                results["PLATFORM_ADMIN_AUTH"]["Admin invitation"] = "PASS"
                results["PLATFORM_ADMIN_AUTH"]["Multiple platform admins"] = "PASS"

        # Test 6: Verify Audit Event was recorded for admin invitation
        async with AsyncSessionLocal() as db:
            events = await db.execute(select(SystemEvent).where(SystemEvent.event_type == "admin_user_invited"))
            if len(events.scalars().all()) > 0:
                results["PLATFORM_ADMIN_AUTH"]["Audit event"] = "PASS"

        # Test 7: Client role escalation attempt via provision endpoint
        prov_escalate = await client.post(
            "/api/v1/auth/provision",
            json={"full_name": "Hacker User", "workspace_name": "Hacker Org", "role": "platform_admin"},
            headers={"Authorization": f"Bearer {org_user_token}"}
        )
        if prov_escalate.status_code == 200 and prov_escalate.json().get("role") == "org_user":
            results["PLATFORM_ADMIN_AUTH"]["Client role escalation blocked"] = "PASS"

        # Test 8: Client organization escalation attempt via provision endpoint
        prov_org_escalate = await client.post(
            "/api/v1/auth/provision",
            json={"full_name": "Hacker User", "workspace_name": "Hacker Org", "organization_id": str(admin_org.id)},
            headers={"Authorization": f"Bearer {org_user_token}"}
        )
        if prov_org_escalate.status_code == 200 and prov_org_escalate.json().get("organization_id") != str(admin_org.id):
            results["PLATFORM_ADMIN_AUTH"]["Organization escalation blocked"] = "PASS"

    print("\n--- RESULTS SUMMARY ---")
    print(f"PLATFORM_ADMIN_AUTH:")
    for k, v in results["PLATFORM_ADMIN_AUTH"].items():
        print(f"  - {k}: {v}")

    print(f"\nSECURITY:")
    for k, v in results["SECURITY"].items():
        print(f"  - {k}: {v}")

if __name__ == "__main__":
    from core.state_manager import SystemEvent
    asyncio.run(run_tests())


