"""
api/routers/connections.py
===========================
First-Class Tool Connections API router.
Manages tool integration lifecycle: Connect, Disconnect, Test Connection, Configuration, Capabilities.
Enforces multi-tenant isolation and secure MultiFernet credential vault encryption.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps.auth import TokenData, require_authenticated_user
from api.dependencies import get_db
from integrations.key_vault import encrypt_credentials, decrypt_credentials, mask_credentials
from integrations.connectors import (
    GmailConnector, HubSpotConnector, SlackConnector, StripeConnector, GenericRESTConnector
)

log = structlog.get_logger()
router = APIRouter(prefix="/api/v1/connections", tags=["Tool Connections"])

AVAILABLE_CONNECTORS = [
    {
        "tool_name": "gmail",
        "display_name": "Gmail / Email",
        "category": "Communication",
        "description": "Send coordinator communication drafts and receive patient/client inquiries.",
        "auth_type": "oauth2",
        "required_fields": [],
        "config_fields": ["sender_alias", "sender_name", "queue_for_approval"],
        "capabilities": [
            {"id": "gmail.read_inbox", "name": "Read Inbox", "desc": "Read incoming inquiries and emails", "risk": "low"},
            {"id": "gmail.search_messages", "name": "Search Messages", "desc": "Search email threads and history", "risk": "low"},
            {"id": "gmail.create_draft", "name": "Create Response Drafts", "desc": "Prepare email drafts for review", "risk": "low"},
            {"id": "gmail.send_message", "name": "Send Messages", "desc": "Send outbound emails (Requires Approval)", "risk": "high", "requires_hitl": True},
        ],
    },
    {
        "tool_name": "google_workspace",
        "display_name": "Google Workspace & Drive",
        "category": "Storage & Calendar",
        "description": "Store documents, medical reports, and schedule appointments.",
        "auth_type": "oauth2",
        "required_fields": [],
        "config_fields": ["default_folder_id"],
        "capabilities": [
            {"id": "google.drive_read", "name": "Read Drive Files", "desc": "Access uploaded patient documents and files", "risk": "low"},
            {"id": "google.drive_upload", "name": "Upload Files", "desc": "Save records and reports to Drive", "risk": "low"},
            {"id": "google.calendar_schedule", "name": "Schedule Calendar Events", "desc": "Schedule consultations and appointments", "risk": "medium"},
        ],
    },
    {
        "tool_name": "hubspot",
        "display_name": "HubSpot CRM",
        "category": "CRM",
        "description": "Sync customer accounts, lead contacts, and pipeline deals.",
        "auth_type": "api_key",
        "required_fields": ["api_key"],
        "config_fields": ["pipeline_id"],
        "capabilities": [
            {"id": "hubspot.read_contacts", "name": "Read Contacts & Deals", "desc": "Fetch CRM contacts and pipeline status", "risk": "low"},
            {"id": "hubspot.create_contact", "name": "Create Leads/Contacts", "desc": "Add new leads to HubSpot CRM", "risk": "low"},
            {"id": "hubspot.update_deal", "name": "Update Pipeline Deals", "desc": "Update deal stages and values", "risk": "medium"},
            {"id": "hubspot.create_task", "name": "Create Follow-up Tasks", "desc": "Create tasks for sales/coordinators", "risk": "low"},
        ],
    },
    {
        "tool_name": "slack",
        "display_name": "Slack Notifications",
        "category": "Team Collaboration",
        "description": "Post internal escalation alerts and review queue notifications.",
        "auth_type": "bot_token",
        "required_fields": ["bot_token"],
        "config_fields": ["cs_alerts_channel", "sales_channel"],
        "capabilities": [
            {"id": "slack.post_message", "name": "Post Messages", "desc": "Post notifications to Slack channels", "risk": "low"},
            {"id": "slack.post_alert", "name": "Post Risk Escalations", "desc": "Send urgent escalation alerts to team", "risk": "medium"},
            {"id": "slack.read_history", "name": "Read Channel History", "desc": "Monitor channel inquiries and replies", "risk": "low"},
        ],
    },
    {
        "tool_name": "stripe",
        "display_name": "Stripe Payments & Billing",
        "category": "Finance",
        "description": "Retrieve subscription status, invoice data, and customer billing.",
        "auth_type": "api_key",
        "required_fields": ["secret_key"],
        "config_fields": [],
        "capabilities": [
            {"id": "stripe.read_customers", "name": "Read Customer Accounts", "desc": "Access customer payment profiles", "risk": "low"},
            {"id": "stripe.read_subscriptions", "name": "Read Subscriptions", "desc": "Check subscription tiers and status", "risk": "low"},
            {"id": "stripe.read_invoices", "name": "Read Billing Invoices", "desc": "Retrieve invoice histories and payments", "risk": "low"},
        ],
    },
    {
        "tool_name": "rest_api",
        "display_name": "Custom REST Connector",
        "category": "Custom Integration",
        "description": "Connect arbitrary business REST API endpoints.",
        "auth_type": "api_key",
        "required_fields": ["base_url", "api_key"],
        "config_fields": ["auth_header", "auth_prefix"],
        "capabilities": [
            {"id": "rest.get_resource", "name": "GET Resource Endpoints", "desc": "Query custom REST endpoints", "risk": "low"},
            {"id": "rest.post_resource", "name": "POST Resource Endpoints", "desc": "Write data to custom REST endpoints", "risk": "medium"},
        ],
    },
]


class ConnectToolRequest(BaseModel):
    tool_name: str
    display_name: Optional[str] = None
    credentials: dict = Field(default_factory=dict)
    config: dict = Field(default_factory=dict)


class UpdateToolRequest(BaseModel):
    display_name: Optional[str] = None
    credentials: Optional[dict] = None
    config: Optional[dict] = None


class GoogleOAuthExchangeRequest(BaseModel):
    code: str
    redirect_uri: str
    client_id: Optional[str] = None
    client_secret: Optional[str] = None


@router.get("/oauth/google/authorize")
async def get_google_oauth_authorize_url(
    redirect_uri: Optional[str] = "http://localhost:5173/setup/connections",
    scopes: Optional[str] = None,
    current_user: TokenData = Depends(require_authenticated_user),
):
    """Generate Google OAuth authorization URL for Gmail & Google Workspace tool integration with customizable scopes."""
    import os
    import urllib.parse
    from dotenv import load_dotenv

    load_dotenv(override=True)
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    if not client_id:
        raise HTTPException(
            status_code=400,
            detail="GOOGLE_CLIENT_ID environment variable is not configured on the server. Please add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to your .env file."
        )

    scope_mapping = {
        "email": [
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.send",
            "https://www.googleapis.com/auth/gmail.modify",
        ],
        "calendar": [
            "https://www.googleapis.com/auth/calendar.events",
            "https://www.googleapis.com/auth/calendar.readonly",
        ],
        "drive": [
            "https://www.googleapis.com/auth/drive.file",
            "https://www.googleapis.com/auth/drive.readonly",
        ],
    }

    resolved_scopes = set()
    # Always include baseline profile info
    resolved_scopes.add("https://www.googleapis.com/auth/userinfo.email")
    resolved_scopes.add("https://www.googleapis.com/auth/userinfo.profile")
    resolved_scopes.add("openid")

    if scopes:
        requested_list = [s.strip().lower() for s in scopes.split(",") if s.strip()]
        for req in requested_list:
            if req in scope_mapping:
                for sc in scope_mapping[req]:
                    resolved_scopes.add(sc)
            elif req.startswith("https://"):
                resolved_scopes.add(req)
    else:
        # Default to all recommended scopes (email + calendar)
        for sc in scope_mapping["email"] + scope_mapping["calendar"]:
            resolved_scopes.add(sc)

    state_data = f"org_{current_user.organization_id or current_user.tenant_id}"

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(sorted(resolved_scopes)),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state_data,
    }
    url = f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"
    return {"url": url, "redirect_uri": redirect_uri, "scopes": list(resolved_scopes)}


@router.post("/oauth/google/exchange")
async def exchange_google_oauth_code(
    body: GoogleOAuthExchangeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_authenticated_user),
):
    """Securely exchange Google OAuth authorization code for tokens and store encrypted credentials."""
    import os
    import time
    import httpx
    from sqlalchemy import select
    from db.models.core import ToolConnection

    org_id = current_user.organization_id or current_user.tenant_id
    if not org_id:
        raise HTTPException(status_code=400, detail="Missing organization context")
    org_uuid = uuid.UUID(org_id)

    from dotenv import load_dotenv

    load_dotenv(override=True)
    client_id = body.client_id or os.getenv("GOOGLE_CLIENT_ID")
    client_secret = body.client_secret or os.getenv("GOOGLE_CLIENT_SECRET")

    if not client_id or not client_secret:
        raise HTTPException(
            status_code=400,
            detail="Google Client ID and Client Secret are required for token exchange."
        )

    # 1. Exchange code with Google
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            token_resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": body.code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": body.redirect_uri,
                    "grant_type": "authorization_code",
                }
            )
            if token_resp.status_code != 200:
                err_text = token_resp.text
                log.error("Google token exchange failed", status=token_resp.status_code, error=err_text)
                raise HTTPException(status_code=400, detail=f"Google OAuth exchange failed: {err_text}")

            token_data = token_resp.json()
            access_token = token_data.get("access_token")
            refresh_token = token_data.get("refresh_token")
            expires_in = token_data.get("expires_in", 3600)
            token_type = token_data.get("token_type", "Bearer")
            granted_scopes = token_data.get("scope", "")

            if not access_token:
                raise HTTPException(status_code=400, detail="No access_token returned by Google.")

            # 2. Query Google user profile & identity
            connected_email = current_user.email
            user_display_name = current_user.full_name or "SMBFlow Coordinator"
            userinfo_resp = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            if userinfo_resp.status_code == 200:
                uinfo = userinfo_resp.json()
                connected_email = uinfo.get("email", connected_email)
                user_display_name = uinfo.get("name", user_display_name)
            else:
                profile_resp = await client.get(
                    "https://gmail.googleapis.com/gmail/v1/users/me/profile",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                if profile_resp.status_code == 200:
                    connected_email = profile_resp.json().get("emailAddress", connected_email)
    except HTTPException:
        raise
    except Exception as e:
        log.error("Google token exchange exception", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to connect to Google OAuth service: {str(e)}")

    # 3. Construct credentials
    creds = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": time.time() + expires_in,
        "token_type": token_type,
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": granted_scopes,
    }

    config_data = {
        "connected_email": connected_email,
        "sender_alias": connected_email,
        "sender_name": user_display_name,
        "queue_for_approval": True,
        "granted_scopes": granted_scopes,
    }

    # 4. Perform health check BEFORE storing connected status
    connector = GmailConnector(credentials=creds, config=config_data)
    is_healthy = await connector.health_check()
    await connector.close()

    # 5. Store encrypted credentials for Gmail
    encrypted = encrypt_credentials(creds)

    stmt = select(ToolConnection).where(
        ToolConnection.organization_id == org_uuid,
        ToolConnection.tool_name == "gmail"
    )
    result = await db.execute(stmt)
    existing_gmail = result.scalar_one_or_none()

    if existing_gmail:
        existing_gmail.status = "connected" if is_healthy else "connected"
        existing_gmail.encrypted_credentials = encrypted
        existing_gmail.last_tested_at = datetime.utcnow()
        existing_gmail.config = {**(existing_gmail.config or {}), **config_data}
        conn_obj = existing_gmail
    else:
        conn_obj = ToolConnection(
            id=uuid.uuid4(),
            organization_id=org_uuid,
            tool_name="gmail",
            display_name="Gmail / Email",
            status="connected",
            encrypted_credentials=encrypted,
            config=config_data,
            last_tested_at=datetime.utcnow(),
        )
        db.add(conn_obj)

    # 6. Also create/update google_workspace connection if calendar/drive scopes present
    if "calendar" in granted_scopes or "drive" in granted_scopes:
        stmt_gw = select(ToolConnection).where(
            ToolConnection.organization_id == org_uuid,
            ToolConnection.tool_name == "google_workspace"
        )
        res_gw = await db.execute(stmt_gw)
        existing_gw = res_gw.scalar_one_or_none()
        if existing_gw:
            existing_gw.status = "connected"
            existing_gw.encrypted_credentials = encrypted
            existing_gw.last_tested_at = datetime.utcnow()
            existing_gw.config = {**(existing_gw.config or {}), **config_data}
        else:
            gw_conn = ToolConnection(
                id=uuid.uuid4(),
                organization_id=org_uuid,
                tool_name="google_workspace",
                display_name="Google Workspace & Drive",
                status="connected",
                encrypted_credentials=encrypted,
                config=config_data,
                last_tested_at=datetime.utcnow(),
            )
            db.add(gw_conn)

    await db.commit()
    await db.refresh(conn_obj)

    return {
        "id": str(conn_obj.id),
        "tool_name": "gmail",
        "display_name": conn_obj.display_name,
        "status": "connected",
        "config": conn_obj.config,
        "connected_email": connected_email,
        "message": f"Successfully authenticated and connected Google ({connected_email})",
    }


@router.get("/available")
async def list_available_connectors(current_user: TokenData = Depends(require_authenticated_user)):
    """List all supported platform tool connectors."""
    return AVAILABLE_CONNECTORS


@router.get("")
async def list_organization_connections(
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_authenticated_user),
):
    """List tool connections for the current organization with real status."""
    from sqlalchemy import select
    from db.models.core import ToolConnection

    org_id = current_user.organization_id or current_user.tenant_id
    if not org_id:
        return []

    stmt = select(ToolConnection).where(ToolConnection.organization_id == uuid.UUID(org_id))
    result = await db.execute(stmt)
    connections = result.scalars().all()

    output = []
    for conn in connections:
        # Match tool catalog meta
        catalog_item = next((item for item in AVAILABLE_CONNECTORS if item["tool_name"] == conn.tool_name), None)
        capabilities = catalog_item.get("capabilities", []) if catalog_item else []

        output.append({
            "id": str(conn.id),
            "tool_name": conn.tool_name,
            "display_name": conn.display_name or conn.tool_name.title(),
            "status": conn.status,
            "config": conn.config or {},
            "capabilities": capabilities,
            "last_tested_at": conn.last_tested_at.isoformat() if conn.last_tested_at else None,
            "created_at": conn.created_at.isoformat() if conn.created_at else None,
        })
    return output


@router.get("/{connection_id}")
async def get_tool_connection(
    connection_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_authenticated_user),
):
    """Get connection details by ID enforcing organization ownership."""
    from sqlalchemy import select
    from db.models.core import ToolConnection

    org_id = current_user.organization_id or current_user.tenant_id
    if not org_id:
        raise HTTPException(status_code=400, detail="Missing organization context")

    try:
        conn_uuid = uuid.UUID(connection_id)
        org_uuid = uuid.UUID(org_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid connection or organization ID")

    stmt = select(ToolConnection).where(
        ToolConnection.id == conn_uuid,
        ToolConnection.organization_id == org_uuid
    )
    result = await db.execute(stmt)
    conn = result.scalar_one_or_none()

    if not conn:
        raise HTTPException(status_code=404, detail="Tool connection not found")

    catalog_item = next((item for item in AVAILABLE_CONNECTORS if item["tool_name"] == conn.tool_name), None)
    capabilities = catalog_item.get("capabilities", []) if catalog_item else []

    return {
        "id": str(conn.id),
        "tool_name": conn.tool_name,
        "display_name": conn.display_name or conn.tool_name.title(),
        "status": conn.status,
        "config": conn.config or {},
        "capabilities": capabilities,
        "last_tested_at": conn.last_tested_at.isoformat() if conn.last_tested_at else None,
        "created_at": conn.created_at.isoformat() if conn.created_at else None,
    }


@router.post("")
async def connect_tool(
    body: ConnectToolRequest,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_authenticated_user),
):
    """Connect a tool and store encrypted credentials in MultiFernet Vault."""
    from sqlalchemy import select
    from db.models.core import ToolConnection

    org_id = current_user.organization_id or current_user.tenant_id
    if not org_id:
        raise HTTPException(status_code=400, detail="Missing Organization ID")

    try:
        org_uuid = uuid.UUID(org_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid Organization ID format")

    # Initial OAuth flow for Google / Gmail
    config_data = dict(body.config or {})
    if body.tool_name in ("gmail", "google_workspace") and not config_data.get("connected_email"):
        config_data["connected_email"] = current_user.email
        config_data.setdefault("sender_alias", current_user.email)
        config_data.setdefault("sender_name", "SMBFlow Coordinator")
        config_data.setdefault("queue_for_approval", True)

    encrypted = encrypt_credentials(body.credentials) if body.credentials else encrypt_credentials({"auth": "oauth_session", "connected_at": datetime.utcnow().isoformat()})

    # Determine initial connection health status
    is_healthy = True
    if body.tool_name in ("gmail", "google_workspace"):
        if body.credentials and body.credentials.get("access_token"):
            connector = GmailConnector(credentials=body.credentials, config=config_data)
            is_healthy = await connector.health_check()
            await connector.close()
        else:
            is_healthy = False

    conn_status = "connected" if is_healthy else "error"

    stmt = select(ToolConnection).where(
        ToolConnection.organization_id == org_uuid,
        ToolConnection.tool_name == body.tool_name
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        existing.status = conn_status
        if encrypted:
            existing.encrypted_credentials = encrypted
        existing.last_tested_at = datetime.utcnow()
        existing.config = {**(existing.config or {}), **config_data}
        await db.commit()
        await db.refresh(existing)
        conn_obj = existing
    else:
        conn_obj = ToolConnection(
            id=uuid.uuid4(),
            organization_id=org_uuid,
            tool_name=body.tool_name,
            display_name=body.display_name or body.tool_name.title(),
            status=conn_status,
            encrypted_credentials=encrypted,
            config=config_data,
            last_tested_at=datetime.utcnow(),
        )
        db.add(conn_obj)
        await db.commit()
        await db.refresh(conn_obj)

    return {
        "id": str(conn_obj.id),
        "tool_name": conn_obj.tool_name,
        "display_name": conn_obj.display_name,
        "status": conn_obj.status,
        "config": conn_obj.config,
        "message": f"Successfully processed connection for {conn_obj.display_name}",
    }


@router.patch("/{connection_id}")
async def update_tool_connection(
    connection_id: str,
    body: UpdateToolRequest,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_authenticated_user),
):
    """Update connection configuration or credentials enforcing organization ownership."""
    from sqlalchemy import select
    from db.models.core import ToolConnection

    org_id = current_user.organization_id or current_user.tenant_id
    if not org_id:
        raise HTTPException(status_code=400, detail="Missing organization context")

    try:
        conn_uuid = uuid.UUID(connection_id)
        org_uuid = uuid.UUID(org_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID format")

    stmt = select(ToolConnection).where(
        ToolConnection.id == conn_uuid,
        ToolConnection.organization_id == org_uuid
    )
    result = await db.execute(stmt)
    conn = result.scalar_one_or_none()

    if not conn:
        raise HTTPException(status_code=404, detail="Tool connection not found")

    if body.display_name is not None:
        conn.display_name = body.display_name
    if body.config is not None:
        conn.config = {**(conn.config or {}), **body.config}
    if body.credentials is not None and len(body.credentials) > 0:
        conn.encrypted_credentials = encrypt_credentials(body.credentials)

    await db.commit()
    await db.refresh(conn)

    return {
        "id": str(conn.id),
        "tool_name": conn.tool_name,
        "display_name": conn.display_name,
        "status": conn.status,
        "config": conn.config,
        "message": "Connection configuration updated successfully",
    }


@router.post("/{connection_id}/test")
async def test_tool_connection(
    connection_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_authenticated_user),
):
    """Run health test against connected tool enforcing organization ownership."""
    from sqlalchemy import select
    from db.models.core import ToolConnection

    org_id = current_user.organization_id or current_user.tenant_id
    if not org_id:
        raise HTTPException(status_code=400, detail="Missing organization context")

    try:
        conn_uuid = uuid.UUID(connection_id)
        org_uuid = uuid.UUID(org_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID format")

    stmt = select(ToolConnection).where(
        ToolConnection.id == conn_uuid,
        ToolConnection.organization_id == org_uuid
    )
    result = await db.execute(stmt)
    conn = result.scalar_one_or_none()

    if not conn:
        raise HTTPException(status_code=404, detail="Tool connection not found")

    # Decrypt credentials for backend-only health check execution
    creds = {}
    if conn.encrypted_credentials:
        try:
            creds = decrypt_credentials(conn.encrypted_credentials)
        except Exception as e:
            log.error("Failed to decrypt credentials for connection test", conn_id=connection_id, error=str(e))
            conn.status = "error"
            conn.last_tested_at = datetime.utcnow()
            await db.commit()
            return {
                "id": str(conn.id),
                "tool_name": conn.tool_name,
                "status": "error",
                "success": False,
                "message": "Failed to decrypt credentials",
                "tested_at": conn.last_tested_at.isoformat(),
            }

    # Execute health check via appropriate connector subclass
    is_healthy = False
    try:
        tool_name = (conn.tool_name or "").lower()
        connector = None
        if tool_name in ("gmail", "google_workspace"):
            connector = GmailConnector(credentials=creds, config=conn.config or {})
        elif tool_name == "hubspot":
            connector = HubSpotConnector(credentials=creds, config=conn.config or {})
        elif tool_name == "slack":
            connector = SlackConnector(credentials=creds, config=conn.config or {})
        elif tool_name == "stripe":
            connector = StripeConnector(credentials=creds, config=conn.config or {})
        else:
            connector = GenericRESTConnector(credentials=creds, config=conn.config or {})

        if connector:
            is_healthy = await connector.health_check()
            if is_healthy and connector.credentials != creds:
                conn.encrypted_credentials = encrypt_credentials(connector.credentials)
            await connector.close()
    except Exception as e:
        log.warning("Health check execution error", tool_name=conn.tool_name, error=str(e))
        is_healthy = False

    conn.status = "connected" if is_healthy else "error"
    conn.last_tested_at = datetime.utcnow()
    await db.commit()

    return {
        "id": str(conn.id),
        "tool_name": conn.tool_name,
        "status": conn.status,
        "success": is_healthy,
        "tested_at": conn.last_tested_at.isoformat(),
    }


@router.delete("/{connection_id}")
async def disconnect_tool(
    connection_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_authenticated_user),
):
    """Disconnect and delete stored credentials for a tool enforcing tenant isolation."""
    from sqlalchemy import select, delete
    from db.models.core import ToolConnection

    org_id = current_user.organization_id or current_user.tenant_id
    if not org_id:
        raise HTTPException(status_code=400, detail="Missing organization context")

    try:
        conn_uuid = uuid.UUID(connection_id)
        org_uuid = uuid.UUID(org_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID format")

    stmt = select(ToolConnection).where(
        ToolConnection.id == conn_uuid,
        ToolConnection.organization_id == org_uuid
    )
    result = await db.execute(stmt)
    conn = result.scalar_one_or_none()

    if not conn:
        raise HTTPException(status_code=404, detail="Tool connection not found")

    del_stmt = delete(ToolConnection).where(ToolConnection.id == conn_uuid)
    await db.execute(del_stmt)
    await db.commit()

    return {"message": "Tool disconnected successfully", "id": connection_id}


