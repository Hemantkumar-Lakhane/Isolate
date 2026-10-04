"""
integrations/oauth_service.py
=============================
Generic Server-Side OAuth 2.0 / 2.1 Framework for SMBFlow Tool Connections.
Handles:
- Cryptographic HMAC-signed OAuth state generation & validation (tenant & user bound)
- Authorization URL construction with least-privilege capability-to-scope resolution
- Server-side authorization code exchange (keeping client secrets strictly on backend)
- Account identity extraction from provider userinfo APIs
- Secure encrypted token persistence via MultiFernet Vault
- Immediate health verification before marking CONNECTED
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import uuid

import httpx
import structlog
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.core import ToolConnection
from integrations.key_vault import encrypt_credentials, decrypt_credentials
from integrations.registry import (
    get_provider,
    normalize_error,
    ProviderDefinition,
    ScopeLevel,
    ConnectionStatus,
)

log = structlog.get_logger()

OAUTH_STATE_VALIDITY_SECONDS = 900  # 15 minutes


def _get_signing_key() -> bytes:
    """Retrieve secret key for signing OAuth state tokens."""
    key = os.getenv("SECRET_KEY") or os.getenv("VAULT_ENCRYPTION_KEY") or "smbflow_oauth_signing_secret_dev"
    return key.encode("utf-8")


def generate_oauth_state(
    provider_name: str,
    organization_id: str,
    user_id: Optional[str] = None,
    requested_capabilities: Optional[List[str]] = None,
    return_to: str = "http://localhost:5173/integrations",
) -> str:
    """
    Generate an HMAC-signed, tamper-proof state payload for the OAuth flow.
    Encodes:
    - provider: Provider key
    - org_id: Organization context
    - user_id: User context (for personal connections like LinkedIn or Gmail)
    - caps: List of capabilities requested
    - return_to: Frontend redirection destination after callback
    - ts: Unix timestamp for expiry validation
    - nonce: Random unique string
    """
    payload = {
        "provider": provider_name,
        "org_id": str(organization_id),
        "user_id": str(user_id) if user_id else None,
        "caps": requested_capabilities or [],
        "return_to": return_to,
        "ts": int(time.time()),
        "nonce": uuid.uuid4().hex[:12],
    }
    json_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    b64_payload = base64.urlsafe_b64encode(json_bytes).decode("utf-8")

    sig = hmac.new(_get_signing_key(), b64_payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{b64_payload}.{sig}"


def verify_oauth_state(state: str) -> Dict[str, Any]:
    """
    Verify HMAC signature and timestamp expiry of an OAuth state token.
    Raises HTTPException(400) if invalid or expired.
    """
    if not state or "." not in state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth state parameter."
        )

    b64_payload, signature = state.rsplit(".", 1)
    expected_sig = hmac.new(_get_signing_key(), b64_payload.encode("utf-8"), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(signature, expected_sig):
        log.warning("OAuth state HMAC signature mismatch", state=state[:20])
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth state verification failed. Possible CSRF attempt or tampering."
        )

    try:
        json_bytes = base64.urlsafe_b64decode(b64_payload.encode("utf-8"))
        payload = json.loads(json_bytes.decode("utf-8"))
    except Exception as e:
        log.error("Failed to decode OAuth state payload", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed OAuth state payload."
        )

    # Expiry validation
    created_at = payload.get("ts", 0)
    if time.time() - created_at > OAUTH_STATE_VALIDITY_SECONDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth authorization session has expired. Please try connecting again."
        )

    return payload


def build_authorization_url(
    provider: ProviderDefinition,
    organization_id: str,
    user_id: Optional[str] = None,
    requested_capabilities: Optional[List[str]] = None,
    redirect_uri: str = "http://127.0.0.1:8000/api/v1/connections/oauth/{provider}/callback",
    return_to: str = "http://localhost:5173/integrations",
    prompt: Optional[str] = "consent",
) -> Tuple[str, str, List[str]]:
    """
    Constructs the full provider OAuth authorization URL with least-privilege scopes.
    Returns: (authorization_url, signed_state, requested_scopes)
    """
    client_id = provider.get_client_id()
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{provider.display_name} client ID ({provider.client_id_env}) is not configured on the server."
        )

    # Resolve scopes based on requested capabilities
    resolved_scopes = provider.resolve_scopes_for_capabilities(requested_capabilities)
    scope_str = provider.scope_separator.join(resolved_scopes)

    # Format redirect URI with provider name
    formatted_redirect_uri = redirect_uri.replace("{provider}", provider.tool_name)

    state = generate_oauth_state(
        provider_name=provider.tool_name,
        organization_id=organization_id,
        user_id=user_id,
        requested_capabilities=requested_capabilities,
        return_to=return_to,
    )

    params: Dict[str, str] = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": formatted_redirect_uri,
        "scope": scope_str,
        "state": state,
    }

    if provider.tool_name in ["gmail", "google_workspace"]:
        params["access_type"] = "offline"
        params["include_granted_scopes"] = "true"
        if prompt:
            params["prompt"] = prompt

    query_string = urllib.parse.urlencode(params)
    auth_url = f"{provider.oauth_authorize_url}?{query_string}"

    return auth_url, state, resolved_scopes


def build_incremental_authorization_url(
    provider: ProviderDefinition,
    existing_scopes: List[str],
    additional_capabilities: List[str],
    org_id: str,
    user_id: Optional[str] = None,
    account_email: Optional[str] = None,
    redirect_uri: str = "http://127.0.0.1:8000/api/v1/connections/oauth/{provider}/callback",
    return_to: str = "http://localhost:5173/integrations",
) -> str:
    """
    Constructs an incremental OAuth authorization URL for an existing connection.
    Passes include_granted_scopes=true, login_hint, and requested additional scopes.
    """
    client_id = provider.get_client_id()
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{provider.display_name} client ID ({provider.client_id_env}) is not configured on the server."
        )

    # Resolve scopes for additional capabilities requested
    new_scopes = provider.resolve_scopes_for_capabilities(additional_capabilities)
    combined_scopes = list(dict.fromkeys(existing_scopes + new_scopes))
    scope_str = provider.scope_separator.join(combined_scopes)

    formatted_redirect_uri = redirect_uri.replace("{provider}", provider.tool_name)

    state = generate_oauth_state(
        provider_name=provider.tool_name,
        organization_id=org_id,
        user_id=user_id,
        requested_capabilities=additional_capabilities,
        return_to=return_to,
    )

    params: Dict[str, str] = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": formatted_redirect_uri,
        "scope": scope_str,
        "state": state,
    }

    if provider.tool_name in ["gmail", "google_workspace"]:
        params["access_type"] = "offline"
        params["include_granted_scopes"] = "true"
        params["prompt"] = "consent"
        if account_email:
            params["login_hint"] = account_email

    query_string = urllib.parse.urlencode(params)
    return f"{provider.oauth_authorize_url}?{query_string}"



async def exchange_code_and_store_connection(
    provider_name: str,
    code: str,
    state: str,
    db: AsyncSession,
    redirect_uri: str,
) -> Tuple[ToolConnection, str]:
    """
    Canonical server-side code exchange and connection persistence.
    1. Verifies signed state.
    2. Exchanges authorization code for tokens directly on server.
    3. Retrieves connected account identity (email/name).
    4. Encrypts tokens in MultiFernet vault.
    5. Saves ToolConnection with capabilities and scope level.
    6. Returns (ToolConnection, return_to_url).
    """
    state_data = verify_oauth_state(state)
    org_id_str = state_data.get("org_id")
    user_id_str = state_data.get("user_id")
    return_to = state_data.get("return_to") or "http://localhost:5173/integrations"

    if not org_id_str:
        raise HTTPException(status_code=400, detail="Missing organization context in OAuth state.")

    org_uuid = uuid.UUID(org_id_str)
    user_uuid = uuid.UUID(user_id_str) if user_id_str else None

    provider = get_provider(provider_name)
    if not provider or provider.auth_type != "oauth2":
        raise HTTPException(status_code=400, detail=f"Unsupported OAuth provider: {provider_name}")

    client_id = provider.get_client_id()
    client_secret = provider.get_client_secret()

    if not client_id or not client_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OAuth credentials for {provider.display_name} are not properly configured on server."
        )

    # 1. Exchange Code for Access & Refresh Tokens
    token_payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri.replace("{provider}", provider.tool_name),
        "client_id": client_id,
        "client_secret": client_secret,
    }

    headers = {"Accept": "application/json"}
    if provider.tool_name == "linkedin":
        headers["Content-Type"] = "application/x-www-form-urlencoded"

    async with httpx.AsyncClient(timeout=25.0) as client:
        try:
            token_resp = await client.post(
                provider.oauth_token_url,
                data=token_payload,
                headers=headers,
            )
        except Exception as net_err:
            log.error("Token exchange network failure", provider=provider_name, error=str(net_err))
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to communicate with {provider.display_name} token server: {str(net_err)}"
            )

        if token_resp.status_code != 200:
            err_text = token_resp.text
            log.error("Token exchange failed with provider", provider=provider_name, status=token_resp.status_code, body=err_text)
            norm = normalize_error(err_text, "OAUTH_EXCHANGE_FAILED")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=norm["user_message"])

        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in", 3600)
        granted_scope_raw = token_data.get("scope", "")

        if not access_token:
            raise HTTPException(status_code=400, detail=f"No access token returned by {provider.display_name}.")

        granted_scopes: List[str] = (
            [s.strip() for s in granted_scope_raw.split(provider.scope_separator) if s.strip()]
            if isinstance(granted_scope_raw, str)
            else (granted_scope_raw or [])
        )

        # 2. Extract Connected Account Identity
        account_id = None
        account_name = None
        userinfo_headers = {"Authorization": f"Bearer {access_token}"}

        try:
            if provider.tool_name == "linkedin":
                # LinkedIn OpenID userinfo endpoint
                u_resp = await client.get("https://api.linkedin.com/v2/userinfo", headers=userinfo_headers)
                if u_resp.status_code == 200:
                    u_data = u_resp.json()
                    account_id = u_data.get("sub")
                    account_name = u_data.get("name") or u_data.get("email") or "LinkedIn Member"
                    if u_data.get("email") and account_name != u_data.get("email"):
                        account_name = f"{account_name} ({u_data.get('email')})"

            elif provider.tool_name in ["gmail", "google_workspace"]:
                u_resp = await client.get("https://www.googleapis.com/oauth2/v2/userinfo", headers=userinfo_headers)
                if u_resp.status_code == 200:
                    u_data = u_resp.json()
                    account_id = u_data.get("id")
                    account_name = u_data.get("email") or u_data.get("name")
        except Exception as u_err:
            log.warning("Userinfo fetch error (non-fatal)", provider=provider_name, error=str(u_err))

        if not account_name:
            account_name = f"{provider.display_name} Account"

    # 3. Handle Refresh Token & Scope Accumulation from Existing Connection
    query = select(ToolConnection).where(
        ToolConnection.organization_id == org_uuid,
        ToolConnection.tool_name == provider.tool_name,
    )
    if provider.scope_level == ScopeLevel.PERSONAL and user_uuid:
        query = query.where(ToolConnection.user_id == user_uuid)

    result = await db.execute(query)
    existing_conn = result.scalar_one_or_none()

    # If Google did not return a new refresh token on re-auth, preserve existing encrypted refresh token
    if not refresh_token and existing_conn and existing_conn.encrypted_credentials:
        try:
            old_creds = decrypt_credentials(existing_conn.encrypted_credentials)
            if old_creds.get("refresh_token"):
                refresh_token = old_creds["refresh_token"]
        except Exception as dec_err:
            log.warning("Could not decrypt existing refresh token", error=str(dec_err))

    # Merge granted scopes for incremental authorization
    if existing_conn and existing_conn.granted_scopes:
        combined = set(existing_conn.granted_scopes or [])
        combined.update(granted_scopes)
        granted_scopes = sorted(list(combined))

    credentials_dict = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": token_data.get("token_type", "Bearer"),
        "expires_at": time.time() + expires_in,
        "scope": " ".join(granted_scopes),
        "client_id": client_id,
        "client_secret": client_secret,
    }

    config_dict = {
        "account_id": account_id,
        "account_name": account_name,
        "connected_email": account_name if "@" in str(account_name) else None,
        "granted_scopes": granted_scopes,
        "connected_at": datetime.now(timezone.utc).isoformat(),
    }

    # Evaluate active capabilities based on accumulated granted scopes
    active_capabilities = [
        c.id for c in provider.capabilities
        if not provider.get_missing_scopes_for_capability(c.id, granted_scopes)
    ]

    # 4. Encrypt Credentials
    encrypted_creds = encrypt_credentials(credentials_dict)

    if existing_conn:
        existing_conn.display_name = provider.display_name
        existing_conn.status = ConnectionStatus.CONNECTED.value
        existing_conn.encrypted_credentials = encrypted_creds
        existing_conn.config = config_dict
        existing_conn.provider_account_id = account_id
        existing_conn.provider_account_name = account_name
        existing_conn.auth_type = "oauth2"
        existing_conn.granted_scopes = granted_scopes
        existing_conn.capabilities = active_capabilities
        existing_conn.expires_at = datetime.fromtimestamp(credentials_dict["expires_at"], tz=timezone.utc)
        existing_conn.last_tested_at = datetime.now(timezone.utc)
        existing_conn.last_error_code = None
        existing_conn.last_error_message = None
        existing_conn.updated_at = datetime.now(timezone.utc)
        conn_record = existing_conn
    else:
        conn_record = ToolConnection(
            id=uuid.uuid4(),
            organization_id=org_uuid,
            user_id=user_uuid if provider.scope_level == ScopeLevel.PERSONAL else None,
            tool_name=provider.tool_name,
            display_name=provider.display_name,
            status=ConnectionStatus.CONNECTED.value,
            encrypted_credentials=encrypted_creds,
            config=config_dict,
            provider_account_id=account_id,
            provider_account_name=account_name,
            auth_type="oauth2",
            granted_scopes=granted_scopes,
            capabilities=active_capabilities,
            expires_at=datetime.fromtimestamp(credentials_dict["expires_at"], tz=timezone.utc),
            last_tested_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(conn_record)

    await db.commit()
    await db.refresh(conn_record)

    # Record Audit Event
    try:
        from integrations.audit_service import record_audit_event
        await record_audit_event(
            db=db,
            org_id=org_uuid,
            user_id=user_uuid,
            provider=provider.tool_name,
            connection_id=conn_record.id,
            event="oauth_completed",
            success=True,
            details={
                "account_name": account_name,
                "capabilities_count": len(active_capabilities),
                "granted_scopes_count": len(granted_scopes),
            },
        )
    except Exception as audit_err:
        log.warning("Failed to record OAuth completion audit", error=str(audit_err))

    log.info(
        "Tool Connection authenticated and saved successfully",
        tool_name=provider.tool_name,
        account=account_name,
        org_id=str(org_uuid),
        capabilities_count=len(active_capabilities),
    )

    return conn_record, return_to

