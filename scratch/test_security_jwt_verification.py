import asyncio
import os
import uuid
import sys
from pathlib import Path
from jose import jwt
from datetime import datetime, timedelta
from fastapi import HTTPException

try:
    from dotenv import load_dotenv
    load_dotenv(override=False)
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import get_raw_session
from api import crud
from api.auth import TokenData, decode_token, SECRET_KEY, create_access_token
from api.main import get_me, provision_user_workspace, ProvisionRequest, require_admin

async def run_security_tests():
    print("--- STARTING SECURITY HARDENING & JWT VERIFICATION TESTS ---")

    # 1. Valid platform JWT -> accepted
    valid_payload = {
        "sub": str(uuid.uuid4()),
        "email": "valid_user@smbflow.com",
        "role": "org_user",
        "exp": datetime.utcnow() + timedelta(hours=1)
    }
    valid_token = create_access_token(valid_payload)
    decoded_valid = decode_token(valid_token)
    print("\n1. Valid Platform JWT Signature Verification:")
    print(f"   Decoded User ID: {decoded_valid.user_id} (PASS)")
    assert decoded_valid.user_id == valid_payload["sub"]

    # 2. Invalid signature -> 401 Unauthorized
    forged_secret = "forged-attacker-secret-key-123456789"
    forged_token = jwt.encode(valid_payload, forged_secret, algorithm="HS256")
    print("\n2. Invalid Signature (Forged Secret) Check:")
    try:
        decode_token(forged_token)
        print("   FAILED: Forged token was wrongly accepted!")
        assert False, "Forged token was wrongly accepted"
    except HTTPException as e:
        print(f"   PASSED: Rejected with HTTP {e.status_code} ({e.detail})")
        assert e.status_code == 401

    # 3. Forged JWT with modified claims (attacker self-elevating to platform_admin) -> 401 Unauthorized
    forged_admin_payload = {
        "sub": str(uuid.uuid4()),
        "email": "attacker@smbflow.com",
        "role": "platform_admin",
        "exp": datetime.utcnow() + timedelta(hours=1)
    }
    forged_admin_token = jwt.encode(forged_admin_payload, forged_secret, algorithm="HS256")
    print("\n3. Forged JWT with Self-Assigned Role ('platform_admin') Check:")
    try:
        decode_token(forged_admin_token)
        print("   FAILED: Forged admin token was accepted!")
        assert False, "Forged admin token accepted"
    except HTTPException as e:
        print(f"   PASSED: Rejected with HTTP {e.status_code} ({e.detail})")
        assert e.status_code == 401

    # 4. Expired token -> 401 Unauthorized
    expired_payload = {
        "sub": str(uuid.uuid4()),
        "email": "expired@smbflow.com",
        "role": "org_user",
        "exp": datetime.utcnow() - timedelta(minutes=10)
    }
    expired_token = jwt.encode(expired_payload, SECRET_KEY, algorithm="HS256")
    print("\n4. Expired Token Check:")
    try:
        decode_token(expired_token)
        print("   FAILED: Expired token was accepted!")
        assert False, "Expired token accepted"
    except HTTPException as e:
        print(f"   PASSED: Rejected with HTTP {e.status_code} ({e.detail})")
        assert e.status_code == 401

    # 5. Missing / Malformed Token Check
    print("\n5. Malformed Token Check:")
    try:
        decode_token("not.a.valid.jwt.string")
        print("   FAILED: Malformed token was accepted!")
        assert False, "Malformed token accepted"
    except HTTPException as e:
        print(f"   PASSED: Rejected with HTTP {e.status_code} ({e.detail})")
        assert e.status_code == 401

    # 6. Valid Google-authenticated User /auth/me
    session = await get_raw_session()
    async with session:
        google_user_id = str(uuid.uuid4())
        google_email = f"google_verified_{uuid.uuid4().hex[:6]}@example.com"
        google_token_data = TokenData(user_id=google_user_id, email=google_email, role="org_user", full_name="Verified Google User")
        
        me_resp = await get_me(current_user=google_token_data, db=session)
        print("\n6. Valid Google-Authenticated User /auth/me:")
        print(f"   User Email: {me_resp['email']} (Expected: {google_email})")
        print(f"   Requires Onboarding: {me_resp['requires_onboarding']} (Expected: True)")
        assert me_resp['email'] == google_email
        assert me_resp['requires_onboarding'] is True

        # 7. auth/provision works for authenticated new user
        prov_req = ProvisionRequest(full_name="Verified Google User", workspace_name="Verified Workspace Inc", industry="finance")
        prov_resp = await provision_user_workspace(body=prov_req, current_user=google_token_data, db=session)
        print("\n7. /auth/provision for New Google User:")
        print(f"   Workspace Name: {prov_resp['organization_name']} (Expected: Verified Workspace Inc)")
        print(f"   Requires Onboarding: {prov_resp['requires_onboarding']} (Expected: False)")
        assert prov_resp['organization_name'] == "Verified Workspace Inc"
        assert prov_resp['requires_onboarding'] is False

        # 8. Organization membership created correctly
        org_user, org = await crud.ensure_user_organization_provisioned(session, google_user_id, google_email)
        print("\n8. Organization & Membership Provision Check:")
        print(f"   Org Name: {org.name}, User Role: {org_user.role}")
        assert org.name == "Verified Workspace Inc"
        assert org_user.role == "org_user"

        # 9. Existing organization user does not receive duplicate organization
        _, org_second = await crud.ensure_user_organization_provisioned(session, google_user_id, google_email)
        print("\n9. Duplicate Prevention Check:")
        print(f"   Same Org ID: {org.id == org_second.id} (Expected: True)")
        assert org.id == org_second.id

        # 10. Platform admin authorization remains protected
        regular_token_data = TokenData(user_id=google_user_id, email=google_email, role="org_user")
        print("\n10. Platform Admin Authorization Enforcement Check:")
        try:
            await require_admin(current_user=regular_token_data)
            print("    FAILED: Regular org_user was granted platform_admin access!")
            assert False, "org_user granted admin access"
        except HTTPException as e:
            print(f"    PASSED: Standard org_user blocked from admin access with HTTP {e.status_code} ({e.detail})")
            assert e.status_code == 403

        # Verify platform_admin is permitted
        admin_token_data = TokenData(user_id=str(uuid.uuid4()), email="admin@smbflow.com", role="platform_admin")
        admin_auth_result = await require_admin(current_user=admin_token_data)
        assert admin_auth_result.role == "platform_admin"
        print("    PASSED: platform_admin user permitted correctly.")

    print("\n==================================================")
    print("--- ALL 10 SECURITY HARDENING TESTS PASSED! ---")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(run_security_tests())
