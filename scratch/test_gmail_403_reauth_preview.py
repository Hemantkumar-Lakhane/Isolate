"""
scratch/test_gmail_403_reauth_preview.py
=========================================
Verification script for Gmail 403 error detection, Re-auth UX endpoints,
real email preview & filter counts, and source-isolation error signaling.
"""

import asyncio
import json
import uuid
import sys
from pathlib import Path
import httpx
from unittest.mock import patch, AsyncMock

# Ensure root directory is on sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from dotenv import load_dotenv
load_dotenv(override=True)

from api.main import app
from api.auth import create_access_token
from db.models.core import ToolConnection, Organization, OrganizationUser
from core.database import get_raw_session
from integrations.key_vault import encrypt_credentials
from integrations.connectors import GmailConnector
from integrations.tool_registry_builder import build_registry

async def run_verification():
    print("=" * 70)
    print("STARTING GMAIL 403 + REAL EMAIL PREVIEW + REAUTH UX VERIFICATION")
    print("=" * 70)

    # 1. Setup Test Organization and ToolConnections
    test_org_id = uuid.uuid4()
    test_user_id = str(uuid.uuid4())
    test_email = f"user_{uuid.uuid4().hex[:6]}@example.com"
    real_oauth_email = "real.connected.owner@gmail.com"

    db = await get_raw_session()
    async with db:
        org = Organization(
            id=test_org_id,
            name="Gmail Reauth & Preview Test Org",
            industry="saas",
            active=True,
            profile_config={
                "client_name": "Gmail Reauth Org",
                "industry": "saas",
                "business_rules": {"operating_hours": {}},
                "tone_profile": {"tone": "professional"},
            }
        )
        db.add(org)

        org_user = OrganizationUser(
            id=uuid.uuid4(),
            organization_id=test_org_id,
            user_id=uuid.UUID(test_user_id),
            email=test_email,
            role="org_admin"
        )
        db.add(org_user)

        enc_creds = encrypt_credentials({
            "access_token": "ya29.mock_access_token",
            "refresh_token": "mock_refresh_token",
            "client_id": "mock_client_id",
            "client_secret": "mock_secret"
        })
        conn = ToolConnection(
            id=uuid.uuid4(),
            organization_id=test_org_id,
            tool_name="gmail",
            display_name="Gmail / Email",
            status="connected",
            encrypted_credentials=enc_creds,
            config={"connected_email": real_oauth_email, "sender_alias": real_oauth_email}
        )
        db.add(conn)
        await db.commit()

    token = create_access_token({
        "sub": test_user_id,
        "email": test_email,
        "role": "org_admin",
        "organization_id": str(test_org_id)
    })
    headers = {"Authorization": f"Bearer {token}"}

    print(f"  [OK] Created test org ({str(test_org_id)[:8]}) with Google identity: {real_oauth_email}")

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # -------------------------------------------------------------
        # TEST 1: Google OAuth Authorize Endpoint & Gmail Scopes
        # -------------------------------------------------------------
        print("\n--- TEST 1: Google OAuth Authorize & Gmail Read Scope ---")
        auth_resp = await client.get("/api/v1/connections/oauth/google/authorize?redirect_uri=http://localhost:5173/setup/connections&scopes=email,calendar,drive", headers=headers)
        assert auth_resp.status_code == 200, f"Expected 200, got {auth_resp.status_code}: {auth_resp.text}"
        auth_data = auth_resp.json()
        assert "url" in auth_data, "Missing url in auth response"
        assert "gmail.readonly" in auth_data.get("url", ""), "gmail.readonly scope missing from Google OAuth authorization URL"
        print("  [OK] Google OAuth Authorize URL includes required scope: https://www.googleapis.com/auth/gmail.readonly")

        # -------------------------------------------------------------
        # TEST 2: GmailConnector 403 Error Capture
        # -------------------------------------------------------------
        print("\n--- TEST 2: GmailConnector Exact 403 Reason Capture ---")
        gc = GmailConnector({"access_token": "invalid_or_expired_token"}, config={"connected_email": real_oauth_email})
        
        # Mock httpx client response returning 403 Forbidden with GCP error message
        mock_403_resp = httpx.Response(
            status_code=403,
            json={
                "error": {
                    "code": 403,
                    "message": "Gmail API has not been used in project 999999 before or it is disabled.",
                    "errors": [{"reason": "accessNotConfigured", "domain": "usageLimits"}]
                }
            },
            request=httpx.Request("GET", "https://gmail.googleapis.com/gmail/v1/users/me/messages")
        )

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock, return_value=mock_403_resp):
            stubs = await gc.read("messages", {"q": "in:inbox"})
            assert len(stubs) == 0
            err_info = gc.get_last_error_info()
            assert err_info["error_code"] == 403, f"Expected error_code 403, got {err_info['error_code']}"
            assert "accessNotConfigured" in err_info["error_reason"] or "disabled" in err_info["error"], f"Unexpected error info: {err_info}"
            print(f"  [OK] Gmail 403 response body correctly captured: code=403, reason={err_info['error_reason']}, msg={err_info['error']}")

        # -------------------------------------------------------------
        # TEST 3: Trigger Info Endpoint with Real Preview & Filter Breakdown
        # -------------------------------------------------------------
        print("\n--- TEST 3: Trigger Info Real Preview & Filter Breakdown ---")

        mock_stubs = [{"id": "msg_101"}, {"id": "msg_102"}]
        mock_detailed = [{
            "email_id": "msg_101",
            "thread_id": "thread_01",
            "from": "client@acme.com",
            "to": "owner@business.com",
            "subject": "Urgent Contract Review",
            "body": "Hello SMBFlow team, please review our urgent agreement",
            "snippet": "Hello SMBFlow team, please review our urgent agreement",
            "received_at": "Wed, 15 Sep 2026 12:00:00 GMT",
            "data_origin": "real_gmail"
        }]

        with patch.object(GmailConnector, "read", new_callable=AsyncMock, return_value=mock_stubs), \
             patch.object(GmailConnector, "read_detailed_messages", new_callable=AsyncMock, return_value=mock_detailed):

            info_resp = await client.get("/api/v1/workflows/email_summarizer/trigger-info?date_range=Today&scope=Inbox&batch_size=10", headers=headers)
            assert info_resp.status_code == 200, f"Expected 200, got {info_resp.status_code}: {info_resp.text}"
            info_data = info_resp.json()

            assert info_data.get("real_gmail_connected") is True, f"real_gmail_connected should be True, got {info_data}"
            assert info_data.get("real_gmail_status") == "ok", f"Expected real_gmail_status ok, got {info_data.get('real_gmail_status')}"
            assert info_data.get("connected_email") == real_oauth_email, f"Expected {real_oauth_email}, got {info_data.get('connected_email')}"
            assert info_data.get("total_inbox_count") == 2, f"Expected 2 total inbox messages, got {info_data.get('total_inbox_count')}"
            assert info_data.get("real_messages_count") == 2, f"Expected 2 matching messages, got {info_data.get('real_messages_count')}"
            assert len(info_data.get("preview_messages", [])) > 0, "Expected non-empty preview_messages"
            pm = info_data["preview_messages"][0]
            assert pm["subject"] == "Urgent Contract Review", f"Unexpected preview subject: {pm.get('subject')}"
            print("  [OK] Trigger Info real preview breakdown verified: total=2, matching=2, connected_email=" + real_oauth_email)

        # -------------------------------------------------------------
        # TEST 4: Tool Registry Source Isolation & GMAIL_SOURCE_UNAVAILABLE
        # -------------------------------------------------------------
        print("\n--- TEST 4: Tool Registry Source Isolation & Error Signal ---")
        tenant_config = {"client_id": str(test_org_id), "organization_id": str(test_org_id)}
        loaded_creds = {"gmail": {"access_token": "invalid_access_token", "connected_email": real_oauth_email}}
        reg = build_registry(tenant_config, credentials=loaded_creds)

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock, return_value=mock_403_resp):
            gmail_tool_fn = reg._tools.get("gmail_read_messages", {}).get("fn")
            assert gmail_tool_fn is not None, "gmail_read_messages tool function missing"

            res = await gmail_tool_fn(query="in:inbox", limit=10)
            assert res.get("status") == "error", f"Expected error status, got {res.get('status')}"
            assert res.get("error_code") == "GMAIL_SOURCE_UNAVAILABLE", f"Expected GMAIL_SOURCE_UNAVAILABLE, got {res.get('error_code')}"
            assert res.get("data_origin") == "real_gmail", f"Expected data_origin real_gmail, got {res.get('data_origin')}"
            assert res.get("is_test_data") is False, "Expected is_test_data False"
            print("  [OK] Real Gmail failure correctly returns GMAIL_SOURCE_UNAVAILABLE without fallback to synthetic data")

    print("\n" + "=" * 70)
    print("ALL VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(run_verification())
