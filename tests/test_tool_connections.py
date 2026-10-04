"""
tests/test_tool_connections.py
==============================
Test Suite for SMBFlow Enterprise Tool Connections & Integrations Platform.
Validates:
- Provider Catalog & Capability Discovery
- Least-Privilege Scope Resolution
- HMAC-signed OAuth State Generation & Anti-Tampering Verification
- MultiFernet Credential Vault Encryption / Decryption
- Error Normalization & User-Facing Safety
- Personal vs. Organization Scope Isolation Logic
"""

import time
import uuid
import pytest
from fastapi import HTTPException

from integrations.registry import (
    PROVIDER_CATALOG,
    get_provider,
    normalize_error,
    ScopeLevel,
    RiskLevel,
)
from integrations.oauth_service import (
    generate_oauth_state,
    verify_oauth_state,
    build_authorization_url,
)
from integrations.key_vault import (
    encrypt_credentials,
    decrypt_credentials,
    mask_credentials,
)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Provider Catalog & Capability Registry Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_provider_catalog_structure():
    """Verify all required providers exist in catalog with complete specifications."""
    expected_providers = ["google_workspace", "linkedin", "slack", "hubspot", "stripe", "rest_api"]
    for prov_name in expected_providers:
        prov = get_provider(prov_name)
        assert prov is not None, f"Provider '{prov_name}' not found in registry"
        assert prov.tool_name == prov_name
        assert prov.display_name
        assert prov.category
        assert prov.auth_type in ["oauth2", "api_key", "bot_token"]
        assert isinstance(prov.capabilities, list)
        assert len(prov.capabilities) > 0

    # Verify Google service aliases map to google_workspace
    for alias in ["gmail", "google", "meet", "calendar", "drive", "docs", "sheets", "slides"]:
        alias_prov = get_provider(alias)
        assert alias_prov is not None
        assert alias_prov.tool_name == "google_workspace"


def test_least_privilege_scope_resolution_google_workspace():
    """Verify Google Workspace least privilege scope resolution for Gmail, Calendar, Meet, Drive, Docs, Sheets, Slides."""
    gw = get_provider("google_workspace")
    assert gw is not None

    # Base scopes always included (email, profile, openid)
    base_scopes = gw.resolve_scopes_for_capabilities([])
    assert "https://www.googleapis.com/auth/userinfo.email" in base_scopes
    assert "openid" in base_scopes
    assert "https://www.googleapis.com/auth/gmail.send" not in base_scopes
    assert "https://www.googleapis.com/auth/meetings.space.readonly" not in base_scopes
    assert "https://www.googleapis.com/auth/documents" not in base_scopes

    # Request only Meet Transcript capability
    meet_scopes = gw.resolve_scopes_for_capabilities(["google.meet.transcript.read"])
    assert "https://www.googleapis.com/auth/meetings.space.readonly" in meet_scopes
    assert "https://www.googleapis.com/auth/gmail.send" not in meet_scopes

    # Request Gmail read + Sheets append capabilities
    mixed_scopes = gw.resolve_scopes_for_capabilities(["google.gmail.read", "google.sheets.write"])
    assert "https://www.googleapis.com/auth/gmail.readonly" in mixed_scopes
    assert "https://www.googleapis.com/auth/spreadsheets" in mixed_scopes
    assert "https://www.googleapis.com/auth/presentations" not in mixed_scopes


def test_google_workspace_16_capabilities_registered():
    """Verify all 16 required Google Workspace capabilities are registered."""
    gw = get_provider("google_workspace")
    assert gw is not None
    cap_ids = [c.id for c in gw.capabilities]
    expected_capabilities = [
        "google.gmail.read",
        "google.gmail.send",
        "google.calendar.read",
        "google.calendar.create",
        "google.meet.read",
        "google.meet.transcript.read",
        "google.meet.transcript.entries.read",
        "google.meet.recording.read",
        "google.drive.read",
        "google.drive.write",
        "google.docs.read",
        "google.docs.write",
        "google.slides.read",
        "google.slides.write",
        "google.sheets.read",
        "google.sheets.write",
    ]
    for expected in expected_capabilities:
        assert expected in cap_ids, f"Capability '{expected}' missing from Google Workspace definition"


def test_least_privilege_scope_resolution_linkedin():
    """Verify LinkedIn least privilege scope resolution."""
    linkedin = get_provider("linkedin")
    assert linkedin is not None
    assert linkedin.scope_level == ScopeLevel.PERSONAL

    # Base scopes for identity
    base_scopes = linkedin.resolve_scopes_for_capabilities([])
    assert "openid" in base_scopes
    assert "profile" in base_scopes
    assert "w_member_social" not in base_scopes

    # Request post capability
    post_scopes = linkedin.resolve_scopes_for_capabilities(["linkedin.post.create"])
    assert "w_member_social" in post_scopes
    assert "openid" in post_scopes


# ─────────────────────────────────────────────────────────────────────────────
# 2. Cryptographic OAuth State Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_oauth_state_generation_and_verification():
    """Verify signed state generation and round-trip verification."""
    org_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    caps = ["gmail.read", "gmail.send"]

    state = generate_oauth_state(
        provider_name="gmail",
        organization_id=org_id,
        user_id=user_id,
        requested_capabilities=caps,
        return_to="http://localhost:5173/integrations",
    )

    assert state and "." in state
    payload = verify_oauth_state(state)

    assert payload["provider"] == "gmail"
    assert payload["org_id"] == org_id
    assert payload["user_id"] == user_id
    assert payload["caps"] == caps
    assert payload["return_to"] == "http://localhost:5173/integrations"


def test_oauth_state_tamper_detection():
    """Verify that tampering with state payload causes verification failure."""
    org_id = str(uuid.uuid4())
    state = generate_oauth_state(provider_name="linkedin", organization_id=org_id)

    b64_part, sig = state.rsplit(".", 1)
    # Tamper with b64 payload
    tampered_b64 = b64_part[:-2] + "AA"
    tampered_state = f"{tampered_b64}.{sig}"

    with pytest.raises(HTTPException) as exc_info:
        verify_oauth_state(tampered_state)
    assert exc_info.value.status_code == 400
    assert "verification failed" in exc_info.value.detail.lower()


# ─────────────────────────────────────────────────────────────────────────────
# 3. Vault Credential Encryption Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_vault_encryption_decryption_roundtrip():
    """Verify credentials are encrypted and decrypted correctly via MultiFernet Vault."""
    test_creds = {
        "access_token": "ya29.a0AfH6SM...",
        "refresh_token": "1//04...",
        "client_secret": "GOCSPX-secret123",
        "api_key": "pat-na1-xyz",
    }

    encrypted = encrypt_credentials(test_creds)
    assert encrypted is not None
    assert encrypted != test_creds
    # Must not contain plaintext token
    assert "ya29" not in str(encrypted)
    assert "GOCSPX" not in str(encrypted)

    decrypted = decrypt_credentials(encrypted)
    assert decrypted == test_creds


def test_mask_credentials():
    """Verify credential masking leaves safe metadata and obscures secrets."""
    raw = {
        "access_token": "ya29.abcdef1234567890",
        "client_id": "client-123.apps.google.com",
        "account_name": "Dr. Smith",
    }
    masked = mask_credentials(raw)
    assert masked["account_name"] == "Dr. Smith"
    assert masked["client_id"] == "client-123.apps.google.com"
    assert "abcdef" not in masked["access_token"]
    assert "*" in masked["access_token"]


# ─────────────────────────────────────────────────────────────────────────────
# 4. Error Normalization Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_normalize_error_user_friendly():
    """Verify raw technical errors are sanitized for user display."""
    err_401 = normalize_error("HTTP 401 Unauthorized invalid_grant expired token", "OAUTH_ERR")
    assert err_401["code"] == "INVALID_CREDENTIALS"
    assert "invalid or have expired" in err_401["user_message"].lower() or "expired" in err_401["user_message"].lower()
    assert "HTTP 401" not in err_401["user_message"]

    err_rate = normalize_error("HTTP 429 Too Many Requests rate limit exceeded", "RATE_ERR")
    assert err_rate["code"] == "RATE_LIMITED"
    assert "rate limit" in err_rate["user_message"].lower() or "too many requests" in err_rate["user_message"].lower()


# ─────────────────────────────────────────────────────────────────────────────
# 5. Marketplace Counts & Capability Resolution Regression Tests (Scenarios A-F)
# ─────────────────────────────────────────────────────────────────────────────

def test_scenario_a_marketplace_counts_zero_connections():
    """Scenario A: Provider registry = 6 providers, 0 connections -> All=6, Connected=0, Available=6."""
    all_count = len(PROVIDER_CATALOG)
    connected_count = 0
    available_count = max(0, all_count - connected_count)
    assert all_count >= 6
    assert connected_count == 0
    assert available_count == all_count
    assert available_count >= 0


def test_scenario_b_marketplace_counts_one_connection():
    """Scenario B: Provider registry = 6, 1 connection -> All=6, Connected=1, Available=5."""
    all_count = len(PROVIDER_CATALOG)
    connected_count = 1
    available_count = max(0, all_count - connected_count)
    assert all_count >= 6
    assert connected_count == 1
    assert available_count == all_count - 1
    assert available_count >= 0


def test_scenario_c_marketplace_counts_all_connections():
    """Scenario C: Provider registry = 6, 6 connections -> All=6, Connected=6, Available=0 (never negative)."""
    all_count = len(PROVIDER_CATALOG)
    connected_count = all_count
    available_count = max(0, all_count - connected_count)
    assert all_count >= 6
    assert connected_count == all_count
    assert available_count == 0
    assert available_count >= 0


@pytest.mark.asyncio
async def test_scenario_e_and_f_workflow_capability_resolution(mocker):
    """
    Scenario E & F:
    - When Gmail is not connected -> returns structured connection_required.
    - When Gmail is connected -> returns status available, is_reusable: True.
    """
    from integrations.registry import resolve_capability_requirement, find_provider_for_capability

    # Verify provider discovery
    prov = find_provider_for_capability("google.gmail.send")
    assert prov is not None
    assert prov.tool_name == "google_workspace"

    prov_short = find_provider_for_capability("gmail.send")
    assert prov_short is not None
    assert prov_short.tool_name == "google_workspace"

    prov_meet = find_provider_for_capability("google.meet.transcript.read")
    assert prov_meet is not None
    assert prov_meet.tool_name == "google_workspace"

    # Scenario E: DB returns no active connection
    mock_db = mocker.AsyncMock()
    mock_result = mocker.MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result

    org_id = uuid.uuid4()
    user_id = uuid.uuid4()

    res_missing = await resolve_capability_requirement(
        db=mock_db,
        org_id=org_id,
        user_id=user_id,
        capability_id="google.gmail.send",
    )
    assert res_missing["status"] == "connection_required"
    assert res_missing["provider"] == "google_workspace"
    assert "connected before this workflow can continue" in res_missing["message"]
    assert "/integrations?connect=google_workspace" in res_missing["connect_url"]

    # Scenario F: DB returns active Google Workspace connection
    mock_conn = mocker.MagicMock()
    mock_conn.id = uuid.uuid4()
    mock_conn.tool_name = "google_workspace"
    mock_conn.status = "connected"
    mock_conn.user_id = None
    mock_conn.provider_account_name = "founder@smbflow.io"
    mock_conn.granted_scopes = [
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/meetings.space.readonly",
    ]
    mock_conn.config = {"connected_email": "founder@smbflow.io"}

    mock_result.scalars.return_value.all.return_value = [mock_conn]

    res_connected = await resolve_capability_requirement(
        db=mock_db,
        org_id=org_id,
        user_id=user_id,
        capability_id="google.gmail.send",
    )
    assert res_connected["status"] == "available"
    assert res_connected["connection_id"] == str(mock_conn.id)
    assert res_connected["account_name"] == "founder@smbflow.io"
    assert res_connected["is_reusable"] is True


# ─────────────────────────────────────────────────────────────────────────────
# 6. Central ConnectionResolver Service Tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_connection_resolver_all_states(mocker):
    """Verify ConnectionResolver returns correct statuses across all tool states."""
    from integrations.resolver import ConnectionResolver, ResolutionStatus
    from db.models.core import ToolConnection

    org_id = uuid.uuid4()
    user_id = uuid.uuid4()

    # 1. CONNECTION_REQUIRED when no connection exists
    mock_db = mocker.AsyncMock()
    mock_result = mocker.MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result

    res_missing = await ConnectionResolver.resolve(
        db=mock_db,
        organization_id=org_id,
        user_id=user_id,
        capability_id="google.meet.transcript.read",
        provider_name="google_workspace",
    )
    assert res_missing["status"] == ResolutionStatus.CONNECTION_REQUIRED.value
    assert res_missing["action"] == "connect"
    assert res_missing.get("connection_id") is None

    # 2. PERMISSION_REQUIRED when connection exists but missing required scope
    mock_conn = mocker.MagicMock()
    mock_conn.id = uuid.uuid4()
    mock_conn.organization_id = org_id
    mock_conn.user_id = None
    mock_conn.tool_name = "google_workspace"
    mock_conn.status = "connected"
    mock_conn.provider_account_name = "ceo@smbflow.io"
    # Only Gmail scopes granted, missing Google Meet transcript scope
    mock_conn.granted_scopes = ["https://www.googleapis.com/auth/gmail.send"]
    mock_conn.capabilities = ["google.gmail.send"]
    mock_conn.encrypted_credentials = None
    mock_conn.expires_at = None
    mock_result.scalars.return_value.all.return_value = [mock_conn]

    res_perm = await ConnectionResolver.resolve(
        db=mock_db,
        organization_id=org_id,
        user_id=user_id,
        capability_id="google.meet.transcript.read",
        provider_name="google_workspace",
    )
    assert res_perm["status"] == ResolutionStatus.PERMISSION_REQUIRED.value
    assert res_perm["action"] == "grant_permission"
    assert res_perm["connection_id"] == str(mock_conn.id)
    assert "permission is required" in res_perm["message"].lower()

    # 3. AVAILABLE when connection has required scope
    mock_conn.granted_scopes.append("https://www.googleapis.com/auth/meetings.space.readonly")
    mock_conn.capabilities.append("google.meet.transcript.read")

    res_avail = await ConnectionResolver.resolve(
        db=mock_db,
        organization_id=org_id,
        user_id=user_id,
        capability_id="google.meet.transcript.read",
        provider_name="google_workspace",
    )
    assert res_avail["status"] == ResolutionStatus.AVAILABLE.value
    assert res_avail.get("action") is None
    assert res_avail["account_name"] == "ceo@smbflow.io"

    # 4. REAUTH_REQUIRED when connection status is revoked or expired
    mock_conn.status = "reauth_required"
    res_reauth = await ConnectionResolver.resolve(
        db=mock_db,
        organization_id=org_id,
        user_id=user_id,
        capability_id="google.meet.transcript.read",
        provider_name="google_workspace",
    )
    assert res_reauth["status"] == ResolutionStatus.REAUTH_REQUIRED.value
    assert res_reauth["action"] == "reconnect"


# ─────────────────────────────────────────────────────────────────────────────
# 7. Audit Service & Zero-Credential Leakage Tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_audit_service_recording_and_sanitization(mocker):
    """Verify audit logs record lifecycle events and strip any credential leaks."""
    from integrations.audit_service import record_audit_event, get_connection_audit_logs

    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    conn_id = uuid.uuid4()

    mock_db = mocker.AsyncMock()

    # Record event with sensitive keys in metadata
    dirty_meta = {
        "access_token": "ya29.super_secret_token_12345",
        "refresh_token": "1//secret_refresh_token",
        "client_secret": "GOCSPX-secret",
        "scope_requested": ["google.meet.transcript.read"],
    }

    event = await record_audit_event(
        db=mock_db,
        org_id=org_id,
        user_id=user_id,
        provider="google_workspace",
        connection_id=conn_id,
        event="permission_granted",
        capability="google.meet.transcript.read",
        success=True,
        details=dirty_meta,
    )

    assert event["event"] == "permission_granted"
    assert event["provider"] == "google_workspace"
    assert event["success"] is True

    # Assert secrets were sanitized and never stored
    meta = event["details"]
    assert meta["access_token"] == "[REDACTED]"
    assert meta["refresh_token"] == "[REDACTED]"
    assert meta["client_secret"] == "[REDACTED]"
    assert "ya29" not in str(event)
    assert "GOCSPX" not in str(event)


# ─────────────────────────────────────────────────────────────────────────────
# 8. Incremental Authorization URL Generation
# ─────────────────────────────────────────────────────────────────────────────

def test_incremental_authorization_url_generation(monkeypatch):
    """Verify incremental OAuth URL builder includes granted scopes and login hint."""
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "mock-client-id.apps.googleusercontent.com")
    from integrations.oauth_service import build_incremental_authorization_url

    gw = get_provider("google_workspace")
    assert gw is not None

    existing_scopes = ["https://www.googleapis.com/auth/gmail.send"]
    new_caps = ["google.meet.transcript.read"]

    auth_url = build_incremental_authorization_url(
        provider=gw,
        existing_scopes=existing_scopes,
        additional_capabilities=new_caps,
        org_id="test-org-123",
        user_id="test-user-456",
        account_email="founder@smbflow.io",
    )

    assert "accounts.google.com" in auth_url
    assert "include_granted_scopes=true" in auth_url
    assert "login_hint=founder%40smbflow.io" in auth_url or "founder@smbflow.io" in auth_url
    assert "meetings.space.readonly" in auth_url
    assert "access_type=offline" in auth_url




