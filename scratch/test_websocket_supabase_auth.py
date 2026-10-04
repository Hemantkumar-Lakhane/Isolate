"""
scratch/test_websocket_supabase_auth.py
=========================================
Verification script for SMBFlow WebSocket 403 & Supabase JWT Auth fix.
"""

import asyncio
import json
import uuid
import sys
from pathlib import Path

# Ensure root dir is on sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from dotenv import load_dotenv
load_dotenv(override=True)

import pytest
from fastapi.testclient import TestClient
from api.main import app
from api.auth import create_access_token, decode_token
from api.deps.auth import get_current_user_from_token, _resolve_org_context
from db.models.core import Organization, OrganizationUser
from core.database import get_raw_session

async def run_verification():
    print("=" * 60)
    print("STARTING WEBSOCKET & SUPABASE JWT AUTH VERIFICATION")
    print("=" * 60)

    # -------------------------------------------------------------
    # 1. Backend Import & Startup Check
    # -------------------------------------------------------------
    print("\n--- STEP 1: Backend Import & Startup Check ---")
    assert app is not None, "FastAPI app instance failed to initialize"
    print("  [OK] FastAPI app imported cleanly without errors")

    # -------------------------------------------------------------
    # 2. Database Organization User Context Setup
    # -------------------------------------------------------------
    test_user_id = str(uuid.uuid4())
    test_email = f"user_{uuid.uuid4().hex[:6]}@example.com"
    test_org_id = uuid.uuid4()

    db = await get_raw_session()
    async with db:
        org = Organization(
            id=test_org_id,
            name="Auth Test Org",
            industry="saas",
            active=True
        )
        db.add(org)
        await db.commit()

        org_user = OrganizationUser(
            id=uuid.uuid4(),
            organization_id=test_org_id,
            user_id=uuid.UUID(test_user_id),
            email=test_email,
            role="org_admin"
        )
        db.add(org_user)
        await db.commit()

    print(f"  [OK] Created test user ({test_email}) in DB associated with Org ({str(test_org_id)[:8]})")

    # -------------------------------------------------------------
    # 3. HTTP Auth Verification & DB Org Resolution Check
    # -------------------------------------------------------------
    print("\n--- STEP 3: HTTP Auth & DB Org Resolution ---")
    valid_token = create_access_token({
        "sub": test_user_id,
        "email": test_email,
        "role": "authenticated"  # standard Supabase role
    })

    user_data = await get_current_user_from_token(valid_token)
    assert user_data.user_id == test_user_id, "User ID mismatch"
    assert user_data.email == test_email, "Email mismatch"
    assert user_data.organization_id == str(test_org_id), "Organization ID was not resolved from DB"
    assert user_data.role == "org_admin", "Role was not resolved from DB"
    print(f"  [OK] get_current_user_from_token resolved org={user_data.organization_id[:8]} role={user_data.role}")

    # -------------------------------------------------------------
    # 4. WebSocket Authenticated Connection Check (FastAPI TestClient)
    # -------------------------------------------------------------
    print("\n--- STEP 4: WebSocket Authenticated Connection Check ---")
    client = TestClient(app)
    session_id = f"test_session_{uuid.uuid4().hex[:6]}"

    with client.websocket_connect(f"/ws/{session_id}?token={valid_token}") as websocket:
        data = websocket.receive_json()
        assert data.get("type") == "connected", f"Expected connected event, got {data}"
        print(f"  [OK] WebSocket connected successfully! Response: {data}")

    # -------------------------------------------------------------
    # 5. Confirm Unauthenticated / Invalid Token is Rejected
    # -------------------------------------------------------------
    print("\n--- STEP 5: Confirm Invalid / Unauthenticated Rejection ---")
    # A. Invalid token
    rejected_invalid = False
    try:
        with client.websocket_connect(f"/ws/{session_id}?token=invalid.jwt.token"):
            pass
    except Exception as e:
        rejected_invalid = True
        print(f"  [OK] Invalid token correctly rejected: {e}")

    assert rejected_invalid, "Invalid token was not rejected!"

    # B. Missing token
    rejected_missing = False
    try:
        with client.websocket_connect(f"/ws/{session_id}"):
            pass
    except Exception as e:
        rejected_missing = True
        print(f"  [OK] Missing token correctly rejected: {e}")

    assert rejected_missing, "Missing token was not rejected!"

    # -------------------------------------------------------------
    # 6. Verification Summary Table
    # -------------------------------------------------------------
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    print("| Test | Expected | Actual | Status |")
    print("|------|----------|--------|--------|")
    print("| Backend startup | clean import | app loaded | PASS |")
    print("| HTTP Auth (/me) | TokenData with org | org=" + str(test_org_id)[:8] + " | PASS |")
    print("| WebSocket Auth | 200/Upgrade (no 403) | connected | PASS |")
    print("| Invalid Token WS | rejected | connection closed | PASS |")
    print("| Org/Role Resolution | org_admin from DB | org_admin | PASS |")

if __name__ == "__main__":
    asyncio.run(run_verification())
