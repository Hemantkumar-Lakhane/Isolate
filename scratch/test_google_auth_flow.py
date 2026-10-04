import asyncio
import os
import uuid
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(override=False)
except ImportError:
    pass

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import get_raw_session
from api import crud
from api.auth import TokenData
from api.main import get_me, provision_user_workspace, ProvisionRequest

async def run_tests():
    print("--- STARTING GOOGLE AUTH & PROVISIONING TESTS ---")
    session = await get_raw_session()
    async with session:
        # Test 1: New Google User (First login)
        new_user_id = str(uuid.uuid4())
        new_email = f"test_google_{uuid.uuid4().hex[:6]}@example.com"
        
        # Simulate /auth/me call for new user
        token_data_new = TokenData(user_id=new_user_id, email=new_email, role="org_user", full_name="Google Test User")
        me_resp_1 = await get_me(current_user=token_data_new, db=session)
        print("\n1. New Google User /auth/me:")
        print(f"   requires_onboarding: {me_resp_1['requires_onboarding']} (Expected: True)")
        print(f"   org_name: {me_resp_1['organization_name']} (Expected: Pending Workspace Setup)")
        assert me_resp_1['requires_onboarding'] is True
        assert me_resp_1['organization_name'] == "Pending Workspace Setup"

        # Simulate onboarding form submission (/auth/provision)
        prov_req = ProvisionRequest(full_name="Google Test User", workspace_name="Alpha Tech Inc", industry="saas")
        prov_resp = await provision_user_workspace(body=prov_req, current_user=token_data_new, db=session)
        print("\n2. New Google User Workspace Onboarding Submission (/auth/provision):")
        print(f"   requires_onboarding: {prov_resp['requires_onboarding']} (Expected: False)")
        print(f"   org_name: {prov_resp['organization_name']} (Expected: Alpha Tech Inc)")
        print(f"   industry: {prov_resp['industry']} (Expected: saas)")
        assert prov_resp['requires_onboarding'] is False
        assert prov_resp['organization_name'] == "Alpha Tech Inc"

        # Simulate subsequent /auth/me call after onboarding completed
        me_resp_2 = await get_me(current_user=token_data_new, db=session)
        print("\n3. Subsequent Google Login /auth/me:")
        print(f"   requires_onboarding: {me_resp_2['requires_onboarding']} (Expected: False)")
        print(f"   org_name: {me_resp_2['organization_name']} (Expected: Alpha Tech Inc)")
        assert me_resp_2['requires_onboarding'] is False
        assert me_resp_2['organization_name'] == "Alpha Tech Inc"

        # Test 2: Existing Email Account + Google OAuth Attempt (Email Linking)
        existing_email = f"existing_email_{uuid.uuid4().hex[:6]}@example.com"
        existing_user_id = str(uuid.uuid4())
        
        # Provision existing email account workspace
        _, existing_org = await crud.ensure_user_organization_provisioned(
            session,
            user_id=existing_user_id,
            email=existing_email,
            full_name="Existing Email User",
            workspace_name="Existing Email Org",
            industry="healthcare"
        )

        # Now simulate Google OAuth login with the SAME email address but DIFFERENT user_id
        google_oauth_id = str(uuid.uuid4())
        token_data_existing_email = TokenData(user_id=google_oauth_id, email=existing_email, role="org_user", full_name="Google Linked User")
        me_resp_linked = await get_me(current_user=token_data_existing_email, db=session)
        print("\n4. Existing Email User signing in via Google OAuth:")
        print(f"   requires_onboarding: {me_resp_linked['requires_onboarding']} (Expected: False)")
        print(f"   org_name: {me_resp_linked['organization_name']} (Expected: Existing Email Org)")
        assert me_resp_linked['requires_onboarding'] is False
        assert me_resp_linked['organization_name'] == "Existing Email Org"

        # Verify no duplicate organization was created
        org_user_check, org_check = await crud.ensure_user_organization_provisioned(session, google_oauth_id, existing_email)
        assert str(org_check.id) == str(existing_org.id)
        print("   Duplicate Prevention Check: PASSED (Reused existing organization)")

        print("\n--- ALL TESTS PASSED SUCCESSFULLY! ---")

if __name__ == "__main__":
    asyncio.run(run_tests())
