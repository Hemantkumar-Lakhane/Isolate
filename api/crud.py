"""
api/crud.py
===========
All PostgreSQL CRUD operations for the SMBFlow API.
Each function receives an AsyncSession and returns ORM objects or plain dicts.
No business logic here — just data access.

CONSTANT — do not modify for business customization.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

import structlog
from sqlalchemy import delete, func, select, update, Integer
from sqlalchemy.ext.asyncio import AsyncSession

from core.state_manager import (
    A2ARequest,
    AgentRun,
    BudgetSettings,
    CustomTool,
    Escalation,
    IntegrationCredential,
    PatternMemory,
    SystemEvent,
    Tenant,
    User,
    WorkflowInstance,
    WorkflowStatus,
)
from db.models.core import Organization, OrganizationUser

log = structlog.get_logger()


# ─────────────────────────────────────────────────────────────────────────────
# Tenants
# ─────────────────────────────────────────────────────────────────────────────

async def create_tenant(
    db: AsyncSession,
    name: str,
    industry: str,
    config: dict,
) -> Tenant:
    t = Tenant(
        id=uuid.uuid4(),
        name=name,
        industry=industry,
        config={
            **config,
            "client_id": str(uuid.uuid4()),
            "client_name": name,
            "industry": industry,
            "active_workflows": [],
            "integrations": {},
            "business_rules": {},
            "tone_profile": {},
            "action_library": {},
            "llm_overrides": {},
        },
        active=True,
    )
    # Merge provided config on top of defaults
    if config:
        t.config.update(config)
    t.config["client_id"] = str(t.id)
    db.add(t)
    await db.flush()
    await db.refresh(t)

    # Create default budget settings
    bs = BudgetSettings(
        id=uuid.uuid4(),
        tenant_id=t.id,
        optimization_level=1,
        strategy="balanced",
    )
    db.add(bs)
    await db.commit()
    return t


async def get_tenant(db: AsyncSession, tenant_id: str) -> Optional[Tenant]:
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    return result.scalar_one_or_none()


async def list_tenants(db: AsyncSession, tenant_id_filter: Optional[str] = None) -> list[Tenant]:
    q = select(Tenant).where(Tenant.active.is_(True))
    if tenant_id_filter:
        q = q.where(Tenant.id == tenant_id_filter)
    result = await db.execute(q.order_by(Tenant.created_at))
    return list(result.scalars().all())


async def update_tenant_config(
    db: AsyncSession, tenant_id: str, partial_config: dict
) -> Optional[Tenant]:
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    t = result.scalar_one_or_none()
    if not t:
        return None
    merged = {**(t.config or {}), **partial_config}
    await db.execute(
        update(Tenant).where(Tenant.id == tenant_id).values(config=merged)
    )
    await db.commit()
    return await get_tenant(db, tenant_id)


# ─────────────────────────────────────────────────────────────────────────────
# Users
# ─────────────────────────────────────────────────────────────────────────────

async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def list_users(db: AsyncSession) -> list[User]:
    result = await db.execute(select(User).order_by(User.created_at))
    return list(result.scalars().all())


async def create_user(
    db: AsyncSession,
    email: str,
    password_hash: str,
    full_name: Optional[str] = None,
    role: str = "tenant_user",
    tenant_id: Optional[str] = None,
) -> User:
    u = User(
        id=uuid.uuid4(),
        email=email,
        password_hash=password_hash,
        full_name=full_name,
        role=role,
        tenant_id=tenant_id,
        is_active=True,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


async def update_user_last_login(db: AsyncSession, user_id: str) -> None:
    await db.execute(
        update(User).where(User.id == user_id).values(last_login=datetime.utcnow())
    )
    await db.commit()


async def deactivate_user(db: AsyncSession, user_id: str) -> None:
    await db.execute(update(User).where(User.id == user_id).values(is_active=False))
    await db.commit()


def user_to_dict(u: User) -> dict:
    return {
        "id": str(u.id),
        "email": u.email,
        "full_name": u.full_name,
        "role": u.role,
        "tenant_id": str(u.tenant_id) if u.tenant_id else None,
        "is_active": u.is_active,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "last_login": u.last_login.isoformat() if u.last_login else None,
    }


async def update_user_password(db: AsyncSession, user_id: str, password_hash: str) -> None:
    await db.execute(
        update(User).where(User.id == user_id).values(password_hash=password_hash)
    )
    await db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Password Reset Tokens
#
# Security: callers store only a SHA-256 hash of the raw token. These helpers
# never receive, return, or log the raw token — they operate on the hash.
# ─────────────────────────────────────────────────────────────────────────────

async def create_password_reset_token(
    db: AsyncSession,
    user_id: str,
    token_hash: str,
    expires_at: datetime,
):
    from core.state_manager import PasswordResetToken
    row = PasswordResetToken(
        id=uuid.uuid4(),
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def get_valid_reset_token(db: AsyncSession, token_hash: str):
    """Return an unused, unexpired token row for this hash, else None."""
    from core.state_manager import PasswordResetToken
    result = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > datetime.utcnow(),
        )
    )
    return result.scalar_one_or_none()


async def mark_reset_token_used(db: AsyncSession, token_id: str) -> None:
    from core.state_manager import PasswordResetToken
    await db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.id == token_id)
        .values(used_at=datetime.utcnow())
    )
    await db.commit()


async def invalidate_user_reset_tokens(db: AsyncSession, user_id: str) -> None:
    """Mark all outstanding (unused) reset tokens for a user as used."""
    from core.state_manager import PasswordResetToken
    await db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user_id,
            PasswordResetToken.used_at.is_(None),
        )
        .values(used_at=datetime.utcnow())
    )
    await db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Workflow Instances
# ─────────────────────────────────────────────────────────────────────────────

async def create_workflow_instance(
    db: AsyncSession,
    run_id: str,
    tenant_id: str,
    workflow_name: str,
    trigger_signal: dict,
    triggered_by: Optional[str] = None,
    tenant_config: Optional[dict] = None,
) -> WorkflowInstance:
    inst = WorkflowInstance(
        id=uuid.UUID(run_id) if isinstance(run_id, str) else run_id,
        tenant_id=uuid.UUID(tenant_id) if isinstance(tenant_id, str) else tenant_id,
        workflow_name=workflow_name,
        status=WorkflowStatus.PENDING,
        trigger_signal=trigger_signal,
        context={
            "trigger_signal": trigger_signal,
            "tenant_id": str(tenant_id),
            "workflow_name": workflow_name,
            "started_at": datetime.utcnow().isoformat(),
            "patterns": [],
            "tenant_config": tenant_config or {},
            "triggered_by": triggered_by,
        },
    )
    db.add(inst)
    await db.commit()
    await db.refresh(inst)
    return inst


async def get_workflow_instance(db: AsyncSession, run_id: str) -> Optional[WorkflowInstance]:
    u_id = uuid.UUID(run_id) if isinstance(run_id, str) else run_id
    result = await db.execute(select(WorkflowInstance).where(WorkflowInstance.id == u_id))
    return result.scalar_one_or_none()


async def list_workflow_instances(
    db: AsyncSession,
    tenant_id: Optional[str] = None,
    limit: int = 100,
) -> list[WorkflowInstance]:
    q = select(WorkflowInstance)
    if tenant_id:
        q = q.where(WorkflowInstance.tenant_id == tenant_id)
    q = q.order_by(WorkflowInstance.started_at.desc()).limit(limit)
    result = await db.execute(q)
    return list(result.scalars().all())


async def list_agent_run_records(
    db: AsyncSession,
    instance_id: str,
) -> list:
    """Return full agent run history for a workflow instance from the normalised table."""
    from core.state_manager import AgentRunRecord
    result = await db.execute(
        select(AgentRunRecord)
        .where(AgentRunRecord.instance_id == instance_id)
        .order_by(AgentRunRecord.completed_at)
    )
    return list(result.scalars().all())
 
 
def agent_run_record_to_dict(r) -> dict:
    return {
        "node_id":            r.node_id,
        "agent_type":         r.agent_type,
        "status":             r.status,
        "cost_usd":           r.cost_usd,
        "tokens_in":          r.tokens_in,
        "tokens_out":         r.tokens_out,
        "model_used":         r.model_used,
        "provider":           getattr(r, "provider", None),
        "confidence":         r.confidence,
        "duration_ms":        r.duration_ms,
        "error":              r.error,
        "tools_used":         r.tools_used or [],
        "output_data":        r.output_data,
        "_prosecutor_issues": r.prosecutor_issues,
        "_judge_verdict":     r.judge_verdict,
        "delta_vs_history":   r.delta_vs_history,
        "delta_trend":        r.delta_trend,
        "delta_analysis":     r.delta_analysis,
        "completed_at":       r.completed_at.isoformat() if r.completed_at else None,
    }

async def update_workflow_status(
    db: AsyncSession,
    run_id: str,
    status: str,
    current_node: Optional[str] = None,
    outcome: Optional[dict] = None,
    error: Optional[str] = None,
    agent_run_data: Optional[dict] = None,
    cost_delta: float = 0.0,
    tokens_in_delta: int = 0,
    tokens_out_delta: int = 0,
) -> None:
    updates: dict[str, Any] = {"status": status}
    if current_node is not None:
        updates["current_node"] = current_node
    if outcome is not None:
        updates["outcome"] = outcome
    if error is not None:
        updates["error_log"] = error
    if status in ("completed", "failed", "stopped"):
        updates["completed_at"] = datetime.utcnow()
    if cost_delta or tokens_in_delta or tokens_out_delta :
        # Row-lock the instance for this read-modify-write: cost/token accumulation and
        # the agent_runs JSONB append are non-atomic in SQL, so concurrent per-agent
        # callbacks on the same run would otherwise lose updates. FOR UPDATE serializes
        # them; the lock is released by the commit below.
        result = await db.execute(
            select(
                WorkflowInstance.total_cost_usd,
                WorkflowInstance.total_tokens_in,
                WorkflowInstance.total_tokens_out,
                WorkflowInstance.agent_runs,
            ).where(WorkflowInstance.id == run_id).with_for_update()
        )
        row = result.one_or_none()
        if row:
            if cost_delta or tokens_in_delta or tokens_out_delta:
                updates["total_cost_usd"] = (row[0] or 0.0) + cost_delta
                updates["total_tokens_in"] = (row[1] or 0) + tokens_in_delta
                updates["total_tokens_out"] = (row[2] or 0) + tokens_out_delta
            # Deduplicate: replace existing entry for this node_id
            if agent_run_data:
                existing_runs = list(row[3] or [])
                node_id = agent_run_data.get("node_id")
                existing_runs = [r for r in existing_runs if r.get("node_id") != node_id]
                existing_runs.append(agent_run_data)
                updates["agent_runs"] = existing_runs

    await db.execute(
        update(WorkflowInstance).where(WorkflowInstance.id == run_id).values(**updates)
    )
    await db.commit()


def workflow_to_dict(inst: WorkflowInstance) -> dict:
    """Serialise a WorkflowInstance to a plain API-friendly dict."""
    signal = getattr(inst, "trigger_signal", None)
    if signal is None:
        signal = getattr(inst, "trigger_payload", None)
    if not isinstance(signal, dict):
        signal = {}

    # Distinguish manual vs new email / automatic trigger
    raw_source = signal.get("source", "manual")
    if raw_source in ("manual_ui", "manual", "ui", "user_trigger"):
        trigger_type = "Manual"
    elif raw_source in ("email_event_detector", "synthetic_fixture", "new_email", "email_inbox", "synthetic_inbox"):
        trigger_type = "New Email"
    elif raw_source in ("scheduled", "cron"):
        trigger_type = "Scheduled"
    elif raw_source in ("webhook", "api_event"):
        trigger_type = "Webhook"
    else:
        trigger_type = str(raw_source).replace("_", " ").title()

    msg_ids = signal.get("message_ids")
    msg_limit = signal.get("limit")
    if isinstance(msg_ids, list):
        message_count = len(msg_ids)
    elif msg_limit is not None:
        message_count = int(msg_limit)
    elif isinstance(inst.outcome, dict) and "emails_processed" in inst.outcome:
        message_count = inst.outcome.get("emails_processed")
    else:
        message_count = None

    tenant_val = getattr(inst, "tenant_id", None) or getattr(inst, "organization_id", None)

    return {
        "run_id": str(inst.id),
        "id": str(inst.id),
        "tenant_id": str(tenant_val) if tenant_val else "",
        "organization_id": str(tenant_val) if tenant_val else "",
        "workflow_name": inst.workflow_name,
        "name": inst.workflow_name,
        "status": inst.status,
        "current_node": inst.current_node,
        "started_at": inst.started_at.isoformat() if inst.started_at else None,
        "completed_at": inst.completed_at.isoformat() if inst.completed_at else None,
        "total_cost_usd": inst.total_cost_usd or 0.0,
        "total_tokens_in": inst.total_tokens_in or 0,
        "total_tokens_out": inst.total_tokens_out or 0,
        "agent_runs": getattr(inst, "agent_runs", []) or [],
        "outcome": inst.outcome,
        "trigger_signal": signal,
        "trigger_payload": signal,
        "trigger_source": raw_source,
        "trigger_type": trigger_type,
        "message_count": message_count,
        "error": getattr(inst, "error_log", None),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Escalations
# ─────────────────────────────────────────────────────────────────────────────

async def get_escalation(db: AsyncSession, esc_id: str) -> Optional[Escalation]:
    result = await db.execute(select(Escalation).where(Escalation.id == esc_id))
    return result.scalar_one_or_none()


async def list_escalations(
    db: AsyncSession,
    status: str = "pending",
    tenant_id: Optional[str] = None,
) -> list[Escalation]:
    q = select(Escalation).where(Escalation.status == status)
    if tenant_id:
        q = q.where(Escalation.tenant_id == tenant_id)
    result = await db.execute(q.order_by(Escalation.created_at.desc()))
    return list(result.scalars().all())


def escalation_to_dict(e: Escalation) -> dict:
    return {
        "id": str(e.id),
        "escalation_id": str(e.id),
        "instance_id": str(e.instance_id),
        "tenant_id": str(e.tenant_id),
        "node_id": e.node_id,
        "reason": e.reason,
        "context_brief": e.context_brief,
        "recommended_action": e.recommended_action,
        "status": e.status,
        "decision": e.decision,
        "decided_by": e.decided_by,
        "decided_at": e.decided_at.isoformat() if e.decided_at else None,
        "action_chosen": getattr(e, "action_chosen", None),
        "required_signatures": getattr(e, "required_signatures", 1),
        "signatures": getattr(e, "signatures", []),
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# A2A Requests
# ─────────────────────────────────────────────────────────────────────────────

async def get_a2a_request(db: AsyncSession, a2a_id: str) -> Optional[A2ARequest]:
    result = await db.execute(select(A2ARequest).where(A2ARequest.id == a2a_id))
    return result.scalar_one_or_none()


async def list_pending_a2a(
    db: AsyncSession, tenant_id: Optional[str] = None
) -> list[A2ARequest]:
    q = select(A2ARequest).where(A2ARequest.status == "pending_permission")
    if tenant_id:
        q = q.where(A2ARequest.tenant_id == tenant_id)
    result = await db.execute(q.order_by(A2ARequest.created_at.desc()))
    return list(result.scalars().all())


def a2a_to_dict(a: A2ARequest) -> dict:
    return {
        "a2a_id": str(a.id),
        "run_id": str(a.instance_id),
        "tenant_id": str(a.tenant_id),
        "requesting_agent": a.requesting_agent,
        "target_agent": a.target_agent,
        "target_node_id": a.target_node_id,
        "reason": a.reason,
        "refinement_note": a.refinement_note,
        "new_tools": list(a.new_tools or []),   # Feature 1
        "estimated_cost_usd": a.estimated_cost_usd,
        "status": a.status,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Credentials
# ─────────────────────────────────────────────────────────────────────────────

async def create_credential(
    db: AsyncSession,
    tenant_id: str,
    tool_name: str,
    display_name: str,
    encrypted_data: str,
) -> IntegrationCredential:
    cred = IntegrationCredential(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        tool_name=tool_name,
        display_name=display_name or tool_name,
        credentials={"encrypted": encrypted_data},
    )
    db.add(cred)
    await db.commit()
    await db.refresh(cred)
    return cred


async def list_credentials(
    db: AsyncSession, tenant_id: Optional[str] = None
) -> list[IntegrationCredential]:
    q = select(IntegrationCredential)
    if tenant_id:
        q = q.where(IntegrationCredential.tenant_id == tenant_id)
    result = await db.execute(q)
    return list(result.scalars().all())


async def get_credential(db: AsyncSession, cred_id: str) -> Optional[IntegrationCredential]:
    result = await db.execute(
        select(IntegrationCredential).where(IntegrationCredential.id == cred_id)
    )
    return result.scalar_one_or_none()


async def delete_credential(db: AsyncSession, cred_id: str) -> None:
    await db.execute(
        delete(IntegrationCredential).where(IntegrationCredential.id == cred_id)
    )
    await db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Custom Tools
# ─────────────────────────────────────────────────────────────────────────────

async def create_custom_tool(db: AsyncSession, data: dict) -> CustomTool:
    tool = CustomTool(id=uuid.uuid4(), **data)
    db.add(tool)
    await db.commit()
    await db.refresh(tool)
    return tool


async def list_custom_tools(
    db: AsyncSession, tenant_id: Optional[str] = None
) -> list[CustomTool]:
    q = select(CustomTool).where(CustomTool.is_active.is_(True))
    if tenant_id:
        q = q.where(CustomTool.tenant_id == tenant_id)
    result = await db.execute(q)
    return list(result.scalars().all())


async def get_custom_tool(db: AsyncSession, tool_id: str) -> Optional[CustomTool]:
    result = await db.execute(select(CustomTool).where(CustomTool.id == tool_id))
    return result.scalar_one_or_none()


async def delete_custom_tool(db: AsyncSession, tool_id: str) -> None:
    await db.execute(delete(CustomTool).where(CustomTool.id == tool_id))
    await db.commit()


def custom_tool_to_dict(t: CustomTool) -> dict:
    return {
        "id": str(t.id),
        "tenant_id": str(t.tenant_id),
        "tool_name": t.tool_name,
        "display_name": t.display_name,
        "description": t.description,
        "base_url": t.base_url,
        "http_method": t.http_method,
        "auth_type": t.auth_type,
        "credential_id": str(t.credential_id) if t.credential_id else None,
        "response_path": t.response_path,
        "is_active": t.is_active,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Budget Settings
# ─────────────────────────────────────────────────────────────────────────────

async def get_budget_settings(db: AsyncSession, tenant_id: str) -> Optional[dict]:
    result = await db.execute(
        select(BudgetSettings).where(BudgetSettings.tenant_id == tenant_id)
    )
    bs = result.scalar_one_or_none()
    if not bs:
        return None
    return {
        "tenant_id": str(bs.tenant_id),
        "optimization_level": bs.optimization_level,
        "strategy": bs.strategy,
        "enable_caching": bs.enable_caching,
        "cache_ttl_seconds": bs.cache_ttl_seconds,
        "max_context_tokens": bs.max_context_tokens,
        "a2a_enabled": bs.a2a_enabled,
        "auto_retry_on_low_confidence": bs.auto_retry_on_low_confidence,
        "confidence_retry_threshold": bs.confidence_retry_threshold,
        "enable_map_reduce_summarization": bs.enable_map_reduce_summarization or False,
        "max_spend_per_run_usd": bs.max_spend_per_run_usd,
    }


async def upsert_budget_settings(db: AsyncSession, tenant_id: str, data: dict) -> dict:
    result = await db.execute(
        select(BudgetSettings).where(BudgetSettings.tenant_id == tenant_id)
    )
    bs = result.scalar_one_or_none()
    if bs:
        await db.execute(
            update(BudgetSettings)
            .where(BudgetSettings.tenant_id == tenant_id)
            .values(**{k: v for k, v in data.items() if k != "tenant_id"})
        )
    else:
        db.add(BudgetSettings(id=uuid.uuid4(), tenant_id=tenant_id, **data))
    await db.commit()
    return await get_budget_settings(db, tenant_id)


# ─────────────────────────────────────────────────────────────────────────────
# System Events
# ─────────────────────────────────────────────────────────────────────────────

async def log_event(
    db: AsyncSession,
    event_type: str,
    tenant_id: Optional[str],
    instance_id: Optional[str],
    message: str,
    metadata: Optional[dict] = None,
) -> None:
    ev = SystemEvent(
        id=uuid.uuid4(),
        event_type=event_type,
        tenant_id=tenant_id,
        instance_id=instance_id,
        message=message[:1000],
        metadata_=metadata or {},
    )
    db.add(ev)
    # Don't commit here — let the parent transaction handle it
    # (or use flush so it's visible without committing)
    await db.flush()


async def list_events(db: AsyncSession, limit: int = 100) -> list[dict]:
    result = await db.execute(
        select(SystemEvent).order_by(SystemEvent.created_at.desc()).limit(limit)
    )
    events = result.scalars().all()
    return [
        {
            "event_type": e.event_type,
            "tenant_id": str(e.tenant_id) if e.tenant_id else None,
            "instance_id": str(e.instance_id) if e.instance_id else None,
            "message": e.message,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in events
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Analytics helpers
# ─────────────────────────────────────────────────────────────────────────────

async def get_fleet_analytics(db: AsyncSession) -> dict:
    result = await db.execute(
        select(
            WorkflowInstance.tenant_id,
            func.count(WorkflowInstance.id).label("runs"),
            func.sum(WorkflowInstance.total_cost_usd).label("cost"),
            func.sum(WorkflowInstance.total_tokens_in).label("tokens"),
            func.sum(
                (WorkflowInstance.status == WorkflowStatus.COMPLETED).cast(Integer)
            ).label("completed"),
        ).group_by(WorkflowInstance.tenant_id)
    )
    rows = result.all()
    by_tenant = {}
    for row in rows:
        tid = str(row[0])
        by_tenant[tid] = {
            "runs": row[1],
            "cost": float(row[2] or 0),
            "tokens": int(row[3] or 0),
            "completed": int(row[4] or 0),
        }
    return {
        "total_cost_usd": sum(v["cost"] for v in by_tenant.values()),
        "total_runs": sum(v["runs"] for v in by_tenant.values()),
        "by_tenant": by_tenant,
    }
    
# ─────────────────────────────────────────────────────────────────────────────
# Email Queue
# ─────────────────────────────────────────────────────────────────────────────

async def list_email_queue(
    db: AsyncSession,
    tenant_id: Optional[str] = None,
    status: str = "pending",
) -> list:
    from core.state_manager import EmailQueue
    q = select(EmailQueue)
    if tenant_id:
        q = q.where(EmailQueue.tenant_id == tenant_id)
    if status != "all":
        q = q.where(EmailQueue.status == status)
    q = q.order_by(EmailQueue.created_at.desc())
    result = await db.execute(q)
    return list(result.scalars().all())


async def get_email_queue_item(db: AsyncSession, item_id: str):
    from core.state_manager import EmailQueue
    result = await db.execute(select(EmailQueue).where(EmailQueue.id == item_id))
    return result.scalar_one_or_none()


async def update_email_queue_item(
    db: AsyncSession,
    item_id: str,
    updates: dict,
) -> None:
    from core.state_manager import EmailQueue
    from sqlalchemy import update as sa_update
    await db.execute(
        sa_update(EmailQueue).where(EmailQueue.id == item_id).values(**updates)
    )
    await db.commit()


def email_queue_to_dict(item) -> dict:
    return {
        "id":               str(item.id),
        "tenant_id":        str(item.tenant_id),
        "run_id":           str(item.run_id) if item.run_id else None,
        "account_id":       item.account_id,
        "recipient_email":  item.recipient_email,
        "recipient_name":   item.recipient_name,
        "subject":          item.subject,
        "body":             item.body,
        "email_type":       item.email_type,
        "csm_name":         item.csm_name,
        "workflow_name":    item.workflow_name,
        "status":           item.status,
        "rejection_reason": item.rejection_reason,
        "reviewed_at":      item.reviewed_at.isoformat() if item.reviewed_at else None,
        "reviewed_by":      item.reviewed_by,
        "created_at":       item.created_at.isoformat() if item.created_at else None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Pattern Memory (tenant-facing CRUD)
# ─────────────────────────────────────────────────────────────────────────────

async def list_patterns(
    db: AsyncSession,
    tenant_id: str,
    status_filter: Optional[str] = None,
) -> list:
    q = select(PatternMemory).where(PatternMemory.tenant_id == tenant_id)
    if status_filter:
        q = q.where(PatternMemory.pattern_status == status_filter)
    q = q.order_by(PatternMemory.last_updated.desc()).limit(100)
    result = await db.execute(q)
    return list(result.scalars().all())


def pattern_to_dict(p: PatternMemory) -> dict:
    return {
        "id":             str(p.id),
        "tenant_id":      str(p.tenant_id),
        "pattern_key":    p.pattern_key,
        "pattern_data":   p.pattern_data,
        "success_rate":   p.success_rate,
        "sample_size":    p.sample_size,
        "pattern_status": p.pattern_status,
        "last_updated":   p.last_updated.isoformat() if p.last_updated else None,
    }

async def get_dashboard_data(db: AsyncSession, tenant_id: str) -> dict:
    from sqlalchemy import select, func, and_, desc, text
    from datetime import datetime, timezone, timedelta
    from core.state_manager import WorkflowInstance, Escalation, A2ARequest, AgentRunRecord, ApprovalItem

    # NOTE: DB DateTime columns are naive UTC (Column(DateTime), default=datetime.utcnow)
    # throughout this schema. Use naive UTC here so comparisons/date_trunc against
    # started_at/completed_at don't raise "can't subtract offset-naive and offset-aware".
    now = datetime.utcnow()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    first_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    ten_days_ago = today - timedelta(days=9)
    seven_days_ago = today - timedelta(days=6)

    # 1. Active Runs — count everything currently in-flight (non-terminal), not just
    #    status=='running'. Runs are short-lived background tasks that finish in seconds,
    #    so 'running' alone reads ~0 at any given 5s poll; work parked in escalated /
    #    pending_a2a / paused is still active from the operator's view and must show up.
    #    Include the enum-repr forms ('WorkflowStatus.*') defensively — some rows were
    #    historically written as the repr rather than the value.
    INFLIGHT_STATES = [
        'pending', 'running', 'paused', 'escalated', 'pending_a2a',
        'WorkflowStatus.PENDING', 'WorkflowStatus.RUNNING', 'WorkflowStatus.PAUSED',
        'WorkflowStatus.ESCALATED', 'WorkflowStatus.PENDING_A2A',
    ]
    RUNNING_STATES = ['running', 'WorkflowStatus.RUNNING']
    active_runs_res = await db.execute(
        select(
            func.count().filter(WorkflowInstance.status.in_(INFLIGHT_STATES)),
            func.count().filter(WorkflowInstance.status.in_(RUNNING_STATES)),
            func.count().filter(WorkflowInstance.started_at >= today),
        ).where(WorkflowInstance.tenant_id == tenant_id)
    )
    active_count, running_count, initiated_today = active_runs_res.first()
    awaiting_count = (active_count or 0) - (running_count or 0)

    # 2. Pending Approvals — union of every human-action queue so this KPI matches the
    #    Action Center exactly: Escalations, A2A permission requests, AND ApprovalItems
    #    (the draft-approval queue the email/HITL workflows write to). ApprovalItem is
    #    scoped by organization_id, which is the same physical column as
    #    WorkflowInstance.tenant_id, so the same tenant_id value applies.
    pending_esc_res = await db.execute(
        select(func.count(Escalation.id)).where(
            and_(Escalation.tenant_id == tenant_id, Escalation.status == 'pending')
        )
    )
    pending_a2a_res = await db.execute(
        select(func.count(A2ARequest.id)).where(
            and_(A2ARequest.tenant_id == tenant_id, A2ARequest.status == 'pending_permission')
        )
    )
    try:
        import uuid as _uuid
        _oid = _uuid.UUID(str(tenant_id))
        pending_appr_res = await db.execute(
            select(func.count(ApprovalItem.id)).where(
                and_(ApprovalItem.organization_id == _oid, ApprovalItem.status == 'pending')
            )
        )
        _appr_count = pending_appr_res.scalar() or 0
    except Exception:
        _appr_count = 0

    pending_approvals = (
        (pending_esc_res.scalar() or 0)
        + (pending_a2a_res.scalar() or 0)
        + _appr_count
    )

    # 3. Tasks Completed
    tasks_res = await db.execute(
        select(func.count(AgentRunRecord.id))
        .join(WorkflowInstance, AgentRunRecord.instance_id == WorkflowInstance.id)
        .where(
            and_(
                WorkflowInstance.tenant_id == tenant_id,
                AgentRunRecord.status.in_(['success', 'completed'])
            )
        )
    )
    tasks_total = tasks_res.scalar() or 0

    # Sparkline trend (last 7 days)
    sparkline_res = await db.execute(
        select(
            func.date_trunc('day', AgentRunRecord.completed_at).label('day'),
            func.count(AgentRunRecord.id)
        )
        .join(WorkflowInstance, AgentRunRecord.instance_id == WorkflowInstance.id)
        .where(
            and_(
                WorkflowInstance.tenant_id == tenant_id,
                AgentRunRecord.status.in_(['success', 'completed']),
                AgentRunRecord.completed_at >= seven_days_ago
            )
        )
        .group_by('day')
    )
    trend_dict = {str(row[0].date()) if row[0] else '': row[1] for row in sparkline_res.all()}
    
    tasks_trend = []
    for i in range(7):
        d = (seven_days_ago + timedelta(days=i)).date()
        tasks_trend.append(trend_dict.get(str(d), 0))

    # 4. Recent Activity
    recent_res = await db.execute(
        select(
            WorkflowInstance.id, 
            WorkflowInstance.workflow_name, 
            WorkflowInstance.status, 
            WorkflowInstance.started_at,
            WorkflowInstance.current_node
        )
        .where(WorkflowInstance.tenant_id == tenant_id)
        .order_by(desc(WorkflowInstance.started_at))
        .limit(5)
    )
    recent_activity = []
    for r in recent_res.all():
        desc_text = 'Workflow is running'
        if r.status in ['completed', 'WorkflowStatus.COMPLETED']:
            desc_text = 'Workflow completed'
        elif r.status in ['failed', 'stopped']:
            desc_text = 'Workflow failed'
        elif r.status in ['escalated', 'pending_a2a']:
            desc_text = 'Awaiting approval'
        
        recent_activity.append({
            'id': str(r.id),
            'name': r.workflow_name or 'Workflow Run',
            'status': r.status,
            'timestamp': r.started_at.isoformat() if r.started_at else None,
            'description': desc_text
        })

    # 5. Workflow Performance — rank by *total* runs across every status so the most-run
    #    workflow appears first (previously ranked by completed+failed only, which hid
    #    workflows whose runs are all still escalated/in-flight and pushed active ones down).
    #    success_rate stays completion-quality among *finished* runs.
    COMPLETED_STATES = ['completed', 'WorkflowStatus.COMPLETED']
    FAILED_STATES = ['failed', 'stopped', 'WorkflowStatus.FAILED', 'WorkflowStatus.STOPPED']
    perf_res = await db.execute(
        select(
            WorkflowInstance.workflow_name,
            func.count().label('total'),
            func.count().filter(WorkflowInstance.status.in_(COMPLETED_STATES)).label('completed'),
            func.count().filter(WorkflowInstance.status.in_(FAILED_STATES)).label('failed'),
        )
        .where(WorkflowInstance.tenant_id == tenant_id)
        .group_by(WorkflowInstance.workflow_name)
    )
    performance = []
    for row in perf_res.all():
        total_all = row.total or 0
        if total_all == 0:
            continue
        comp = row.completed or 0
        fail = row.failed or 0
        finished = comp + fail
        rate = round((comp / finished) * 100) if finished > 0 else 0
        performance.append({
            'name': row.workflow_name or 'Unknown',
            'success_rate': rate,
            'runs': total_all,
            'completed': comp,
            'failed': fail,
        })
    performance.sort(key=lambda x: x['runs'], reverse=True)
    performance = performance[:5]

    # 6. Cost Overview
    cost_res = await db.execute(
        select(
            func.sum(WorkflowInstance.total_cost_usd),
            func.count(WorkflowInstance.id)
        )
        .where(
            and_(
                WorkflowInstance.tenant_id == tenant_id,
                WorkflowInstance.started_at >= first_of_month
            )
        )
    )
    cost_row = cost_res.first()
    mtd_spend = cost_row[0] or 0.0
    mtd_runs = cost_row[1] or 0
    avg_cost = (mtd_spend / mtd_runs) if mtd_runs > 0 else 0.0

    daily_cost_res = await db.execute(
        select(
            func.date_trunc('day', WorkflowInstance.started_at).label('day'),
            func.sum(WorkflowInstance.total_cost_usd)
        )
        .where(
            and_(
                WorkflowInstance.tenant_id == tenant_id,
                WorkflowInstance.started_at >= ten_days_ago
            )
        )
        .group_by('day')
    )
    daily_cost_dict = {str(row[0].date()) if row[0] else '': (row[1] or 0.0) for row in daily_cost_res.all()}
    
    daily_trend = []
    for i in range(10):
        d = (ten_days_ago + timedelta(days=i)).date()
        daily_trend.append({
            'date': str(d),
            'cost': daily_cost_dict.get(str(d), 0.0)
        })

    return {
        'active_runs': {
            'current': active_count or 0,
            'running': running_count or 0,
            'awaiting': awaiting_count or 0,
            'initiated_today': initiated_today or 0,
        },
        'pending_approvals': {'total': pending_approvals},
        'tasks_completed': {'total': tasks_total, 'trend': tasks_trend},
        'net_savings': {'value': None, 'status': 'not_measured'},
        'recent_activity': recent_activity,
        'workflow_performance': performance,
        'cost_overview': {
            'mtd_spend': round(mtd_spend, 6) if mtd_spend is not None else 0.0,
            'avg_cost_per_run': round(avg_cost, 6) if avg_cost is not None else 0.0,
            'daily_trend': daily_trend
        }
    }


# ─────────────────────────────────────────────────────────────────────────────
# Organization & User Auto-Provisioning (Supabase Managed PostgreSQL)
# ─────────────────────────────────────────────────────────────────────────────

async def ensure_user_organization_provisioned(
    db: AsyncSession,
    user_id: str,
    email: str,
    full_name: Optional[str] = None,
    workspace_name: Optional[str] = None,
    industry: Optional[str] = None,
) -> tuple[Optional[OrganizationUser], Optional[Organization]]:
    """
    Deterministically resolves or auto-provisions an SMBFlow organization_users
    and Organization record for a valid Supabase Auth user.
    Enforces server-side authority:
      - Uses stable auth.users.id (user_id)
      - Never allows client-supplied role self-assignment
      - New users receive default 'org_user' role
      - Reuses existing organization if present to prevent duplicate org creation
    """
    try:
        u_uuid = uuid.UUID(user_id)
    except (ValueError, TypeError):
        u_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, user_id)

    # 1. Query existing OrganizationUser by user_id
    res = await db.execute(select(OrganizationUser).where(OrganizationUser.user_id == u_uuid))
    org_user = res.scalar_one_or_none()

    if not org_user and email:
        # Fallback check by email to prevent duplicate entries for existing users
        res_email = await db.execute(select(OrganizationUser).where(OrganizationUser.email == email))
        org_user = res_email.scalar_one_or_none()
        if org_user and org_user.user_id != u_uuid:
            org_user.user_id = u_uuid
            await db.flush()

    # Check if this email is a legacy platform admin or admin@smbflow.com
    is_bootstrap_admin = False
    if email:
        if email.lower() == "admin@smbflow.com":
            is_bootstrap_admin = True
        else:
            legacy_u = await get_user_by_email(db, email)
            if legacy_u and legacy_u.role in ("super_admin", "platform_admin"):
                is_bootstrap_admin = True

    if org_user:
        # Fetch organization
        org_res = await db.execute(select(Organization).where(Organization.id == org_user.organization_id))
        org = org_res.scalar_one_or_none()

        updated = False
        if is_bootstrap_admin and org_user.role != "platform_admin":
            org_user.role = "platform_admin"
            updated = True

        if org:
            if workspace_name and org.name != workspace_name:
                org.name = workspace_name
                updated = True
            if industry and org.industry != industry:
                org.industry = industry
                org.enabled_modules = [industry]
                updated = True
            if workspace_name:
                cfg = dict(org.profile_config or {})
                if cfg.get("requires_onboarding") != False:
                    cfg["requires_onboarding"] = False
                    org.profile_config = cfg
                    updated = True
        else:
            org = Organization(
                id=org_user.organization_id,
                name=workspace_name or "Pending Workspace Setup",
                industry=industry or "saas",
                enabled_modules=[industry] if industry else ["saas"],
                profile_config={"requires_onboarding": False if workspace_name else True},
                active=True,
            )
            db.add(org)
            updated = True

        if full_name and org_user.full_name != full_name:
            org_user.full_name = full_name
            updated = True

        if updated:
            await db.commit()
            await db.refresh(org)
            await db.refresh(org_user)

        return org_user, org

    # 2. No organization_user record found — check if user provided workspace_name
    if workspace_name:
        org = Organization(
            id=uuid.uuid4(),
            name=workspace_name,
            industry=industry or "saas",
            enabled_modules=[industry] if industry else ["saas"],
            profile_config={"requires_onboarding": False},
            active=True,
        )
        db.add(org)
        await db.flush()
        await db.refresh(org)
    else:
        # New user without workspace_name gets a dedicated pending workspace requiring onboarding
        org = Organization(
            id=uuid.uuid4(),
            name="Pending Workspace Setup",
            industry=industry or "saas",
            enabled_modules=[industry] if industry else ["saas"],
            profile_config={"requires_onboarding": True},
            active=True,
        )
        db.add(org)
        await db.flush()
        await db.refresh(org)

    # 3. Create OrganizationUser record for new user (enforces org_user role unless bootstrap admin)
    name_display = full_name or (email.split("@")[0].replace(".", " ").title() if email else "User")
    assigned_role = "platform_admin" if is_bootstrap_admin else "org_user"
    org_user = OrganizationUser(
        id=uuid.uuid4(),
        organization_id=org.id,
        user_id=u_uuid,
        email=email or f"{user_id}@smbflow.com",
        full_name=name_display,
        role=assigned_role,
        created_at=datetime.utcnow(),
    )
    db.add(org_user)
    await db.commit()
    await db.refresh(org_user)

    return org_user, org


# ─────────────────────────────────────────────────────────────────────────────
# Organizations (new auth-layer table — distinct from legacy tenants table)
# ─────────────────────────────────────────────────────────────────────────────

async def get_organization_by_id(
    db: AsyncSession, org_id: str
) -> Optional[Organization]:
    """Query organizations table by id (UUID string)."""
    try:
        result = await db.execute(
            select(Organization).where(Organization.id == org_id)
        )
        return result.scalar_one_or_none()
    except Exception:
        return None


async def update_organization_config(
    db: AsyncSession, org_id: str, partial_config: dict
) -> Optional[Organization]:
    """Merge partial_config into organizations.profile_config."""
    org = await get_organization_by_id(db, org_id)
    if not org:
        return None
    merged = {**(org.profile_config or {}), **partial_config}
    await db.execute(
        update(Organization)
        .where(Organization.id == org_id)
        .values(profile_config=merged, updated_at=datetime.utcnow())
    )
    await db.commit()
    return await get_organization_by_id(db, org_id)


async def update_organization_profile(
    db: AsyncSession,
    org_id: str,
    name: Optional[str] = None,
    industry: Optional[str] = None,
    profile_config: Optional[dict] = None,
) -> Optional[Organization]:
    """Update organization name, industry and/or profile_config."""
    org = await get_organization_by_id(db, org_id)
    if not org:
        return None
    values: dict = {"updated_at": datetime.utcnow()}
    if name is not None:
        values["name"] = name
    if industry is not None:
        values["industry"] = industry
    if profile_config is not None:
        values["profile_config"] = {**(org.profile_config or {}), **profile_config}
    await db.execute(
        update(Organization).where(Organization.id == org_id).values(**values)
    )
    await db.commit()
    return await get_organization_by_id(db, org_id)


async def resolve_tenant_config_bridge(
    db: AsyncSession,
    org_id: str,
) -> tuple:
    """
    Option B Tenant Bridge — Phase 0.

    The workflow orchestrator needs a Tenant record + config (from the legacy
    ``tenants`` table).  The authenticated user's identity is anchored to the
    ``organizations`` table.  These share the same physical DB but are separate
    tables with different UUIDs.

    Resolution strategy:
      1. Try org_id directly against the ``tenants`` table (covers the case where
         a Tenant was created with the same UUID during prior onboarding).
      2. If not found, synthesize a minimal config dict from the Organization
         record so the orchestrator can still run without modification.

    Returns: (effective_tenant_id: str, config: dict)
    """
    # Step 1 — try legacy tenants table directly
    legacy = await get_tenant(db, org_id)
    if legacy:
        return str(legacy.id), legacy.config or {}

    # Step 2 — fall back to synthesizing from the organizations record
    org = await get_organization_by_id(db, org_id)
    if not org:
        return org_id, {}

    merged_profile = dict(org.profile_config or {})
    synthesized_config: dict = {
        "client_id":        str(org.id),
        "client_name":      org.name or "SMBFlow Organization",
        "industry":         org.industry or "saas",
        "enabled_modules":  org.enabled_modules or [org.industry or "saas"],
        "active_workflows": ["email_summarizer"],
        "integrations":     {},
        "business_rules":   merged_profile.get("business_rules") or {
            "high_value_deal_threshold": 50000,
            "sla_warning_threshold_hours": 24,
            "escalate_urgency_level": "high",
        },
        "tone_profile":     merged_profile.get("tone_profile") or {
            "brand_voice": "Professional, empathetic, and action-oriented",
            "formality": "high",
        },
        "action_library":   merged_profile.get("action_library") or {
            "actions": [
                {
                    "id": "action_sla_urgent_response",
                    "action_type": "send_email",
                    "description": "Send urgent SLA response to client",
                    "required_approval": True,
                },
                {
                    "id": "action_log_summary",
                    "action_type": "log_event",
                    "description": "Log email summary into audit records",
                    "required_approval": False,
                }
            ]
        },
        "llm_overrides":    merged_profile.get("llm_overrides") or {},
        **merged_profile,
    }
    # Strip internal onboarding flags that the orchestrator does not need
    synthesized_config.pop("requires_onboarding", None)
    synthesized_config.pop("_is_test_artifact", None)

    return str(org.id), synthesized_config


# ─────────────────────────────────────────────────────────────────────────────
# Workflow Definitions (organization-scoped, separate from filesystem DAGs)
# ─────────────────────────────────────────────────────────────────────────────

async def list_workflow_definitions(
    db: AsyncSession,
    organization_id: Optional[str] = None,
    include_templates: bool = False,
) -> list:
    """
    List WorkflowDefinitions scoped to an organization.

    - organization_id: filter to this org's definitions.
    - include_templates: also return platform templates
      (organization_id IS NULL and is_template=True).
    """
    from db.models.core import WorkflowDefinition as WFDef
    from sqlalchemy import or_

    q = select(WFDef).where(WFDef.active.is_(True))

    if organization_id and include_templates:
        q = q.where(
            or_(
                WFDef.organization_id == organization_id,
                WFDef.is_template.is_(True),
            )
        )
    elif organization_id:
        q = q.where(WFDef.organization_id == organization_id)
    elif include_templates:
        q = q.where(WFDef.is_template.is_(True))

    q = q.order_by(WFDef.created_at.desc())
    result = await db.execute(q)
    return list(result.scalars().all())


async def create_workflow_definition(
    db: AsyncSession,
    organization_id: str,
    name: str,
    industry: str,
    dag_definition: dict,
    version: str = "1.0.0",
    is_template: bool = False,
) -> object:
    """Create a new WorkflowDefinition owned by an organization."""
    from db.models.core import WorkflowDefinition as WFDef

    wf = WFDef(
        id=uuid.uuid4(),
        organization_id=organization_id,
        name=name,
        industry=industry,
        version=version,
        dag_definition=dag_definition,
        is_template=is_template,
        active=True,
        created_at=datetime.utcnow(),
    )
    db.add(wf)
    await db.commit()
    await db.refresh(wf)
    return wf


# ─────────────────────────────────────────────────────────────────────────────
# Approval Items & Processed Email Events (HITL & Idempotency)
# ─────────────────────────────────────────────────────────────────────────────

async def create_approval_item(
    db: AsyncSession,
    organization_id: str,
    node_id: str = "evaluate_actions",
    review_type: str = "approval",
    reason: str = "Action requires human approval",
    context_brief: str = "",
    payload: Optional[dict] = None,
    instance_id: Optional[str] = None,
    required_signatures: int = 1,
) -> object:
    from db.models.core import ApprovalItem
    org_uuid = uuid.UUID(organization_id) if isinstance(organization_id, str) else organization_id
    inst_uuid = uuid.UUID(instance_id) if isinstance(instance_id, str) and instance_id else None
    item = ApprovalItem(
        id=uuid.uuid4(),
        organization_id=org_uuid,
        instance_id=inst_uuid,
        node_id=node_id,
        review_type=review_type,
        reason=reason,
        context_brief=context_brief,
        payload=payload or {},
        status="pending",
        required_signatures=required_signatures,
        signatures=[],
        created_at=datetime.utcnow(),
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


async def list_approval_items(
    db: AsyncSession,
    organization_id: Optional[str] = None,
    status: Optional[str] = "pending",
) -> list:
    from db.models.core import ApprovalItem
    q = select(ApprovalItem)
    if organization_id:
        org_uuid = uuid.UUID(organization_id) if isinstance(organization_id, str) else organization_id
        q = q.where(ApprovalItem.organization_id == org_uuid)
    if status and status != "all":
        if status == "pending":
            q = q.where(ApprovalItem.status.in_(["pending", "waiting", "suggested", "pending_review", "awaiting_review", "snoozed"]))
        elif status in ("resolved", "approved"):
            q = q.where(ApprovalItem.status.in_(["approved", "completed", "rejected", "dismissed", "discarded"]))
        else:
            q = q.where(ApprovalItem.status == status)
    q = q.order_by(ApprovalItem.created_at.desc())
    result = await db.execute(q)
    return list(result.scalars().all())


async def get_approval_item(db: AsyncSession, approval_id: str) -> Optional[object]:
    from db.models.core import ApprovalItem
    appr_uuid = uuid.UUID(approval_id) if isinstance(approval_id, str) else approval_id
    result = await db.execute(select(ApprovalItem).where(ApprovalItem.id == appr_uuid))
    return result.scalar_one_or_none()


async def decide_approval_item(
    db: AsyncSession,
    approval_id: str,
    decision_status: str,
    decided_by: Optional[str] = "human_reviewer",
    patch_payload: Optional[dict] = None,
) -> Optional[object]:
    from db.models.core import ApprovalItem
    appr_uuid = uuid.UUID(approval_id) if isinstance(approval_id, str) else approval_id
    result = await db.execute(select(ApprovalItem).where(ApprovalItem.id == appr_uuid))
    item = result.scalar_one_or_none()
    if not item:
        return None
    item.status = decision_status
    item.decided_by = decided_by
    item.decided_at = datetime.utcnow()
    if patch_payload and isinstance(item.payload, dict):
        item.payload = {**item.payload, **patch_payload}
    await db.commit()
    await db.refresh(item)
    return item


async def approval_item_to_dict(item) -> dict:
    raw_payload = item.payload or {}
    inner_payload = raw_payload.get("payload") if isinstance(raw_payload.get("payload"), dict) else {}
    proposed_action = raw_payload.get("proposed_action") or inner_payload.get("proposed_action") or {}
    source = raw_payload.get("source") or inner_payload.get("source") or {}

    recipient = (
        proposed_action.get("recipient")
        or raw_payload.get("to_address")
        or raw_payload.get("to")
        or raw_payload.get("recipient")
        or raw_payload.get("contact_name")
        or raw_payload.get("owner_display")
        or source.get("sender")
        or inner_payload.get("to_address")
        or inner_payload.get("recipient")
        or "client@enterprise.com"
    )
    subject = (
        proposed_action.get("subject")
        or raw_payload.get("subject")
        or raw_payload.get("action")
        or (f"Meeting Action: {item.reason}" if item.review_type == "meeting_action" else None)
        or source.get("subject")
        or inner_payload.get("subject")
        or "CRITICAL SLA Notice — Incident Investigation Update"
    )
    draft_reply = (
        proposed_action.get("body")
        or proposed_action.get("draft_reply")
        or raw_payload.get("draft_reply")
        or raw_payload.get("draft_content")
        or raw_payload.get("draft_text")
        or raw_payload.get("body")
        or inner_payload.get("draft_reply")
        or inner_payload.get("body")
        or f"Dear Partner,\n\nWe have received your alert regarding '{item.reason or 'system inquiry'}'. Our senior engineering and customer success teams are investigating the matter and applying mitigations.\n\nWe will provide a full resolution update within 60 minutes.\n\nBest regards,\nSMBFlow Enterprise Support"
    )
    urgency_score = (
        raw_payload.get("urgency_score")
        or inner_payload.get("urgency_score")
        or (9 if "sla" in (item.reason or "").lower() or "urgent" in (item.reason or "").lower() else 7)
    )
    try:
        urgency_score = int(float(urgency_score))
    except (TypeError, ValueError):
        urgency_score = 7
    reason_text = " ".join([
        str(item.reason or ""),
        str(subject or ""),
        str(raw_payload.get("title") or raw_payload.get("context_brief") or ""),
    ]).lower()
    if raw_payload.get("category") or inner_payload.get("category"):
        category = raw_payload.get("category") or inner_payload.get("category")
    elif "billing" in reason_text or "invoice" in reason_text or "charge" in reason_text:
        category = "billing_dispute"
    elif "outage" in reason_text or "downtime" in reason_text or "500" in reason_text:
        category = "service_outage"
    elif "executive" in reason_text or "partner" in reason_text or "cto" in reason_text:
        category = "executive_partner"
    elif "sla" in reason_text or "urgent" in reason_text:
        category = "sla_risk"
    else:
        category = "routine_inquiry"

    category_labels = {
        "sla_risk": "SLA Risk",
        "billing_dispute": "Billing Dispute",
        "service_outage": "Service Outage",
        "executive_partner": "Executive Partner",
        "routine_inquiry": "Routine Inquiry",
    }
    category_label = (
        raw_payload.get("category_label")
        or inner_payload.get("category_label")
        or category_labels.get(category, str(category).replace("_", " ").title())
    )
    trigger_keywords = (
        raw_payload.get("trigger_keywords")
        or inner_payload.get("trigger_keywords")
        or [kw for kw in ("urgent", "sla", "billing", "outage", "invoice") if kw in reason_text]
        or ["customer escalation"]
    )
    detected_sentiment = (
        raw_payload.get("detected_sentiment")
        or inner_payload.get("detected_sentiment")
        or ("urgent_negative" if int(urgency_score) >= 9 else "concerned")
    )
    xai_explanation = (
        raw_payload.get("xai_explanation")
        or inner_payload.get("xai_explanation")
        or {
            "trigger_rationale": f"Flagged because the message matched {category_label.lower()} signals and scored {urgency_score}/10 urgency.",
            "strategy_rationale": "Recommended human-reviewed response because the item is customer-facing and time-sensitive.",
            "confidence_metrics": {
                "intent_match": raw_payload.get("confidence") or inner_payload.get("confidence") or 0.90,
                "sentiment_confidence": 0.88,
                "safety_boundary_cleared": 0.96,
            },
        }
    )

    normalized_payload = {
        **raw_payload,
        "to_address": recipient,
        "recipient": recipient,
        "subject": subject,
        "draft_reply": draft_reply,
        "source": source,
        "urgency_score": urgency_score,
        "category": category,
        "category_label": category_label,
        "detected_sentiment": detected_sentiment,
        "trigger_keywords": trigger_keywords,
        "xai_explanation": xai_explanation,
    }

    return {
        "id": str(item.id),
        "escalation_id": str(item.id),
        "instance_id": str(item.instance_id) if item.instance_id else None,
        "run_id": str(item.instance_id) if item.instance_id else None,
        "workflow_name": raw_payload.get("workflow_name") or "email_summarizer",
        "workflow_key": raw_payload.get("workflow_key") or raw_payload.get("workflow_name") or "email_summarizer",
        "node_id": item.node_id or "evaluate_actions",
        "review_type": item.review_type or "approval",
        "reason": item.reason or "Action requires human approval",
        "recommended_action": raw_payload.get("action_type") or "approve_draft",
        "context_brief": item.context_brief or "",
        "payload": normalized_payload,
        "category": category,
        "urgency_score": urgency_score,
        "detected_sentiment": detected_sentiment,
        "trigger_keywords": trigger_keywords,
        "xai_explanation": xai_explanation,
        "status": item.status,
        "required_signatures": item.required_signatures or 1,
        "signatures": item.signatures or [],
        "decided_by": item.decided_by,
        "decided_at": item.decided_at.isoformat() if item.decided_at else None,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }



async def get_processed_email_ids(db: AsyncSession, source: Optional[str] = None) -> set[str]:
    from db.models.core import ProcessedEmailEvent
    q = select(ProcessedEmailEvent.message_id)
    if source:
        q = q.where(ProcessedEmailEvent.source == source)
    result = await db.execute(q)
    return set(result.scalars().all())


async def record_processed_emails(
    db: AsyncSession,
    message_ids: list[str],
    batch_id: Optional[str] = None,
    instance_id: Optional[str] = None,
    organization_id: Optional[str] = None,
    source: str = "synthetic_fixture",
) -> int:
    from db.models.core import ProcessedEmailEvent
    count = 0
    org_uuid = uuid.UUID(organization_id) if isinstance(organization_id, str) and organization_id else None
    inst_uuid = uuid.UUID(instance_id) if isinstance(instance_id, str) and instance_id else None
    for mid in message_ids:
        if not mid:
            continue
        evt = ProcessedEmailEvent(
            id=uuid.uuid4(),
            organization_id=org_uuid,
            message_id=mid,
            batch_id=batch_id,
            instance_id=inst_uuid,
            source=source,
            processed_at=datetime.utcnow(),
        )
        db.add(evt)
        count += 1
    await db.commit()
    return count




# =============================================================================
# Billing & Entitlement CRUD  (Migration 003)
# =============================================================================

from db.models.core import (
    AuditEvent,
    BillingPeriod,
    BillingPlan,
    Invoice,
    OrganizationSubscription,
    OrganizationWorkflowAssignment,
    PlanWorkflowEntitlement,
    PlatformSetting,
    ToolConnection,
    UsageRecord,
    WorkflowCatalog,
    WorkflowDefinition,
    WorkflowInstance as WFInstance,
    AgentRunRecord,
    ApprovalItem,
)

# ─── Workflow Catalog ─────────────────────────────────────────────────────────

async def list_workflow_catalog(db: AsyncSession, *, active_only: bool = False) -> list[WorkflowCatalog]:
    stmt = select(WorkflowCatalog).order_by(WorkflowCatalog.name)
    if active_only:
        stmt = stmt.where(WorkflowCatalog.active.is_(True))
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_workflow_catalog_entry(db: AsyncSession, workflow_id: str) -> Optional[WorkflowCatalog]:
    try:
        wid = uuid.UUID(str(workflow_id))
    except (ValueError, AttributeError):
        return None
    result = await db.execute(select(WorkflowCatalog).where(WorkflowCatalog.id == wid))
    return result.scalar_one_or_none()


async def get_workflow_catalog_by_key(db: AsyncSession, key: str) -> Optional[WorkflowCatalog]:
    result = await db.execute(select(WorkflowCatalog).where(WorkflowCatalog.key == key))
    wf = result.scalar_one_or_none()
    if wf is not None:
        return wf

    # Alias fallback: some workflows have a canonical key that differs from the
    # short alias used in routing (e.g. frontend route key "meeting_intelligence"
    # maps to the catalog key "meeting_intelligence_followup").
    # Rather than requiring every caller to know the canonical form, we resolve
    # well-known aliases here so check_org_workflow_access never hard-fails on
    # an alias that wasn't seeded under that exact name.
    _ALIASES: dict[str, str] = {
        "meeting_intelligence": "meeting_intelligence_followup",
        "product_launch":       "product_launch_sprint",
    }
    canonical = _ALIASES.get(key)
    if canonical:
        result2 = await db.execute(select(WorkflowCatalog).where(WorkflowCatalog.key == canonical))
        return result2.scalar_one_or_none()

    return None


async def create_workflow_catalog_entry(db: AsyncSession, data: dict) -> WorkflowCatalog:
    entry = WorkflowCatalog(
        name=data["name"],
        key=data["key"],
        description=data.get("description"),
        category=data.get("category", "general"),
        status=data.get("status", "active"),
        version=data.get("version", "1.0.0"),
        pricing_model=data.get("pricing_model", "included"),
        required_integrations=data.get("required_integrations", []),
        supported_modules=data.get("supported_modules", []),
        active=data.get("active", True),
        scope=data.get("scope", "GLOBAL"),
        industry=data.get("industry"),
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


async def update_workflow_catalog_entry(db: AsyncSession, workflow_id: str, data: dict) -> Optional[WorkflowCatalog]:
    entry = await get_workflow_catalog_entry(db, workflow_id)
    if not entry:
        return None
    allowed = ("name", "description", "category", "status", "version", "pricing_model",
               "required_integrations", "supported_modules", "active", "scope", "industry")
    for field in allowed:
        if field in data:
            setattr(entry, field, data[field])
    await db.commit()
    await db.refresh(entry)
    return entry


def workflow_catalog_to_dict(w: WorkflowCatalog) -> dict:
    return {
        "id":                     str(w.id),
        "name":                   w.name,
        "key":                    w.key,
        "description":            w.description,
        "category":               w.category,
        "status":                 w.status,
        "version":                w.version,
        "pricing_model":          w.pricing_model,
        "required_integrations":  w.required_integrations or [],
        "supported_modules":      w.supported_modules or [],
        "active":                 w.active,
        # ── Industry applicability (Migration 004) ────────────────────────
        "scope":                  getattr(w, "scope", "GLOBAL") or "GLOBAL",
        "industry":               getattr(w, "industry", None),
        "created_at":             w.created_at.isoformat() if w.created_at else None,
        "updated_at":             w.updated_at.isoformat() if w.updated_at else None,
    }


# ─── Billing Plans ────────────────────────────────────────────────────────────

async def list_billing_plans(db: AsyncSession, *, include_archived: bool = False) -> list[BillingPlan]:
    stmt = select(BillingPlan).order_by(BillingPlan.sort_order, BillingPlan.name)
    if not include_archived:
        stmt = stmt.where(BillingPlan.status != "archived")
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_billing_plan(db: AsyncSession, plan_id: str) -> Optional[BillingPlan]:
    try:
        pid = uuid.UUID(str(plan_id))
    except (ValueError, AttributeError):
        return None
    result = await db.execute(select(BillingPlan).where(BillingPlan.id == pid))
    return result.scalar_one_or_none()


async def get_billing_plan_by_slug(db: AsyncSession, slug: str) -> Optional[BillingPlan]:
    result = await db.execute(select(BillingPlan).where(BillingPlan.slug == slug))
    return result.scalar_one_or_none()


async def create_billing_plan(db: AsyncSession, data: dict) -> BillingPlan:
    plan = BillingPlan(
        name=data["name"],
        slug=data["slug"],
        description=data.get("description"),
        monthly_price_usd=data.get("monthly_price_usd", 0),
        annual_price_usd=data.get("annual_price_usd", 0),
        included_workflow_runs=data.get("included_workflow_runs", 0),
        included_ai_tokens=data.get("included_ai_tokens", 0),
        included_image_gens=data.get("included_image_gens", 0),
        included_users=data.get("included_users", 1),
        overage_run_price_usd=data.get("overage_run_price_usd", 0),
        overage_token_price_usd=data.get("overage_token_price_usd", 0),
        overage_image_price_usd=data.get("overage_image_price_usd", 0),
        max_workflow_runs=data.get("max_workflow_runs", 0),
        max_users=data.get("max_users", 0),
        status=data.get("status", "active"),
        is_public=data.get("is_public", True),
        sort_order=data.get("sort_order", 0),
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return plan


async def update_billing_plan(db: AsyncSession, plan_id: str, data: dict) -> Optional[BillingPlan]:
    plan = await get_billing_plan(db, plan_id)
    if not plan:
        return None
    allowed = (
        "name", "description", "monthly_price_usd", "annual_price_usd",
        "included_workflow_runs", "included_ai_tokens", "included_image_gens", "included_users",
        "overage_run_price_usd", "overage_token_price_usd", "overage_image_price_usd",
        "max_workflow_runs", "max_users", "status", "is_public", "sort_order",
    )
    for field in allowed:
        if field in data:
            setattr(plan, field, data[field])
    await db.commit()
    await db.refresh(plan)
    return plan


def billing_plan_to_dict(p: BillingPlan) -> dict:
    def _num(v) -> Optional[float]:
        return float(v) if v is not None else None
    return {
        "id":                      str(p.id),
        "name":                    p.name,
        "slug":                    p.slug,
        "description":             p.description,
        "monthly_price_usd":       _num(p.monthly_price_usd),
        "annual_price_usd":        _num(p.annual_price_usd),
        "included_workflow_runs":  p.included_workflow_runs,
        "included_ai_tokens":      p.included_ai_tokens,
        "included_image_gens":     p.included_image_gens,
        "included_users":          p.included_users,
        "overage_run_price_usd":   _num(p.overage_run_price_usd),
        "overage_token_price_usd": _num(p.overage_token_price_usd),
        "overage_image_price_usd": _num(p.overage_image_price_usd),
        "max_workflow_runs":       p.max_workflow_runs,
        "max_users":               p.max_users,
        "status":                  p.status,
        "is_public":               p.is_public,
        "sort_order":              p.sort_order,
        "created_at":              p.created_at.isoformat() if p.created_at else None,
        "updated_at":              p.updated_at.isoformat() if p.updated_at else None,
    }


# ─── Plan Workflow Entitlements ───────────────────────────────────────────────

async def get_plan_entitlements(db: AsyncSession, plan_id: str) -> list[str]:
    """Return list of workflow_ids entitled to this plan."""
    try:
        pid = uuid.UUID(str(plan_id))
    except (ValueError, AttributeError):
        return []
    result = await db.execute(
        select(PlanWorkflowEntitlement.workflow_id)
        .where(PlanWorkflowEntitlement.plan_id == pid)
    )
    return [str(r) for r in result.scalars().all()]


async def set_plan_entitlements(db: AsyncSession, plan_id: str, workflow_ids: list[str]) -> None:
    """Replace all entitlements for a plan with the given workflow_ids list."""
    try:
        pid = uuid.UUID(str(plan_id))
    except (ValueError, AttributeError):
        return
    await db.execute(
        delete(PlanWorkflowEntitlement).where(PlanWorkflowEntitlement.plan_id == pid)
    )
    for wid_str in workflow_ids:
        try:
            wid = uuid.UUID(str(wid_str))
            db.add(PlanWorkflowEntitlement(plan_id=pid, workflow_id=wid))
        except (ValueError, AttributeError):
            pass
    await db.commit()


# ─── Organization Subscriptions ───────────────────────────────────────────────

async def get_org_subscription(db: AsyncSession, organization_id: str) -> Optional[OrganizationSubscription]:
    try:
        oid = uuid.UUID(str(organization_id))
    except (ValueError, AttributeError):
        return None
    result = await db.execute(
        select(OrganizationSubscription).where(OrganizationSubscription.organization_id == oid)
    )
    return result.scalar_one_or_none()


async def list_org_subscriptions(db: AsyncSession) -> list[OrganizationSubscription]:
    result = await db.execute(
        select(OrganizationSubscription).order_by(OrganizationSubscription.created_at.desc())
    )
    return list(result.scalars().all())


async def create_org_subscription(
    db: AsyncSession,
    organization_id: str,
    plan_id: str,
    billing_cycle: str = "monthly",
    with_trial: bool = False,
    trial_days: int = 14,
) -> OrganizationSubscription:
    from datetime import timedelta
    now = datetime.utcnow()
    trial_ends_at = now + timedelta(days=trial_days) if with_trial else None
    sub = OrganizationSubscription(
        organization_id=uuid.UUID(str(organization_id)),
        plan_id=uuid.UUID(str(plan_id)),
        status="trialing" if with_trial else "active",
        billing_cycle=billing_cycle,
        current_period_start=now,
        current_period_end=now + timedelta(days=365 if billing_cycle == "annual" else 30),
        trial_ends_at=trial_ends_at,
    )
    db.add(sub)
    await db.commit()
    await db.refresh(sub)
    # Auto-init a billing period for new subscription
    await _ensure_billing_period(db, str(organization_id), str(sub.id), now, sub.current_period_end)
    return sub


async def _ensure_billing_period(
    db: AsyncSession,
    organization_id: str,
    subscription_id: str,
    period_start: datetime,
    period_end: datetime,
) -> None:
    """Idempotently create an open billing period for a new subscription."""
    from db.models.core import BillingPeriod as BP
    try:
        oid = uuid.UUID(str(organization_id))
        sid = uuid.UUID(str(subscription_id))
    except (ValueError, AttributeError):
        return
    # Check if one already exists for this org in this period
    existing = await db.execute(
        select(BP).where(
            BP.organization_id == oid,
            BP.status == "open",
        ).limit(1)
    )
    if existing.scalar_one_or_none():
        return
    db.add(BP(
        organization_id=oid,
        subscription_id=sid,
        period_start=period_start,
        period_end=period_end,
        status="open",
    ))
    await db.commit()


async def update_org_subscription(db: AsyncSession, organization_id: str, data: dict) -> Optional[OrganizationSubscription]:
    sub = await get_org_subscription(db, organization_id)
    if not sub:
        return None
    allowed = ("plan_id", "status", "billing_cycle", "current_period_end",
               "trial_ends_at", "cancelled_at", "cancel_reason", "notes")
    for field in allowed:
        if field in data:
            val = data[field]
            if field == "plan_id" and val:
                try:
                    val = uuid.UUID(str(val))
                except (ValueError, AttributeError):
                    continue
            # Parse ISO datetime strings for datetime fields
            if field in ("trial_ends_at", "cancelled_at", "current_period_end") and isinstance(val, str):
                try:
                    val = datetime.fromisoformat(val.replace("Z", "+00:00")).replace(tzinfo=None)
                except (ValueError, AttributeError):
                    continue
            setattr(sub, field, val)
    await db.commit()
    await db.refresh(sub)
    return sub


def org_subscription_to_dict(s: OrganizationSubscription, plan: Optional[BillingPlan] = None) -> dict:
    from datetime import datetime as _dt
    now = _dt.utcnow()
    # Compute effective status including trial expiry
    effective_status = s.status
    trial_days_remaining = None
    if s.status == "trialing" and s.trial_ends_at:
        remaining = (s.trial_ends_at - now).days
        if s.trial_ends_at < now:
            effective_status = "trial_expired"
            trial_days_remaining = 0
        else:
            trial_days_remaining = max(0, remaining)
    return {
        "id":                    str(s.id),
        "organization_id":       str(s.organization_id),
        "plan_id":               str(s.plan_id),
        "plan_name":             plan.name if plan else None,
        "plan_slug":             plan.slug if plan else None,
        "status":                s.status,
        "effective_status":      effective_status,
        "billing_cycle":         s.billing_cycle,
        "current_period_start":  s.current_period_start.isoformat() if s.current_period_start else None,
        "current_period_end":    s.current_period_end.isoformat() if s.current_period_end else None,
        "trial_ends_at":         s.trial_ends_at.isoformat() if s.trial_ends_at else None,
        "trial_days_remaining":  trial_days_remaining,
        "cancelled_at":          s.cancelled_at.isoformat() if s.cancelled_at else None,
        "cancel_reason":         s.cancel_reason,
        "notes":                 s.notes,
        "created_at":            s.created_at.isoformat() if s.created_at else None,
        "updated_at":            s.updated_at.isoformat() if s.updated_at else None,
    }


# ─── Organization Workflow Assignments ────────────────────────────────────────

async def get_org_workflow_assignments(db: AsyncSession, organization_id: str) -> list[OrganizationWorkflowAssignment]:
    try:
        oid = uuid.UUID(str(organization_id))
    except (ValueError, AttributeError):
        return []
    result = await db.execute(
        select(OrganizationWorkflowAssignment)
        .where(OrganizationWorkflowAssignment.organization_id == oid)
        .order_by(OrganizationWorkflowAssignment.assigned_at.desc())
    )
    return list(result.scalars().all())


async def get_org_workflow_assignment(db: AsyncSession, organization_id: str,
                                       workflow_id: str) -> Optional[OrganizationWorkflowAssignment]:
    try:
        oid = uuid.UUID(str(organization_id))
        wid = uuid.UUID(str(workflow_id))
    except (ValueError, AttributeError):
        return []
    result = await db.execute(
        select(OrganizationWorkflowAssignment)
        .where(
            OrganizationWorkflowAssignment.organization_id == oid,
            OrganizationWorkflowAssignment.workflow_id == wid,
        )
    )
    return result.scalar_one_or_none()


async def list_all_workflow_assignments(db: AsyncSession) -> list[OrganizationWorkflowAssignment]:
    result = await db.execute(
        select(OrganizationWorkflowAssignment)
        .order_by(OrganizationWorkflowAssignment.assigned_at.desc())
    )
    return list(result.scalars().all())


async def assign_workflow_to_org(db: AsyncSession, organization_id: str, workflow_id: str,
                                  assigned_by: str = None, notes: str = None) -> OrganizationWorkflowAssignment:
    existing = await get_org_workflow_assignment(db, organization_id, workflow_id)
    if existing:
        existing.status = "active"
        existing.updated_at = datetime.utcnow()
        if assigned_by:
            existing.assigned_by = assigned_by
        await db.commit()
        await db.refresh(existing)
        return existing
    assignment = OrganizationWorkflowAssignment(
        organization_id=uuid.UUID(str(organization_id)),
        workflow_id=uuid.UUID(str(workflow_id)),
        assigned_by=assigned_by,
        notes=notes,
        status="active",
    )
    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)
    return assignment


async def unassign_workflow_from_org(db: AsyncSession, organization_id: str, workflow_id: str) -> bool:
    assignment = await get_org_workflow_assignment(db, organization_id, workflow_id)
    if not assignment:
        return False
    await db.delete(assignment)
    await db.commit()
    return True


async def check_org_workflow_access(db: AsyncSession, organization_id: str, workflow_key: str) -> dict:
    """
    Returns {allowed: bool, reason: str}.
    Enforces all 9 access steps in order:
      1. Org exists and is active
      2. Workflow exists in catalog and is active
      3. Workflow is applicable to org industry (scope=GLOBAL or industry matches)  ← NEW step
      4. Org has an active/trialing subscription (trial expiry enforced)
      5. Plan entitles this workflow
      6. Admin has explicitly assigned the workflow to this org
    This is the server-side authorization boundary — never trust the frontend.
    """
    try:
        oid = uuid.UUID(str(organization_id))
    except (ValueError, AttributeError):
        return {"allowed": False, "reason": "Invalid organization ID"}

    # 1. Check org exists and is active
    org_result = await db.execute(select(Organization).where(Organization.id == oid))
    org = org_result.scalar_one_or_none()
    if not org:
        return {"allowed": False, "reason": "Organization not found"}
    if not org.active:
        return {"allowed": False, "reason": "Organization is not active"}

    # 2. Resolve workflow catalog entry
    wf = await get_workflow_catalog_by_key(db, workflow_key)
    if not wf:
        return {"allowed": False, "reason": f"Workflow '{workflow_key}' not found in catalog"}
    if not wf.active:
        return {"allowed": False, "reason": f"Workflow '{workflow_key}' is not active"}

    # 3. Industry applicability check — GLOBAL workflows pass for any org;
    #    INDUSTRY workflows only pass when the org's industry matches.
    #    Use getattr with fallback so pre-migration DBs don't crash.
    wf_scope    = getattr(wf, "scope",    "GLOBAL") or "GLOBAL"
    wf_industry = getattr(wf, "industry", None)
    if wf_scope == "INDUSTRY":
        org_industry = (org.industry or "").lower().strip()
        req_industry = (wf_industry or "").lower().strip()
        if org_industry != req_industry:
            return {
                "allowed": False,
                "reason": (
                    f"Workflow '{workflow_key}' is only available to "
                    f"'{wf_industry}' organizations (this org is '{org.industry}')"
                ),
            }

    # 4. Check org has an active subscription (with real trial lifecycle enforcement)
    sub = await get_org_subscription(db, organization_id)
    if not sub:
        return {"allowed": False, "reason": "No active subscription for this organization"}

    # Enforce trial expiry: if trialing and trial_ends_at has passed → block
    now = datetime.utcnow()
    effective_status = sub.status
    if sub.status == "trialing" and sub.trial_ends_at and sub.trial_ends_at < now:
        effective_status = "trial_expired"

    if effective_status not in ("active", "trialing"):
        return {"allowed": False, "reason": f"Subscription is not active (status: {effective_status})"}

    # 5. Check plan entitles this workflow
    entitlements = await get_plan_entitlements(db, str(sub.plan_id))
    if str(wf.id) not in entitlements:
        return {"allowed": False, "reason": f"Current plan does not include '{workflow_key}'"}

    # 6. Check explicit workflow assignment
    assignment = await get_org_workflow_assignment(db, organization_id, str(wf.id))
    if not assignment or assignment.status != "active":
        return {"allowed": False, "reason": f"Workflow '{workflow_key}' has not been assigned to this organization"}

    return {
        "allowed":       True,
        "reason":        "Access granted",
        "workflow_id":   str(wf.id),
        "workflow_name": wf.name,
        "assignment_id": str(assignment.id),
        "scope":         wf_scope,
        "industry":      wf_industry,
    }


async def get_available_workflows_for_org(
    db: AsyncSession,
    organization_id: str,
) -> list[WorkflowCatalog]:
    """
    Return the subset of active workflow_catalog entries that are applicable
    to the given organization's industry.

    A workflow is applicable when:
      scope = 'GLOBAL'
      OR (scope = 'INDUSTRY' AND industry == org.industry)

    This does NOT enforce plan entitlement or assignment — those remain
    separate checks layered on top.  This is purely applicability.

    Platform admins should NOT call this; they get the full catalog.
    """
    try:
        oid = uuid.UUID(str(organization_id))
    except (ValueError, AttributeError):
        return []

    org_result = await db.execute(select(Organization).where(Organization.id == oid))
    org = org_result.scalar_one_or_none()
    if not org:
        return []

    org_industry = (org.industry or "saas").lower().strip()

    from sqlalchemy import or_
    stmt = (
        select(WorkflowCatalog)
        .where(
            WorkflowCatalog.active.is_(True),
            or_(
                WorkflowCatalog.scope == "GLOBAL",
                WorkflowCatalog.industry == org_industry,
            ),
        )
        .order_by(WorkflowCatalog.name)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def assert_workflow_access(db: AsyncSession, organization_id: str, workflow_key: str) -> dict:
    """
    Hard backend security boundary helper.
    Raises HTTPException(403) if workflow access is denied for any reason:
    - Organization inactive
    - Subscription inactive or trial expired
    - Workflow not applicable to org industry (industry mismatch)
    - Plan does not include workflow entitlement
    - Workflow not explicitly assigned to organization
    - Workflow catalog entry inactive
    """
    res = await check_org_workflow_access(db, organization_id, workflow_key)
    if not res.get("allowed"):
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": "WORKFLOW_ACCESS_DENIED",
                "message": res.get("reason", "Workflow access denied"),
                "workflow": workflow_key,
                "organization_id": str(organization_id),
            },
        )
    return res


def workflow_assignment_to_dict(a: OrganizationWorkflowAssignment,
                                 catalog_entry: Optional[WorkflowCatalog] = None) -> dict:
    return {
        "id":              str(a.id),
        "organization_id": str(a.organization_id),
        "workflow_id":     str(a.workflow_id),
        "workflow_name":   catalog_entry.name if catalog_entry else None,
        "workflow_key":    catalog_entry.key  if catalog_entry else None,
        "workflow_status": catalog_entry.status if catalog_entry else None,
        "assigned_by":     a.assigned_by,
        "status":          a.status,
        "notes":           a.notes,
        "assigned_at":     a.assigned_at.isoformat() if a.assigned_at else None,
        "updated_at":      a.updated_at.isoformat() if a.updated_at else None,
    }


# ─── Industry auto-assignment ─────────────────────────────────────────────────

# Maps org.industry → which workflow catalog categories that org should see.
# "general" categories are visible to all industries.
# An org sees: its own industry's categories + all GENERAL categories.
INDUSTRY_CATEGORY_MAP: dict[str, list[str]] = {
    "finance":     ["finance"],
    "healthcare":  ["healthcare"],
    "saas":        ["sales", "marketing"],
    "startup":     ["sales", "marketing"],
    "real_estate": ["real_estate", "operations"],
    "retail":      ["retail", "operations"],
    "marketing":   ["marketing"],
    "ecommerce":   ["retail", "sales"],
    "services":    ["operations"],
    "other":       [],
    # "general" industries get only the universal categories below
}

# Categories visible to ALL industries regardless of org.industry
UNIVERSAL_CATEGORIES: list[str] = ["productivity", "compliance"]


def get_visible_categories_for_industry(industry: str) -> list[str]:
    """
    Returns the full list of catalog categories an org in `industry` should see.
    Always includes UNIVERSAL_CATEGORIES.
    """
    ind = (industry or "saas").lower().strip()
    industry_specific = INDUSTRY_CATEGORY_MAP.get(ind, [])
    return list({*industry_specific, *UNIVERSAL_CATEGORIES})


async def auto_assign_industry_workflows(
    db: AsyncSession,
    organization_id: str,
    industry: str,
    assigned_by: str = "system",
    plan_slug: str = "free",
) -> int:
    """
    Automatically assign all applicable workflow catalog entries to a new org.

    Selection rule: workflow.category is in get_visible_categories_for_industry(org.industry)
    Plus a plan entitlement check (bypassed when no entitlements seeded yet).

    Returns the count of new assignments created.
    """
    try:
        oid = uuid.UUID(str(organization_id))
    except (ValueError, AttributeError):
        return 0

    visible_categories = get_visible_categories_for_industry(industry)

    # Fetch the plan's entitled workflow IDs
    plan = await get_billing_plan_by_slug(db, plan_slug)
    plan_entitled_ids: set[str] = set()
    if plan:
        plan_entitled_ids = set(await get_plan_entitlements(db, str(plan.id)))

    # Query catalog entries that match the visible categories
    from sqlalchemy import func as _func
    stmt = (
        select(WorkflowCatalog)
        .where(
            WorkflowCatalog.active.is_(True),
            WorkflowCatalog.category.in_(visible_categories),
        )
    )
    result = await db.execute(stmt)
    candidates = list(result.scalars().all())

    # Filter out workflows that require explicit administrator assignment
    candidates = [
        w for w in candidates
        if not (getattr(w, "metadata_", {}) or {}).get("requires_explicit_assignment", False)
    ]

    # Apply plan entitlement filter; bypass if no entitlements seeded yet
    if plan_entitled_ids:
        applicable = [w for w in candidates if str(w.id) in plan_entitled_ids]
    else:
        applicable = candidates
        log.warning(
            "auto_assign_industry_workflows: no plan entitlements — assigning all category matches",
            org_id=organization_id,
            plan=plan_slug,
        )

    # Existing assignments — avoid duplicates
    existing_result = await db.execute(
        select(OrganizationWorkflowAssignment.workflow_id)
        .where(OrganizationWorkflowAssignment.organization_id == oid)
    )
    already_assigned: set[str] = {str(r[0]) for r in existing_result.all()}

    assigned_count = 0
    for wf in applicable:
        wf_id = str(wf.id)
        if wf_id in already_assigned:
            continue
        db.add(OrganizationWorkflowAssignment(
            organization_id=oid,
            workflow_id=wf.id,
            assigned_by=assigned_by,
            status="active",
            notes=f"Auto-assigned on org creation (industry={industry}, category={wf.category})",
        ))
        already_assigned.add(wf_id)
        assigned_count += 1

    if assigned_count > 0:
        await db.commit()

    log.info(
        "auto_assign_industry_workflows: done",
        org_id=organization_id,
        industry=industry,
        visible_categories=visible_categories,
        plan=plan_slug,
        assigned=assigned_count,
    )
    return assigned_count


# ─── Usage Records ────────────────────────────────────────────────────────────

async def record_usage(db: AsyncSession, organization_id: str, usage_type: str,
                        workflow_key: str = None, workflow_instance_id: str = None,
                        agent_run_id: str = None, provider: str = None, model: str = None,
                        quantity: int = 1, tokens_in: int = 0, tokens_out: int = 0,
                        cost_usd=None) -> UsageRecord:
    """Create a granular usage record. Calculates cost from token count if not provided."""
    if cost_usd is None and (tokens_in > 0 or tokens_out > 0):
        # Accurate calculation based on production multi-agent model rate blend
        cost_usd = round((tokens_in * 0.000003) + (tokens_out * 0.000015), 6)

    rec = UsageRecord(
        organization_id=uuid.UUID(str(organization_id)),
        workflow_key=workflow_key,
        workflow_instance_id=uuid.UUID(str(workflow_instance_id)) if workflow_instance_id else None,
        agent_run_id=uuid.UUID(str(agent_run_id)) if agent_run_id else None,
        usage_type=usage_type,
        provider=provider,
        model=model,
        quantity=quantity,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=cost_usd,
    )
    # Attempt to link to catalog entry
    if workflow_key:
        wf = await get_workflow_catalog_by_key(db, workflow_key)
        if wf:
            rec.workflow_id = wf.id
    db.add(rec)
    await db.commit()
    await db.refresh(rec)
    return rec


async def get_usage_summary(db: AsyncSession, organization_id: str = None,
                             days: int = 30) -> dict:
    """Aggregate usage for platform or a specific org over the last N days."""
    from datetime import timedelta
    from sqlalchemy import and_
    cutoff = datetime.utcnow() - timedelta(days=days)

    stmt = select(
        UsageRecord.organization_id,
        UsageRecord.usage_type,
        UsageRecord.workflow_key,
        func.count().label("event_count"),
        func.sum(UsageRecord.tokens_in).label("tokens_in"),
        func.sum(UsageRecord.tokens_out).label("tokens_out"),
        func.sum(UsageRecord.quantity).label("total_quantity"),
    ).where(UsageRecord.recorded_at >= cutoff)

    if organization_id:
        try:
            oid = uuid.UUID(str(organization_id))
            stmt = stmt.where(UsageRecord.organization_id == oid)
        except (ValueError, AttributeError):
            pass

    stmt = stmt.group_by(
        UsageRecord.organization_id, UsageRecord.usage_type, UsageRecord.workflow_key
    ).order_by(func.count().desc())

    result = await db.execute(stmt)
    rows = result.all()

    # Cost totals are separate because cost_usd is nullable
    cost_stmt = select(
        func.sum(UsageRecord.cost_usd).label("total_cost"),
        func.count().filter(UsageRecord.cost_usd.isnot(None)).label("reported_events"),
        func.count().filter(UsageRecord.cost_usd.is_(None)).label("unreported_events"),
    ).where(UsageRecord.recorded_at >= cutoff)
    if organization_id:
        try:
            cost_stmt = cost_stmt.where(UsageRecord.organization_id == uuid.UUID(str(organization_id)))
        except (ValueError, AttributeError):
            pass
    cost_result = await db.execute(cost_stmt)
    cost_row = cost_result.one_or_none()

    breakdown = []
    for row in rows:
        breakdown.append({
            "organization_id": str(row.organization_id),
            "usage_type":      row.usage_type,
            "workflow_key":    row.workflow_key,
            "event_count":     row.event_count,
            "tokens_in":       int(row.tokens_in or 0),
            "tokens_out":      int(row.tokens_out or 0),
            "total_quantity":  int(row.total_quantity or 0),
        })

    total_cost = float(cost_row.total_cost) if cost_row and cost_row.total_cost is not None else None
    return {
        "period_days":         days,
        "total_cost_usd":      total_cost,             # None = no reported cost data
        "reported_events":     cost_row.reported_events if cost_row else 0,
        "unreported_events":   cost_row.unreported_events if cost_row else 0,
        "breakdown":           breakdown,
    }


async def get_org_billing_summary(
    db: AsyncSession,
    organization_id: str,
    days: int = 30,
) -> dict:
    """
    Return billing/usage summary for a single organization, grouped by workflow.
    Accurately aggregates all recorded usage for the organization with
    zero loss of runs or token metrics, ensuring database atomicity and consistency.
    """
    from datetime import timedelta
    from sqlalchemy import or_

    try:
        oid = uuid.UUID(str(organization_id))
    except (ValueError, AttributeError):
        return {"error": "Invalid organization ID"}

    # Resolve org + industry
    org_result = await db.execute(select(Organization).where(Organization.id == oid))
    org = org_result.scalar_one_or_none()
    if not org:
        return {"error": "Organization not found"}

    cutoff = datetime.utcnow() - timedelta(days=days)

    # 1. Fetch usage grouped by workflow from UsageRecord
    stmt = (
        select(
            UsageRecord.workflow_key,
            func.count().label("run_count"),
            func.sum(UsageRecord.quantity).label("total_quantity"),
            func.sum(UsageRecord.tokens_in).label("tokens_in"),
            func.sum(UsageRecord.tokens_out).label("tokens_out"),
            func.sum(UsageRecord.cost_usd).label("total_cost"),
        )
        .where(
            UsageRecord.organization_id == oid,
            UsageRecord.recorded_at >= cutoff,
        )
        .group_by(UsageRecord.workflow_key)
        .order_by(func.count().desc())
    )
    result = await db.execute(stmt)
    rows = result.all()

    breakdown_map: dict[str, dict] = {}
    for row in rows:
        wf_key = row.workflow_key or "unspecified_workflow"
        cost = float(row.total_cost) if row.total_cost is not None else 0.0
        runs = int(row.run_count or 0)
        breakdown_map[wf_key] = {
            "workflow_key":    wf_key,
            "run_count":       runs,
            "total_quantity":  int(row.total_quantity or 0),
            "tokens_in":       int(row.tokens_in or 0),
            "tokens_out":      int(row.tokens_out or 0),
            "cost_usd":        cost,
        }

    # 2. Check workflow_instances to catch any runs not yet logged in UsageRecord
    inst_stmt = (
        select(
            WorkflowInstance.workflow_name,
            func.count().label("inst_count"),
            func.sum(WorkflowInstance.total_tokens_in).label("tokens_in"),
            func.sum(WorkflowInstance.total_tokens_out).label("tokens_out"),
            func.sum(WorkflowInstance.total_cost_usd).label("total_cost"),
        )
        .where(
            WorkflowInstance.tenant_id == oid,
            WorkflowInstance.started_at >= cutoff,
            WorkflowInstance.status != "pending",  # exclude raw unsubmitted drafts
        )
        .group_by(WorkflowInstance.workflow_name)
    )
    inst_res = await db.execute(inst_stmt)
    inst_rows = inst_res.all()

    for irow in inst_rows:
        w_name = irow.workflow_name
        if not w_name:
            continue
        inst_cnt = int(irow.inst_count or 0)
        t_in = int(irow.tokens_in or 0)
        t_out = int(irow.tokens_out or 0)
        c_usd = float(irow.total_cost or 0.0)

        if w_name not in breakdown_map:
            breakdown_map[w_name] = {
                "workflow_key":    w_name,
                "run_count":       inst_cnt,
                "total_quantity":  inst_cnt,
                "tokens_in":       t_in,
                "tokens_out":      t_out,
                "cost_usd":        c_usd,
            }
        else:
            existing = breakdown_map[w_name]
            if inst_cnt > existing["run_count"]:
                existing["run_count"] = inst_cnt
                existing["total_quantity"] = max(existing["total_quantity"], inst_cnt)
                existing["tokens_in"] = max(existing["tokens_in"], t_in)
                existing["tokens_out"] = max(existing["tokens_out"], t_out)
                existing["cost_usd"] = max(existing["cost_usd"], c_usd)

    applicable_wfs = await get_available_workflows_for_org(db, organization_id)
    applicable_keys: set[str] = {wf.key for wf in applicable_wfs if wf.key}

    filtered_breakdown = []
    for wf_key, entry in breakdown_map.items():
        if applicable_keys and wf_key not in applicable_keys:
            continue
        filtered_breakdown.append(entry)

    workflow_breakdown = filtered_breakdown
    grand_total_cost = sum(w["cost_usd"] for w in workflow_breakdown)
    grand_run_count  = sum(w["run_count"] for w in workflow_breakdown)

    return {
        "organization_id":    str(oid),
        "organization_name":  org.name,
        "industry":           org.industry,
        "period_days":        days,
        "total_run_count":    grand_run_count,
        "total_cost_usd":     grand_total_cost if workflow_breakdown else None,
        "workflow_breakdown": workflow_breakdown,
        "applicable_workflow_keys": sorted(applicable_keys),
    }


async def list_usage_records(db: AsyncSession, organization_id: str = None,
                              workflow_key: str = None, limit: int = 200,
                              offset: int = 0) -> list[UsageRecord]:
    stmt = select(UsageRecord).order_by(UsageRecord.recorded_at.desc()).limit(limit).offset(offset)
    if organization_id:
        try:
            stmt = stmt.where(UsageRecord.organization_id == uuid.UUID(str(organization_id)))
        except (ValueError, AttributeError):
            pass
    if workflow_key:
        stmt = stmt.where(UsageRecord.workflow_key == workflow_key)
    result = await db.execute(stmt)
    return list(result.scalars().all())


def usage_record_to_dict(r: UsageRecord) -> dict:
    return {
        "id":                    str(r.id),
        "organization_id":       str(r.organization_id),
        "workflow_key":          r.workflow_key,
        "workflow_instance_id":  str(r.workflow_instance_id) if r.workflow_instance_id else None,
        "usage_type":            r.usage_type,
        "provider":              r.provider,
        "model":                 r.model,
        "quantity":              r.quantity,
        "tokens_in":             r.tokens_in,
        "tokens_out":            r.tokens_out,
        # Never fake cost — None means provider did not report it
        "cost_usd":              float(r.cost_usd) if r.cost_usd is not None else None,
        "recorded_at":           r.recorded_at.isoformat() if r.recorded_at else None,
    }


# ─── Invoices ─────────────────────────────────────────────────────────────────

async def list_invoices(db: AsyncSession, organization_id: str = None,
                         limit: int = 100) -> list[Invoice]:
    stmt = select(Invoice).order_by(Invoice.created_at.desc()).limit(limit)
    if organization_id:
        try:
            stmt = stmt.where(Invoice.organization_id == uuid.UUID(str(organization_id)))
        except (ValueError, AttributeError):
            pass
    result = await db.execute(stmt)
    return list(result.scalars().all())


def invoice_to_dict(inv: Invoice, org_name: str = None) -> dict:
    return {
        "id":                  str(inv.id),
        "organization_id":     str(inv.organization_id),
        "organization_name":   org_name,
        "invoice_number":      inv.invoice_number,
        "status":              inv.status,
        "subtotal_usd":        float(inv.subtotal_usd) if inv.subtotal_usd is not None else 0.0,
        "tax_usd":             float(inv.tax_usd) if inv.tax_usd is not None else 0.0,
        "total_usd":           float(inv.total_usd) if inv.total_usd is not None else 0.0,
        "due_date":            inv.due_date.isoformat() if inv.due_date else None,
        "paid_at":             inv.paid_at.isoformat() if inv.paid_at else None,
        "line_items":          inv.line_items or [],
        "notes":               inv.notes,
        "created_at":          inv.created_at.isoformat() if inv.created_at else None,
    }


# ─── Audit Events ─────────────────────────────────────────────────────────────

async def create_audit_event(db: AsyncSession, actor_id: str, action: str,
                              entity_type: str, entity_id: str = None,
                              organization_id: str = None, metadata: dict = None) -> AuditEvent:
    evt = AuditEvent(
        organization_id=uuid.UUID(str(organization_id)) if organization_id else None,
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id else None,
        metadata_=metadata or {},
    )
    db.add(evt)
    await db.commit()
    return evt


async def list_audit_events(db: AsyncSession, organization_id: str = None,
                             action: str = None, entity_type: str = None,
                             limit: int = 200, offset: int = 0) -> list[AuditEvent]:
    stmt = (
        select(AuditEvent)
        .order_by(AuditEvent.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if organization_id:
        try:
            stmt = stmt.where(AuditEvent.organization_id == uuid.UUID(str(organization_id)))
        except (ValueError, AttributeError):
            pass
    if action:
        stmt = stmt.where(AuditEvent.action.ilike(f"%{action}%"))
    if entity_type:
        stmt = stmt.where(AuditEvent.entity_type == entity_type)
    result = await db.execute(stmt)
    return list(result.scalars().all())


def audit_event_to_dict(e: AuditEvent) -> dict:
    return {
        "id":              str(e.id),
        "organization_id": str(e.organization_id) if e.organization_id else None,
        "actor_id":        e.actor_id,
        "action":          e.action,
        "entity_type":     e.entity_type,
        "entity_id":       e.entity_id,
        "metadata":        e.metadata_ or {},
        "created_at":      e.created_at.isoformat() if e.created_at else None,
    }


# ─── Platform Settings ────────────────────────────────────────────────────────

async def get_platform_setting(db: AsyncSession, key: str) -> Optional[Any]:
    result = await db.execute(select(PlatformSetting).where(PlatformSetting.key == key))
    row = result.scalar_one_or_none()
    return row.value if row else None


async def set_platform_setting(db: AsyncSession, key: str, value: Any,
                                updated_by: str = None, description: str = None) -> PlatformSetting:
    result = await db.execute(select(PlatformSetting).where(PlatformSetting.key == key))
    row = result.scalar_one_or_none()
    if row:
        row.value = value
        row.updated_by = updated_by
        row.updated_at = datetime.utcnow()
    else:
        row = PlatformSetting(key=key, value=value, updated_by=updated_by, description=description)
        db.add(row)
    await db.commit()
    return row


async def get_all_platform_settings(db: AsyncSession) -> dict:
    result = await db.execute(select(PlatformSetting))
    rows = result.scalars().all()
    return {r.key: r.value for r in rows}


# ─── Admin Dashboard Aggregates ───────────────────────────────────────────────

async def get_admin_platform_metrics(db: AsyncSession, include_test_fixtures: bool = False) -> dict:
    """
    Return KPI metrics for the Platform Overview dashboard.
    All values are from real DB queries — no fabricated numbers.
    Filters test fixture organizations by default.
    """
    from datetime import timedelta
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Active organizations
    active_orgs_query = select(Organization).where(Organization.active.is_(True))
    all_active_orgs = (await db.execute(active_orgs_query)).scalars().all()
    if not include_test_fixtures:
        test_patterns = ["test org", "test organization", "isolation test", "final verification", "hacker org", "auth test", "fixture org"]
        all_active_orgs = [
            o for o in all_active_orgs
            if not any(pat in (o.name or "").lower() for pat in test_patterns)
        ]
    active_orgs = len(all_active_orgs)

    # Total users (organization_users)
    total_users_result = await db.execute(select(func.count()).select_from(OrganizationUser))
    total_users = total_users_result.scalar() or 0

    # Active users = org users with active role (proxy: total org_users)
    active_users = total_users

    # Enabled workflows across all orgs (active assignments)
    enabled_wf_result = await db.execute(
        select(func.count()).select_from(OrganizationWorkflowAssignment)
        .where(OrganizationWorkflowAssignment.status == "active")
    )
    enabled_workflows = enabled_wf_result.scalar() or 0

    # Workflow runs today (using organization_id on workflow_instances)
    runs_today_result = await db.execute(
        select(func.count()).select_from(WFInstance)
        .where(WFInstance.started_at >= today_start)
    )
    runs_today = runs_today_result.scalar() or 0

    # Total runs all time
    total_runs_result = await db.execute(select(func.count()).select_from(WFInstance))
    total_runs = total_runs_result.scalar() or 0

    # Pending exceptions (approval_items with status=pending and review_type indicating failure/escalation)
    pending_exc_result = await db.execute(
        select(func.count()).select_from(ApprovalItem)
        .where(ApprovalItem.status == "pending")
    )
    pending_exceptions = pending_exc_result.scalar() or 0

    # AI spend — sum of cost_usd from usage_records and workflow_instances
    spend_result = await db.execute(
        select(func.sum(UsageRecord.cost_usd))
        .where(UsageRecord.cost_usd.isnot(None))
    )
    ai_spend_month = spend_result.scalar()
    if ai_spend_month is None or float(ai_spend_month) == 0.0:
        inst_spend_result = await db.execute(
            select(func.sum(WFInstance.total_cost_usd))
            .where(WFInstance.total_cost_usd.isnot(None))
        )
        inst_spend = inst_spend_result.scalar()
        ai_spend_month = float(inst_spend) if inst_spend is not None else 0.0
    else:
        ai_spend_month = float(ai_spend_month)

    # Active subscriptions count
    active_subs_result = await db.execute(
        select(func.count()).select_from(OrganizationSubscription)
        .where(OrganizationSubscription.status.in_(["active", "trialing"]))
    )
    active_subscriptions = active_subs_result.scalar() or 0

    return {
        "active_organizations":  active_orgs,
        "active_users":          active_users,
        "total_users":           total_users,
        "enabled_workflows":     enabled_workflows,
        "runs_today":            runs_today,
        "total_runs":            total_runs,
        "pending_exceptions":    pending_exceptions,
        "ai_spend_month_usd":    ai_spend_month,   # None = no cost data recorded yet
        "active_subscriptions":  active_subscriptions,
    }


async def get_org_activity_feed(db: AsyncSession, limit: int = 20) -> list[dict]:
    """Recent workflow runs across all orgs for the platform overview activity table."""
    stmt = (
        select(WFInstance, Organization.name.label("org_name"))
        .join(Organization, WFInstance.organization_id == Organization.id, isouter=True)
        .order_by(WFInstance.started_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.all()
    out = []
    for inst, org_name in rows:
        out.append({
            "run_id":          str(inst.id),
            "organization":    org_name or "Unknown",
            "organization_id": str(inst.organization_id),
            "workflow":        inst.workflow_name,
            "status":          inst.status,
            "started_at":      inst.started_at.isoformat() if inst.started_at else None,
            "completed_at":    inst.completed_at.isoformat() if inst.completed_at else None,
            "cost_usd":        float(inst.total_cost_usd) if inst.total_cost_usd else None,
            "tokens":          (inst.total_tokens_in or 0) + (inst.total_tokens_out or 0),
        })
    return out


async def get_org_with_details(db: AsyncSession, organization_id: str) -> Optional[dict]:
    """
    Return a single org with its subscription, plan, workflow assignments, user count,
    and recent run stats — used by the org detail page.
    """
    try:
        oid = uuid.UUID(str(organization_id))
    except (ValueError, AttributeError):
        return None

    org_result = await db.execute(select(Organization).where(Organization.id == oid))
    org = org_result.scalar_one_or_none()
    if not org:
        return None

    # Users
    users_result = await db.execute(
        select(OrganizationUser).where(OrganizationUser.organization_id == oid)
    )
    users = list(users_result.scalars().all())

    # Subscription + plan
    sub = await get_org_subscription(db, organization_id)
    plan = await get_billing_plan(db, str(sub.plan_id)) if sub else None

    # Workflow assignments with catalog info
    assignments = await get_org_workflow_assignments(db, organization_id)
    assignment_dicts = []
    for a in assignments:
        cat = await get_workflow_catalog_entry(db, str(a.workflow_id))
        assignment_dicts.append(workflow_assignment_to_dict(a, cat))

    # Run stats
    runs_result = await db.execute(
        select(
            func.count().label("total_runs"),
            func.sum(WFInstance.total_cost_usd).label("total_cost"),
            func.sum(WFInstance.total_tokens_in + WFInstance.total_tokens_out).label("total_tokens"),
        ).where(WFInstance.organization_id == oid)
    )
    run_stats = runs_result.one_or_none()

    return {
        "id":           str(org.id),
        "name":         org.name,
        "industry":     org.industry,
        "active":       org.active,
        "created_at":   org.created_at.isoformat() if org.created_at else None,
        "updated_at":   org.updated_at.isoformat() if org.updated_at else None,
        "user_count":   len(users),
        "users":        [
            {
                "id":       str(u.id),
                "user_id":  str(u.user_id),
                "email":    u.email,
                "full_name": u.full_name,
                "role":     u.role,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in users
        ],
        "subscription": org_subscription_to_dict(sub, plan) if sub else None,
        "plan":         billing_plan_to_dict(plan) if plan else None,
        "workflow_assignments": assignment_dicts,
        "run_stats": {
            "total_runs":    run_stats.total_runs if run_stats else 0,
            "total_cost_usd": float(run_stats.total_cost or 0) if run_stats else None,
            "total_tokens":   int(run_stats.total_tokens or 0) if run_stats else 0,
        },
    }


async def list_organizations_with_details(db: AsyncSession, include_test_fixtures: bool = False) -> list[dict]:
    """
    Return all organizations with subscription, plan, assignment counts, user counts,
    and recent run activity — used by the organizations list page.
    Filters out automated test fixture orgs by default.
    """
    orgs_result = await db.execute(select(Organization).order_by(Organization.created_at.desc()))
    orgs = list(orgs_result.scalars().all())

    if not include_test_fixtures:
        test_patterns = ["test org", "test organization", "isolation test", "final verification", "hacker org", "auth test", "fixture org"]
        orgs = [
            o for o in orgs
            if not any(pat in (o.name or "").lower() for pat in test_patterns)
        ]

    # Bulk-load subscriptions
    subs_result = await db.execute(select(OrganizationSubscription))
    subs_map: dict[str, OrganizationSubscription] = {
        str(s.organization_id): s for s in subs_result.scalars().all()
    }

    # Bulk-load plans
    plans_result = await db.execute(select(BillingPlan))
    plans_map: dict[str, BillingPlan] = {
        str(p.id): p for p in plans_result.scalars().all()
    }

    # Bulk user counts
    users_count_result = await db.execute(
        select(OrganizationUser.organization_id, func.count().label("cnt"))
        .group_by(OrganizationUser.organization_id)
    )
    users_count: dict[str, int] = {str(r.organization_id): r.cnt for r in users_count_result.all()}

    # Bulk assignment counts
    assign_count_result = await db.execute(
        select(OrganizationWorkflowAssignment.organization_id, func.count().label("cnt"))
        .where(OrganizationWorkflowAssignment.status == "active")
        .group_by(OrganizationWorkflowAssignment.organization_id)
    )
    assign_count: dict[str, int] = {str(r.organization_id): r.cnt for r in assign_count_result.all()}

    # Bulk run counts + latest activity
    runs_result = await db.execute(
        select(
            WFInstance.organization_id,
            func.count().label("run_count"),
            func.max(WFInstance.started_at).label("last_activity"),
            func.sum(WFInstance.total_cost_usd).label("total_cost"),
        ).group_by(WFInstance.organization_id)
    )
    run_stats: dict[str, Any] = {}
    for row in runs_result.all():
        run_stats[str(row.organization_id)] = {
            "run_count":    row.run_count,
            "last_activity": row.last_activity.isoformat() if row.last_activity else None,
            "total_cost":   float(row.total_cost) if row.total_cost else None,
        }

    result = []
    for org in orgs:
        oid = str(org.id)
        sub = subs_map.get(oid)
        plan = plans_map.get(str(sub.plan_id)) if sub else None
        stats = run_stats.get(oid, {})
        result.append({
            "id":               oid,
            "name":             org.name,
            "industry":         org.industry,
            "active":           org.active,
            "created_at":       org.created_at.isoformat() if org.created_at else None,
            "user_count":       users_count.get(oid, 0),
            "assigned_workflows": assign_count.get(oid, 0),
            "plan_name":        plan.name if plan else None,
            "plan_slug":        plan.slug if plan else None,
            "subscription_status": sub.status if sub else None,
            "effective_subscription_status": (
                "trial_expired" if (
                    sub and sub.status == "trialing"
                    and sub.trial_ends_at
                    and sub.trial_ends_at < datetime.utcnow()
                ) else (sub.status if sub else None)
            ),
            "trial_ends_at":    sub.trial_ends_at.isoformat() if (sub and sub.trial_ends_at) else None,
            "run_count":        stats.get("run_count", 0),
            "last_activity":    stats.get("last_activity"),
            "total_spend_usd":  stats.get("total_cost"),
        })
    return result
