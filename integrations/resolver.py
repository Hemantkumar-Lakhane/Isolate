"""
integrations/resolver.py
========================
Central ConnectionResolver & Capability Service for SMBFlow.
Evaluates workflow tool capability requests against tenant connections with:
- Strict tenant and personal vs. organization scope isolation
- Automatic token expiration checking and auto-refresh via KeyVault
- Granted OAuth scope verification
- Standardized structured response codes:
  - AVAILABLE
  - CONNECTION_REQUIRED
  - PERMISSION_REQUIRED
  - REAUTH_REQUIRED
  - CONNECTION_ERROR
  - ACCESS_DENIED
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.core import ToolConnection
from integrations.audit_service import record_audit_event
from integrations.key_vault import decrypt_credentials, encrypt_credentials
from integrations.registry import (
    PROVIDER_CATALOG,
    ConnectionStatus,
    ProviderDefinition,
    ScopeLevel,
    find_provider_for_capability,
    get_provider,
    normalize_error,
)

log = structlog.get_logger()


class ResolutionStatus(str, Enum):
    AVAILABLE = "available"
    CONNECTION_REQUIRED = "connection_required"
    PERMISSION_REQUIRED = "permission_required"
    REAUTH_REQUIRED = "reauth_required"
    CONNECTION_ERROR = "connection_error"
    ACCESS_DENIED = "access_denied"
    UNSUPPORTED_CAPABILITY = "unsupported_capability"


class ConnectionResolver:
    """
    Central connection resolution engine for SMBFlow workflows.
    Ensures all workflows and AI nodes resolve external connections through a single hardened path.
    """

    @classmethod
    async def resolve(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID | str,
        user_id: Optional[uuid.UUID | str],
        capability_id: str,
        provider_name: Optional[str] = None,
        auto_refresh: bool = True,
    ) -> Dict[str, Any]:
        """
        Main capability resolution pipeline.
        Steps:
        1. Find provider definition and canonical capability.
        2. Query database for active organization / personal connections.
        3. Validate tenant and user authorization.
        4. Validate connection status.
        5. Check token expiry and auto-refresh if needed.
        6. Check granted OAuth scopes.
        7. Return structured status dictionary.
        """
        org_uuid = uuid.UUID(str(organization_id)) if organization_id else None
        user_uuid = uuid.UUID(str(user_id)) if user_id else None

        if not org_uuid:
            return {
                "status": ResolutionStatus.ACCESS_DENIED.value,
                "code": "ACCESS_DENIED",
                "message": "Missing organization context for capability resolution.",
                "retryable": False,
                "action": "contact_admin",
                "capability": capability_id,
            }

        # 1. Identify Provider Definition
        provider = get_provider(provider_name) if provider_name else find_provider_for_capability(capability_id)
        if not provider:
            return {
                "status": ResolutionStatus.UNSUPPORTED_CAPABILITY.value,
                "code": "UNSUPPORTED_CAPABILITY",
                "message": f"No supported integration provider registered for capability '{capability_id}'.",
                "retryable": False,
                "action": None,
                "capability": capability_id,
            }

        target_tool_names = [provider.tool_name]
        if provider.tool_name == "google_workspace":
            target_tool_names.extend(["google", "gmail", "calendar", "meet", "drive", "docs", "sheets", "slides"])

        # 2. Query Connections for this Tenant
        stmt = select(ToolConnection).where(
            ToolConnection.organization_id == org_uuid,
            ToolConnection.tool_name.in_(target_tool_names),
        )
        res = await db.execute(stmt)
        all_conns = res.scalars().all()

        # Filter by Scope Level
        matched_conn: Optional[ToolConnection] = None
        for conn in all_conns:
            if provider.scope_level == ScopeLevel.PERSONAL:
                if user_uuid and conn.user_id == user_uuid:
                    matched_conn = conn
                    break
            else:
                # Organization-wide connection: usable by any authorized org user
                matched_conn = conn
                break

        # 3. Connection Not Found
        if not matched_conn:
            return {
                "status": ResolutionStatus.CONNECTION_REQUIRED.value,
                "code": "CONNECTION_REQUIRED",
                "provider": provider.tool_name,
                "provider_name": provider.display_name,
                "capability": capability_id,
                "message": f"{provider.display_name} must be connected before this workflow can continue.",
                "retryable": True,
                "action": "connect",
                "connect_url": f"/integrations?connect={provider.tool_name}&capability={capability_id}",
            }

        conn_id_str = str(matched_conn.id)

        # 4. Check Connection Status (Error / Reauth)
        if matched_conn.status == "reauth_required":
            return {
                "status": ResolutionStatus.REAUTH_REQUIRED.value,
                "code": "REAUTH_REQUIRED",
                "provider": provider.tool_name,
                "provider_name": provider.display_name,
                "connection_id": conn_id_str,
                "capability": capability_id,
                "message": f"Your {provider.display_name} connection needs to be reconnected ({matched_conn.last_error_message or 'Token revoked'}).",
                "retryable": True,
                "action": "reconnect",
                "connect_url": f"/integrations?connect={provider.tool_name}&reauth=true",
            }

        if matched_conn.status == "error":
            return {
                "status": ResolutionStatus.CONNECTION_ERROR.value,
                "code": matched_conn.last_error_code or "CONNECTION_ERROR",
                "provider": provider.tool_name,
                "provider_name": provider.display_name,
                "connection_id": conn_id_str,
                "capability": capability_id,
                "message": matched_conn.last_error_message or f"Connection issue detected with {provider.display_name}.",
                "retryable": True,
                "action": "retry",
                "connect_url": f"/integrations?connect={provider.tool_name}",
            }

        # 5. Check Token Expiration & Perform Auto-Refresh
        if auto_refresh and provider.auth_type.value == "oauth2" and matched_conn.encrypted_credentials:
            try:
                refreshed, new_token = await cls._ensure_valid_token(db, matched_conn, provider)
                if not refreshed and not new_token:
                    # Token refresh failed -> update status to reauth_required
                    matched_conn.status = "reauth_required"
                    matched_conn.last_error_code = "TOKEN_REFRESH_FAILED"
                    matched_conn.last_error_message = "Automated token refresh failed. Please reconnect."
                    matched_conn.updated_at = datetime.now(timezone.utc)
                    await db.commit()

                    await record_audit_event(
                        db=db,
                        org_id=org_uuid,
                        user_id=user_uuid,
                        provider=provider.tool_name,
                        connection_id=matched_conn.id,
                        event="token_refresh_failed",
                        capability=capability_id,
                        success=False,
                        error_code="TOKEN_REFRESH_FAILED",
                    )

                    return {
                        "status": ResolutionStatus.REAUTH_REQUIRED.value,
                        "code": "TOKEN_REFRESH_FAILED",
                        "provider": provider.tool_name,
                        "provider_name": provider.display_name,
                        "connection_id": conn_id_str,
                        "capability": capability_id,
                        "message": f"Your session with {provider.display_name} has expired and could not be refreshed. Please reconnect.",
                        "retryable": True,
                        "action": "reconnect",
                        "connect_url": f"/integrations?connect={provider.tool_name}&reauth=true",
                    }
            except Exception as ref_err:
                log.error("Token refresh exception", provider=provider.tool_name, error=str(ref_err))

        # 6. Check Granted Scopes for Capability
        granted_scopes = matched_conn.granted_scopes or []
        missing_scopes = provider.get_missing_scopes_for_capability(capability_id, granted_scopes)
        if missing_scopes:
            return {
                "status": ResolutionStatus.PERMISSION_REQUIRED.value,
                "code": "PERMISSION_REQUIRED",
                "provider": provider.tool_name,
                "provider_name": provider.display_name,
                "connection_id": conn_id_str,
                "capability": capability_id,
                "missing_scopes": missing_scopes,
                "message": f"{provider.display_name} is connected, but additional permission is required for '{capability_id}'.",
                "retryable": True,
                "action": "grant_permission",
                "connect_url": f"/integrations?connect={provider.tool_name}&capabilities={capability_id}&incremental=true",
            }

        # 7. Available & Ready to Execute
        return {
            "status": ResolutionStatus.AVAILABLE.value,
            "code": "AVAILABLE",
            "provider": provider.tool_name,
            "provider_name": provider.display_name,
            "connection_id": conn_id_str,
            "capability": capability_id,
            "account_name": matched_conn.provider_account_name or (matched_conn.config or {}).get("connected_email"),
            "scope_level": provider.scope_level.value,
            "is_reusable": True,
            "message": f"{provider.display_name} connection is verified and ready for '{capability_id}'.",
        }

    @classmethod
    async def _ensure_valid_token(
        cls,
        db: AsyncSession,
        conn: ToolConnection,
        provider: ProviderDefinition,
    ) -> Tuple[bool, Optional[str]]:
        """
        Inspect token expiration timestamp and refresh if within 60s of expiring.
        Returns (success: bool, access_token: Optional[str])
        """
        if not conn.encrypted_credentials:
            return False, None

        creds = decrypt_credentials(conn.encrypted_credentials)
        expires_at = float(creds.get("expires_at", 0))
        access_token = creds.get("access_token")
        refresh_token = creds.get("refresh_token")
        client_id = creds.get("client_id") or provider.get_client_id()
        client_secret = creds.get("client_secret") or provider.get_client_secret()

        now = time.time()
        # If token has more than 60s of lifetime remaining, it is valid
        if expires_at and now < (expires_at - 60) and access_token:
            return True, access_token

        # Need to refresh
        if not refresh_token or not client_id or not client_secret:
            return False, access_token

        refresh_payload = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        }

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(
                    provider.oauth_token_url,
                    data=refresh_payload,
                    headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
                )
                if resp.status_code == 200:
                    tdata = resp.json()
                    new_access_token = tdata.get("access_token")
                    expires_in = tdata.get("expires_in", 3600)

                    creds["access_token"] = new_access_token
                    creds["expires_at"] = time.time() + expires_in
                    if tdata.get("refresh_token"):
                        creds["refresh_token"] = tdata["refresh_token"]

                    conn.encrypted_credentials = encrypt_credentials(creds)
                    conn.expires_at = datetime.fromtimestamp(creds["expires_at"], tz=timezone.utc)
                    conn.updated_at = datetime.now(timezone.utc)
                    await db.commit()

                    log.info("Successfully refreshed OAuth access token via ConnectionResolver", tool_name=provider.tool_name)
                    return True, new_access_token
                else:
                    log.warning("Token refresh rejected by provider", status=resp.status_code, body=resp.text[:200])
                    return False, None
        except Exception as e:
            log.error("Token refresh network failure", error=str(e))
            return False, None
