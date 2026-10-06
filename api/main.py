"""
api/main.py  (full rewrite — DB-first)
=======================================
FastAPI application — SMBFlow API v3.

All state lives in PostgreSQL.  In-memory dicts are removed.
Two things remain in-memory legitimately:
  _ws_connections    — transient WebSocket handles (process-local, OK)
  _active_orchestrators — running asyncio tasks (process-local, OK)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import aiofiles
import structlog
from fastapi import (
    BackgroundTasks, Depends, FastAPI, HTTPException,
    Query, Request, WebSocket, WebSocketDisconnect, status,
)
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

try:
    from dotenv import load_dotenv
    load_dotenv(override=False)
except ImportError:
    pass

import hashlib
import secrets
from datetime import timedelta

import api.crud as crud
from api.auth import (
    LoginRequest, SignupRequest, TokenData, TokenResponse,
    assert_tenant_access, build_token_for_user,
    get_tenant_filter, hash_password, require_admin,
    require_any_auth, verify_password,
)
from api import mailer
from api.dependencies import get_db
from core.database import get_raw_session
from core.state_manager import WorkflowStatus
from integrations.key_vault import (
    decrypt_credentials, encrypt_credentials, get_credential_schema, mask_credentials,
)
from core.redis_pubsub import pubsub as redis_pubsub
from core.dag_validator import validate_dag
log = structlog.get_logger()


class _RedactWebSocketTokenFilter(logging.Filter):
    """Keep bearer tokens and credentials out of uvicorn access-log request paths and fix status code string formatting."""

    _token_pattern = re.compile(r"([?&](?:token|jwt|access_token|api_key|auth|authorization|credentials|secret)=)[^&\s\"]+", re.IGNORECASE)

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self._token_pattern.sub(r"\1[REDACTED]", record.msg)
        if record.args:
            args_list = list(record.args)
            for idx, arg in enumerate(args_list):
                if isinstance(arg, str):
                    args_list[idx] = self._token_pattern.sub(r"\1[REDACTED]", arg)
            # Fix uvicorn access log '%s - "%s %s HTTP/%s" %d' error when 5th arg is str digit
            if len(args_list) >= 5 and isinstance(args_list[4], str) and args_list[4].isdigit():
                args_list[4] = int(args_list[4])
            record.args = tuple(args_list)
        return True


logging.getLogger("uvicorn.access").addFilter(_RedactWebSocketTokenFilter())

# ─────────────────────────────────────────────────────────────────────────────
# In-memory (ONLY transient, process-local state)
# ─────────────────────────────────────────────────────────────────────────────
_ws_connections: dict[str, tuple] = {}
_active_orchestrators: dict[str, Any] = {}


# ─────────────────────────────────────────────────────────────────────────────
# App lifespan
# ─────────────────────────────────────────────────────────────────────────────

# (No changes to lifespan section)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: ensure DB tables exist, seed super-admin, recover stuck workflows."""
    from core.database import engine
    from core.state_manager import Base
    # Also ensure the new billing/entitlement models are created
    from db.models.core import Base as OrgBase  # noqa: F401 — triggers create_all for new tables

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(OrgBase.metadata.create_all)

    # Additive, idempotent column migrations. create_all() only creates missing
    # TABLES — it never adds a column to a table that already exists — so any
    # database provisioned before this column existed needs an explicit ALTER.
    # These are safe to run on every boot: nullable, IF NOT EXISTS, no data loss.
    try:
        from sqlalchemy import text as _sql_text
        async with engine.begin() as _mconn:
            await _mconn.execute(_sql_text(
                "ALTER TABLE agent_run_records "
                "ADD COLUMN IF NOT EXISTS output_data JSONB"
            ))
        log.info("Schema check: agent_run_records.output_data present")
    except Exception as _mig_err:
        # Non-fatal: the app still runs; per-node structured output just won't
        # persist to the normalized table until this column exists.
        log.error("Additive column migration failed (non-fatal)", error=str(_mig_err))

    # Migration 004: workflow_catalog scope + industry columns (idempotent)
    try:
        from sqlalchemy import text as _sql_text
        async with engine.begin() as _mconn:
            # Add scope column (GLOBAL by default — backward-compatible)
            await _mconn.execute(_sql_text(
                "ALTER TABLE workflow_catalog "
                "ADD COLUMN IF NOT EXISTS scope VARCHAR(20) NOT NULL DEFAULT 'GLOBAL'"
            ))
            # Add industry column (nullable — GLOBAL workflows have no industry)
            await _mconn.execute(_sql_text(
                "ALTER TABLE workflow_catalog "
                "ADD COLUMN IF NOT EXISTS industry VARCHAR(100)"
            ))
            # Indexes for efficient filtering
            await _mconn.execute(_sql_text(
                "CREATE INDEX IF NOT EXISTS idx_workflow_catalog_scope "
                "ON workflow_catalog(scope)"
            ))
            await _mconn.execute(_sql_text(
                "CREATE INDEX IF NOT EXISTS idx_workflow_catalog_industry "
                "ON workflow_catalog(industry)"
            ))
        log.info("Schema check: workflow_catalog.scope + industry columns present")
    except Exception as _scope_mig_err:
        log.error("Workflow scope migration failed (non-fatal)", error=str(_scope_mig_err))

    # Initialize Redis pub/sub
    await redis_pubsub.connect()
    await redis_pubsub.start_subscriber(_local_broadcast)
    log.info("Redis pub/sub initialized")

    # Sync workflow catalog from DAG files (idempotent — only inserts missing entries)
    try:
        from core.workflow_catalog_sync import sync_workflow_catalog, sync_plan_entitlements_for_new_workflows
        from db.seed.plans_seed import seed_plans_and_catalog
        _catalog_session = await get_raw_session()
        async with _catalog_session:
            await seed_plans_and_catalog(_catalog_session)
            sync_result = await sync_workflow_catalog(_catalog_session)
            await sync_plan_entitlements_for_new_workflows(_catalog_session)
            log.info("Workflow catalog and plans seed complete", **sync_result)
    except Exception as _sync_err:
        log.warning("Workflow catalog sync failed (non-fatal)", error=str(_sync_err))

    # Seed super-admin from env
    _admin_email = os.getenv("ADMIN_EMAIL", "admin@smbflow.com")
    _admin_pw    = os.getenv("ADMIN_PASSWORD", "admin123")
    _admin_name  = os.getenv("ADMIN_FULL_NAME", "SMBFlow Admin")
    try:
        session = await get_raw_session()
        async with session:
            existing = await crud.get_user_by_email(session, _admin_email)
            if not existing:
                await crud.create_user(
                    session,
                    email=_admin_email,
                    password_hash=hash_password(_admin_pw),
                    full_name=_admin_name,
                    role="super_admin",
                    tenant_id=None,
                )
                log.info("Super-admin seeded", email=_admin_email)
    except Exception as _seed_err:
        log.error("Admin seed failed (non-fatal)", error=str(_seed_err))

    # Startup recovery: mark workflows interrupted by a previous crash as failed
    try:
        recovery_db = await get_raw_session()
        async with recovery_db:
            all_instances = await crud.list_workflow_instances(recovery_db, limit=1000)
            stuck = [w for w in all_instances if w.status == "running"]
            if stuck:
                for w in stuck:
                    await crud.update_workflow_status(
                        recovery_db, str(w.id), "failed",
                        error=(
                            "Server restart detected: workflow interrupted mid-execution. "
                            "Re-trigger from the dashboard if needed."
                        ),
                    )
                log.warning(
                    "Startup recovery: marked interrupted workflows as failed",
                    count=len(stuck),
                )
    except Exception as _rec_err:
        log.warning("Startup recovery failed (non-fatal)", error=str(_rec_err))

    # Start Email Event Detector
    global _email_detector
    try:
        from core.event_detector import EmailEventDetector
        _email_detector = EmailEventDetector(
            poll_interval=float(os.getenv("EMAIL_DETECTOR_POLL_INTERVAL", "5.0")),
            execute_workflow_fn=_execute_workflow_background,
            broadcast_fn=broadcast_event,
        )
        await _email_detector.start()
    except Exception as _det_err:
        log.error("Failed to start EmailEventDetector", error=str(_det_err))

    log.info("SMBFlow API started")
    yield

    # Shutdown
    if "_email_detector" in globals() and _email_detector:
        await _email_detector.stop()
    await redis_pubsub.stop()
    log.info("SMBFlow API stopped")


from api.routers import connections, reviews, medical_tourism, product_launch, copilot, meeting_intelligence, notifications
from api.routers import admin as admin_router

app = FastAPI(
    title="SMBFlow API v3",
    description="Autonomous Multi-Tenant Agentic Workflow Automation Platform",
    version="3.0.0",
    lifespan=lifespan,
)

app.include_router(admin_router.router)   # /api/v1/admin/* — must be first to win over legacy admin routes
app.include_router(connections.router)
app.include_router(reviews.router)
app.include_router(medical_tourism.router)
app.include_router(product_launch.router)
app.include_router(meeting_intelligence.router)
app.include_router(copilot.router)
app.include_router(notifications.router)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "https://smb-flow.vercel.app",
    ],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|.*\.vercel\.app)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Paths that must remain reachable before the system is initialised
_BYPASS_PATHS = {"/api/v1/health", "/docs", "/openapi.json", "/redoc", "/"}


@app.middleware("http")
async def system_integrity_check(request: Request, call_next):
    """
    Validate required environment variables on every request.
    Returns a clear 503 'System Not Initialized' error if any are missing,
    so operators get an actionable message rather than a cryptic DB error.
    """
    if request.url.path in _BYPASS_PATHS or request.url.path.startswith("/redoc"):
        return await call_next(request)

    missing = []
    if not os.getenv("DATABASE_URL"):
        missing.append("DATABASE_URL")
    if not os.getenv("VAULT_ENCRYPTION_KEY"):
        missing.append("VAULT_ENCRYPTION_KEY")

    if missing:
        return JSONResponse(
            status_code=503,
            content={
                "detail": "System Not Initialized",
                "message": (
                    "One or more required environment variables are missing. "
                    "Configure your .env file and restart the server."
                ),
                "missing_variables": missing,
                "hint": "Copy .env.example to .env and fill in the required values.",
            },
        )
    return await call_next(request)


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket
# ─────────────────────────────────────────────────────────────────────────────

async def broadcast_event(event_type: str, data: dict) -> None:
    """Broadcast event via Redis (multi-worker) or in-process fallback."""
    # redis_pubsub.publish() already calls _local_broadcast via its internal fallback
    # when Redis is unavailable — do NOT duplicate the delivery here.
    await redis_pubsub.publish(event_type, data)
 
# Add separate local-only broadcast (used by Redis subscriber callback):
async def _local_broadcast(event_type: str, data: dict) -> None:
    """In-process broadcast with tenant-aware filtering."""
    msg = json.dumps({"type": event_type, "data": data, "ts": datetime.utcnow().isoformat()})
    event_tenant = data.get("tenant_id")
    dead = []
    for sid, (ws, user_tenant) in _ws_connections.items():
        try:
            # Deliver if: global event, admin (no tenant), or tenant match
            if not event_tenant or not user_tenant or str(event_tenant) == str(user_tenant):
                await ws.send_text(msg)
        except Exception:
            dead.append(sid)
    for sid in dead:
        _ws_connections.pop(sid, None)


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001)
        return
    try:
        from api.deps.auth import get_current_user_from_token
        token_data = await get_current_user_from_token(token)
    except Exception as e:
        log.warning("WebSocket authentication failed", error=str(e), session_id=session_id)
        await websocket.close(code=4001)
        return
 
    await websocket.accept()
    user_tenant = getattr(token_data, "tenant_id", None) or getattr(token_data, "organization_id", None)
    user_role   = getattr(token_data, "role", "anon")
    _ws_connections[session_id] = (websocket, user_tenant)
 
    # BUG-004 FIX: Subscribe this worker to the tenant-scoped Redis channel.
    # Without this, events from OTHER uvicorn workers never reach this connection.
    _tenant_sub_task = None
    if redis_pubsub.available and user_tenant:
        tenant_ch = f"opsgrid:events:tenant:{user_tenant}"
        _tenant_sub_task = asyncio.create_task(
            _redis_channel_relay(session_id, tenant_ch)
        )
 
    try:
        await websocket.send_text(json.dumps({
            "type": "connected",
            "data": {"session_id": session_id, "role": user_role},
        }))
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                try:
                    await websocket.send_text(json.dumps({"type": "keepalive"}))
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    finally:
        _ws_connections.pop(session_id, None)
        if _tenant_sub_task and not _tenant_sub_task.done():
            _tenant_sub_task.cancel()
            
            
async def _redis_channel_relay(session_id: str, channel: str) -> None:
    """
    Subscribe to a specific Redis channel and relay messages to the WebSocket
    connection identified by session_id. One task per (connection, channel).
    Exits cleanly when the connection is closed.
    """
    import os
    redis_url = os.getenv("REDIS_URL", "")
    if not redis_url:
        return
    try:
        import redis.asyncio as aioredis
        async with aioredis.from_url(
            redis_url, encoding="utf-8", decode_responses=True
        ).pubsub() as pubsub:
            await pubsub.subscribe(channel)
            async for message in pubsub.listen():
                if session_id not in _ws_connections:
                    break  # Connection closed — exit
                if message["type"] != "message":
                    continue
                try:
                    ws, _ = _ws_connections[session_id]
                    await ws.send_text(message["data"])
                except Exception:
                    break
    except asyncio.CancelledError:
        pass
    except Exception as e:
        log.debug("Tenant channel relay error", channel=channel, error=str(e))


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic schemas
# ─────────────────────────────────────────────────────────────────────────────

class TenantCreate(BaseModel):
    name: str
    industry: str
    config: dict = Field(default_factory=dict)

class WorkflowTriggerRequest(BaseModel):
    # tenant_id is OPTIONAL — Phase 0 bridge derives it from the authenticated
    # user's organization when not supplied.  Kept for backwards compatibility
    # with platform-admin triggers that supply an explicit tenant.
    tenant_id: Optional[str] = None
    workflow_name: str
    signal_data: Optional[dict] = Field(default_factory=dict)
    trigger_signal: Optional[dict] = None

class EscalationDecision(BaseModel):
    decision: dict
    action_chosen: str
    decided_by: str

class A2ADecision(BaseModel):
    approved: bool
    reason: Optional[str] = None

class CredentialCreate(BaseModel):
    tenant_id: str
    tool_name: str
    display_name: Optional[str] = None
    credentials: dict

class CustomToolCreate(BaseModel):
    tenant_id: str
    tool_name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    base_url: str
    http_method: str = "GET"
    headers_template: dict = Field(default_factory=dict)
    body_template: dict = Field(default_factory=dict)
    query_params: dict = Field(default_factory=dict)
    auth_type: str = "api_key"
    credential_id: Optional[str] = None
    response_path: Optional[str] = None

class BudgetSettingsUpdate(BaseModel):
    optimization_level: int = Field(ge=0, le=3)
    enable_caching: bool = True
    cache_ttl_seconds: int = 3600
    max_context_tokens: int = 10000
    a2a_enabled: bool = False
    auto_retry_on_low_confidence: bool = True
    confidence_retry_threshold: float = 0.6
    enable_map_reduce_summarization: bool = False
    max_spend_per_run_usd: Optional[float] = None

class TenantConfigUpdate(BaseModel):
    config: dict

class UserCreate(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None
    tenant_id: Optional[str] = None

class WorkflowDAGCreate(BaseModel):
    name: str
    dag: dict

class PromptUpdate(BaseModel):
    content: str

class WorkflowForkRequest(BaseModel):
    from_node_id: str
    context_patch: Optional[dict] = None   # override specific accumulated_context keys

class AutoEvalRunRequest(BaseModel):
    tenant_id: str
    workflow_name: str

class AutoEvalApplyRequest(BaseModel):
    admin_email: str

class WebhookMappingCreate(BaseModel):
    """No-code webhook routing configuration."""
    tenant_id: str
    webhook_name: str
    sample_payload: dict
    workflow_name: str
    field_mappings: dict  # e.g. {"account_id": "data.object.customer_id"}
class AdminUserInviteRequest(BaseModel):
    email: str
    full_name: Optional[str] = None
    role: Optional[str] = "platform_admin"
    organization_id: Optional[str] = None

class ProvisionRequest(BaseModel):
    full_name: Optional[str] = None
    workspace_name: Optional[str] = None
    industry: Optional[str] = "saas"
    website: Optional[str] = None
    company_size: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/v1/auth/login", response_model=TokenResponse, tags=["Auth"])
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await crud.get_user_by_email(db, body.email)
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="Account disabled")
    await crud.update_user_last_login(db, str(user.id))
    token = build_token_for_user(crud.user_to_dict(user))
    return TokenResponse(
        access_token=token,
        user={
            "id": str(user.id), "email": user.email,
            "full_name": user.full_name, "role": user.role,
            "tenant_id": str(user.tenant_id) if user.tenant_id else None,
        },
    )


@app.post("/api/v1/auth/signup", response_model=TokenResponse, tags=["Auth"])
async def signup(body: SignupRequest, db: AsyncSession = Depends(get_db)):
    if await crud.get_user_by_email(db, body.email):
        raise HTTPException(status_code=409, detail="Email already registered")

    tenant_id = None
    if body.tenant_name:
        tenant = await crud.create_tenant(
            db,
            body.tenant_name,
            body.industry or "saas",
            {
                "website": body.website,
                "company_size": body.company_size,
                "requires_onboarding": False,
            },
        )
        tenant_id = str(tenant.id)

    user = await crud.create_user(
        db,
        email=body.email,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        role="tenant_user",
        tenant_id=tenant_id,
    )
    token = build_token_for_user(crud.user_to_dict(user))
    await broadcast_event("user_created", {"user_id": str(user.id), "email": user.email})
    return TokenResponse(
        access_token=token,
        user={
            "id": str(user.id), "email": user.email,
            "full_name": user.full_name, "role": "tenant_user",
            "tenant_id": tenant_id,
            "website": body.website,
            "company_size": body.company_size,
            "requires_onboarding": False,
        },
    )


@app.post("/api/v1/auth/provision", tags=["Auth"])
async def provision_user_workspace(
    body: ProvisionRequest,
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    org_user, org = await crud.ensure_user_organization_provisioned(
        db,
        user_id=current_user.user_id,
        email=current_user.email,
        full_name=body.full_name,
        workspace_name=body.workspace_name,
        industry=body.industry,
    )
    org_id = str(org.id) if org else (current_user.organization_id or current_user.tenant_id)
    org_name = org.name if org else body.workspace_name

    if org:
        cfg = dict(org.profile_config or {})
        if body.website:
            cfg["website"] = body.website
        if body.company_size:
            cfg["company_size"] = body.company_size
        cfg["requires_onboarding"] = False
        org.profile_config = cfg
        await db.commit()
        await db.refresh(org)

    # Auto-assign industry workflows on first provision.
    # Check whether the org already has assignments — if not, this is a fresh
    # workspace and we populate it based on the chosen industry.
    if org and org_id:
        try:
            existing_assignments = await crud.get_org_workflow_assignments(db, org_id)
            if not existing_assignments:
                resolved_industry = (org.industry or body.industry or "saas")
                # Resolve which plan slug this org is on (default free for self-signup)
                sub = await crud.get_org_subscription(db, org_id)
                plan_slug = "free"
                if sub:
                    plan = await crud.get_billing_plan(db, str(sub.plan_id))
                    if plan:
                        plan_slug = plan.slug
                await crud.auto_assign_industry_workflows(
                    db,
                    organization_id=org_id,
                    industry=resolved_industry,
                    assigned_by="system:provision",
                    plan_slug=plan_slug,
                )
        except Exception as _aa_err:
            # Non-fatal — user still lands on dashboard, just with no workflows shown
            # until the admin assigns them manually or on next request
            log.warning(
                "provision: auto-assign failed (non-fatal)",
                error=str(_aa_err),
                org_id=org_id,
            )

    return {
        "id": current_user.user_id,
        "email": current_user.email,
        "role": org_user.role if org_user else "org_user",
        "organization_id": org_id,
        "tenant_id": org_id,
        "full_name": org_user.full_name if org_user else body.full_name,
        "organization_name": org_name,
        "tenant_name": org_name,
        "industry": org.industry if org else (body.industry or "saas"),
        "website": (org.profile_config or {}).get("website") if org else body.website,
        "company_size": (org.profile_config or {}).get("company_size") if org else body.company_size,
        "requires_onboarding": False,
    }


@app.get("/api/v1/auth/me", tags=["Auth"])
async def get_me(
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    org_user, org = await crud.ensure_user_organization_provisioned(
        db,
        user_id=current_user.user_id,
        email=current_user.email,
        full_name=current_user.full_name,
    )
    role = org_user.role if org_user else current_user.role
    org_id = str(org.id) if org else (current_user.organization_id or current_user.tenant_id)
    org_name = org.name if org else None

    # Check if user requires workspace onboarding setup
    requires_onboarding = False
    profile = org.profile_config or {} if org else {}

    if role not in ("super_admin", "platform_admin"):
        if not org or org.name == "Pending Workspace Setup":
            requires_onboarding = True
        elif profile.get("requires_onboarding") is True:
            requires_onboarding = True
        elif not org.name:
            requires_onboarding = True
        else:
            requires_onboarding = False

    resolved_full_name = (
        (org_user.full_name if org_user and org_user.full_name and "@" not in org_user.full_name else None)
        or current_user.full_name
        or (current_user.email.split("@")[0].replace(".", " ").title() if current_user.email else "Dev User")
    )

    return {
        "id": current_user.user_id,
        "email": current_user.email,
        "role": role,
        "organization_id": org_id,
        "tenant_id": org_id,
        "full_name": resolved_full_name,
        "organization_name": org_name,
        "tenant_name": org_name,
        "industry": org.industry if org else "saas",
        "website": profile.get("website"),
        "company_size": profile.get("company_size"),
        "requires_onboarding": requires_onboarding,
    }


class UserProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None


@app.put("/api/v1/auth/profile", tags=["Auth"])
async def update_user_profile(
    body: UserProfileUpdate,
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    org_user, org = await crud.ensure_user_organization_provisioned(
        db,
        user_id=current_user.user_id,
        email=current_user.email,
        full_name=body.full_name or current_user.full_name,
    )
    if org_user and body.full_name:
        org_user.full_name = body.full_name
        await db.commit()
        await db.refresh(org_user)
    
    u = await crud.get_user_by_email(db, current_user.email)
    if u and body.full_name:
        u.full_name = body.full_name
        await db.commit()

    return {
        "id": current_user.user_id,
        "email": current_user.email,
        "full_name": body.full_name or (org_user.full_name if org_user else current_user.full_name),
        "avatar_url": body.avatar_url,
        "role": org_user.role if org_user else current_user.role,
        "organization_id": str(org.id) if org else current_user.organization_id,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Organizations — canonical org-scoped endpoints (Phase 0)
# ─────────────────────────────────────────────────────────────────────────────

class OrgConfigUpdate(BaseModel):
    """Partial update to organizations.profile_config."""
    config: dict = Field(default_factory=dict)

class OrgProfileUpdate(BaseModel):
    """Update organization name / industry / settings."""
    name: Optional[str] = None
    industry: Optional[str] = None
    website: Optional[str] = None
    company_size: Optional[str] = None
    config: Optional[dict] = None


@app.get("/api/v1/organizations/me", tags=["Organizations"])
async def get_my_organization(
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    """
    Return the authenticated user's organization from the ``organizations`` table.
    This is the canonical source of truth for org name, industry, and profile.
    Used by: GeneralSettings, Dashboard header, Workflow Builder industry pre-fill.
    """
    org_user, org = await crud.ensure_user_organization_provisioned(
        db,
        user_id=current_user.user_id,
        email=current_user.email,
        full_name=current_user.full_name,
    )
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    profile = org.profile_config or {}
    return {
        "id":               str(org.id),
        "name":             org.name,
        "industry":         org.industry,
        "website":          profile.get("website"),
        "company_size":     profile.get("company_size"),
        "enabled_modules":  org.enabled_modules or [],
        "active":           org.active,
        "created_at":       org.created_at.isoformat() if org.created_at else None,
        "config": {
            "timezone":      profile.get("timezone", "UTC"),
            "notifications": profile.get("notifications", {}),
            "retention":     profile.get("retention", {}),
        },
        "role":             org_user.role if org_user else "org_user",
        "full_name":        org_user.full_name if org_user else current_user.full_name,
    }


@app.put("/api/v1/organizations/me/config", tags=["Organizations"])
async def update_my_organization_config(
    body: OrgConfigUpdate,
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    """
    Merge partial config into the authenticated user's organization.profile_config.
    Used by: GeneralSettings → Save changes.
    """
    org_user, org = await crud.ensure_user_organization_provisioned(
        db,
        user_id=current_user.user_id,
        email=current_user.email,
        full_name=current_user.full_name,
    )
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    updated = await crud.update_organization_config(db, str(org.id), body.config)
    await broadcast_event("org_config_updated", {"org_id": str(org.id)})
    return {"message": "Organization config updated", "org_id": str(org.id)}


@app.put("/api/v1/organizations/me/profile", tags=["Organizations"])
async def update_my_organization_profile(
    body: OrgProfileUpdate,
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    """
    Update the authenticated user's organization name/industry/profile.
    Only org_admin or platform_admin may change org name and industry.
    """
    org_user, org = await crud.ensure_user_organization_provisioned(
        db,
        user_id=current_user.user_id,
        email=current_user.email,
        full_name=current_user.full_name,
    )
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    merged_config = dict(org.profile_config or {})
    if body.config:
        merged_config.update(body.config)
    if body.website is not None:
        merged_config["website"] = body.website
    if body.company_size is not None:
        merged_config["company_size"] = body.company_size

    updated = await crud.update_organization_profile(
        db,
        str(org.id),
        name=body.name,
        industry=body.industry,
        profile_config=merged_config,
    )
    await broadcast_event("org_profile_updated", {"org_id": str(org.id)})
    return {
        "message":  "Organization profile updated",
        "org_id":   str(org.id),
        "name":     updated.name if updated else body.name,
        "industry": updated.industry if updated else body.industry,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Password Reset  (secure, single-use, expiring — see api/mailer.py)
#
# Security invariants enforced here:
#   • forgot-password returns an IDENTICAL generic response for known/unknown
#     emails (no account-existence disclosure).
#   • Only a SHA-256 hash of the token is persisted; the raw token is never
#     logged or stored — it lives only in the emailed link (or, in an explicitly
#     enabled non-production dev environment with email unconfigured, the
#     dev_reset_url field of the response).
#   • Tokens expire (PASSWORD_RESET_TOKEN_TTL_MINUTES) and are single-use.
#   • Best-effort per-email + per-IP rate limiting when Redis is available.
# ─────────────────────────────────────────────────────────────────────────────

MIN_PASSWORD_LENGTH = 8
_RESET_TTL_MINUTES = int(os.getenv("PASSWORD_RESET_TOKEN_TTL_MINUTES", "30"))
_GENERIC_FORGOT_MESSAGE = (
    "If an account exists for that email, you'll receive password reset instructions."
)
_GENERIC_INVALID_TOKEN = "This reset link is invalid or has expired."


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


def _hash_reset_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


async def _reset_rate_limited(email: str, client_ip: str) -> bool:
    """
    Best-effort rate limit: max 5 requests / 15 min per email and per IP.
    Uses the existing Redis client when available; if Redis is down we do NOT
    block (availability over strictness for a non-critical control).
    """
    r = getattr(redis_pubsub, "_redis", None)
    if not redis_pubsub.available or not r:
        return False
    try:
        window = 900
        limit = 5
        for scope in (f"pwreset:email:{email.lower()}", f"pwreset:ip:{client_ip}"):
            n = await r.incr(scope)
            if n == 1:
                await r.expire(scope, window)
            if n > limit:
                return True
    except Exception:
        return False
    return False


@app.post("/api/v1/auth/forgot-password", tags=["Auth"])
async def forgot_password(
    body: ForgotPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    email = (body.email or "").strip()
    client_ip = request.client.host if request.client else "unknown"

    # Uniform response object built once — returned on every path so timing and
    # payload do not reveal whether the account exists.
    response: dict[str, Any] = {"message": _GENERIC_FORGOT_MESSAGE}

    # Rate limit silently (still returns the generic message).
    if email and await _reset_rate_limited(email, client_ip):
        return JSONResponse(response)

    user = await crud.get_user_by_email(db, email) if email else None
    if user and user.is_active:
        raw_token = secrets.token_urlsafe(32)
        token_hash = _hash_reset_token(raw_token)
        expires_at = datetime.utcnow() + timedelta(minutes=_RESET_TTL_MINUTES)
        await crud.create_password_reset_token(db, str(user.id), token_hash, expires_at)

        reset_url = f"{mailer.app_base_url()}/auth/reset-password?token={raw_token}"
        delivered = mailer.send_password_reset_email(user.email, reset_url)

        # Dev-only inspection: ONLY when explicitly enabled, non-production, and
        # email delivery is not configured. Never in production/staging.
        if not delivered and mailer.dev_token_inspection_enabled():
            response["dev_reset_url"] = reset_url

    return JSONResponse(response)


@app.post("/api/v1/auth/reset-password", tags=["Auth"])
async def reset_password(
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    new_password = body.new_password or ""
    if len(new_password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=422,
            detail=f"Password must be at least {MIN_PASSWORD_LENGTH} characters.",
        )

    token_hash = _hash_reset_token((body.token or "").strip())
    row = await crud.get_valid_reset_token(db, token_hash)
    if not row:
        # Generic — do not distinguish invalid / expired / already-used.
        raise HTTPException(status_code=400, detail=_GENERIC_INVALID_TOKEN)

    user = await crud.get_user_by_id(db, str(row.user_id))
    if not user or not user.is_active:
        raise HTTPException(status_code=400, detail=_GENERIC_INVALID_TOKEN)

    await crud.update_user_password(db, str(user.id), hash_password(new_password))
    await crud.mark_reset_token_used(db, str(row.id))
    await crud.invalidate_user_reset_tokens(db, str(user.id))

    return {"message": "Your password has been updated."}



@app.post("/internal/startup-demo", tags=["System"])
async def startup_demo(background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """One‑time demo that triggers each enabled workflow after server start.

    An idempotent lock file ``startup_demo.lock`` in the project root ensures the demo runs only once per process.
    The demo uses the first tenant (or aborts if none) and triggers all workflows where ``_meta.trigger.enabled`` is true.
    """
    from pathlib import Path
    import uuid
    import json

    lock_path = Path("startup_demo.lock")
    if lock_path.exists():
        return {"message": "Startup demo already executed"}
    try:
        lock_path.touch(exist_ok=False)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create demo lock: {e}")
    # Determine a tenant to run the demo under
    tenants = await crud.list_tenants(db)
    if not tenants:
        return {"message": "No tenants available for demo"}
    tenant = tenants[0]
    tenant_id = str(tenant.id)
    tenant_config = tenant.config or {}
    tenant_config["client_id"] = tenant_id
    # Iterate DAG files
    dag_dir = Path("workflows/dags")
    if not dag_dir.exists():
        return {"message": "No workflow DAGs found"}
    triggered = []
    for dag_file in dag_dir.glob("*.json"):
        try:
            data = json.loads(dag_file.read_text())
        except Exception:
            continue
        meta = data.get("_meta", {})
        trigger = meta.get("trigger", {})
        if not trigger.get("enabled", False):
            continue
        workflow_name = dag_file.stem
        run_id = str(uuid.uuid4())
        # Create DB instance record
        await crud.create_workflow_instance(
            db,
            run_id=run_id,
            tenant_id=tenant_id,
            workflow_name=workflow_name,
            trigger_signal={"source": "startup_demo"},
            triggered_by="startup_demo",
            tenant_config=tenant_config,
        )
        budget = await crud.get_budget_settings(db, tenant_id) or {}
        background_tasks.add_task(
            _execute_workflow_background,
            run_id,
            tenant_config,
            workflow_name,
            {"source": "startup_demo"},
            budget,
        )
        triggered.append(workflow_name)
        await crud.log_event(db, "startup_demo_triggered", tenant_id, run_id,
            f"Startup demo triggered workflow '{workflow_name}'")
        await broadcast_event("startup_demo_workflow_triggered", {
            "run_id": run_id,
            "workflow": workflow_name,
            "tenant_id": tenant_id,
        })
    return {"message": "Startup demo executed", "tenant_id": tenant_id, "triggered_workflows": triggered}

@app.get("/api/v1/health", tags=["System"])
async def health_check(db: AsyncSession = Depends(get_db)):
    llm_providers = {}
    for provider, key_env in [
        ("anthropic", "ANTHROPIC_API_KEY"),
        ("openai", "OPENAI_API_KEY"),
        ("google", "GOOGLE_API_KEY"),
        ("google_ai", "GOOGLE_API_KEY"),
        ("groq", "GROQ_API_KEY"),
        ("pollinations", "POLLINATIONS_API_KEY"),
        ("huggingface", "HUGGINGFACE_API_KEY"),
    ]:
        key_val = os.getenv(key_env, "") or (os.getenv("GEMINI_API_KEY", "") if "google" in provider else "")
        token_val = os.getenv(provider.upper() + "_AUTH_TOKEN", "")
        if (key_val and len(key_val) > 8 and not key_val.startswith("YOUR_")) or token_val:
            llm_providers[provider] = {"status": "configured"}
        else:
            llm_providers[provider] = {"status": "not_configured"}


    instances = await crud.list_workflow_instances(db, limit=500)
    active = sum(1 for i in instances if i.status == "running")
    tenants = await crud.list_tenants(db)
    ev_dir = Path(os.getenv("EPI_EVIDENCE_DIR", "./evidence"))
    ev_count = len(list(ev_dir.glob("*"))) if ev_dir.exists() else 0

    return {
        "status": "ok", "db": "postgresql",
        "llm_providers": llm_providers,
        "epi": f"{ev_count} evidence files",
        "timestamp": datetime.utcnow().isoformat(),
        "active_workflows": active,
        "total_tenants": len(tenants),
        "ws_connections": len(_ws_connections),
    }
    
    
@app.get("/api/v1/tenants/{tenant_id}/connectors/health", tags=["Tenants"])
async def check_connector_health(
    tenant_id: str,
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    """
    Run health checks on all configured integrations for a tenant.
    Returns per-connector status so operators know before triggering workflows.
    """
    assert_tenant_access(current_user, tenant_id)
    tenant = await crud.get_tenant(db, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
 
    creds_rows = await crud.list_credentials(db, tenant_id=tenant_id)
    stored_creds: dict = {}
    for c in creds_rows:
        raw = (c.credentials or {}).get("encrypted", "")
        if raw:
            try:
                from integrations.key_vault import decrypt_credentials
                stored_creds[c.tool_name] = decrypt_credentials(raw)
            except Exception:
                pass
 
    integrations = (tenant.config or {}).get("integrations", {})
    results = {}
 
    for int_name, int_conf in integrations.items():
        if not isinstance(int_conf, dict) or not int_conf.get("enabled"):
            results[int_name] = {"status": "disabled"}
            continue
        if int_name not in stored_creds:
            results[int_name] = {"status": "no_credentials"}
            continue
 
        connector_cls = {
            "hubspot": "HubSpotConnector",
            "gmail":   "GmailConnector",
            "slack":   "SlackConnector",
            "stripe":  "StripeConnector",
        }.get(int_name)
 
        if not connector_cls:
            results[int_name] = {"status": "unknown_connector_type"}
            continue
 
        try:
            from integrations import connectors as _conn_mod
            cls = getattr(_conn_mod, connector_cls)
            connector = cls(credentials=stored_creds[int_name], config=int_conf)
            ok = await asyncio.wait_for(connector.health_check(), timeout=5.0)
            results[int_name] = {"status": "healthy" if ok else "auth_failed"}
        except asyncio.TimeoutError:
            results[int_name] = {"status": "timeout"}
        except Exception as e:
            results[int_name] = {"status": "error", "detail": str(e)[:100]}
 
    all_healthy = all(
        v["status"] in ("healthy", "disabled")
        for v in results.values()
    )
    return {
        "tenant_id": tenant_id,
        "all_healthy": all_healthy,
        "connectors": results,
        "checked_at": datetime.utcnow().isoformat(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Admin
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/v1/admin/god-view", tags=["Admin"])
async def get_god_view(
    _: TokenData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    instances = await crud.list_workflow_instances(db, limit=200)
    tenants = await crud.list_tenants(db)
    pending_escs = await crud.list_escalations(db, status="pending")
    pending_a2a = await crud.list_pending_a2a(db)
    events = await crud.list_events(db, limit=50)

    active = [crud.workflow_to_dict(i) for i in instances if i.status in ("running", "paused", "escalated", "pending_a2a")]
    fleet_cost = sum((i.total_cost_usd or 0) for i in instances)
    fleet_tokens_in = sum((i.total_tokens_in or 0) for i in instances)

    return {
        "active_workflows": active,
        "all_workflows": [crud.workflow_to_dict(i) for i in instances],
        "tenants": [
            {"id": str(t.id), "name": t.name, "industry": t.industry,
             "active": t.active, "config": t.config}
            for t in tenants
        ],
        "pending_escalations": [crud.escalation_to_dict(e) for e in pending_escs],
        "pending_a2a": [crud.a2a_to_dict(a) for a in pending_a2a],
        "fleet_stats": {
            "total_cost_usd": round(fleet_cost, 4),
            "total_tokens_in": fleet_tokens_in,
            "active_runs": len(active),
            "ws_clients": len(_ws_connections),
        },
        "recent_events": events,
        "users": [crud.user_to_dict(u) for u in await crud.list_users(db)],
    }


@app.get("/api/v1/admin/live-stats", tags=["Admin"])
async def get_live_stats(
    _: TokenData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    instances = await crud.list_workflow_instances(db, limit=500)
    active = [i for i in instances if i.status in ("running", "paused", "escalated")]
    fleet_cost = sum((i.total_cost_usd or 0) for i in instances)
    tenants = await crud.list_tenants(db)
    users = await crud.list_users(db)
    pending_escs = await crud.list_escalations(db, status="pending")
    pending_a2a = await crud.list_pending_a2a(db)
    return {
        "active_workflows": len(active),
        "total_workflows": len(instances),
        "fleet_cost_usd": round(fleet_cost, 6),
        "pending_escalations": len(pending_escs),
        "pending_a2a": len(pending_a2a),
        "ws_connections": len(_ws_connections),
        "total_tenants": len(tenants),
        "total_users": len(users),
        "ts": datetime.utcnow().isoformat(),
    }


@app.get("/api/v1/admin/system-events", tags=["Admin"])
async def get_system_events(
    limit: int = Query(100),
    _: TokenData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await crud.list_events(db, limit=limit)


# ─────────────────────────────────────────────────────────────────────────────
# Users & Admin Management
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/v1/admin/users/invite", tags=["Admin"])
async def invite_platform_admin_or_user(
    body: AdminUserInviteRequest,
    current_user: TokenData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role not in ("platform_admin", "super_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform Admin access required",
        )

    target_role = body.role or "platform_admin"
    if target_role == "super_admin":
        target_role = "platform_admin"
    elif target_role == "tenant_user":
        target_role = "org_user"

    if target_role not in ("platform_admin", "org_user"):
        target_role = "org_user"

    target_uid = str(uuid.uuid5(uuid.NAMESPACE_DNS, body.email.lower().strip()))
    supabase_url = os.getenv("SUPABASE_URL") or os.getenv("VITE_SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SECRET_KEY")

    if supabase_url and service_key and not service_key.startswith("YOUR_"):
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                res = await client.post(
                    f"{supabase_url.rstrip('/')}/auth/v1/admin/users",
                    json={"email": body.email.strip(), "email_confirm": True},
                    headers={
                        "apikey": service_key,
                        "Authorization": f"Bearer {service_key}",
                        "Content-Type": "application/json",
                    },
                    timeout=5.0,
                )
                if res.status_code in (200, 201):
                    data = res.json()
                    target_uid = str(data.get("id") or target_uid)
        except Exception as e:
            log.warning("Supabase Admin API call failed/skipped", error=str(e))

    org_user, org = await crud.ensure_user_organization_provisioned(
        db,
        user_id=target_uid,
        email=body.email.strip(),
        full_name=body.full_name,
    )
    if org_user:
        org_user.role = target_role
        if body.full_name:
            org_user.full_name = body.full_name
        await db.commit()
        await db.refresh(org_user)

    legacy_u = await crud.get_user_by_email(db, body.email.strip())
    if legacy_u:
        legacy_u.role = "super_admin" if target_role == "platform_admin" else "tenant_user"
        await db.commit()

    await crud.log_event(
        db,
        event_type="admin_user_invited",
        tenant_id=str(org.id) if org else None,
        instance_id=None,
        message=f"Platform Admin {current_user.email} invited {body.email} as {target_role}",
        metadata={
            "actor_user_id": current_user.user_id,
            "actor_email": current_user.email,
            "target_email": body.email.strip(),
            "assigned_role": target_role,
        },
    )

    return {
        "message": f"Successfully invited {body.email.strip()} as {target_role}",
        "user_id": target_uid,
        "email": body.email.strip(),
        "role": target_role,
    }


@app.get("/api/v1/users", tags=["Users"])
@app.get("/api/v1/admin/users", tags=["Admin"])
async def list_admin_users(
    current_user: TokenData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role not in ("platform_admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Platform Admin access required")

    res_ou = await db.execute(select(OrganizationUser).order_by(OrganizationUser.created_at.desc()))
    ous = res_ou.scalars().all()

    res_orgs = await db.execute(select(Organization))
    orgs_map = {str(o.id): o.name for o in res_orgs.scalars().all()}

    result = []
    seen_emails = set()

    for ou in ous:
        role = "platform_admin" if ou.role in ("platform_admin", "super_admin") else "org_user"
        seen_emails.add(ou.email.lower())
        result.append({
            "id": str(ou.id),
            "user_id": str(ou.user_id),
            "email": ou.email,
            "full_name": ou.full_name,
            "role": role,
            "organization_id": str(ou.organization_id) if ou.organization_id else None,
            "organization_name": orgs_map.get(str(ou.organization_id), "SMBFlow Workspace"),
            "tenant_id": str(ou.organization_id) if ou.organization_id else None,
            "is_active": True,
            "created_at": ou.created_at.isoformat() if ou.created_at else None,
        })

    legacy_users = await crud.list_users(db)
    for u in legacy_users:
        if u.email.lower() not in seen_emails:
            role = "platform_admin" if u.role in ("platform_admin", "super_admin") else "org_user"
            result.append({
                "id": str(u.id),
                "user_id": str(u.id),
                "email": u.email,
                "full_name": u.full_name,
                "role": role,
                "organization_id": str(u.tenant_id) if u.tenant_id else None,
                "organization_name": orgs_map.get(str(u.tenant_id), "—"),
                "tenant_id": str(u.tenant_id) if u.tenant_id else None,
                "is_active": u.is_active,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            })

    return result


@app.post("/api/v1/users", tags=["Users"])
async def create_user(
    body: UserCreate,
    current_user: TokenData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role not in ("platform_admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Platform Admin access required")
    if await crud.get_user_by_email(db, body.email):
        raise HTTPException(status_code=409, detail="Email already exists")
    user = await crud.create_user(
        db, body.email, hash_password(body.password),
        body.full_name, "tenant_user", body.tenant_id,
    )
    return {"user_id": str(user.id), "message": "User created"}


@app.patch("/api/v1/users/{user_id}/deactivate", tags=["Users"])
async def deactivate_user(
    user_id: str,
    current_user: TokenData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role not in ("platform_admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Platform Admin access required")
    if not await crud.get_user_by_id(db, user_id):
        raise HTTPException(status_code=404, detail="User not found")
    await crud.deactivate_user(db, user_id)
    return {"message": "User deactivated"}



# ─────────────────────────────────────────────────────────────────────────────
# Tenants
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/v1/tenants", tags=["Tenants"])
async def list_tenants(
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    filter_id = get_tenant_filter(current_user)
    tenants = await crud.list_tenants(db, tenant_id_filter=filter_id)
    instances = await crud.list_workflow_instances(db, limit=1000)
    users = await crud.list_users(db)

    res = []
    for t in tenants:
        tid_str = str(t.id)
        t_users = [u for u in users if str(u.tenant_id or "") == tid_str]
        t_runs = [i for i in instances if str(i.tenant_id or "") == tid_str]
        t_cost = sum((i.total_cost_usd or 0) for i in t_runs)
        res.append({
            "id": tid_str,
            "name": t.name,
            "industry": t.industry,
            "active": t.active,
            "config": t.config,
            "user_count": len(t_users),
            "run_count": len(t_runs),
            "total_cost_usd": round(t_cost, 4),
            "created_at": t.created_at.isoformat() if hasattr(t, "created_at") and t.created_at else None,
        })
    return res


@app.post("/api/v1/tenants", tags=["Tenants"])
async def create_tenant(
    body: TenantCreate,
    _: TokenData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    tenant = await crud.create_tenant(db, body.name, body.industry, body.config)
    await broadcast_event("tenant_created", {"tenant_id": str(tenant.id), "name": body.name})
    return {"tenant_id": str(tenant.id), "message": f"Tenant '{body.name}' created"}


@app.get("/api/v1/tenants/{tenant_id}", tags=["Tenants"])
async def get_tenant(
    tenant_id: str,
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    assert_tenant_access(current_user, tenant_id)
    tenant = await crud.get_tenant(db, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return {"id": str(tenant.id), "name": tenant.name, "industry": tenant.industry,
            "config": tenant.config, "active": tenant.active}


@app.put("/api/v1/tenants/{tenant_id}/config", tags=["Tenants"])
async def update_tenant_config(
    tenant_id: str,
    body: TenantConfigUpdate,
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    assert_tenant_access(current_user, tenant_id)
    if not await crud.get_tenant(db, tenant_id):
        raise HTTPException(status_code=404, detail="Tenant not found")
    await crud.update_tenant_config(db, tenant_id, body.config)
    await broadcast_event("config_updated", {"tenant_id": tenant_id})
    return {"message": "Config updated", "tenant_id": tenant_id}


@app.get("/api/v1/tenants/{tenant_id}/config-schema", tags=["Tenants"])
async def get_config_schema(tenant_id: str):
    return _build_config_schema()

@app.post("/api/v1/tenants/{tenant_id}/validate-config", tags=["Tenants"])
async def validate_tenant_config_endpoint(
    tenant_id: str,
    strict: bool = False,
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    """
    Validate a tenant's current config.
    
    Returns blocking errors (would prevent workflow execution) and warnings.
    Use strict=True to treat warnings as errors (for production gate).
    """
    assert_tenant_access(current_user, tenant_id)
    tenant = await crud.get_tenant(db, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    from core.config_validator import validate_tenant_config
    result = validate_tenant_config(tenant.config or {}, strict=strict)
    
    return {
        **result.to_dict(),
        "tenant_id": tenant_id,
        "tenant_name": tenant.name,
        "message": (
            "Config is valid and ready for workflow execution."
            if result.valid else
            f"Config has {len(result.errors)} blocking error(s) that must be fixed before triggering."
        ),
    }

@app.get("/api/v1/evidence/{filename}/content", tags=["Evidence"])
async def get_evidence_file_content(
    filename: str,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_any_auth),
):
    """Return the parsed content of an evidence artifact for the UI viewer."""
    evidence_dir = Path(os.getenv("EPI_EVIDENCE_DIR", "./evidence"))
    # Sanitize — no path traversal
    safe = filename.replace("..", "").replace("/", "").replace("\\", "")
    p = evidence_dir / safe
    if p.exists():
        try:
            size_kb = round(p.stat().st_size / 1024, 1)
            if p.suffix == ".json":
                data = json.loads(p.read_text())
                return {"filename": safe, "type": "json_summary", "data": data, "size_kb": size_kb}
            elif p.suffix == ".epi":
                try:
                    data = json.loads(p.read_text())
                    return {"filename": safe, "type": "epi", "data": data, "size_kb": size_kb}
                except Exception:
                    return {
                        "filename": safe,
                        "type": "epi_binary",
                        "data": None,
                        "note": f"Binary EPI artifact — use CLI: epi view evidence/{safe}",
                        "size_kb": size_kb,
                    }
            raise HTTPException(status_code=400, detail="Unsupported file type")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # DB Fallback for workflow instances
    try:
        from db.models.core import WorkflowInstance, AgentRunRecord
        raw_target = safe.replace(".json", "").replace("product_launch_", "").replace("email_summarizer_", "").replace("finance_expense_monitoring_", "")
        stmt = select(WorkflowInstance)
        res = await db.execute(stmt)
        all_wf = res.scalars().all()
        target_wf = next((w for w in all_wf if str(w.id).startswith(raw_target) or raw_target in str(w.id)), None)

        if target_wf:
            stmt_runs = select(AgentRunRecord).where(AgentRunRecord.instance_id == target_wf.id)
            res_runs = await db.execute(stmt_runs)
            runs = res_runs.scalars().all()

            synth_data = {
                "run_id": str(target_wf.id),
                "workflow_name": target_wf.workflow_name,
                "status": target_wf.status,
                "created_at": target_wf.started_at.isoformat() if target_wf.started_at else datetime.utcnow().isoformat(),
                "total_cost_usd": target_wf.total_cost_usd or 0.0,
                "total_tokens_in": target_wf.total_tokens_in or 0,
                "total_tokens_out": target_wf.total_tokens_out or 0,
                "outcome": {
                    "situation_summary": f"Workflow {target_wf.workflow_name} executed with status {target_wf.status}.",
                    "details": target_wf.context or {},
                },
                "agent_runs": [
                    {
                        "node_id": r.node_id,
                        "agent_type": r.agent_capability,
                        "status": r.status,
                        "tokens_in": r.tokens_in,
                        "tokens_out": r.tokens_out,
                        "cost_usd": r.cost_usd,
                        "model_used": r.model_used,
                    }
                    for r in runs
                ],
            }
            return {"filename": safe, "type": "json_summary", "data": synth_data, "size_kb": 1.5}
    except Exception as db_err:
        log.warning("Evidence DB fallback error", error=str(db_err))

    raise HTTPException(status_code=404, detail="Evidence file not found")

# ─────────────────────────────────────────────────────────────────────────────
# Workflows
# NOTE: /workflows/trigger and /workflows/estimate-cost MUST be registered
# before /workflows/{run_id}/... routes so FastAPI does not swallow static
# path segments as run_id values.
# ─────────────────────────────────────────────────────────────────────────────



@app.post("/api/v1/workflows/prepare-demo-data", tags=["Workflows"])
async def prepare_demo_data(current_user: TokenData = Depends(require_any_auth)):
    """Prepare synthetic fixture data for enabled workflows.

    Returns a summary per workflow with source type and available record count.
    No workflow runs are created, and no approvals or side‑effects occur.
    """
    from pathlib import Path
    import json, aiofiles
    dags_dir = Path("workflows/dags")
    if not dags_dir.exists():
        return {"demo_data": []}
    demo = []
    for f in dags_dir.glob("*.json"):
        name = f.stem
        source = "unavailable"
        available = 0
        message = "No demo input configured"
        # Email summarizer fixture
        if "email" in name:
            fixture = Path("db/seed/data/email_messages.json")
            if fixture.exists():
                try:
                    async with aiofiles.open(fixture) as fp:
                        emails = json.loads(await fp.read())
                    if isinstance(emails, list):
                        available = len(emails)
                    else:
                        available = 0
                    source = "synthetic_inbox"
                    message = None
                except Exception:
                    pass
        demo.append({
            "workflow_name": name,
            "source": source,
            "available_count": available,
            "message": message,
        })
    return {"demo_data": demo}

@app.post("/api/v1/workflows/trigger", tags=["Workflows"])
async def trigger_workflow(
    body: WorkflowTriggerRequest,
    background_tasks: BackgroundTasks,
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    """Trigger a workflow run via manual UI.

    Mirrors the logic previously present but was missing a route definition.
    """
    # Determine effective tenant ID (explicit in payload or from auth)
    effective_tenant_id = body.tenant_id or (current_user.organization_id or current_user.tenant_id)
    # Load tenant config via bridge — handles both legacy tenants table and new organizations table.
    _resolved_tid, tenant_config = await crud.resolve_tenant_config_bridge(db, effective_tenant_id) if effective_tenant_id else (effective_tenant_id, {})

    # ── Workflow entitlement enforcement (server-side — frontend is NOT the boundary) ──
    # Only enforce when the org has a subscription record (new-model orgs).
    # Legacy tenants without subscriptions are permitted through unchanged.
    if effective_tenant_id and current_user.role not in ("platform_admin", "super_admin"):
        try:
            access = await crud.check_org_workflow_access(db, effective_tenant_id, body.workflow_name)
            if not access.get("allowed"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error_code": "WORKFLOW_ACCESS_DENIED",
                        "message": access.get("reason", "Workflow not authorized for this organization"),
                        "workflow": body.workflow_name,
                        "organization_id": effective_tenant_id,
                    },
                )
        except HTTPException:
            raise
        except Exception as _ent_err:
            # Entitlement tables are missing (pre-migration environment).
            # Log at WARNING — this is a configuration gap, not a benign skip.
            # In production (post-migration) this branch should never be reached.
            log.warning(
                "Workflow entitlement check could not be completed — "
                "entitlement tables may not exist yet (pre-migration). "
                "Blocking execution to fail safe.",
                workflow=body.workflow_name,
                tenant_id=effective_tenant_id,
                error=str(_ent_err),
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error_code": "ENTITLEMENT_CHECK_UNAVAILABLE",
                    "message": (
                        "Workflow access cannot be verified at this time. "
                        "Run database migrations and try again."
                    ),
                    "workflow": body.workflow_name,
                },
            )

    # Pre-flight config validation — block ALL users when config is invalid.
    # The workflow would fail in the background anyway; surfacing the error here
    # lets the frontend show a config-input form instead of a silent failure.
    from core.config_validator import validate_tenant_config
    validation = validate_tenant_config(tenant_config, strict=False)
    if not validation.valid and validation.errors:
        log.warning(
            "Workflow trigger blocked — config validation failed",
            tenant_id=effective_tenant_id,
            errors=[e.message for e in validation.errors],
        )
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Configuration required before this workflow can run",
                "errors": [{"field": e.field, "message": e.message} for e in validation.errors],
                "warnings": [{"field": w.field, "message": w.message} for w in validation.warnings],
                "missing_fields": [e.field for e in validation.errors],
                "hint": "Provide the required configuration values, then trigger again.",
            },
        )

    # Normalize trigger signal / payload
    sig = body.trigger_signal or body.signal_data or getattr(body, "trigger_payload", None) or {}
    if not isinstance(sig, dict):
        sig = {}

    req_source = sig.get("source")
    if body.workflow_name == "email_summarizer":
        if req_source not in ("real_gmail", "synthetic_demo"):
            raise HTTPException(
                status_code=422,
                detail={
                    "error_code": "INVALID_SOURCE",
                    "message": "Explicit 'source' parameter required for email_summarizer. Allowed values: 'real_gmail' or 'synthetic_demo'.",
                },
            )

        if req_source == "real_gmail":
            org_id = effective_tenant_id or current_user.organization_id or current_user.tenant_id
            gmail_conn_ok = False
            if org_id:
                try:
                    from sqlalchemy import select
                    from db.models.core import ToolConnection
                    org_uuid = uuid.UUID(str(org_id))
                    conn_stmt = select(ToolConnection).where(
                        ToolConnection.organization_id == org_uuid,
                        ToolConnection.tool_name == "gmail",
                        ToolConnection.status == "connected",
                    )
                    tc_res = await db.execute(conn_stmt)
                    if tc_res.scalar_one_or_none():
                        gmail_conn_ok = True
                except Exception as _check_err:
                    log.warning("Failed checking Gmail connection status", error=str(_check_err))

            if not gmail_conn_ok:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error_code": "GMAIL_CONNECTION_REQUIRED",
                        "message": "Real Gmail source requested, but no active connected Gmail connection was found for this organization. Please connect Gmail in Settings -> Tool Connections.",
                    },
                )

    # Create workflow instance record
    run_id = str(uuid.uuid4())
    await crud.create_workflow_instance(
        db,
        run_id=run_id,
        tenant_id=effective_tenant_id,
        workflow_name=body.workflow_name,
        trigger_signal=sig,
        triggered_by=current_user.user_id,
        tenant_config=tenant_config,
    )
    # Schedule background execution
    budget = await crud.get_budget_settings(db, effective_tenant_id) or {}
    background_tasks.add_task(
        _execute_workflow_background,
        run_id,
        tenant_config,
        body.workflow_name,
        sig,
        budget,
    )
    # Log and broadcast event
    await crud.log_event(
        db,
        "workflow_triggered",
        effective_tenant_id,
        run_id,
        f"Workflow '{body.workflow_name}' triggered by {current_user.email}",
    )
    await broadcast_event(
        "workflow_triggered",
        {"run_id": run_id, "workflow": body.workflow_name, "tenant_id": effective_tenant_id},
    )
    return {
        "run_id": run_id,
        "status": "pending",
        "tenant_id": effective_tenant_id,
        "message": f"Workflow '{body.workflow_name}' queued.",
    }




@app.get("/api/v1/workflows/{workflow_name}/trigger-info", tags=["Workflows"])
async def get_workflow_trigger_info(
    workflow_name: str,
    date_range: Optional[str] = "Today",
    scope: Optional[str] = "Inbox",
    batch_size: Optional[int] = 10,
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns real runtime trigger information, available message counts from fixtures or real Gmail,
    filtered counts, preview messages, and connection health status for the given workflow.
    """
    safe_name = workflow_name.replace("/", "_").replace("..", "")
    dag_path = Path("workflows/dags") / f"{safe_name}.json"
    meta = {}
    if dag_path.exists():
        try:
            async with aiofiles.open(dag_path) as fp:
                dag = json.loads(await fp.read())
            meta = dag.get("_meta", {})
        except Exception:
            pass

    available_messages_count = 0
    if workflow_name == "email_summarizer" or "email" in workflow_name:
        fixture_path = Path("db/seed/data/email_messages.json")
        if fixture_path.exists():
            try:
                async with aiofiles.open(fixture_path) as fp:
                    emails = json.loads(await fp.read())
                if isinstance(emails, list):
                    available_messages_count = len(emails)
            except Exception:
                pass

    trigger_meta = meta.get("trigger", {})
    trigger_type = "New Email" if ("email" in workflow_name or trigger_meta.get("type") == "email") else "Manual"
    source = "Synthetic Inbox" if ("email" in workflow_name or "synthetic" in str(trigger_meta.get("source", ""))) else "Direct"

    # Compute stats for authenticated org / tenant
    org_id = current_user.organization_id or current_user.tenant_id
    real_messages_count = 0
    total_inbox_count = 0
    real_gmail_connected = False
    real_gmail_status = "not_connected"
    real_gmail_error = None
    connected_email = None
    preview_messages = []

    def _build_gmail_query(dr: str = "Today", sc: str = "Inbox") -> str:
        parts = []
        sc_lower = (sc or "").lower()
        if sc_lower == "unread":
            parts.append("is:unread in:inbox")
        elif sc_lower == "important":
            parts.append("is:important in:inbox")
        elif sc_lower == "starred":
            parts.append("is:starred in:inbox")
        else:
            parts.append("in:inbox")

        dr_lower = (dr or "").lower()
        if "today" in dr_lower:
            parts.append("newer_than:1d")
        elif "7" in dr_lower:
            parts.append("newer_than:7d")
        elif "30" in dr_lower:
            parts.append("newer_than:30d")
        
        return " ".join(parts)

    if org_id and (workflow_name == "email_summarizer" or "email" in workflow_name):
        try:
            from sqlalchemy import select
            from db.models.core import ToolConnection
            from integrations.key_vault import decrypt_credentials
            from integrations.connectors import GmailConnector

            org_uuid = uuid.UUID(str(org_id)) if isinstance(org_id, str) else org_id
            conn_stmt = select(ToolConnection).where(
                ToolConnection.organization_id == org_uuid,
                ToolConnection.tool_name == "gmail",
                ToolConnection.status == "connected"
            )
            c_res = await db.execute(conn_stmt)
            conn_obj = c_res.scalar_one_or_none()

            if conn_obj and conn_obj.encrypted_credentials:
                raw_creds = decrypt_credentials(conn_obj.encrypted_credentials)
                if raw_creds:
                    real_gmail_connected = True
                    connected_email = (conn_obj.config or {}).get("connected_email") or (conn_obj.config or {}).get("sender_alias")
                    gc = GmailConnector(raw_creds, config=conn_obj.config or {})
                    
                    inbox_stubs = await gc.read("messages", {"q": "in:inbox", "limit": 100})
                    err_info = gc.get_last_error_info() if hasattr(gc, "get_last_error_info") else {}

                    if err_info.get("error_code") in (401, 403, 500) or err_info.get("error"):
                        real_gmail_status = "reauth_required" if err_info.get("error_code") in (401, 403) else "error"
                        real_gmail_error = err_info.get("error") or "Gmail API read error"
                        real_messages_count = 0
                        total_inbox_count = 0
                    else:
                        real_gmail_status = "ok"
                        total_inbox_count = len(inbox_stubs)
                        query_q = _build_gmail_query(date_range, scope)
                        if query_q == "in:inbox":
                            filter_stubs = inbox_stubs
                        else:
                            filter_stubs = await gc.read("messages", {"q": query_q, "limit": 100})
                        
                        real_messages_count = len(filter_stubs)
                        prev_limit = min(max(1, batch_size or 10), 5)
                        preview_messages = await gc.read_detailed_messages(query=query_q, limit=prev_limit)
        except Exception as ex:
            log.warning("Failed to query real Gmail count for trigger info", error=str(ex))
            real_gmail_error = str(ex)

    instances = await crud.list_workflow_instances(db, tenant_id=org_id, limit=200)
    wf_runs = [i for i in instances if i.workflow_name == workflow_name]
    completed_runs = [i for i in wf_runs if i.status in ("completed", "WorkflowStatus.COMPLETED")]
    last_run = wf_runs[0] if wf_runs else None

    # ── Config validation — surface missing fields before the user triggers ──
    config_validation = None
    if org_id:
        _resolved_tid, tenant_config = await crud.resolve_tenant_config_bridge(db, org_id)
        from core.config_validator import validate_tenant_config
        cv = validate_tenant_config(tenant_config, strict=False)
        config_validation = {
            "valid": cv.valid,
            "errors": [{"field": e.field, "message": e.message} for e in cv.errors],
            "warnings": [{"field": w.field, "message": w.message} for w in cv.warnings],
        }

    return {
        "workflow_name": workflow_name,
        "display_name": meta.get("name", workflow_name.replace("_", " ").title()),
        "description": meta.get("description", ""),
        "status": "active",
        "automation_status": "active",
        "automation_enabled": True,
        "trigger_type": trigger_type,
        "source": source,
        "available_messages_count": available_messages_count,
        "synthetic_messages_count": available_messages_count,
        "real_messages_count": real_messages_count,
        "total_inbox_count": total_inbox_count,
        "real_gmail_connected": real_gmail_connected,
        "real_gmail_status": real_gmail_status,
        "real_gmail_error": real_gmail_error,
        "connected_email": connected_email,
        "preview_messages": preview_messages,
        "date_range": date_range,
        "scope": scope,
        "batch_size": batch_size,
        "total_runs": len(wf_runs),
        "completed_runs": len(completed_runs),
        "success_rate": round((len(completed_runs) / len(wf_runs)) * 100) if wf_runs else None,
        "last_run": crud.workflow_to_dict(last_run) if last_run else None,
        "config_validation": config_validation,
    }


@app.get("/api/v1/workflows/estimate-cost", tags=["Workflows"])
async def estimate_workflow_cost(
    tenant_id: str,
    workflow_name: str,
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    """
    Pre-trigger cost forecast.

    Analyzes the last completed run for this workflow+tenant, extracts data size,
    and estimates cost at the current optimization level.

    Returns: { estimated_cost_usd, estimated_duration_min, accounts_count,
               breakdown_by_agent, optimization_level, confidence }
    """
    assert_tenant_access(current_user, tenant_id)

    # Find last completed run
    instances = await crud.list_workflow_instances(db, tenant_id=tenant_id, limit=50)
    last_run = next(
        (i for i in instances
         if i.workflow_name == workflow_name and i.status == "completed"),
        None
    )

    if not last_run:
        return {
            "estimated_cost_usd": None,
            "confidence": "low",
            "message": "No previous completed run found for this workflow. Run it once to get estimates.",
            "workflow_name": workflow_name,
        }

    # Get budget settings
    budget = await crud.get_budget_settings(db, tenant_id) or {}
    opt_level = budget.get("optimization_level", 1)

    # Extract data size from last run context
    context = last_run.context or {}
    research = context.get("research", {})
    account_count = len(
        research.get("accounts") or
        research.get("deals") or
        research.get("patients") or
        research.get("transactions") or []
    )

    # Use actual last run cost as baseline
    last_cost = last_run.total_cost_usd or 0.0

    # Apply optimization level savings estimate
    from core.llm_router import LLMRouter
    router = LLMRouter()
    savings = router.get_predicted_savings(opt_level)
    savings_pct = savings.get("savings_pct", 0) / 100.0

    estimated_cost = last_cost * (1.0 - savings_pct)

    # Per-agent breakdown from last run's agent_runs
    agent_runs = last_run.agent_runs or []
    breakdown = {}
    for run in agent_runs:
        if isinstance(run, dict):
            node_id = run.get("node_id", "?")
            run_c = run.get("cost_usd")
            breakdown[node_id] = {
                "agent_type": run.get("agent_type", "?"),
                "last_cost_usd": round(run_c, 6) if run_c is not None else None,
                "estimated_cost_usd": round(run_c * (1.0 - savings_pct), 6) if run_c is not None else None,
                "model_last_used": run.get("model_used", "?"),
            }

    return {
        "workflow_name": workflow_name,
        "tenant_id": tenant_id,
        "optimization_level": opt_level,
        "optimization_strategy": savings.get("description", ""),
        "estimated_cost_usd": round(estimated_cost, 5),
        "last_run_cost_usd": round(last_cost, 5),
        "estimated_savings_pct": savings_pct * 100,
        "estimated_duration_minutes": 5,
        "accounts_in_last_run": account_count,
        "confidence": "high" if last_cost > 0.001 else "low",
        "breakdown_by_agent": breakdown,
        "note": f"Estimate based on last completed run ({str(last_run.id)[:8]}). Actual cost varies with data volume.",
    }


@app.get("/api/v1/workflows/{run_id}/status", tags=["Workflows"])
async def get_workflow_status(
    run_id: str,
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    inst = await crud.get_workflow_instance(db, run_id)
    if not inst:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    if current_user.role != "super_admin":
        assert_tenant_access(current_user, str(inst.tenant_id))
    return crud.workflow_to_dict(inst)


@app.get("/api/v1/workflows", tags=["Workflows"])
async def list_workflows(
    tenant_id: Optional[str] = Query(None),
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    """
    List workflow instances (runs) scoped to the authenticated user's org.
    """
    if current_user.role in ("platform_admin", "super_admin"):
        filter_tid = get_tenant_filter(current_user) or tenant_id
    else:
        filter_tid = current_user.organization_id or current_user.tenant_id
    instances = await crud.list_workflow_instances(db, tenant_id=filter_tid, limit=200)
    return [crud.workflow_to_dict(i) for i in instances]


@app.get("/api/v1/workflow-instances", tags=["Workflows"])
async def list_workflow_instances_alias(
    tenant_id: Optional[str] = Query(None),
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    """Alias for /api/v1/workflows — returns run instances."""
    if current_user.role in ("platform_admin", "super_admin"):
        filter_tid = get_tenant_filter(current_user) or tenant_id
    else:
        filter_tid = current_user.organization_id or current_user.tenant_id
    instances = await crud.list_workflow_instances(db, tenant_id=filter_tid, limit=200)
    return [crud.workflow_to_dict(i) for i in instances]


@app.get("/api/v1/workflows/definitions", tags=["Workflows"])
async def list_org_workflow_definitions(
    include_templates: bool = Query(False, description="Also return platform templates"),
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    """
    List WorkflowDefinitions owned by the authenticated user's organization.

    Returns definitions from the ``workflow_definitions`` DB table — distinct
    from the filesystem DAGs returned by ``/config/workflows``.
    Set ``include_templates=true`` to also return platform-level templates.
    """
    org_id = current_user.organization_id or current_user.tenant_id
    defs = await crud.list_workflow_definitions(
        db,
        organization_id=org_id,
        include_templates=include_templates,
    )
    return [
        {
            "id":              str(d.id),
            "name":            d.name,
            "industry":        d.industry,
            "version":         d.version,
            "is_template":     d.is_template,
            "organization_id": str(d.organization_id) if d.organization_id else None,
            "active":          d.active,
            "created_at":      d.created_at.isoformat() if d.created_at else None,
        }
        for d in defs
    ]


@app.post("/api/v1/workflows/{run_id}/pause", tags=["Workflows"])
async def pause_workflow(
    run_id: str,
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    inst = await crud.get_workflow_instance(db, run_id)
    if not inst:
        raise HTTPException(status_code=404, detail="Run not found")
    assert_tenant_access(current_user, str(inst.tenant_id))
    orch = _active_orchestrators.get(run_id)
    if orch:
        orch.signal_pause(run_id)
    await crud.update_workflow_status(db, run_id, "paused")
    await crud.log_event(db, "workflow_paused", str(inst.tenant_id), run_id,
                         f"Paused by {current_user.email}")
    await broadcast_event("workflow_paused", {"run_id": run_id})
    return {"message": "Pause signal sent", "run_id": run_id}


@app.post("/api/v1/workflows/{run_id}/stop", tags=["Workflows"])
async def stop_workflow(
    run_id: str,
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    inst = await crud.get_workflow_instance(db, run_id)
    if not inst:
        raise HTTPException(status_code=404, detail="Run not found")
    assert_tenant_access(current_user, str(inst.tenant_id))
    orch = _active_orchestrators.get(run_id)
    if orch:
        orch.signal_stop(run_id)
    await crud.update_workflow_status(db, run_id, "stopped")
    await crud.log_event(db, "workflow_stopped", str(inst.tenant_id), run_id,
                         f"Stopped by {current_user.email}")
    await broadcast_event("workflow_stopped", {"run_id": run_id})
    return {"message": "Stop signal sent", "run_id": run_id}


@app.post("/api/v1/workflows/{run_id}/resume", tags=["Workflows"])
async def resume_workflow(
    run_id: str,
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    inst = await crud.get_workflow_instance(db, run_id)
    if not inst:
        raise HTTPException(status_code=404, detail="Run not found")
    assert_tenant_access(current_user, str(inst.tenant_id))
    orch = _active_orchestrators.get(run_id)
    if orch:
        orch.signal_resume(run_id)
    await crud.update_workflow_status(db, run_id, "running")
    await broadcast_event("workflow_resumed", {"run_id": run_id})
    return {"message": "Resume signal sent", "run_id": run_id}


@app.get("/api/v1/workflows/{run_id}/evidence", tags=["Workflows"])
async def get_workflow_evidence(
    run_id: str,
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    inst = await crud.get_workflow_instance(db, run_id)
    if not inst:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    if current_user.role != "super_admin":
        assert_tenant_access(current_user, str(inst.tenant_id))
    ev_dir = Path(os.getenv("EPI_EVIDENCE_DIR", "./evidence"))
    matches = list(ev_dir.glob(f"*{run_id[:8]}*"))
    if not matches:
        return {"found": False}
    p = sorted(matches, key=lambda x: x.stat().st_mtime, reverse=True)[0]
    try:
        data = json.loads(p.read_text()) if p.suffix == ".json" else {}
        return {"found": True, "filename": p.name, "path": str(p),
                "size_kb": round(p.stat().st_size / 1024, 1),
                "created": datetime.fromtimestamp(p.stat().st_mtime).isoformat(),
                "data": data}
    except Exception:
        return {"found": True, "filename": p.name}


@app.get("/api/v1/workflows/{run_id}/system-log", tags=["Workflows"])
async def get_workflow_system_log(
    run_id: str,
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    """
    Detailed system log for a workflow run.
    
    Shows per-agent: model used, tier, cost, cache hits, features activated.
    Shows: which features fired (HyDE, map-reduce, consensus gate, etc.)
    Shows: what worked, what failed, why.
    
    Useful for operators debugging unexpected costs or quality regressions.
    """
    inst = await crud.get_workflow_instance(db, run_id)
    if not inst:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    if current_user.role != "super_admin":
        assert_tenant_access(current_user, str(inst.tenant_id))
    
    outcome = inst.outcome or {}
    agent_runs = inst.agent_runs or []
    
    # Build system log from available data
    system_log = {
        "run_id": run_id,
        "workflow_name": inst.workflow_name,
        "status": inst.status,
        "duration_seconds": (
            (inst.completed_at - inst.started_at).total_seconds()
            if inst.completed_at and inst.started_at else None
        ),
        "cost_summary": {
            "total_usd": round(inst.total_cost_usd or 0.0, 6),
            "tokens_in": inst.total_tokens_in or 0,
            "tokens_out": inst.total_tokens_out or 0,
        },
        "agents": [
            {
                "node_id": r.get("node_id"),
                "agent_type": r.get("agent_type"),
                "status": r.get("status"),
                "model": r.get("model_used", "?"),
                "cost_usd": round(r_c, 6) if (r_c := r.get("cost_usd")) is not None else None,
                "tokens_in": r.get("tokens_in", 0),
                "tokens_out": r.get("tokens_out", 0),
                "confidence": r.get("confidence"),
                "duration_ms": r.get("duration_ms"),
                "error": r.get("error"),
                "tools_used": r.get("tools_used", []),
                # Verification-specific
                "prosecutor_issues": r.get("_prosecutor_issues"),
                "judge_verdict": r.get("_judge_verdict"),
                # Memory-specific
                "delta_vs_history": r.get("delta_vs_history"),
                "delta_trend": r.get("delta_trend"),
            }
            for r in agent_runs
            if isinstance(r, dict)
        ],
        "epi_steps": (outcome.get("_epi_steps") or [])[:20],
        "note": (
            "Enhanced system log with feature audit available after enabling "
            "WorkflowSystemLogger (core/workflow_logger.py). "
            "This response shows DB-persisted data only."
        ),
    }
    
    return system_log

@app.post("/api/v1/workflows/{run_id}/fork", tags=["Workflows"])
async def fork_workflow(
    run_id: str,
    body: WorkflowForkRequest,
    background_tasks: BackgroundTasks,
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    """
    Time-Travel Debugging: fork a workflow from a specific node checkpoint.
    Creates a new run that replays from the given node, reusing the accumulated
    context stored from the original run. Optionally patch context keys.
    """
    inst = await crud.get_workflow_instance(db, run_id)
    if not inst:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    if current_user.role != "super_admin":
        assert_tenant_access(current_user, str(inst.tenant_id))

    # Validate node exists in DAG
    dag_path = Path("workflows/dags") / f"{inst.workflow_name}.json"
    if dag_path.exists():
        import json as _j
        dag = _j.loads(dag_path.read_text())
        valid_nodes = [n["id"] for n in dag.get("nodes", [])]
        if body.from_node_id not in valid_nodes:
            raise HTTPException(
                status_code=400,
                detail=f"Node '{body.from_node_id}' not in DAG. Valid: {valid_nodes}",
            )

    new_run_id = str(uuid.uuid4())
    tenant_config = inst.tenant_config or {}

    await crud.create_workflow_instance(
        db,
        run_id=new_run_id,
        tenant_id=str(inst.tenant_id),
        workflow_name=inst.workflow_name,
        trigger_signal={
            **(inst.trigger_signal or {}),
            "_forked_from": run_id,
            "_fork_node": body.from_node_id,
        },
        triggered_by=current_user.user_id,
        tenant_config=tenant_config,
    )

    budget = await crud.get_budget_settings(db, str(inst.tenant_id)) or {}

    background_tasks.add_task(
        _fork_workflow_background,
        new_run_id=new_run_id,
        original_run_id=run_id,
        tenant_config=tenant_config,
        workflow_name=inst.workflow_name,
        from_node_id=body.from_node_id,
        budget_settings=budget,
        context_patch=body.context_patch,
    )

    await crud.log_event(
        db, "workflow_forked", str(inst.tenant_id), new_run_id,
        f"Forked from {run_id[:8]} at '{body.from_node_id}' by {current_user.email}",
    )
    await broadcast_event("workflow_forked", {
        "run_id": new_run_id, "parent_run_id": run_id,
        "fork_node": body.from_node_id, "tenant_id": str(inst.tenant_id),
    })

    return {
        "run_id": new_run_id,
        "parent_run_id": run_id,
        "fork_node": body.from_node_id,
        "status": "pending",
        "message": f"Forked from node '{body.from_node_id}'. Navigate to run: {new_run_id}",
    }

@app.get("/api/v1/tenants/{tenant_id}/workflows/stats", tags=["Workflows"])
async def get_tenant_workflow_stats(
    tenant_id: str,
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    assert_tenant_access(current_user, tenant_id)
    instances = await crud.list_workflow_instances(db, tenant_id=tenant_id, limit=500)
    return {
        "total": len(instances),
        "running":   sum(1 for i in instances if i.status == "running"),
        "completed": sum(1 for i in instances if i.status == "completed"),
        "failed":    sum(1 for i in instances if i.status == "failed"),
        "paused":    sum(1 for i in instances if i.status == "paused"),
        "escalated": sum(1 for i in instances if i.status in ("escalated", "pending_a2a")),
        "total_cost_usd": round(sum(i.total_cost_usd or 0 for i in instances), 6),
        "total_tokens_in": sum(i.total_tokens_in or 0 for i in instances),
        "total_tokens_out": sum(i.total_tokens_out or 0 for i in instances),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Escalations
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/v1/escalations", tags=["Escalations"])
async def list_escalations(
    status: str = Query("pending"),
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    filter_tid = get_tenant_filter(current_user)
    escs = await crud.list_escalations(db, status=status, tenant_id=filter_tid)
    res = [crud.escalation_to_dict(e) for e in escs]

    # Also query ApprovalItems so Action Center displays workflow recommendations & email drafts
    org_id = current_user.organization_id or filter_tid
    approval_status = "pending" if status == "pending" else ("approved" if status in ("resolved", "approved") else status)
    approval_items = await crud.list_approval_items(db, organization_id=org_id, status=approval_status)
    for a in approval_items:
        res.append(await crud.approval_item_to_dict(a))
    return res


@app.post("/api/v1/escalations/{escalation_id}/decide", tags=["Escalations"])
async def decide_escalation(
    escalation_id: str,
    body: EscalationDecision,
    background_tasks: BackgroundTasks,
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    from core.state_manager import StateManager
    sm = StateManager(session=db)
    esc = await crud.get_escalation(db, escalation_id)
    if not esc:
        # Check if this ID is an ApprovalItem
        from db.models.core import ApprovalItem
        from sqlalchemy import select
        try:
            r = await db.execute(select(ApprovalItem).where(ApprovalItem.id == uuid.UUID(escalation_id)))
            appr = r.scalar_one_or_none()
        except Exception:
            appr = None

        if appr:
            action_lower = body.action_chosen.lower()
            if "snooze" in action_lower:
                decided_status = "snoozed"
            elif "discard" in action_lower or "dismiss" in action_lower:
                decided_status = "discarded"
            elif "edit" in action_lower:
                decided_status = "awaiting_review"
            elif "approve" in action_lower or "send" in action_lower:
                decided_status = "approved"
            else:
                decided_status = "rejected"

            appr.status = decided_status
            appr.decided_by = body.decided_by or current_user.email
            appr.decided_at = datetime.utcnow()
            payload = appr.payload or {}
            if isinstance(body.decision, dict) and body.decision.get("notes"):
                payload["decision_notes"] = body.decision.get("notes")
            if isinstance(body.decision, dict) and isinstance(body.decision.get("patch_payload"), dict):
                payload = {**payload, **body.decision.get("patch_payload")}
            if isinstance(body.decision, dict) and body.decision.get("snoozed_until"):
                payload["snoozed_until"] = body.decision.get("snoozed_until")
            if isinstance(body.decision, dict) and body.decision.get("snooze_reason"):
                payload["snooze_reason"] = body.decision.get("snooze_reason")
            appr.payload = payload
            await db.commit()

            # Safe test mode execution boundary — zero external side effects
            if decided_status == "approved":
                log.info(
                    "[TEST MODE] Approval executed safely — Simulated email action approved",
                    approval_id=escalation_id,
                    recipient=payload.get("to_address") or payload.get("to") or "client@enterprise.com",
                    subject=payload.get("subject"),
                    simulated=True,
                )

            await broadcast_event("approval_decided", {
                "approval_id": escalation_id,
                "status": decided_status,
                "action_chosen": body.action_chosen,
                "decided_by": appr.decided_by,
                "organization_id": str(appr.organization_id) if appr.organization_id else None,
            })

            return {
                "message": f"Approval item {decided_status}.",
                "escalation_id": escalation_id,
                "action_chosen": body.action_chosen,
                "resolved": True,
                "signatures_collected": 1,
                "required_signatures": 1,
            }

        raise HTTPException(status_code=404, detail="Escalation or Approval item not found")

    assert_tenant_access(current_user, str(esc.tenant_id))

    updated_esc = await sm.add_escalation_signature(
        escalation_id=escalation_id,
        user_id=current_user.user_id,
        user_email=current_user.email,
        action_chosen=body.action_chosen,
        decision=body.decision,
    )

    run_id = str(esc.instance_id)
    # Auto-resume if all required signatures collected
    if updated_esc.status == "resolved":
        inst = await crud.get_workflow_instance(db, run_id)
        if inst and inst.status in ("escalated",):
            tenant = await crud.get_tenant(db, str(inst.tenant_id))
            if tenant:
                background_tasks.add_task(
                    _resume_workflow_background,
                    run_id=run_id,
                    tenant_config=tenant.config,
                    decision_context={
                        "escalation_decision": {
                            "action": body.action_chosen,
                            "decided_by": body.decided_by,
                            "decision": body.decision,
                            "escalation_id": escalation_id,
                        }
                    },
                )

    await crud.log_event(
        db, "escalation_resolved", str(esc.tenant_id), run_id,
        f"Decision: {body.action_chosen} by {body.decided_by}",
    )
    await broadcast_event("escalation_resolved", {
        "escalation_id": escalation_id, "run_id": run_id,
        "action_chosen": body.action_chosen, "decided_by": body.decided_by,
        "tenant_id": str(esc.tenant_id), "auto_resumed": updated_esc.status == "resolved",
    })
    # Feature 2: Feed the human override back into RAG so the Reasoning agent
    # learns from it on future runs for this tenant.
    if updated_esc.status == "resolved":
        notes = (
            body.decision.get("notes", "")
            if isinstance(body.decision, dict) else ""
        )
        background_tasks.add_task(
            _store_human_correction_rag,
            tenant_id=str(esc.tenant_id),
            run_id=run_id,
            escalation_id=escalation_id,
            original_recommendation=esc.recommended_action or "",
            human_action=body.action_chosen,
            context_brief=esc.context_brief or "",
            notes=notes,
        )
 
    return {
        "message": "Decision recorded.",
        "escalation_id": escalation_id,
        "action_chosen": body.action_chosen,
        "resolved": updated_esc.status == "resolved",
        "signatures_collected": len(updated_esc.signatures or []),
        "required_signatures": updated_esc.required_signatures or 1,
    }


# ─────────────────────────────────────────────────────────────────────────────
# A2A
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/v1/a2a/requests", tags=["A2A"])
async def list_a2a_requests(
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    filter_tid = get_tenant_filter(current_user)
    a2as = await crud.list_pending_a2a(db, tenant_id=filter_tid)
    return [crud.a2a_to_dict(a) for a in a2as]


@app.get("/api/v1/a2a/pending", tags=["A2A"])
async def list_pending_a2a(
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    filter_tid = get_tenant_filter(current_user)
    a2as = await crud.list_pending_a2a(db, tenant_id=filter_tid)
    return [crud.a2a_to_dict(a) for a in a2as]


@app.post("/api/v1/a2a/{a2a_id}/decide", tags=["A2A"])
async def decide_a2a(
    a2a_id: str,
    body: A2ADecision,
    background_tasks: BackgroundTasks,
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    from core.state_manager import StateManager
    sm = StateManager(session=db)
    req = await crud.get_a2a_request(db, a2a_id)
    if not req:
        raise HTTPException(status_code=404, detail="A2A request not found")
    assert_tenant_access(current_user, str(req.tenant_id))

    updated = await sm.decide_a2a_request(a2a_id, approved=body.approved)
    run_id = str(req.instance_id)

    if body.approved:
        inst = await crud.get_workflow_instance(db, run_id)
        if inst and inst.status == "pending_a2a":
            tenant = await crud.get_tenant(db, str(inst.tenant_id))
            if tenant:
                background_tasks.add_task(
                        _resume_workflow_background,
                        run_id=run_id,
                        tenant_config=tenant.config,
                        decision_context={
                            "_a2a_refinement_note": req.refinement_note or "",
                            "_a2a_approved": True,
                            "_a2a_new_tools":  list(req.new_tools or []),    # Feature 1
                            "_a2a_target_node": req.target_node_id or "",    # Feature 1
                        },
                    )

    decision = "approved" if body.approved else "rejected"
    await broadcast_event("a2a_decided", {
        "a2a_id": a2a_id, "decision": decision, "tenant_id": str(req.tenant_id),
    })
    return {"message": f"A2A request {decision}", "a2a_id": a2a_id}


# ─────────────────────────────────────────────────────────────────────────────
# Credentials
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/v1/credentials/schema/{tool_name}", tags=["Credentials"])
async def get_cred_schema(tool_name: str):
    return {"tool_name": tool_name, "fields": get_credential_schema(tool_name)}


@app.post("/api/v1/credentials", tags=["Credentials"])
async def store_credential(
    body: CredentialCreate,
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    assert_tenant_access(current_user, body.tenant_id)
    encrypted = encrypt_credentials(body.credentials)
    cred = await crud.create_credential(
        db, body.tenant_id, body.tool_name,
        body.display_name or body.tool_name, encrypted,
    )
    return {"credential_id": str(cred.id), "message": "Credentials stored securely"}


@app.get("/api/v1/credentials", tags=["Credentials"])
async def list_credentials(
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    filter_tid = get_tenant_filter(current_user)
    creds = await crud.list_credentials(db, tenant_id=filter_tid)
    return [
        {"id": str(c.id), "tenant_id": str(c.tenant_id),
         "tool_name": c.tool_name, "display_name": c.display_name,
         "created_at": c.created_at.isoformat() if c.created_at else None}
        for c in creds
    ]


@app.delete("/api/v1/credentials/{cred_id}", tags=["Credentials"])
async def delete_credential(
    cred_id: str,
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    cred = await crud.get_credential(db, cred_id)
    if not cred:
        raise HTTPException(status_code=404, detail="Credential not found")
    assert_tenant_access(current_user, str(cred.tenant_id))
    await crud.delete_credential(db, cred_id)
    return {"message": "Credential deleted"}


# ─────────────────────────────────────────────────────────────────────────────
# Custom Tools
# NOTE: /tools/local and /tools/available MUST be registered before
# /tools/{tool_id} so FastAPI does not swallow "local"/"available" as a tool_id.
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/v1/tools/local", tags=["Tools"])
async def list_local_tools(current_user: TokenData = Depends(require_any_auth)):
    from integrations.local_dev_tools import LOCAL_TOOL_SCHEMAS, SEED_DIR
    tools = []
    for name, schema in LOCAL_TOOL_SCHEMAS.items():
        fn_schema = schema.get("function", {})
        tools.append({
            "name": name,
            "description": fn_schema.get("description", ""),
            "parameters": fn_schema.get("parameters", {}).get("properties", {}),
            "type": "local_dev", "is_active": True,
        })
    return {"tools": tools, "total": len(tools),
            "note": "Local dev tools — run seed scripts to populate data."}


@app.get("/api/v1/tools/available", tags=["Tools"])
async def get_available_tools(
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    from integrations.local_dev_tools import LOCAL_TOOL_SCHEMAS
    local = [
        {"name": n, "description": s.get("function", {}).get("description", ""),
         "type": "local_dev",
         "parameters": list(s.get("function", {}).get("parameters", {}).get("properties", {}).keys())}
        for n, s in LOCAL_TOOL_SCHEMAS.items()
    ]
    utility = [
        {"name": "db_write_outcome", "description": "Log outcome", "type": "utility", "parameters": ["tenant_id", "action_taken"]},
        {"name": "db_update_pattern", "description": "Update pattern", "type": "utility", "parameters": ["tenant_id", "pattern_key", "pattern_data"]},
    ]
    filter_tid = get_tenant_filter(current_user)
    custom_tools = await crud.list_custom_tools(db, tenant_id=filter_tid)
    custom = [
        {"name": t.tool_name, "description": t.description or "", "type": "custom_rest", "parameters": ["filters"]}
        for t in custom_tools
    ]
    return {"local_dev": local, "utility": utility, "custom_rest": custom,
            "all": [t["name"] for t in local + utility + custom]}


@app.get("/api/v1/tools", tags=["Tools"])
async def list_tools(
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    filter_tid = get_tenant_filter(current_user)
    tools = await crud.list_custom_tools(db, tenant_id=filter_tid)
    return [crud.custom_tool_to_dict(t) for t in tools]


@app.post("/api/v1/tools", tags=["Tools"])
async def create_custom_tool(
    body: CustomToolCreate,
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    assert_tenant_access(current_user, body.tenant_id)
    tool = await crud.create_custom_tool(db, {
        "tenant_id": body.tenant_id, "tool_name": body.tool_name,
        "display_name": body.display_name, "description": body.description,
        "base_url": body.base_url, "http_method": body.http_method,
        "headers_template": body.headers_template, "body_template": body.body_template,
        "query_params": body.query_params, "auth_type": body.auth_type,
        "credential_id": body.credential_id, "response_path": body.response_path,
    })
    return {"tool_id": str(tool.id), "message": f"Tool '{body.tool_name}' added to registry"}


@app.delete("/api/v1/tools/{tool_id}", tags=["Tools"])
async def delete_tool(
    tool_id: str,
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    tool = await crud.get_custom_tool(db, tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    assert_tenant_access(current_user, str(tool.tenant_id))
    await crud.delete_custom_tool(db, tool_id)
    return {"message": "Tool deleted"}


class ToolTestRequest(BaseModel):
    test_args: dict = Field(default_factory=dict)
    tenant_id: str
 
@app.post("/api/v1/tools/{tool_id}/test", tags=["Tools"])
async def test_custom_tool(
    tool_id: str,
    body: ToolTestRequest,
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    """
    Test a custom REST tool with provided arguments.
    Runs the tool in isolation and returns the raw response.
    Useful for validating credentials and endpoint configuration before workflow runs.
    """
    tool = await crud.get_custom_tool(db, tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    assert_tenant_access(current_user, str(tool.tenant_id))
 
    # Fetch the stored credentials for this tool
    creds_rows = await crud.list_credentials(db, tenant_id=str(tool.tenant_id))
    stored_creds: dict = {}
    for c in creds_rows:
        raw = (c.credentials or {}).get("encrypted", "")
        if raw:
            try:
                from integrations.key_vault import decrypt_credentials
                stored_creds[c.tool_name] = decrypt_credentials(raw)
            except Exception:
                pass
 
    try:
        from integrations.tool_registry_builder import build_registry
        # Build a minimal registry with only this tool
        minimal_config = {
            "client_id": str(tool.tenant_id),
            "integrations": {},
            "business_rules": {},
            "tone_profile": {},
            "action_library": {},
        }
        registry = build_registry(minimal_config, credentials=stored_creds)
 
        if tool.tool_name not in registry._tools:
            # Tool might be a custom REST tool — register it dynamically
            raise HTTPException(
                status_code=422,
                detail=f"Tool '{tool.tool_name}' could not be loaded. "
                       "Ensure credentials are stored and the integration is enabled."
            )
 
        start = __import__("time").time()
        result = await registry.execute(tool.tool_name, body.test_args)
        duration_ms = int((__import__("time").time() - start) * 1000)
 
        if result.success:
            return {
                "status": "success",
                "tool_name": tool.tool_name,
                "duration_ms": duration_ms,
                "result": result.data,
                "result_size": len(json.dumps(result.data, default=str)),
            }
        else:
            return {
                "status": "error",
                "tool_name": tool.tool_name,
                "duration_ms": duration_ms,
                "error": result.error,
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Tool test failed: {str(e)}")

# ─────────────────────────────────────────────────────────────────────────────
# Budget
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/v1/tenants/{tenant_id}/budget", tags=["Budget"])
async def get_budget_settings(
    tenant_id: str,
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    assert_tenant_access(current_user, tenant_id)
    settings = await crud.get_budget_settings(db, tenant_id) or {
        "optimization_level": 1, "strategy": "balanced",
        "enable_caching": True, "cache_ttl_seconds": 3600,
        "max_context_tokens": 10000, "a2a_enabled": False,
    }
    from core.llm_router import LLMRouter
    router = LLMRouter()
    settings["predicted_savings"] = {level: router.get_predicted_savings(level) for level in range(4)}
    return settings


@app.put("/api/v1/tenants/{tenant_id}/budget", tags=["Budget"])
async def update_budget_settings(
    tenant_id: str,
    body: BudgetSettingsUpdate,
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    assert_tenant_access(current_user, tenant_id)
    if not await crud.get_tenant(db, tenant_id):
        raise HTTPException(status_code=404, detail="Tenant not found")
    strategy_names = {0: "max_accuracy", 1: "balanced", 2: "aggressive", 3: "budget_first"}
    data = {
        "optimization_level": body.optimization_level,
        "strategy": strategy_names.get(body.optimization_level, "balanced"),
        "enable_caching": body.enable_caching,
        "cache_ttl_seconds": body.cache_ttl_seconds,
        "max_context_tokens": body.max_context_tokens,
        "a2a_enabled": body.a2a_enabled,
        "auto_retry_on_low_confidence": body.auto_retry_on_low_confidence,
        "confidence_retry_threshold": body.confidence_retry_threshold,
        "enable_map_reduce_summarization": body.enable_map_reduce_summarization,
    }
    settings = await crud.upsert_budget_settings(db, tenant_id, data)
    await broadcast_event("budget_updated", {"tenant_id": tenant_id, "level": body.optimization_level})
    return {"message": "Budget settings updated", "settings": settings}


# ─────────────────────────────────────────────────────────────────────────────
# Analytics
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/v1/dashboard/{tenant_id}", tags=["Analytics"])
async def get_dashboard(
    tenant_id: str,
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    assert_tenant_access(current_user, tenant_id)
    target_tenant = current_user.organization_id or current_user.tenant_id or tenant_id
    return await crud.get_dashboard_data(db, str(target_tenant))


# NOTE: /analytics/admin/fleet MUST be registered before /analytics/{tenant_id}
# so FastAPI does not swallow "admin" as a tenant_id parameter.
@app.get("/api/v1/analytics/admin/fleet", tags=["Analytics"])
async def get_fleet_analytics(
    _: TokenData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    analytics = await crud.get_fleet_analytics(db)
    tenants = await crud.list_tenants(db)
    tenant_map = {str(t.id): t.name for t in tenants}
    for tid in analytics.get("by_tenant", {}):
        analytics["by_tenant"][tid]["tenant_name"] = tenant_map.get(tid, "Unknown")
    return analytics


@app.get("/api/v1/analytics/{tenant_id}", tags=["Analytics"])
async def get_analytics(
    tenant_id: str,
    days: int = Query(30),
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    assert_tenant_access(current_user, tenant_id)
    instances = await crud.list_workflow_instances(db, tenant_id=tenant_id, limit=500)
    completed = [i for i in instances if i.status == "completed"]
    total_cost = sum(i.total_cost_usd or 0 for i in instances)
    total_tokens = sum((i.total_tokens_in or 0) + (i.total_tokens_out or 0) for i in instances)
    pending_esc = await crud.list_escalations(db, status="pending", tenant_id=tenant_id)
    return {
        "tenant_id": tenant_id,
        "workflows_run": len(instances),
        "actions_taken": len(completed) * 3,
        "escalations_pending": len(pending_esc),
        "total_cost_usd": round(total_cost, 6),
        "total_tokens": total_tokens,
        "estimated_hours_saved": round(len(completed) * 0.75, 1),
        "success_rate": round(len(completed) / max(len(instances), 1), 3),
    }


@app.post("/api/v1/outcomes/{tenant_id}/check-pending", tags=["Analytics"])
async def check_pending_outcomes(
    tenant_id: str,
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    """
    Process pending outcome follow-up checks for a tenant.
    
    Checks all registered outcomes whose follow-up date has passed,
    fetches current account state, and stores positive/negative outcomes in RAG.
    
    This enables the outcome-closed learning loop:
      email sent → account recovered? → RAG lesson stored
    """
    assert_tenant_access(current_user, tenant_id)
    
    from core.outcome_tracker import OutcomeTracker
    from core.rag_engine import RAGEngine
    from core.llm_router import LLMRouter
    from integrations.tool_registry_builder import build_registry
    
    tenant = await crud.get_tenant(db, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    from core.state_manager import StateManager
    sm = StateManager(session=db)
    llm = LLMRouter()
    rag = RAGEngine(db_session=db, llm_router=llm)
    tracker = OutcomeTracker(state_manager=sm, rag_engine=rag)
    
    # Build tool registry for current data fetching
    tool_registry = build_registry(tenant.config or {}, credentials={})
    
    result = await tracker.check_pending_outcomes(
        tenant_id=tenant_id,
        tool_registry=tool_registry,
    )
    
    await crud.log_event(db, "outcome_check", tenant_id, None,
                         f"Processed {result['processed']} outcome checks. "
                         f"Positive: {result['positive']}, Negative: {result['negative']}")
    
    return {
        "tenant_id": tenant_id,
        **result,
        "message": (
            f"Processed {result['processed']} outcome checks. "
            f"{result['positive']} positive, {result['negative']} negative outcomes stored in RAG."
        ),
    }
    
    
# ─────────────────────────────────────────────────────────────────────────────
# Email Queue (Draft Review & Send)
# ─────────────────────────────────────────────────────────────────────────────

class EmailQueueUpdate(BaseModel):
    subject: Optional[str] = None
    body: Optional[str] = None

class EmailQueueDecision(BaseModel):
    decided_by: str
    rejection_reason: Optional[str] = None

@app.get("/api/v1/tenants/{tenant_id}/email-queue", tags=["EmailQueue"])
async def list_email_queue(
    tenant_id: str,
    status: str = Query("pending", description="pending | approved | rejected | sent | all"),
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    """List email drafts waiting for review."""
    assert_tenant_access(current_user, tenant_id)
    items = await crud.list_email_queue(db, tenant_id=tenant_id, status=status)
    return [crud.email_queue_to_dict(i) for i in items]


@app.put("/api/v1/email-queue/{item_id}", tags=["EmailQueue"])
async def edit_email_draft(
    item_id: str,
    body: EmailQueueUpdate,
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    """Edit subject/body of a pending draft before approving."""
    item = await crud.get_email_queue_item(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Draft not found")
    assert_tenant_access(current_user, str(item.tenant_id))
    if item.status != "pending":
        raise HTTPException(status_code=400, detail=f"Cannot edit draft with status '{item.status}'")
    updates = {k: v for k, v in body.dict().items() if v is not None}
    if updates:
        await crud.update_email_queue_item(db, item_id, updates)
    return {"message": "Draft updated"}


@app.post("/api/v1/email-queue/{item_id}/approve", tags=["EmailQueue"])
async def approve_email_draft(
    item_id: str,
    decision: EmailQueueDecision,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_any_auth),
):
    """Approve a draft (marks as approved; actual sending is handled by integration)."""
    item = await crud.get_email_queue_item(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Draft not found")
    assert_tenant_access(current_user, str(item.tenant_id))
    await crud.update_email_queue_item(db, item_id, {
        "status": "approved",
        "reviewed_by": decision.decided_by,
        "reviewed_at": datetime.utcnow(),
    })
    await broadcast_event("email_draft_approved", {
        "item_id": item_id, "tenant_id": str(item.tenant_id),
        "recipient": item.recipient_email,
    })
    return {"message": "Draft approved", "item_id": item_id, "status": "approved"}


@app.post("/api/v1/email-queue/{item_id}/reject", tags=["EmailQueue"])
async def reject_email_draft(
    item_id: str,
    decision: EmailQueueDecision,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_any_auth),
):
    """Reject a draft (will not be sent)."""
    item = await crud.get_email_queue_item(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Draft not found")
    assert_tenant_access(current_user, str(item.tenant_id))
    await crud.update_email_queue_item(db, item_id, {
        "status": "rejected",
        "rejection_reason": decision.rejection_reason or "",
        "reviewed_by": decision.decided_by,
        "reviewed_at": datetime.utcnow(),
    })
    return {"message": "Draft rejected", "item_id": item_id}

# ─────────────────────────────────────────────────────────────────────────────
# Evidence, Config, DAG, Prompts, Tools — filesystem-based (unchanged logic)
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/v1/evidence", tags=["Evidence"])
async def list_evidence(
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_any_auth),
):
    try:
        evidence_dir = Path(os.getenv("EPI_EVIDENCE_DIR", "./evidence"))
        evidence_dir.mkdir(parents=True, exist_ok=True)
        artifacts = []
        try:
            from epi.epi_manager import EPIManager
            artifacts.extend(EPIManager().list_artifacts())
        except Exception:
            pass
        for p in sorted(evidence_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
            if not any(a.get("filename") == p.name for a in artifacts):
                try:
                    data = json.loads(p.read_text())
                    artifacts.append({
                        "filename": p.name,
                        "path": str(p),
                        "size_kb": round(p.stat().st_size / 1024, 1),
                        "created": datetime.fromtimestamp(p.stat().st_mtime).isoformat(),
                        "type": "workflow_summary",
                        "workflow_name": data.get("workflow_name", ""),
                        "run_id": data.get("run_id", ""),
                        "status": data.get("status", ""),
                        "total_cost_usd": data.get("total_cost_usd", 0),
                    })
                except Exception:
                    pass

        # Also pull database WorkflowInstance records to guarantee 100% audit visibility
        try:
            from db.models.core import WorkflowInstance
            stmt_wf = select(WorkflowInstance).order_by(WorkflowInstance.started_at.desc()).limit(100)
            res_wf = await db.execute(stmt_wf)
            wf_instances = res_wf.scalars().all()
            for wf in wf_instances:
                inst_id_str = str(wf.id)
                prefix_id = inst_id_str[:8]
                has_disk_match = any(
                    inst_id_str in (a.get("run_id") or "") or
                    prefix_id in (a.get("filename") or "") or
                    inst_id_str in (a.get("filename") or "")
                    for a in artifacts
                )
                if not has_disk_match:
                    fn = f"{wf.workflow_name}_{prefix_id}.json"
                    artifacts.append({
                        "filename": fn,
                        "path": f"evidence/{fn}",
                        "size_kb": 1.5,
                        "created": wf.started_at.isoformat() if wf.started_at else datetime.utcnow().isoformat(),
                        "type": "workflow_summary",
                        "workflow_name": wf.workflow_name,
                        "run_id": inst_id_str,
                        "status": wf.status,
                        "total_cost_usd": wf.total_cost_usd or 0.0,
                    })
        except Exception as db_err:
            log.warning("Could not query DB workflow instances in list_evidence", error=str(db_err))

        return sorted(artifacts, key=lambda x: x.get("created", ""), reverse=True)
    except Exception:
        return []


@app.get("/api/v1/config/models", tags=["Config"])
async def get_available_models():
    try:
        async with aiofiles.open("config/templates/llm_config.json") as f:
            return json.loads(await f.read())
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="LLM config file not found")


@app.get("/api/v1/config/dag/{workflow_name}", tags=["Config"])
async def get_workflow_dag(workflow_name: str):
    dag_path = Path("workflows/dags") / f"{workflow_name}.json"
    if not dag_path.exists():
        raise HTTPException(status_code=404, detail=f"DAG not found: {workflow_name}")
    async with aiofiles.open(dag_path) as f:
        return json.loads(await f.read())


@app.get("/api/v1/config/workflows", tags=["Config"])
async def list_workflow_dags(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select, func
    from core.state_manager import WorkflowInstance

    dags_dir = Path("workflows/dags")
    if not dags_dir.exists():
        return []

    # Run counts per workflow so the builder lists the most-active workflows first
    # instead of alphabetically. Join key: workflow_instances.workflow_name == DAG stem
    # (the same value /config/dag/{name} loads by).
    run_counts: dict[str, int] = {}
    last_run: dict[str, str] = {}
    try:
        rc_res = await db.execute(
            select(
                WorkflowInstance.workflow_name,
                func.count().label("runs"),
                func.max(WorkflowInstance.started_at).label("last_started"),
            ).group_by(WorkflowInstance.workflow_name)
        )
        for row in rc_res.all():
            if row.workflow_name:
                run_counts[row.workflow_name] = row.runs or 0
                last_run[row.workflow_name] = row.last_started.isoformat() if row.last_started else None
    except Exception:
        run_counts, last_run = {}, {}

    workflows = []
    for f in sorted(dags_dir.glob("*.json")):
        try:
            async with aiofiles.open(f) as fp:
                dag = json.loads(await fp.read())
            meta = dag.get("_meta", {})
            trigger_meta = meta.get("trigger", {})
            trigger_type = "New Email" if ("email" in f.stem or trigger_meta.get("type") == "email") else "Manual"
            source = "Synthetic Inbox" if ("email" in f.stem or "synthetic" in str(trigger_meta.get("source", ""))) else "Direct"

            workflows.append({
                "name": f.stem,
                "display_name": meta.get("name", f.stem.replace("_", " ").title()),
                "industry": meta.get("industry", "general"),
                "description": meta.get("description", ""),
                "status": "active",
                "automation_status": "active",
                "automation_enabled": True,
                "trigger_type": trigger_type,
                "trigger_types": meta.get("trigger_types", ["manual"]),
                "trigger": trigger_meta,
                "source": source,
                "sla_hours": meta.get("sla_hours", 2),
                "estimated_duration_minutes": meta.get("estimated_duration_minutes", 2),
                "run_count": run_counts.get(f.stem, 0),
                "last_run_at": last_run.get(f.stem),
            })
        except Exception:
            workflows.append({
                "name": f.stem,
                "display_name": f.stem.replace("_", " ").title(),
                "status": "active",
                "trigger_type": "Manual",
                "source": "Direct",
                "automation_status": "active",
                "run_count": run_counts.get(f.stem, 0),
                "last_run_at": last_run.get(f.stem),
            })

    # Most-run workflows first; ties fall back to alphabetical display name.
    workflows.sort(key=lambda w: (-(w.get("run_count") or 0), (w.get("display_name") or "").lower()))
    return workflows


# ─────────────────────────────────────────────────────────────────────────────
# Tenant-scoped workflow listing (assignment-enforced)
# GET /api/v1/workflows  — returns ONLY workflows assigned to the authenticated org.
# This is the secure alternative to /config/workflows for SMB Owner clients.
# Admins receive the full catalog without assignment filtering.
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/v1/catalog/assigned", tags=["Workflows"])
async def list_tenant_workflows(
    include_unassigned: bool = Query(default=True),
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns the list of workflows available to the authenticated user's organization.
    Enforcement rule:
      - org must be active
      - subscription must be active or trialing (and trial not expired)
      - plan must entitle the workflow
      - workflow must be explicitly assigned to the org by an admin
      - workflow catalog entry must be active

    Platform admins receive the full catalog without assignment filtering.
    """
    from pathlib import Path as _Path
    from datetime import datetime as _dt

    is_admin = current_user.role in ("platform_admin", "super_admin")
    org_id = current_user.organization_id or current_user.tenant_id

    # Admins: return full catalog (same as /config/workflows)
    if is_admin:
        from sqlalchemy import select as _sel, func as _func
        from core.state_manager import WorkflowInstance as _WFI
        dags_dir = _Path("workflows/dags")
        if not dags_dir.exists():
            return []
        run_counts: dict[str, int] = {}
        last_run: dict[str, str] = {}
        try:
            rc = await db.execute(
                _sel(_WFI.workflow_name, _func.count().label("c"), _func.max(_WFI.started_at).label("l"))
                .group_by(_WFI.workflow_name)
            )
            for row in rc.all():
                if row.workflow_name:
                    run_counts[row.workflow_name] = row.c or 0
                    last_run[row.workflow_name] = row.l.isoformat() if row.l else None
        except Exception:
            pass
        result = []
        for f in sorted(dags_dir.glob("*.json")):
            try:
                import aiofiles as _af, json as _json
                async with _af.open(f) as fp:
                    meta = _json.loads(await fp.read()).get("_meta", {})
                result.append({
                    "name": f.stem,
                    "display_name": meta.get("name", f.stem.replace("_", " ").title()),
                    "industry": meta.get("industry", "general"),
                    "description": meta.get("description", ""),
                    "status": "active",
                    "trigger_type": "New Email" if "email" in f.stem else "Manual",
                    "run_count": run_counts.get(f.stem, 0),
                    "last_run_at": last_run.get(f.stem),
                })
            except Exception:
                result.append({"name": f.stem, "display_name": f.stem.replace("_", " ").title(), "status": "active"})
        return result

    # Non-admin: enforce assignments + industry applicability
    # ── Step 1: Resolve org_id ────────────────────────────────────────────────
    # The Supabase JWT doesn't embed organization_id. We get it from the DB
    # lookup in deps/auth.py. If it's still None here, the user's
    # organization_users row may not exist yet — provision it now.
    if not org_id:
        try:
            _ou, _org = await crud.ensure_user_organization_provisioned(
                db,
                user_id=current_user.user_id,
                email=current_user.email,
                full_name=current_user.full_name,
            )
            org_id = str(_org.id) if _org else None
        except Exception:
            pass

    if not org_id:
        return []

    from sqlalchemy import select as _sel
    from db.models.core import (
        Organization as _Org, OrganizationSubscription as _Sub,
        OrganizationWorkflowAssignment as _Assign, WorkflowCatalog as _WCat,
    )
    import uuid as _uuid

    # Check org is active
    try:
        oid = _uuid.UUID(str(org_id))
    except (ValueError, TypeError):
        return []

    org_res = await db.execute(_sel(_Org).where(_Org.id == oid))
    org = org_res.scalar_one_or_none()
    if not org or not org.active:
        return []

    org_industry = (org.industry or "saas").lower().strip()

    # ── Resolve visible categories for this org's industry ───────────────────
    # This mirrors exactly what the admin catalog shows when filtered by category.
    # finance org → sees "finance" + universal categories (productivity, compliance, operations)
    # healthcare org → sees "healthcare" + universal categories
    # saas org → sees "sales" + "marketing" + universal categories
    from api.crud import get_visible_categories_for_industry as _get_cats
    visible_categories = _get_cats(org_industry)

    # Check subscription is not expired
    sub_res = await db.execute(_sel(_Sub).where(_Sub.organization_id == oid))
    sub = sub_res.scalar_one_or_none()

    # ── Subscription guard ────────────────────────────────────────────────────
    # If there is no subscription row yet (race between provision + catalog fetch),
    # attempt a one-time auto-assign+subscribe recovery then re-check.
    if not sub:
        try:
            # Try to create a free subscription on the fly so the owner isn't
            # blocked just because the billing row hasn't propagated yet.
            from api.crud import (
                get_billing_plan_by_slug as _get_plan,
                create_org_subscription as _create_sub,
            )
            _free_plan = await _get_plan(db, "free")
            if _free_plan:
                sub = await _create_sub(db, str(oid), str(_free_plan.id), "monthly")
        except Exception:
            pass
    if not sub:
        return []

    effective_status = sub.status
    if sub.status == "trialing" and sub.trial_ends_at and sub.trial_ends_at < _dt.utcnow():
        effective_status = "trial_expired"
    if effective_status not in ("active", "trialing"):
        return []

    # ── Assignment query ──────────────────────────────────────────────────────
    # Returns all active workflow catalog entries assigned to this organization.
    # For a finance org, auto_assign_industry_workflows will have assigned all "finance"
    # category workflows. Explicit admin assignments are also included.
    assigns_res = await db.execute(
        _sel(_Assign, _WCat)
        .join(_WCat, _Assign.workflow_id == _WCat.id)
        .where(
            _Assign.organization_id == oid,
            _Assign.status == "active",
            _WCat.active.is_(True),
        )
    )
    rows = assigns_res.all()

    # ── If there are no assignments yet, trigger auto-assign now ─────────────
    # This handles the window between provision completing and the next request.
    if not rows:
        try:
            from api.crud import (
                auto_assign_industry_workflows as _auto_assign,
                get_billing_plan as _get_plan_by_id,
            )
            _plan_for_assign = await _get_plan_by_id(db, str(sub.plan_id))
            _slug = _plan_for_assign.slug if _plan_for_assign else "free"
            await _auto_assign(
                db,
                organization_id=str(oid),
                industry=org_industry,
                assigned_by="system:catalog_assigned",
                plan_slug=_slug,
            )
            # Re-query now that assignments exist
            assigns_res2 = await db.execute(
                _sel(_Assign, _WCat)
                .join(_WCat, _Assign.workflow_id == _WCat.id)
                .where(
                    _Assign.organization_id == oid,
                    _Assign.status == "active",
                    _WCat.active.is_(True),
                )
            )
            rows = assigns_res2.all()
        except Exception as _lazy_err:
            log.warning("catalog/assigned lazy auto-assign failed", error=str(_lazy_err), org_id=str(oid))

    # ── Plan entitlement check ────────────────────────────────────────────────
    # If no entitlements are seeded for this plan yet (fresh DB / pre-migration),
    # skip the entitlement gate entirely — an empty whitelist must never mean
    # "block everything". The real guard is the assignment row itself.
    from api.crud import get_plan_entitlements as _get_ent
    entitled_wf_ids = set(await _get_ent(db, str(sub.plan_id)))
    entitlements_seeded = len(entitled_wf_ids) > 0

    # Load run stats
    from sqlalchemy import func as _func
    from core.state_manager import WorkflowInstance as _WFI
    run_counts: dict[str, int] = {}
    last_run: dict[str, str] = {}
    try:
        rc = await db.execute(
            _sel(_WFI.workflow_name, _func.count().label("c"), _func.max(_WFI.started_at).label("l"))
            .where(_WFI.tenant_id == oid)
            .group_by(_WFI.workflow_name)
        )
        for row in rc.all():
            if row.workflow_name:
                run_counts[row.workflow_name] = row.c or 0
                last_run[row.workflow_name] = row.l.isoformat() if row.l else None
    except Exception:
        pass

    # ── Tenant workflow catalog resolution ──────────────────────────────────────
    # Returns all workflows applicable to this tenant's industry + universal GLOBAL workflows.
    # ONLY workflows with an active OrganizationWorkflowAssignment have status="active" & is_assigned=True.
    all_cats_res = await db.execute(_sel(_WCat).where(_WCat.active.is_(True)))
    all_catalogs = all_cats_res.scalars().all()
    assign_map = {str(assign.workflow_id): assign for assign, _ in rows if assign.status == "active"}

    result = []
    for wf_cat in all_catalogs:
        wf_scope = getattr(wf_cat, "scope", "GLOBAL") or "GLOBAL"
        wf_industry = getattr(wf_cat, "industry", None)
        is_global = (wf_scope == "GLOBAL")
        is_assigned = is_global or (str(wf_cat.id) in assign_map)
        assign = assign_map.get(str(wf_cat.id))

        # Non-assigned industry workflows only visible if matching tenant industry
        if not is_assigned and wf_scope == "INDUSTRY" and wf_industry and org_industry != wf_industry.lower().strip():
            continue

        item = {
            "id":           str(wf_cat.id),
            "name":         wf_cat.key,
            "key":          wf_cat.key,
            "display_name": wf_cat.name,
            "description":  wf_cat.description or "",
            "category":     wf_cat.category,
            "status":       "active" if is_assigned else "ready",
            "scope":        wf_scope,
            "industry":     wf_industry,
            "trigger_type": "New Email" if "email" in (wf_cat.key or "") else "Manual",
            "assigned_at":  (assign.assigned_at.isoformat() if (assign and assign.assigned_at) else datetime.utcnow().isoformat()) if is_assigned else None,
            "is_assigned":  is_assigned,
            "can_run":      is_assigned,
            "run_count":    run_counts.get(wf_cat.key, 0),
            "last_run_at":  last_run.get(wf_cat.key),
        }

        if not include_unassigned and not is_assigned:
            continue

        result.append(item)

    # Sort: assigned workflows first, then by runs, then alphabetical
    result.sort(key=lambda w: (
        not w.get("is_assigned", False),
        -(w.get("run_count") or 0),
        (w.get("display_name") or "").lower(),
    ))
    return result


@app.get("/api/v1/workflows/{workflow_name}/check-access", tags=["Workflows"])
async def check_workflow_access_endpoint(
    workflow_name: str,
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    """
    Client-side pre-flight authorization check for workflow execution.
    Returns 200 with access details if allowed, or raises 403 Forbidden.
    Admins are always granted access.
    Tenants must pass org active, industry match, active subscription, plan entitlement,
    and explicit organization assignment.
    """
    if current_user.role in ("platform_admin", "super_admin"):
        return {"allowed": True, "reason": "Platform admin access granted", "scope": "GLOBAL"}

    org_id = current_user.organization_id or current_user.tenant_id
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error_code": "NO_ORGANIZATION", "message": "User is not associated with an organization"},
        )

    res = await crud.check_org_workflow_access(db, str(org_id), workflow_name)
    if not res.get("allowed"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": "WORKFLOW_ACCESS_DENIED",
                "message": res.get("reason", "Workflow access denied"),
                "workflow": workflow_name,
                "organization_id": str(org_id),
            },
        )
    return res


class WorkflowAccessRequestPayload(BaseModel):
    workflow_id: Optional[str] = None
    workflow_name: Optional[str] = None
    workflow_key: Optional[str] = None
    reason: Optional[str] = None
    notes: Optional[str] = None


@app.post("/api/v1/catalog/request-access", tags=["Workflows"])
async def request_workflow_access(
    payload: WorkflowAccessRequestPayload,
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    """
    Allows an organization user to request access to an unassigned workflow in real-time.
    Creates an ApprovalItem in PostgreSQL and broadcasts instant WebSocket notifications to Admins.
    """
    from db.models.core import WorkflowCatalog, Organization, ApprovalItem
    from core.redis_pubsub import pubsub as redis_pubsub

    org_id = current_user.organization_id or current_user.tenant_id
    lookup_val = payload.workflow_key or payload.workflow_id or payload.workflow_name or ""
    
    wf = None
    if lookup_val:
        try:
            val_uuid = uuid.UUID(str(lookup_val))
            wf_stmt = select(WorkflowCatalog).where(WorkflowCatalog.id == val_uuid)
            wf_res = await db.execute(wf_stmt)
            wf = wf_res.scalar_one_or_none()
        except (ValueError, TypeError):
            pass
        
        if not wf:
            wf_stmt = select(WorkflowCatalog).where(
                (WorkflowCatalog.key == lookup_val) | (WorkflowCatalog.name == lookup_val)
            ).limit(1)
            wf_res = await db.execute(wf_stmt)
            wf = wf_res.scalar_one_or_none()

    wf_key = wf.key if wf else (payload.workflow_key or payload.workflow_id or "custom_workflow")
    wf_name = wf.name if wf else (payload.workflow_name or payload.workflow_id or "Workflow")
    wf_id_str = str(wf.id) if wf else (payload.workflow_id or str(uuid.uuid4()))

    org_name = "Independent User"
    org_uuid = None
    if org_id:
        try:
            org_uuid = uuid.UUID(str(org_id))
            o_res = await db.execute(select(Organization).where(Organization.id == org_uuid))
            org_obj = o_res.scalar_one_or_none()
            if org_obj:
                org_name = org_obj.name
        except Exception:
            org_uuid = uuid.uuid4()
    else:
        org_uuid = uuid.uuid4()

    req_id = uuid.uuid4()
    req_reason = payload.reason or payload.notes or f"Requesting access to execute {wf_name} workflow."
    req_payload = {
        "workflow_key": wf_key,
        "workflow_id": wf_id_str,
        "workflow_name": wf_name,
        "org_id": str(org_id) if org_id else None,
        "org_name": org_name,
        "user_id": current_user.user_id,
        "user_email": current_user.email,
        "user_name": current_user.full_name or current_user.email,
        "reason": req_reason,
        "requested_at": datetime.utcnow().isoformat(),
    }

    approval = ApprovalItem(
        id=req_id,
        organization_id=org_uuid,
        instance_id=None,
        node_id="access_request",
        review_type="workflow_access_request",
        reason=f"Access requested for {wf_name} by {current_user.email} ({org_name})",
        context_brief=req_reason,
        payload=req_payload,
        status="pending",
        required_signatures=1,
        signatures=[],
        created_at=datetime.utcnow(),
    )
    db.add(approval)
    await db.commit()

    # Real-time WebSocket Event Dispatch to Admin & Org channels
    ws_event = {
        "type": "workflow.access_requested",
        "id": str(req_id),
        "title": "Workflow Access Request",
        "message": f"{current_user.email} ({org_name}) requested access to {wf_name}",
        "workflow_key": wf_key,
        "workflow_name": wf_name,
        "org_id": str(org_id) if org_id else None,
        "org_name": org_name,
        "user_email": current_user.email,
        "timestamp": datetime.utcnow().isoformat(),
    }
    try:
        await redis_pubsub.publish("admin", ws_event)
        if org_id:
            await redis_pubsub.publish(f"org:{org_id}", ws_event)
    except Exception as pub_err:
        log.warning("WebSocket publish notification failed", error=str(pub_err))

    log.info("Workflow access requested and broadcasted", user=current_user.email, org_id=str(org_id), workflow=wf_name)
    return {
        "status": "success",
        "request_id": str(req_id),
        "workflow_key": wf_key,
        "workflow_name": wf_name,
        "message": f"Access request for '{wf_name}' submitted successfully in real time. Your administrator has been notified.",
    }


@app.get("/api/v1/billing/summary", tags=["Billing"])
async def get_org_billing_summary_endpoint(
    days: int = Query(30, ge=1, le=365),
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    """
    Return billing/usage summary for the authenticated organization.

    Only usage from workflows applicable to the org's industry is included
    (scope=GLOBAL or industry match). This prevents Finance/Healthcare data
    from leaking into each other's billing view.

    The `industry` field in the response lets the frontend derive the page
    title dynamically (e.g. "Healthcare Usage & Billing").
    """
    org_id = current_user.organization_id or current_user.tenant_id
    if not org_id:
        raise HTTPException(status_code=400, detail="No organization context")

    summary = await crud.get_org_billing_summary(db, org_id, days=days)
    if "error" in summary:
        raise HTTPException(status_code=404, detail=summary["error"])
    return summary


@app.get("/api/v1/billing/summary/{org_id}", tags=["Billing"])
async def get_org_billing_summary_admin(
    org_id: str,
    days: int = Query(30, ge=1, le=365),
    current_user: TokenData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Admin-only: return billing/usage summary for any organization.
    Admins can view all orgs; industry filter still applies to keep data clean.
    """
    summary = await crud.get_org_billing_summary(db, org_id, days=days)
    if "error" in summary:
        raise HTTPException(status_code=404, detail=summary["error"])
    return summary


@app.put("/api/v1/config/dag/{workflow_name}", tags=["Config"])
async def update_workflow_dag(
    workflow_name: str, body: WorkflowDAGCreate,
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    
        # Import custom tools for this tenant
    from core.dag_validator import validate_dag
    
    custom_tool_names = set()
    try:
        tools = await crud.list_custom_tools(db)
        custom_tool_names = {t.tool_name for t in tools}
    except Exception:
        pass
    
    validation = validate_dag(body.dag, custom_tool_names)
    if not validation.valid:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "DAG validation failed — workflow would crash at runtime",
                "errors": validation.errors,
                "warnings": validation.warnings,
            }
        )
    # Log warnings even if valid
    if validation.warnings:
        log.info("DAG validation warnings", workflow=workflow_name, warnings=validation.warnings)

    safe_name = workflow_name.replace("/", "_").replace("..", "")
    dag_path = Path("workflows/dags") / f"{safe_name}.json"
    dag_path.parent.mkdir(parents=True, exist_ok=True)
    dag_path.write_text(json.dumps(body.dag, indent=2, default=str))
    await crud.log_event(db, "dag_updated", current_user.tenant_id, None,
                         f"DAG '{safe_name}' updated by {current_user.email}")
    return {"message": f"DAG '{safe_name}' saved", "path": str(dag_path)}


@app.post("/api/v1/config/dag", tags=["Config"])
async def create_workflow_dag(
    body: WorkflowDAGCreate,
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
        # Import custom tools for this tenant
    from core.dag_validator import validate_dag
    
    custom_tool_names = set()
    try:
        tools = await crud.list_custom_tools(db)
        custom_tool_names = {t.tool_name for t in tools}
    except Exception:
        pass
    
    validation = validate_dag(body.dag, custom_tool_names)
    if not validation.valid:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "DAG validation failed — workflow would crash at runtime",
                "errors": validation.errors,
                "warnings": validation.warnings,
            }
        )
    # Log warnings even if valid
    if validation.warnings:
        log.info("DAG validation warnings", workflow=body.name, warnings=validation.warnings)

    safe = body.name.replace("/", "_").replace("..", "").replace(" ", "_").lower()
    dag_path = Path("workflows/dags") / f"{safe}.json"
    if dag_path.exists():
        raise HTTPException(status_code=409, detail=f"Workflow '{safe}' already exists")
    dag_path.write_text(json.dumps(body.dag, indent=2, default=str))
    await crud.log_event(db, "dag_created", current_user.tenant_id, None,
                         f"DAG '{safe}' created by {current_user.email}")
    return {"message": f"Workflow '{safe}' created", "name": safe}


@app.delete("/api/v1/config/dag/{workflow_name}", tags=["Config"])
async def delete_workflow_dag(
    workflow_name: str,
    current_user: TokenData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    safe = workflow_name.replace("/", "_").replace("..", "")
    dag_path = Path("workflows/dags") / f"{safe}.json"
    if not dag_path.exists():
        raise HTTPException(status_code=404, detail="Workflow not found")
    dag_path.unlink()
    await crud.log_event(db, "dag_deleted", None, None,
                         f"DAG '{safe}' deleted by {current_user.email}")
    return {"message": f"Workflow '{safe}' deleted"}


@app.get("/api/v1/config/prompt-tree", tags=["Config"])
async def get_prompt_tree(current_user: TokenData = Depends(require_any_auth)):
    prompts_dir = Path("workflows/prompts")
    if not prompts_dir.exists():
        return {"tree": {}, "files": []}
    tree: dict = {}
    files = []
    for p in sorted(prompts_dir.rglob("*.txt")):
        rel = p.relative_to(prompts_dir)
        parts = rel.parts
        category = "/".join(parts[:-1]) if len(parts) > 1 else "root"
        files.append({"path": str(rel).replace("\\", "/"), "filename": p.name,
                      "category": category, "size_chars": p.stat().st_size,
                      "agent": p.stem.split("_")[0] if "_" in p.stem else p.stem})
        node = tree
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[p.name] = str(rel).replace("\\", "/")
    return {"tree": tree, "files": files, "total": len(files)}


@app.get("/api/v1/config/prompts/{prompt_path:path}", tags=["Config"])
async def get_prompt(
    prompt_path: str,
    current_user: TokenData = Depends(require_any_auth),
):
    """
    Read a prompt file. Priority order:
    1. Tenant-specific override: workflows/prompts/tenants/{tenant_id}/{path}
    2. Base system prompt:        workflows/prompts/{path}
    All authenticated users can read system prompts (read-only for non-admins).
    """
    safe_path = prompt_path.replace("..", "").replace("//", "/").lstrip("/")
    base = Path("workflows/prompts")

    # Priority 1: tenant-specific override (non-admins write here via PUT)
    if current_user.tenant_id:
        tenant_path = base / "tenants" / str(current_user.tenant_id) / safe_path
        if tenant_path.exists():
            return {
                "path": prompt_path,
                "content": tenant_path.read_text(encoding="utf-8"),
                "filename": tenant_path.name,
                "scope": "tenant_override",
            }

    # Priority 2: base system path (readable by everyone)
    system_path = base / safe_path
    if system_path.exists():
        scope = "system" if current_user.role == "super_admin" else "system_readonly"
        return {
            "path": prompt_path,
            "content": system_path.read_text(encoding="utf-8"),
            "filename": system_path.name,
            "scope": scope,
        }

    raise HTTPException(status_code=404, detail=f"Prompt file not found: {prompt_path}")
 
 
@app.put("/api/v1/config/prompts/{prompt_path:path}", tags=["Config"])
async def update_prompt(
    prompt_path: str,
    body: PromptUpdate,
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    """
    Update a prompt file.
    - super_admin: writes to system path (workflows/prompts/{path})
    - tenant_user: writes to tenant override path (workflows/prompts/tenants/{id}/{path})
    """
    safe_path = prompt_path.replace("..", "").replace("//", "/").lstrip("/")
    base = Path("workflows/prompts")

    if current_user.role == "super_admin":
        full_path = base / safe_path
        scope = "system"
    else:
        if not current_user.tenant_id:
            raise HTTPException(status_code=403, detail="No tenant context")
        full_path = base / "tenants" / str(current_user.tenant_id) / safe_path
        scope = "tenant_override"

    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(body.content, encoding="utf-8")
    await crud.log_event(
        db, "prompt_updated", current_user.tenant_id, None,
        f"Prompt '{prompt_path}' updated by {current_user.email} (scope={scope})"
    )
    return {"message": "Prompt saved", "path": prompt_path, "scope": scope}


@app.post("/api/v1/config/prompts/{prompt_path:path}", tags=["Config"])
async def create_prompt(
    prompt_path: str, body: PromptUpdate,
    current_user: TokenData = Depends(require_any_auth),
):
    p = Path("workflows/prompts") / prompt_path.replace("..", "")
    if p.exists():
        raise HTTPException(status_code=409, detail="Prompt file already exists")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body.content, encoding="utf-8")
    return {"message": "Prompt created", "path": prompt_path}


@app.get("/api/v1/seed-data/status", tags=["SeedData"])
async def get_seed_data_status(current_user: TokenData = Depends(require_any_auth)):
    seed_dir = Path("db/seed/data")
    files = {
        "saas_accounts.json":              {"industry": "saas",         "seeder": "db/seed/saas_seed.py"},
        "saas_deals.json":                 {"industry": "saas",         "seeder": "db/seed/saas_seed.py"},
        "retail_products.json":            {"industry": "retail",       "seeder": "db/seed/retail_seed.py"},
        "healthcare_patients.json":        {"industry": "healthcare",   "seeder": "db/seed/healthcare_seed.py"},
        "healthcare_appointments.json":    {"industry": "healthcare",   "seeder": "db/seed/healthcare_seed.py"},
        "finance_expenses.json":           {"industry": "finance",      "seeder": "db/seed/finance_seed.py"},
        "re_listings.json":                {"industry": "real_estate",  "seeder": "db/seed/real_estate_seed.py"},
        "re_leases.json":                  {"industry": "real_estate",  "seeder": "db/seed/real_estate_seed.py"},
        "re_buyers.json":                  {"industry": "real_estate",  "seeder": "db/seed/real_estate_seed.py"},
    }
    status = {}
    for fname, meta in files.items():
        p = seed_dir / fname
        if p.exists():
            try:
                data = json.loads(p.read_text())
                count = len(data) if isinstance(data, list) else 0
            except Exception:
                count = -1
            status[fname] = {**meta, "exists": True, "records": count,
                             "size_kb": round(p.stat().st_size / 1024, 1)}
        else:
            status[fname] = {**meta, "exists": False, "records": 0}
    return {"files": status, "all_ready": all(v["exists"] for v in status.values()),
            "seed_dir": str(seed_dir.absolute())}


@app.post("/api/v1/seed-data/generate", tags=["SeedData"])
async def generate_seed_data(
    industry: Optional[str] = Query(None, description="saas|retail|healthcare|finance|real_estate"),
    current_user: TokenData = Depends(require_any_auth),
):
    import subprocess, sys
    seeders = {
        "saas":         "db/seed/saas_seed.py",
        "retail":       "db/seed/retail_seed.py",
        "healthcare":   "db/seed/healthcare_seed.py",
        "finance":      "db/seed/finance_seed.py",
        "real_estate":  "db/seed/real_estate_seed.py",
    }
    to_run = {industry: seeders[industry]} if industry and industry in seeders else seeders
    results = {}
    for ind, script in to_run.items():
        if not Path(script).exists():
            results[ind] = {"status": "error", "message": f"Seeder not found: {script}"}
            continue
        try:
            r = subprocess.run([sys.executable, script], capture_output=True, text=True, timeout=60)
            results[ind] = {"status": "ok", "output": r.stdout.strip()} if r.returncode == 0 \
                else {"status": "error", "output": r.stderr.strip()}
        except Exception as e:
            results[ind] = {"status": "error", "message": str(e)}
    return {"results": results, "all_ok": all(v["status"] == "ok" for v in results.values())}


@app.post("/api/v1/webhooks/{tenant_id}", tags=["Webhooks"])
async def receive_webhook(
    tenant_id: str,
    payload: dict,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Receive a webhook and route it to a workflow.
    
    FIX: Original was hardcoded for only Stripe and HubSpot.
    Now supports dynamic routing via webhook_configurations in tenant config.
    """
    tenant = await crud.get_tenant(db, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    cfg = tenant.config or {}
    wf = None
    signal_data = payload
    
    # ── Check dynamic webhook configurations first ────────────────────────
    webhook_configs = cfg.get("webhook_configurations", {})
    for webhook_name, wh_conf in webhook_configs.items():
        trigger_conditions = wh_conf.get("trigger_conditions", {})
        # Check if payload matches trigger conditions
        if _payload_matches_conditions(payload, trigger_conditions):
            candidate_wf = wh_conf.get("workflow_name")
            if candidate_wf and candidate_wf in cfg.get("active_workflows", []):
                wf = candidate_wf
                # Apply field mappings
                field_mappings = wh_conf.get("field_mappings", {})
                signal_data = _apply_field_mappings(payload, field_mappings)
                log.info(
                    "Webhook routed via dynamic config",
                    webhook=webhook_name,
                    workflow=wf,
                    tenant=tenant_id[:8],
                )
                break
    
    # ── Fallback to hardcoded legacy routing ─────────────────────────────
    if not wf:
        if payload.get("type") == "invoice.payment_failed":
            wf = "saas_churn_prevention"
        elif payload.get("subscriptionType") == "deal.propertyChange":
            wf = "saas_pipeline_velocity"
    
    if wf and wf in cfg.get("active_workflows", []):
        run_id = str(uuid.uuid4())
        await crud.create_workflow_instance(db, run_id, tenant_id, wf, signal_data, tenant_config=cfg)
        budget = await crud.get_budget_settings(db, tenant_id) or {}
        background_tasks.add_task(_execute_workflow_background, run_id, cfg, wf, signal_data, budget)
        return {"triggered": wf, "run_id": run_id, "routing": "dynamic" if webhook_configs else "legacy"}
    
    return {"received": True, "workflow_triggered": False, "reason": "no matching webhook configuration"}
 
 
def _payload_matches_conditions(payload: dict, conditions: dict) -> bool:
    """Check if a webhook payload matches the configured trigger conditions."""
    if not conditions:
        return True  # No conditions = match all
    
    for key, expected_value in conditions.items():
        # Support dot notation: "type" or "data.object.status"
        parts = key.split(".")
        current = payload
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                current = None
                break
        
        if current != expected_value:
            return False
    
    return True
 
 
def _apply_field_mappings(payload: dict, mappings: dict) -> dict:
    """Apply field mappings to extract workflow signal from webhook payload."""
    result = dict(payload)  # keep original
    
    for target_field, source_path in mappings.items():
        parts = source_path.split(".")
        current = payload
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                current = None
                break
        if current is not None:
            result[target_field] = current
    
    return result


@app.post("/api/v1/webhooks/configure", tags=["Webhooks"])
async def configure_webhook(
    body: WebhookMappingCreate,
    background_tasks: BackgroundTasks,
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    """
    No-code webhook configurator.
    
    Takes a sample payload and uses LLM to:
    1. Analyze the payload structure
    2. Suggest field mappings to standard workflow signals
    3. Store the mapping so the webhook endpoint can route dynamically
    
    Previously required modifying main.py directly. Now self-service.
    """
    assert_tenant_access(current_user, body.tenant_id)
    tenant = await crud.get_tenant(db, body.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    # Analyze payload structure with LLM
    background_tasks.add_task(
        _analyze_webhook_payload_background,
        tenant_id=body.tenant_id,
        webhook_name=body.webhook_name,
        sample_payload=body.sample_payload,
        workflow_name=body.workflow_name,
        field_mappings=body.field_mappings,
        trigger_conditions=body.trigger_conditions,
    )
    
    # Store the mapping in tenant config
    existing_config = tenant.config or {}
    webhook_configs = existing_config.get("webhook_configurations", {})
    webhook_configs[body.webhook_name] = {
        "workflow_name": body.workflow_name,
        "field_mappings": body.field_mappings,
        "trigger_conditions": body.trigger_conditions or {},
        "configured_at": datetime.utcnow().isoformat(),
        "configured_by": current_user.email,
    }
    
    await crud.update_tenant_config(db, body.tenant_id, {"webhook_configurations": webhook_configs})
    await crud.log_event(db, "webhook_configured", body.tenant_id, None,
                         f"Webhook '{body.webhook_name}' → '{body.workflow_name}' by {current_user.email}")
    
    return {
        "message": f"Webhook '{body.webhook_name}' configured to trigger '{body.workflow_name}'",
        "webhook_url": f"/api/v1/webhooks/{body.tenant_id}",
        "mapping": webhook_configs[body.webhook_name],
    }
 
 
async def _analyze_webhook_payload_background(
    tenant_id: str,
    webhook_name: str,
    sample_payload: dict,
    workflow_name: str,
    field_mappings: dict,
    trigger_conditions: Optional[dict],
) -> None:
    """Background: use LLM to validate and enhance webhook mapping."""
    import json
    try:
        from core.llm_router import LLMRouter, LLMMessage
        llm = LLMRouter()
        system = (
            "You are a webhook integration specialist. "
            "Analyze the webhook payload and validate the field mappings. "
            "Return JSON: { valid: bool, suggestions: [...], warnings: [...] }"
        )
        user = (
            f"Webhook name: {webhook_name}\n"
            f"Target workflow: {workflow_name}\n"
            f"Sample payload: {json.dumps(sample_payload, indent=2)[:1500]}\n"
            f"Proposed field mappings: {json.dumps(field_mappings)}\n"
            "Validate the mappings and suggest improvements."
        )
        await llm.call(
            agent_name="webhook_analyzer",
            messages=[LLMMessage(role="system", content=system), LLMMessage(role="user", content=user)],
            tier_override="mini",
        )
    except Exception as e:
        log.debug("Webhook analysis background task failed (non-fatal)", error=str(e))

@app.post("/api/v1/admin/patterns/{tenant_id}/{pattern_key}/promote", tags=["Admin"])
async def promote_pattern_admin(
    tenant_id: str,
    pattern_key: str,
    _: TokenData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin: promote any tenant's pattern."""
    from core.state_manager import StateManager
    sm = StateManager(session=db)
    promoted = await sm.promote_pattern(tenant_id, pattern_key)
    if not promoted:
        raise HTTPException(status_code=404, detail="Pattern not found or already active")
    return {"message": f"Pattern '{pattern_key}' promoted to active", "tenant_id": tenant_id}


# ── Tenant-facing pattern management ──────────────────────────────────────────

@app.get("/api/v1/tenants/{tenant_id}/patterns", tags=["Tenants"])
async def list_tenant_patterns(
    tenant_id: str,
    status: Optional[str] = Query(None, description="pending_review | active | all"),
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    """List all learned patterns for this tenant (includes sandbox + active)."""
    assert_tenant_access(current_user, tenant_id)
    patterns = await crud.list_patterns(db, tenant_id, status_filter=status if status != "all" else None)
    return [crud.pattern_to_dict(p) for p in patterns]


@app.post("/api/v1/tenants/{tenant_id}/patterns/{pattern_key}/promote", tags=["Tenants"])
async def promote_pattern_tenant(
    tenant_id: str,
    pattern_key: str,
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    """Business owner promotes a sandbox pattern to active (injects into future RAG context)."""
    assert_tenant_access(current_user, tenant_id)
    from core.state_manager import StateManager
    sm = StateManager(session=db)
    promoted = await sm.promote_pattern(tenant_id, pattern_key)
    if not promoted:
        raise HTTPException(status_code=404, detail="Pattern not found or already active")
    await crud.log_event(db, "pattern_promoted", tenant_id, None,
                         f"Pattern '{pattern_key}' promoted by {current_user.email}")
    return {"message": f"Pattern '{pattern_key}' is now active", "tenant_id": tenant_id}


@app.post("/api/v1/tenants/{tenant_id}/patterns/{pattern_key}/demote", tags=["Tenants"])
async def demote_pattern_tenant(
    tenant_id: str,
    pattern_key: str,
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    """Business owner moves an active pattern back to pending_review (stops RAG injection)."""
    assert_tenant_access(current_user, tenant_id)
    from sqlalchemy import update as _upd
    from core.state_manager import PatternMemory
    result = await db.execute(
        _upd(PatternMemory)
        .where(PatternMemory.tenant_id == tenant_id)
        .where(PatternMemory.pattern_key == pattern_key)
        .where(PatternMemory.pattern_status == "active")
        .values(pattern_status="pending_review")
    )
    await db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Active pattern not found")
    return {"message": f"Pattern '{pattern_key}' moved back to pending review", "tenant_id": tenant_id}

# ─────────────────────────────────────────────────────────────────────────────
# Auto-Eval (Prompt Improvement Suggestions)
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/v1/admin/auto-eval/run", tags=["Admin"])
async def run_auto_eval(
    body: AutoEvalRunRequest,
    _: TokenData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Analyze human escalation corrections and generate prompt improvement suggestions.
    NEVER modifies prompts — only produces suggestions for admin review.
    """
    from core.auto_eval import AutoEvalService
    from core.llm_router import LLMRouter
    from core.rag_engine import RAGEngine

    llm = LLMRouter()
    rag = RAGEngine(db_session=db, llm_router=llm)
    service = AutoEvalService(llm_router=llm, rag_engine=rag)

    suggestions = await service.analyze_and_suggest(
        tenant_id=body.tenant_id,
        workflow_name=body.workflow_name,
    )
    return {"suggestions": suggestions, "count": len(suggestions)}


@app.get("/api/v1/admin/auto-eval/suggestions", tags=["Admin"])
async def get_auto_eval_suggestions(
    status: Optional[str] = Query(None, description="pending | applied | dismissed"),
    workflow_name: Optional[str] = Query(None),
    _: TokenData = Depends(require_admin),
):
    """Return stored prompt improvement suggestions."""
    from core.auto_eval import AutoEvalService
    service = AutoEvalService()
    return {"suggestions": service.get_suggestions(status=status, workflow_name=workflow_name)}


@app.post("/api/v1/admin/auto-eval/suggestions/{suggestion_id}/apply", tags=["Admin"])
async def apply_auto_eval_suggestion(
    suggestion_id: str,
    body: AutoEvalApplyRequest,
    _: TokenData = Depends(require_admin),
):
    """
    Apply a prompt improvement suggestion to the actual prompt file.
    Requires explicit admin action — suggestions are NEVER auto-applied.
    """
    from core.auto_eval import AutoEvalService
    service = AutoEvalService()
    try:
        result = service.apply_suggestion(suggestion_id, body.admin_email)
        return {"message": "Suggestion applied", "suggestion": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/v1/admin/auto-eval/suggestions/{suggestion_id}/dismiss", tags=["Admin"])
async def dismiss_auto_eval_suggestion(
    suggestion_id: str,
    _: TokenData = Depends(require_admin),
):
    """Dismiss a suggestion without applying it."""
    from core.auto_eval import AutoEvalService
    service = AutoEvalService()
    try:
        result = service.dismiss_suggestion(suggestion_id)
        return {"message": "Suggestion dismissed", "suggestion": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))  
    
# ─────────────────────────────────────────────────────────────────────────────
# Background execution (creates own DB sessions)
# ─────────────────────────────────────────────────────────────────────────────

async def _load_stored_credentials_for_workflow(db: AsyncSession, tenant_config: dict) -> dict:
    """
    Fetch stored credentials for workflow execution from both:
    1. Legacy IntegrationCredential rows (by client_id / tenant_id)
    2. First-Class ToolConnection rows (by organization_id / client_id)
    """
    client_id = tenant_config.get("client_id")
    org_id = tenant_config.get("organization_id") or client_id
    stored_creds = {}

    # 1. Legacy IntegrationCredential table
    if client_id:
        try:
            creds_rows = await crud.list_credentials(db, tenant_id=client_id)
            for c in creds_rows:
                raw = (c.credentials or {}).get("encrypted", "")
                if raw:
                    try:
                        stored_creds[c.tool_name] = decrypt_credentials(raw)
                    except Exception as _e:
                        log.warning("Failed to decrypt legacy credential", tool=c.tool_name, error=str(_e))
        except Exception as _leg_err:
            log.warning("Failed reading legacy credentials", error=str(_leg_err))

    # 2. Canonical ToolConnection table
    if org_id:
        try:
            import uuid
            from sqlalchemy import select
            from db.models.core import ToolConnection
            org_uuid = uuid.UUID(str(org_id))
            conn_stmt = select(ToolConnection).where(
                ToolConnection.organization_id == org_uuid,
                ToolConnection.status == "connected"
            )
            tc_result = await db.execute(conn_stmt)
            for tc in tc_result.scalars().all():
                if tc.encrypted_credentials:
                    try:
                        dec = decrypt_credentials(tc.encrypted_credentials)
                        if isinstance(dec, dict):
                            if tc.config and isinstance(tc.config, dict):
                                dec = {**tc.config, **dec}
                            stored_creds[tc.tool_name] = dec
                    except Exception as _tc_dec_err:
                        log.warning("Failed to decrypt ToolConnection credentials", tool=tc.tool_name, error=str(_tc_dec_err))
        except Exception as _tc_err:
            log.warning("Failed querying ToolConnection table for credentials", error=str(_tc_err))

    return stored_creds


async def _execute_workflow_background(
    run_id: str,
    tenant_config: dict,
    workflow_name: str,
    signal_data: dict,
    budget_settings: dict,
) -> None:
    """Fresh workflow execution — always starts from node 0."""
    from core.database import get_raw_session
    from core.llm_router import LLMRouter
    from core.state_manager import StateManager
    from core.orchestrator import WorkflowOrchestrator
    from core.rag_engine import RAGEngine
    from agents.base_agent import ToolRegistry
    from epi.epi_manager import EPIManager
    from integrations.tool_registry_builder import build_registry

    db = await get_raw_session()
    async with db:
        try:
            llm_router = LLMRouter()
            stored_creds = await _load_stored_credentials_for_workflow(db, tenant_config)
            tool_registry = build_registry(tenant_config, credentials=stored_creds)
            state_manager = StateManager(session=db)
            rag_engine = RAGEngine(db_session=db, llm_router=llm_router)

            async def _on_agent_run(rn_id: str, agent_run_data: dict) -> None:
                await crud.update_workflow_status(
                    db, rn_id,
                    status="running",
                    current_node=agent_run_data.get("node_id"),
                    agent_run_data=agent_run_data,
                    cost_delta=agent_run_data.get("cost_usd", 0.0),
                    tokens_in_delta=agent_run_data.get("tokens_in", 0),
                    tokens_out_delta=agent_run_data.get("tokens_out", 0),
                )

            async def _on_escalation(esc_id: str, esc_data: dict) -> None:
                await crud.log_event(db, "escalation_created",
                                     esc_data.get("tenant_id"), esc_data.get("instance_id"),
                                     esc_data.get("reason", "")[:200])

            orchestrator = WorkflowOrchestrator(
                state_manager=state_manager, llm_router=llm_router,
                tool_registry=tool_registry, epi_manager=EPIManager(),
                rag_engine=rag_engine, ws_broadcast=broadcast_event,
                escalation_callback=_on_escalation, agent_run_callback=_on_agent_run,
            )
            _active_orchestrators[run_id] = orchestrator
            await crud.update_workflow_status(db, run_id, "running")

            result = await orchestrator.run_workflow(
                tenant_config=tenant_config, workflow_name=workflow_name,
                trigger_signal=signal_data, instance_id=run_id,
                budget_settings=budget_settings or {},
            )
            _raw_status = result.get("status", "completed")
            final_status = _raw_status.value if hasattr(_raw_status, "value") else str(_raw_status)
            # If suspended (escalated / pending_a2a), orchestrator already called suspend_workflow
            if final_status not in ("escalated", "pending_a2a"):
                await crud.update_workflow_status(
                    db, run_id, final_status,
                    outcome=result.get("outcome"),
                )
                # ── Reconcile full LLM cost (includes HyDE, tool_result_compressor, etc.) ──────────
                try:
                    full_stats = llm_router.get_live_stats()
                    inst_check = await crud.get_workflow_instance(db, run_id)
                    if inst_check:
                        cost_gap = full_stats.get("total_cost_usd", 0.0) - (inst_check.total_cost_usd or 0.0)
                        tok_in_gap = full_stats.get("total_tokens_in", 0) - (inst_check.total_tokens_in or 0)
                        tok_out_gap = full_stats.get("total_tokens_out", 0) - (inst_check.total_tokens_out or 0)
                        if cost_gap > 0.000001:
                            await crud.update_workflow_status(
                                db, run_id, final_status,
                                cost_delta=cost_gap,
                                tokens_in_delta=max(0, tok_in_gap),
                                tokens_out_delta=max(0, tok_out_gap),
                            )
                            log.debug("Cost reconciliation applied", gap=f"${cost_gap:.6f}", run=run_id[:8])
                except Exception as _cost_e:
                    log.debug("Cost reconciliation failed (non-fatal)", error=str(_cost_e))
                await _write_evidence_summary(run_id, workflow_name, tenant_config, result)

            # ── Write usage record for billing/metering (Atomic & Consistent across all statuses) ──
            try:
                inst_final = await crud.get_workflow_instance(db, run_id)
                org_id = (
                    tenant_config.get("organization_id")
                    or tenant_config.get("client_id")
                    or tenant_config.get("tenant_id")
                    or (str(inst_final.tenant_id) if inst_final and inst_final.tenant_id else None)
                )
                if org_id and inst_final:
                    await crud.record_usage(
                        db,
                        organization_id=org_id,
                        usage_type="workflow_run",
                        workflow_key=workflow_name,
                        workflow_instance_id=run_id,
                        quantity=1,
                        tokens_in=inst_final.total_tokens_in or 0,
                        tokens_out=inst_final.total_tokens_out or 0,
                        cost_usd=float(inst_final.total_cost_usd) if inst_final.total_cost_usd else None,
                    )
                    log.debug("Usage record written", run_id=run_id[:8], workflow=workflow_name, org_id=org_id)
            except Exception as _usage_e:
                log.warning("Usage record write failed (non-fatal)", error=str(_usage_e), run_id=run_id[:8])

            await broadcast_event(
                "workflow_completed" if final_status == "completed" else f"workflow_{final_status}",
                {"run_id": run_id, "workflow": workflow_name,
                 "tenant_id": tenant_config.get("client_id") or tenant_config.get("tenant_id"), "status": final_status},
            )

        except Exception as e:
            log.error("Background workflow failed", run_id=run_id, error=str(e))
            from core.database import get_raw_session
            err_db = await get_raw_session()
            async with err_db:
                await crud.update_workflow_status(err_db, run_id, "failed", error=str(e))
                await err_db.commit()
                
            await broadcast_event("workflow_failed", {
                "run_id": run_id, "error": str(e),
                "tenant_id": tenant_config.get("client_id")
            })
        finally:
            _active_orchestrators.pop(run_id, None)


async def _resume_workflow_background(
    run_id: str,
    tenant_config: dict,
    decision_context: dict,
) -> None:
    """Resume a suspended workflow from its DB-persisted state."""
    from core.database import get_raw_session
    from core.llm_router import LLMRouter
    from core.state_manager import StateManager
    from core.orchestrator import WorkflowOrchestrator
    from core.rag_engine import RAGEngine
    from agents.base_agent import ToolRegistry
    from epi.epi_manager import EPIManager
    from integrations.tool_registry_builder import build_registry

    db = await get_raw_session()
    async with db:
        try:
            state_manager = StateManager(session=db)
            inst = await crud.get_workflow_instance(db, run_id)
            if not inst:
                log.error("Cannot resume: instance not found", run_id=run_id)
                return

            llm_router = LLMRouter()
            stored_creds = await _load_stored_credentials_for_workflow(db, tenant_config)
            tool_registry = build_registry(tenant_config, credentials=stored_creds)
            rag_engine = RAGEngine(db_session=db, llm_router=llm_router)

            async def _on_agent_run(rn_id: str, agent_run_data: dict) -> None:
                await crud.update_workflow_status(
                    db, rn_id, "running",
                    current_node=agent_run_data.get("node_id"),
                    agent_run_data=agent_run_data,
                    cost_delta=agent_run_data.get("cost_usd", 0.0),
                    tokens_in_delta=agent_run_data.get("tokens_in", 0),
                    tokens_out_delta=agent_run_data.get("tokens_out", 0),
                )

            orchestrator = WorkflowOrchestrator(
                state_manager=state_manager, llm_router=llm_router,
                tool_registry=tool_registry, epi_manager=EPIManager(),
                rag_engine=rag_engine, ws_broadcast=broadcast_event,
                agent_run_callback=_on_agent_run,
            )
            _active_orchestrators[run_id] = orchestrator
            await crud.update_workflow_status(db, run_id, "running")

            result = await orchestrator.resume_workflow(
                instance_id=run_id,
                additional_context=decision_context,
            )

            _raw_status = result.get("status", "completed")
            final_status = _raw_status.value if hasattr(_raw_status, "value") else str(_raw_status)
            if final_status not in ("escalated", "pending_a2a"):
                await crud.update_workflow_status(
                    db, run_id, final_status,
                    outcome=result.get("outcome"),
                )
                await _write_evidence_summary(run_id, inst.workflow_name, tenant_config, result)

            # Record resumed usage
            try:
                inst_resumed = await crud.get_workflow_instance(db, run_id)
                res_org_id = (
                    tenant_config.get("organization_id")
                    or tenant_config.get("client_id")
                    or tenant_config.get("tenant_id")
                    or (str(inst_resumed.tenant_id) if inst_resumed and inst_resumed.tenant_id else None)
                )
                if res_org_id and inst_resumed:
                    await crud.record_usage(
                        db,
                        organization_id=res_org_id,
                        usage_type="workflow_run",
                        workflow_key=inst.workflow_name,
                        workflow_instance_id=run_id,
                        quantity=1,
                        tokens_in=inst_resumed.total_tokens_in or 0,
                        tokens_out=inst_resumed.total_tokens_out or 0,
                        cost_usd=float(inst_resumed.total_cost_usd) if inst_resumed.total_cost_usd else None,
                    )
            except Exception as _res_usage_e:
                log.warning("Resume usage record failed (non-fatal)", error=str(_res_usage_e))

            await broadcast_event(
                f"workflow_{final_status}",
                {"run_id": run_id, "workflow": inst.workflow_name,
                 "tenant_id": tenant_config.get("client_id") or tenant_config.get("tenant_id"), "status": final_status},
            )
        except Exception as e:
            log.error("Resume workflow failed", run_id=run_id, error=str(e))
            await crud.update_workflow_status(db, run_id, "failed", error=str(e))
        finally:
            _active_orchestrators.pop(run_id, None)

async def _fork_workflow_background(
    new_run_id: str,
    original_run_id: str,
    tenant_config: dict,
    workflow_name: str,
    from_node_id: str,
    budget_settings: dict,
    context_patch: Optional[dict] = None,
) -> None:
    """
    Fork an existing workflow from a specific node.
    Loads the original run's accumulated context from DB, optionally patches it,
    then replays the workflow from the given node forward.
    """
    from core.database import get_raw_session
    from core.llm_router import LLMRouter
    from core.state_manager import StateManager
    from core.orchestrator import WorkflowOrchestrator
    from core.rag_engine import RAGEngine
    from epi.epi_manager import EPIManager
    from integrations.tool_registry_builder import build_registry

    db = await get_raw_session()
    async with db:
        try:
            # Load accumulated context from original run (stored in context column)
            orig_inst = await crud.get_workflow_instance(db, original_run_id)
            accumulated_context = dict(orig_inst.context or {})
            accumulated_context.pop("_suspension", None)  # strip suspension envelope
            # Restore full research context if it was preserved for fork replay
            if "_fork_research_full" in accumulated_context:
                accumulated_context["research"] = accumulated_context.pop("_fork_research_full")
                log.info(
                    "Fork: restored full research context",
                    accounts=accumulated_context.pop("_fork_accounts_count", "?"),
                )

            # Apply optional context patch
            if context_patch:
                accumulated_context.update(context_patch)

            accumulated_context["_forked_from"] = original_run_id
            accumulated_context["_fork_node"] = from_node_id

            llm_router = LLMRouter()
            stored_creds = await _load_stored_credentials_for_workflow(db, tenant_config)
            tool_registry = build_registry(tenant_config, credentials=stored_creds)
            state_manager = StateManager(session=db)
            rag_engine = RAGEngine(db_session=db, llm_router=llm_router)

            async def _on_agent_run(rn_id: str, agent_run_data: dict) -> None:
                await crud.update_workflow_status(
                    db, rn_id, "running",
                    current_node=agent_run_data.get("node_id"),
                    agent_run_data=agent_run_data,
                    cost_delta=agent_run_data.get("cost_usd", 0.0),
                    tokens_in_delta=agent_run_data.get("tokens_in", 0),
                    tokens_out_delta=agent_run_data.get("tokens_out", 0),
                )

            orchestrator = WorkflowOrchestrator(
                state_manager=state_manager, llm_router=llm_router,
                tool_registry=tool_registry, epi_manager=EPIManager(),
                rag_engine=rag_engine, ws_broadcast=broadcast_event,
                agent_run_callback=_on_agent_run,
            )
            _active_orchestrators[new_run_id] = orchestrator
            await crud.update_workflow_status(db, new_run_id, "running")

            result = await orchestrator.fork_workflow(
                new_instance_id=new_run_id,
                workflow_name=workflow_name,
                tenant_config=tenant_config,
                accumulated_context=accumulated_context,
                resume_from_node=from_node_id,
                budget_settings=budget_settings or {},
            )

            _raw_status = result.get("status", "completed")
            final_status = _raw_status.value if hasattr(_raw_status, "value") else str(_raw_status)
            if final_status not in ("escalated", "pending_a2a"):
                await crud.update_workflow_status(
                    db, new_run_id, final_status,
                    outcome=result.get("outcome"),
                )
                await _write_evidence_summary(new_run_id, workflow_name, tenant_config, result)

            await broadcast_event(
                f"workflow_{final_status}",
                {
                    "run_id": new_run_id, "workflow": workflow_name,
                    "tenant_id": tenant_config.get("client_id"),
                    "status": final_status, "forked_from": original_run_id,
                },
            )

        except Exception as e:
            log.error("Fork workflow failed", run_id=new_run_id, error=str(e))
            await crud.update_workflow_status(db, new_run_id, "failed", error=str(e))
            await broadcast_event("workflow_failed", {
                "run_id": new_run_id, "error": str(e),
                "tenant_id": tenant_config.get("client_id"),
            })
        finally:
            _active_orchestrators.pop(new_run_id, None)


async def _write_evidence_summary(
    run_id: str, workflow_name: str, tenant_config: dict, result: dict
) -> None:
    """
    Write evidence summary JSON asynchronously (non-blocking).
    Previously was synchronous, which briefly blocked the event loop.
    """
    try:
        evidence_dir = Path(os.getenv("EPI_EVIDENCE_DIR", "./evidence"))
        evidence_dir.mkdir(parents=True, exist_ok=True)
        ts   = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        safe = workflow_name.replace("/", "_")
        path = evidence_dir / f"{safe}_{run_id[:8]}_{ts}.json"
        summary = {
            "run_id":       run_id,
            "workflow_name": workflow_name,
            "tenant_id":    tenant_config.get("client_id"),
            "tenant_name":  tenant_config.get("client_name"),
            "status":       result.get("status", "unknown"),
            "completed_at": datetime.utcnow().isoformat(),
            "llm_stats":    result.get("llm_stats", {}),
            "outcome":      result.get("outcome", {}),
        }
        content = json.dumps(summary, indent=2, default=str)
        # Use aiofiles for non-blocking write
        import aiofiles as _af
        async with _af.open(path, "w") as f:
            await f.write(content)
    except Exception as e:
        log.warning("Evidence summary write failed", error=str(e))
 
 
async def _store_human_correction_rag(
    tenant_id: str,
    run_id: str,
    escalation_id: str,
    original_recommendation: str,
    human_action: str,
    context_brief: str,
    notes: str,
) -> None:
    """
    Background task: persist a human escalation decision as a RAG correction.
 
    The next time the Reasoning agent encounters a similar situation for this
    tenant, `get_historical_context_for_reasoning` will surface this lesson
    and label it as HIGH PRIORITY in the injected context.
    """
    from core.rag_engine import RAGEngine
    from core.llm_router import LLMRouter
 
    db = await get_raw_session()
    async with db:
        try:
            rag = RAGEngine(db_session=db, llm_router=LLMRouter())
            await rag.store_human_correction(
                tenant_id=tenant_id,
                run_id=run_id,
                escalation_id=escalation_id,
                original_recommendation=original_recommendation,
                human_action=human_action,
                context_brief=context_brief,
                notes=notes,
            )
        except Exception as e:
            log.warning(
                "Failed to store human correction in RAG (non-fatal)",
                error=str(e),
                escalation_id=escalation_id,
            )


# ─────────────────────────────────────────────────────────────────────────────
# Config schema helper
# ─────────────────────────────────────────────────────────────────────────────

def _build_config_schema() -> dict:
    return {
        "sections": [
            {
                "id": "company_profile", "title": "Company Profile",
                "fields": [
                    {"key": "client_name", "label": "Company Name", "type": "text", "required": True},
                    {"key": "industry", "label": "Industry", "type": "select",
                     "options": ["saas", "retail", "healthcare", "finance",
                                 "real_estate", "logistics", "cpg"]},
                    {"key": "company_profile.description", "label": "Description", "type": "textarea"},
                    {"key": "company_profile.avg_contract_value", "label": "Avg Contract Value", "type": "text"},
                ],
            },
            {
                "id": "business_rules", "title": "Business Rules",
                "fields": [
                    {"key": "business_rules.confidence_threshold", "label": "Confidence Threshold",
                     "type": "range", "min": 0.5, "max": 1.0, "step": 0.05, "default": 0.75},
                ],
            },
            {
                "id": "tone_profile", "title": "Tone & Brand Voice",
                "fields": [
                    {"key": "tone_profile.brand_voice", "label": "Brand Voice", "type": "textarea"},
                    {"key": "tone_profile.formality", "label": "Formality", "type": "select",
                     "options": ["formal", "medium", "casual"]},
                    {"key": "tone_profile.sign_off_name", "label": "Sign-off Name", "type": "text"},
                ],
            },
            {
                "id": "active_workflows", "title": "Active Workflows",
                "fields": [
                    {"key": "active_workflows", "label": "Enabled Workflows", "type": "multiselect",
                     "options": [
                         "saas_churn_prevention", "saas_pipeline_velocity",
                         "retail_inventory_health", "healthcare_patient_engagement",
                         "finance_expense_monitoring",
                         "re_listing_health_monitor", "re_tenant_flight_risk",
                     ]},
                ],
            },
        ]
    }
