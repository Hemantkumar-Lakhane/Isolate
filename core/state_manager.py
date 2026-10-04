"""
core/state_manager.py
=====================
Manages all workflow instance state in PostgreSQL.
Provides atomic state transitions and full history.

CONSTANT — do not modify for business customization.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional

import structlog
from sqlalchemy import (Column, DateTime, Float, Integer, String, Text,
                         Boolean, select, update)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, mapped_column
import uuid
from datetime import datetime
log = structlog.get_logger()


class WorkflowStatus(str, Enum):
    PENDING    = "pending"
    RUNNING    = "running"
    PAUSED     = "paused"      # Admin paused
    ESCALATED  = "escalated"   # Waiting for human decision
    PENDING_A2A = "pending_a2a"
    COMPLETED  = "completed"
    FAILED     = "failed"
    STOPPED    = "stopped"     # Admin force-stopped


class AgentStatus(str, Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    SUCCESS   = "success"
    ESCALATED = "escalated"
    FAILED    = "failed"
    SKIPPED   = "skipped"


# ─────────────────────────────────────────────────────────────────────────────
# SQLAlchemy ORM Models
# ─────────────────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


class Tenant(Base):
    __tablename__ = "tenants"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name        = Column(String(255), nullable=False)
    industry    = Column(String(100), nullable=False)
    config      = Column(JSONB, nullable=False)
    active      = Column(Boolean, default=True)
    created_at  = Column(DateTime, default=datetime.utcnow)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WorkflowDefinition(Base):
    __tablename__ = "workflow_definitions"

    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name           = Column(String(255), nullable=False)
    industry       = Column(String(100), nullable=False)
    version        = Column(String(20), nullable=False, default="1.0.0")
    dag_definition = Column(JSONB, nullable=False)
    prompt_refs    = Column(JSONB)
    active         = Column(Boolean, default=True)
    created_at     = Column(DateTime, default=datetime.utcnow)


class WorkflowInstance(Base):
    __tablename__ = "workflow_instances"

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id        = Column("organization_id", UUID(as_uuid=True), nullable=False)
    definition_id    = Column(UUID(as_uuid=True), nullable=True)
    workflow_name    = Column(String(255), nullable=False)
    status           = Column(String(50), nullable=False, default=WorkflowStatus.PENDING)
    trigger_signal   = Column("trigger_payload", JSONB, nullable=False)
    current_node     = Column(String(100))
    context          = Column(JSONB, default={})
    started_at       = Column(DateTime, default=datetime.utcnow)
    completed_at     = Column(DateTime)
    outcome          = Column(JSONB)
    error_log        = Column(Text)

    # Cost tracking
    total_tokens_in  = Column(Integer, default=0)
    total_tokens_out = Column(Integer, default=0)
    total_cost_usd   = Column(Float, default=0.0)

    # Denormalized last-10 per-node run summary. The physical column is added in
    # db/init.sql (ALTER TABLE ... ADD COLUMN agent_runs JSONB DEFAULT '[]') with a
    # BEFORE UPDATE trigger that trims to the 10 most-recent entries; full durable
    # history lives in the normalized agent_run_records table. This mapping is
    # REQUIRED: update_workflow_status()/workflow_to_dict() reference it, and without
    # it the per-agent callback raises AttributeError on every run (silently swallowed),
    # so current_node/per-node status never persist and completed runs can't rehydrate
    # their pipeline coloring on reload.
    agent_runs       = Column(JSONB, default=list)


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    instance_id     = Column(UUID(as_uuid=True), nullable=False)
    agent_type      = Column(String(100), nullable=False)
    node_id         = Column(String(100), nullable=False)
    input_data      = Column(JSONB, nullable=False)
    output_data     = Column(JSONB)
    confidence      = Column(Float)
    reasoning_chain = Column(Text)
    tokens_in       = Column(Integer, default=0)
    tokens_out      = Column(Integer, default=0)
    cost_usd        = Column(Float, default=0.0)
    model_used      = Column(String(200))
    duration_ms     = Column(Integer)
    status          = Column(String(50), default=AgentStatus.PENDING)
    created_at      = Column(DateTime, default=datetime.utcnow)
    completed_at    = Column(DateTime)


class AgentRunRecord(Base):
    """
    Normalised per-node agent run record.
    Replaces the unbounded agent_runs JSONB array on WorkflowInstance.
    """
    __tablename__ = "agent_run_records"

    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    instance_id       = Column(UUID(as_uuid=True), nullable=False)
    node_id           = Column(String(100), nullable=False)
    agent_type        = Column("agent_capability", String(100))
    status            = Column(String(50))
    cost_usd          = Column(Float, default=0.0)
    tokens_in         = Column(Integer, default=0)
    tokens_out        = Column(Integer, default=0)
    model_used        = Column(String(200))
    confidence        = Column(Float)
    duration_ms       = Column(Integer)
    error             = Column(Text)
    tools_used        = Column(JSONB, default=list)
    # Full structured output of this node (what the agent actually produced),
    # tied to (instance_id, node_id). Secrets are redacted and the payload is
    # size-capped by the orchestrator before it reaches here. The physical
    # column is added idempotently at startup (api/main.py lifespan) and in
    # db/init.sql / db/migrations for fresh databases. Metrics stay in the
    # dedicated columns above; this holds the business result the UI renders.
    output_data       = Column(JSONB, nullable=True)
    completed_at      = Column(DateTime, default=datetime.utcnow)


class Escalation(Base):
    __tablename__ = "escalations"

    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    instance_id         = Column(UUID(as_uuid=True), nullable=False)
    tenant_id           = Column(UUID(as_uuid=True), nullable=False)
    node_id             = Column(String(100), nullable=False)
    reason              = Column(Text, nullable=False)
    context_brief       = Column(Text, nullable=False)
    recommended_action  = Column(Text)
    options             = Column(JSONB)
    status              = Column(String(50), default="pending")
    decision            = Column(JSONB)
    decided_by          = Column(String(255))
    decided_at          = Column(DateTime)
    # Multi-step approval — added via migration 001, must match DB schema
    required_signatures = Column(Integer, nullable=False, server_default="1")
    signatures          = Column(JSONB, nullable=False, server_default="[]")
    action_chosen       = Column(String(255))
    created_at          = Column(DateTime, default=datetime.utcnow)


class PatternMemory(Base):
    __tablename__ = "pattern_memory"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id    = Column(UUID(as_uuid=True), nullable=False)
    pattern_key  = Column(String(255), nullable=False)
    pattern_data = Column(JSONB, nullable=False)
    success_rate = Column(Float)
    sample_size  = Column(Integer, default=1)
    pattern_status = Column(String(50), default="active")
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Outcome(Base):
    __tablename__ = "outcomes"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    instance_id   = Column(UUID(as_uuid=True), nullable=False)
    tenant_id     = Column(UUID(as_uuid=True), nullable=False)
    action_taken  = Column(String(255), nullable=False)
    action_detail = Column(JSONB)
    metric_name   = Column(String(255))
    metric_value  = Column(Float)
    measured_at   = Column(DateTime)
    created_at    = Column(DateTime, default=datetime.utcnow)

class User(Base):
    __tablename__ = "users"
 
    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email         = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name     = Column(String(255))
    role          = Column(String(50), nullable=False, default="tenant_user")
    tenant_id     = Column(UUID(as_uuid=True), nullable=True)
    is_active     = Column(Boolean, default=True)
    last_login    = Column(DateTime)
    created_at    = Column(DateTime, default=datetime.utcnow)
    updated_at    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PasswordResetToken(Base):
    """
    Single-use, expiring password-reset tokens.

    Only a SHA-256 hash of the token is ever stored (``token_hash``); the raw
    token exists only in the emailed reset link (or the dev-only inspection
    response). ``used_at`` enforces single-use; ``expires_at`` enforces TTL.
    Naive UTC datetimes, consistent with the rest of this schema.
    """
    __tablename__ = "password_reset_tokens"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id    = Column(UUID(as_uuid=True), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, index=True)  # SHA-256 hex
    expires_at = Column(DateTime, nullable=False)
    used_at    = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class A2ARequest(Base):
    __tablename__ = "a2a_requests"
 
    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    instance_id         = Column(UUID(as_uuid=True))
    tenant_id           = Column(UUID(as_uuid=True))
    requesting_agent    = Column(String(100), nullable=False)
    target_agent        = Column(String(100), nullable=False)
    target_node_id      = Column(String(100))
    reason              = Column(Text, nullable=False)
    refinement_note     = Column(Text)
    new_tools           = Column(JSONB, nullable=False, server_default="[]")
    estimated_cost_usd  = Column(Float, default=0.001)
    status              = Column(String(50), default="pending_permission")
    client_decision     = Column(String(50))
    decided_at          = Column(DateTime)
    completed_at        = Column(DateTime)
    created_at          = Column(DateTime, default=datetime.utcnow)
 
 
class CustomTool(Base):
    __tablename__ = "custom_tools"
 
    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id        = Column(UUID(as_uuid=True), nullable=False)
    tool_name        = Column(String(255), nullable=False)
    display_name     = Column(String(255))
    description      = Column(Text)
    base_url         = Column(String(500))
    http_method      = Column(String(10), default="GET")
    headers_template = Column(JSONB, default=dict)
    body_template    = Column(JSONB, default=dict)
    query_params     = Column(JSONB, default=dict)
    auth_type        = Column(String(50), default="api_key")
    credential_id    = Column(UUID(as_uuid=True))
    response_path    = Column(String(255))
    is_active        = Column(Boolean, default=True)
    created_at       = Column(DateTime, default=datetime.utcnow)
 
 
class BudgetSettings(Base):
    __tablename__ = "budget_settings"
 
    id                            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id                     = Column(UUID(as_uuid=True), unique=True, nullable=False)
    optimization_level            = Column(Integer, default=1)
    strategy                      = Column(String(50), default="balanced")
    max_context_tokens            = Column(Integer, default=10000)
    enable_caching                = Column(Boolean, default=True)
    cache_ttl_seconds             = Column(Integer, default=3600)
    a2a_enabled                   = Column(Boolean, default=False)
    auto_retry_on_low_confidence    = Column(Boolean, default=True)
    confidence_retry_threshold      = Column(Float, default=0.6)
    enable_map_reduce_summarization = Column(Boolean, default=False)
    created_at                      = Column(DateTime, default=datetime.utcnow)
    updated_at                      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    max_spend_per_run_usd  = Column(Float, nullable=True)
 
 
class SystemEvent(Base):
    __tablename__ = "system_events"
 
    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type  = Column(String(100), nullable=False)
    tenant_id   = Column(UUID(as_uuid=True))
    instance_id = Column(UUID(as_uuid=True))
    message     = Column(Text, nullable=False)
    metadata_   = Column("metadata", JSONB, default=dict)
    created_at  = Column(DateTime, default=datetime.utcnow)

class IntegrationCredential(Base):
    __tablename__ = "integration_credentials"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id    = Column(UUID(as_uuid=True), nullable=False)
    tool_name    = Column(String(100), nullable=False)
    display_name = Column(String(255))                                        # <-- Add this
    credentials  = Column(JSONB, nullable=False)                              # (Keep this as JSONB)
    expires_at   = Column(DateTime)
    created_at   = Column(DateTime, default=datetime.utcnow)
    updated_at   = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow) # <-- Add this
    
    
class EmailQueue(Base):
    """Holds email drafts approved by the VerificationAgent, awaiting human review & send."""
    __tablename__ = "email_queue"

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id        = Column(UUID(as_uuid=True), nullable=False)
    run_id           = Column(UUID(as_uuid=True), nullable=True)
    account_id       = Column(String(255))
    recipient_email  = Column(String(255), nullable=False)
    recipient_name   = Column(String(255))
    subject          = Column(Text, nullable=False)
    body             = Column(Text, nullable=False)
    email_type       = Column(String(50))       # critical | at_risk | etc.
    csm_name         = Column(String(255))
    workflow_name    = Column(String(255))
    status           = Column(String(50), default="pending")  # pending | approved | rejected | sent
    rejection_reason = Column(Text)
    reviewed_at      = Column(DateTime)
    reviewed_by      = Column(String(255))
    created_at       = Column(DateTime, default=datetime.utcnow)


class ApprovalItem(Base):
    __tablename__ = "approval_items"

    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id     = Column(UUID(as_uuid=True), nullable=False)
    instance_id         = Column(UUID(as_uuid=True), nullable=True)
    node_id             = Column(String(100))
    review_type         = Column(String(100), nullable=False)
    reason              = Column(Text, nullable=False)
    context_brief       = Column(Text, nullable=False)
    payload             = Column(JSONB, default={})
    status              = Column(String(50), default="pending")
    required_signatures = Column(Integer, default=1)
    signatures          = Column(JSONB, default=list)
    decided_by          = Column(String(255))
    decided_at          = Column(DateTime)
    created_at          = Column(DateTime, default=datetime.utcnow)


class ProcessedEmailEvent(Base):
    __tablename__ = "processed_email_events"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), nullable=True)
    message_id      = Column(String(255), unique=True, nullable=False, index=True)
    batch_id        = Column(String(255), nullable=True, index=True)
    instance_id     = Column(UUID(as_uuid=True), nullable=True)
    source          = Column(String(100), default="synthetic_email")
    processed_at    = Column(DateTime, default=datetime.utcnow)


# ─────────────────────────────────────────────────────────────────────────────
# State Manager
# ─────────────────────────────────────────────────────────────────────────────

class StateManager:
    """
    All workflow state operations. Atomic transitions with full history.
    Admin controls: pause, stop, resume all go through here.
    """

    def __init__(self, session: AsyncSession):
        self._db = session
        self._admin_stop_flags: set[str] = set()  # instance_ids flagged for stop
        self._admin_pause_flags: set[str] = set() # instance_ids flagged for pause

    # ── Workflow Instance CRUD ─────────────────────────────────────────────

    async def create_instance(
        self,
        tenant_id: str,
        definition_id: str,
        workflow_name: str,
        trigger_signal: dict,
    ) -> WorkflowInstance:
        """Create a new workflow instance in PENDING state."""
        instance = WorkflowInstance(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            definition_id=definition_id,
            workflow_name=workflow_name,
            trigger_signal=trigger_signal,
            status=WorkflowStatus.PENDING,
            context={},
        )
        self._db.add(instance)
        await self._db.commit()
        await self._db.refresh(instance)
        log.info("Workflow instance created", instance_id=str(instance.id), workflow=workflow_name)
        return instance

    async def transition(
        self,
        instance_id: str,
        new_status: WorkflowStatus,
        current_node: Optional[str] = None,
        outcome: Optional[dict] = None,
        error: Optional[str] = None,
    ) -> None:
        """Atomically transition workflow status."""
        values: dict[str, Any] = {"status": new_status}
        if current_node is not None:
            values["current_node"] = current_node
        if outcome is not None:
            values["outcome"] = outcome
        if error is not None:
            values["error_log"] = error
        if new_status in (WorkflowStatus.COMPLETED, WorkflowStatus.FAILED, WorkflowStatus.STOPPED):
            values["completed_at"] = datetime.utcnow()

        await self._db.execute(
            update(WorkflowInstance)
            .where(WorkflowInstance.id == instance_id)
            .values(**values)
        )
        await self._db.commit()
        log.info("Workflow transitioned", instance_id=instance_id, status=new_status)

    async def update_context(self, instance_id: str, new_data: dict) -> None:
        """Merge new data into the workflow's accumulated context."""
        result = await self._db.execute(
            select(WorkflowInstance).where(WorkflowInstance.id == instance_id)
        )
        instance = result.scalar_one_or_none()
        if not instance:
            raise ValueError(f"Instance {instance_id} not found")

        merged = {**(instance.context or {}), **new_data}
        await self._db.execute(
            update(WorkflowInstance)
            .where(WorkflowInstance.id == instance_id)
            .values(context=merged)
        )
        await self._db.commit()

    
    async def write_agent_run_record(
        self,
        instance_id: str,
        agent_run_data: dict,
    ) -> None:
        """
        Write a single agent run to the normalised agent_run_records table.
        Called by the orchestrator's agent_run_callback in addition to (or
        instead of) the JSONB array append.
        """
        instance_uuid = uuid.UUID(instance_id) if isinstance(instance_id, str) else instance_id
        record = AgentRunRecord(
            id=uuid.uuid4(),
            instance_id=instance_uuid,
            node_id=agent_run_data.get("node_id", ""),
            agent_type=agent_run_data.get("agent_type", ""),
            status=agent_run_data.get("status", ""),
            cost_usd=agent_run_data.get("cost_usd", 0.0),
            tokens_in=agent_run_data.get("tokens_in", 0),
            tokens_out=agent_run_data.get("tokens_out", 0),
            model_used=agent_run_data.get("model_used", ""),
            confidence=agent_run_data.get("confidence"),
            duration_ms=agent_run_data.get("duration_ms"),
            error=agent_run_data.get("error"),
            tools_used=agent_run_data.get("tools_used", []),
            output_data=agent_run_data.get("output_data"),
            completed_at=datetime.utcnow(),
        )
        self._db.add(record)
        await self._db.commit()
    
    async def update_cost(
        self, instance_id: str, tokens_in: int, tokens_out: int, cost_usd: float
    ) -> None:
        """Accumulate cost tracking on instance."""
        result = await self._db.execute(
            select(WorkflowInstance).where(WorkflowInstance.id == instance_id)
        )
        inst = result.scalar_one_or_none()
        if inst:
            await self._db.execute(
                update(WorkflowInstance)
                .where(WorkflowInstance.id == instance_id)
                .values(
                    total_tokens_in=inst.total_tokens_in + tokens_in,
                    total_tokens_out=inst.total_tokens_out + tokens_out,
                    total_cost_usd=inst.total_cost_usd + cost_usd,
                )
            )
            await self._db.commit()

    async def get_instance(self, instance_id: str) -> Optional[WorkflowInstance]:
        result = await self._db.execute(
            select(WorkflowInstance).where(WorkflowInstance.id == instance_id)
        )
        return result.scalar_one_or_none()
    
    
    async def add_to_email_queue(
        self,
        tenant_id: str,
        run_id: str,
        account_id: str,
        recipient_email: str,
        recipient_name: str,
        subject: str,
        body: str,
        email_type: str = "",
        csm_name: str = "",
        workflow_name: str = "",
    ) -> "EmailQueue":
        item = EmailQueue(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            run_id=run_id,
            account_id=account_id,
            recipient_email=recipient_email,
            recipient_name=recipient_name,
            subject=subject,
            body=body,
            email_type=email_type,
            csm_name=csm_name,
            workflow_name=workflow_name,
            status="pending",
        )
        self._db.add(item)
        await self._db.flush()
        await self._db.commit()
        await self._db.refresh(item)
        return item

    async def get_active_instances(self, tenant_id: Optional[str] = None) -> list[WorkflowInstance]:
        q = select(WorkflowInstance).where(
            WorkflowInstance.status.in_([
                WorkflowStatus.RUNNING,
                WorkflowStatus.PAUSED,
                WorkflowStatus.ESCALATED,
            ])
        )
        if tenant_id:
            q = q.where(WorkflowInstance.tenant_id == tenant_id)
        result = await self._db.execute(q)
        return list(result.scalars().all())
    
    
    async def increment_loop_count(self, instance_id: str) -> int:
        """
        Atomically increment the A2A loop counter and return the new value.
        
        RACE-CONDITION FIX: The previous implementation did a SELECT then UPDATE
        in two separate statements — a second coroutine could read the same value
        between the two statements. Replaced with a single atomic SQL statement
        using PostgreSQL's UPDATE ... RETURNING.
        """
        from sqlalchemy import text as _text
        result = await self._db.execute(
            _text("""
                UPDATE workflow_instances
                SET loop_count = COALESCE(loop_count, 0) + 1
                WHERE id = :iid
                RETURNING loop_count
            """),
            {"iid": str(instance_id)},
        )
        await self._db.commit()
        row = result.fetchone()
        return row[0] if row else 1

    # ── Agent Run CRUD ─────────────────────────────────────────────────────

    async def create_agent_run(
        self, instance_id: str, agent_type: str, node_id: str, input_data: dict
    ) -> AgentRun:
        run = AgentRun(
            id=uuid.uuid4(),
            instance_id=instance_id,
            agent_type=agent_type,
            node_id=node_id,
            input_data=input_data,
            status=AgentStatus.RUNNING,
        )
        self._db.add(run)
        await self._db.commit()
        await self._db.refresh(run)
        return run

    async def complete_agent_run(
        self,
        run_id: str,
        output_data: dict,
        status: AgentStatus,
        confidence: Optional[float] = None,
        reasoning_chain: Optional[str] = None,
        tokens_in: int = 0,
        tokens_out: int = 0,
        cost_usd: float = 0.0,
        model_used: str = "",
        duration_ms: int = 0,
    ) -> None:
        await self._db.execute(
            update(AgentRun)
            .where(AgentRun.id == run_id)
            .values(
                output_data=output_data,
                status=status,
                confidence=confidence,
                reasoning_chain=reasoning_chain,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_usd=cost_usd,
                model_used=model_used,
                duration_ms=duration_ms,
                completed_at=datetime.utcnow(),
            )
        )
        await self._db.commit()

    # ── Escalation CRUD ────────────────────────────────────────────────────

    async def create_escalation(
        self,
        instance_id: str,
        tenant_id: str,
        node_id: str,
        reason: str,
        context_brief: str,
        recommended_action: Optional[str] = None,
        options: Optional[list] = None,
    ) -> Escalation:
        esc = Escalation(
            id=uuid.uuid4(),
            instance_id=instance_id,
            tenant_id=tenant_id,
            node_id=node_id,
            reason=reason,
            context_brief=context_brief,
            recommended_action=recommended_action,
            options=options or [],
        )
        self._db.add(esc)
        await self._db.commit()
        await self._db.refresh(esc)
        return esc

    async def resolve_escalation(
        self, escalation_id: str, decision: dict, decided_by: str
    ) -> None:
        await self._db.execute(
            update(Escalation)
            .where(Escalation.id == escalation_id)
            .values(
                status="resolved",
                decision=decision,
                decided_by=decided_by,
                decided_at=datetime.utcnow(),
            )
        )
        await self._db.commit()

    async def get_pending_escalations(
        self, tenant_id: Optional[str] = None
    ) -> list[Escalation]:
        q = select(Escalation).where(Escalation.status == "pending")
        if tenant_id:
            q = q.where(Escalation.tenant_id == tenant_id)
        result = await self._db.execute(q)
        return list(result.scalars().all())

    # ── Approval Items (HITL Action Center) ──────────────────────────────────

    async def create_approval_item(
        self,
        organization_id: str,
        instance_id: Optional[str],
        node_id: str,
        review_type: str,
        reason: str,
        context_brief: str,
        payload: Optional[dict] = None,
        required_signatures: int = 1,
    ) -> ApprovalItem:
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
        self._db.add(item)
        await self._db.commit()
        await self._db.refresh(item)
        log.info("ApprovalItem created", approval_id=str(item.id), review_type=review_type)
        return item

    async def get_pending_approvals(
        self, organization_id: Optional[str] = None
    ) -> list[ApprovalItem]:
        q = select(ApprovalItem).where(ApprovalItem.status == "pending").order_by(ApprovalItem.created_at.desc())
        if organization_id:
            org_uuid = uuid.UUID(organization_id) if isinstance(organization_id, str) else organization_id
            q = q.where(ApprovalItem.organization_id == org_uuid)
        result = await self._db.execute(q)
        return list(result.scalars().all())

    async def decide_approval_item(
        self,
        approval_id: str,
        decision_status: str,
        decided_by: str,
        patch_payload: Optional[dict] = None,
    ) -> Optional[ApprovalItem]:
        appr_uuid = uuid.UUID(approval_id) if isinstance(approval_id, str) else approval_id
        result = await self._db.execute(select(ApprovalItem).where(ApprovalItem.id == appr_uuid))
        item = result.scalar_one_or_none()
        if not item:
            return None

        item.status = decision_status  # "approved" or "rejected"
        item.decided_by = decided_by
        item.decided_at = datetime.utcnow()
        if patch_payload and isinstance(item.payload, dict):
            item.payload = {**item.payload, **patch_payload}

        await self._db.commit()
        await self._db.refresh(item)
        log.info("ApprovalItem decided", approval_id=str(item.id), status=decision_status, decided_by=decided_by)
        return item

    # ── Processed Email Events (Idempotency & Batching) ──────────────────────

    async def get_processed_email_ids(self, source: str = "synthetic_email") -> set[str]:
        q = select(ProcessedEmailEvent.message_id).where(ProcessedEmailEvent.source == source)
        result = await self._db.execute(q)
        return set(result.scalars().all())

    async def record_processed_emails(
        self,
        message_ids: list[str],
        batch_id: Optional[str] = None,
        instance_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        source: str = "synthetic_email",
    ) -> int:
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
            self._db.add(evt)
            count += 1
        await self._db.commit()
        return count
    async def suspend_workflow(
        self,
        instance_id: str,
        resume_from_node: Optional[str],
        context: dict,
        status: WorkflowStatus,
        extra: Optional[dict] = None,
    ) -> None:
        """
        Persist workflow state so it can be resumed after a human decision.
        Stores the full accumulated_context and a suspension envelope in context["_suspension"].
        """
        suspension_data = {
            "resume_from_node": resume_from_node,
            **(extra or {}),
        }
        # Merge suspension metadata into context so it survives a single JSONB column
        frozen_context = {**context, "_suspension": suspension_data}
        await self._db.execute(
            update(WorkflowInstance)
            .where(WorkflowInstance.id == instance_id)
            .values(
                status=status,
                context=frozen_context,
                suspension_data=suspension_data,
            )
        )
        await self._db.commit()
        log.info("Workflow suspended", instance_id=instance_id, status=status,
                 resume_from=resume_from_node)
 
    async def get_suspension_context(self, instance_id: str) -> tuple[dict, dict]:
        """
        Load a suspended workflow's accumulated context and suspension envelope.
        Returns (accumulated_context, suspension_data).
        """
        result = await self._db.execute(
            select(WorkflowInstance).where(WorkflowInstance.id == instance_id)
        )
        inst = result.scalar_one_or_none()
        if not inst:
            raise ValueError(f"Workflow instance {instance_id} not found")
 
        raw = inst.context or {}
        suspension = raw.get("_suspension", {})
        # Strip the suspension envelope from the context returned to the agent
        ctx = {k: v for k, v in raw.items() if k != "_suspension"}
        return ctx, suspension
 
    # ── Escalation multi-step approval ───────────────────────────────────────
 
    async def add_escalation_signature(
        self,
        escalation_id: str,
        user_id: str,
        user_email: str,
        action_chosen: str,
        decision: dict,
    ) -> Escalation:
        """
        Append a human signature to an escalation.
        Returns the updated escalation.  Call is idempotent for the same user_id.
        """
        result = await self._db.execute(
            select(Escalation).where(Escalation.id == escalation_id)
        )
        esc = result.scalar_one_or_none()
        if not esc:
            raise ValueError(f"Escalation {escalation_id} not found")
 
        current_sigs: list = list(esc.signatures or [])
        # Idempotent — don't double-count the same signer
        if not any(s.get("user_id") == user_id for s in current_sigs):
            current_sigs.append({
                "user_id": user_id,
                "user_email": user_email,
                "action_chosen": action_chosen,
                "decision": decision,
                "signed_at": datetime.utcnow().isoformat(),
            })
 
        required = esc.required_signatures or 1
        new_status = "resolved" if len(current_sigs) >= required else esc.status
 
        await self._db.execute(
            update(Escalation)
            .where(Escalation.id == escalation_id)
            .values(
                signatures=current_sigs,
                status=new_status,
                decided_at=datetime.utcnow() if new_status == "resolved" else esc.decided_at,
                decided_by=user_email if new_status == "resolved" else esc.decided_by,
                decision={"action": action_chosen, **decision} if new_status == "resolved" else esc.decision,
                action_chosen=action_chosen if new_status == "resolved" else esc.action_chosen,
            )
        )
        await self._db.commit()
 
        # Re-fetch to return updated state
        result = await self._db.execute(
            select(Escalation).where(Escalation.id == escalation_id)
        )
        return result.scalar_one()
 
    # ── A2A requests ─────────────────────────────────────────────────────────
 
    async def create_a2a_request(
        self,
        instance_id: str,
        tenant_id: str,
        requesting_agent: str,
        target_agent: str,
        target_node_id: str,
        reason: str,
        refinement_note: str = "",
        estimated_cost_usd: float = 0.001,
        new_tools: list = None,
    ) -> A2ARequest:
        req = A2ARequest(
            id=uuid.uuid4(),
            instance_id=instance_id,
            tenant_id=tenant_id,
            requesting_agent=requesting_agent,
            target_agent=target_agent,
            target_node_id=target_node_id,
            reason=reason,
            refinement_note=refinement_note,
            new_tools=new_tools or [],
            estimated_cost_usd=estimated_cost_usd,
            status="pending_permission",
        )
        self._db.add(req)
        await self._db.commit()
        await self._db.refresh(req)
        return req
 
    async def decide_a2a_request(self, a2a_id: str, approved: bool) -> A2ARequest:
        decision = "approved" if approved else "rejected"
        await self._db.execute(
            update(A2ARequest)
            .where(A2ARequest.id == a2a_id)
            .values(status=decision, client_decision=decision, decided_at=datetime.utcnow())
        )
        await self._db.commit()
        result = await self._db.execute(select(A2ARequest).where(A2ARequest.id == a2a_id))
        return result.scalar_one()
 
    async def get_pending_a2a(self, tenant_id: Optional[str] = None) -> list[A2ARequest]:
        q = select(A2ARequest).where(A2ARequest.status == "pending_permission")
        if tenant_id:
            q = q.where(A2ARequest.tenant_id == tenant_id)
        result = await self._db.execute(q)
        return list(result.scalars().all())
    # ── Admin Controls ─────────────────────────────────────────────────────

    def signal_stop(self, instance_id: str) -> None:
        """Admin: request graceful stop of a running workflow."""
        self._admin_stop_flags.add(instance_id)
        log.warning("ADMIN: Stop signal sent", instance_id=instance_id)

    def signal_pause(self, instance_id: str) -> None:
        """Admin: pause workflow at next node boundary."""
        self._admin_pause_flags.add(instance_id)
        log.warning("ADMIN: Pause signal sent", instance_id=instance_id)

    def signal_resume(self, instance_id: str) -> None:
        """Admin: resume a paused workflow."""
        self._admin_pause_flags.discard(instance_id)
        log.info("ADMIN: Resume signal sent", instance_id=instance_id)

    def should_stop(self, instance_id: str) -> bool:
        """Check if admin has requested stop for this instance."""
        return instance_id in self._admin_stop_flags

    def should_pause(self, instance_id: str) -> bool:
        """Check if admin has requested pause for this instance."""
        return instance_id in self._admin_pause_flags

    # ── Pattern Memory ─────────────────────────────────────────────────────

    async def get_patterns(self, tenant_id: str, pattern_key: str) -> list[PatternMemory]:
        result = await self._db.execute(
            select(PatternMemory)
            .where(PatternMemory.tenant_id == tenant_id)
            .where(PatternMemory.pattern_key.like(f"{pattern_key}%"))
            .order_by(PatternMemory.last_updated.desc())
            .limit(10)
        )
        return list(result.scalars().all())

    async def upsert_pattern(
        self,
        tenant_id: str,
        pattern_key: str,
        pattern_data: dict,
        success: bool,
        sandbox: bool = True,           # ← ADD: default to sandbox mode
    ) -> None:
        result = await self._db.execute(
            select(PatternMemory)
            .where(PatternMemory.tenant_id == tenant_id)
            .where(PatternMemory.pattern_key == pattern_key)
        )
        existing = result.scalar_one_or_none()
 
        if existing:
            old_rate = existing.success_rate or 0.5
            n = existing.sample_size or 1
            new_rate = (old_rate * n + (1.0 if success else 0.0)) / (n + 1)
            await self._db.execute(
                update(PatternMemory)
                .where(PatternMemory.id == existing.id)
                .values(
                    pattern_data=pattern_data,
                    success_rate=new_rate,
                    sample_size=n + 1,
                    last_updated=datetime.utcnow(),
                    # Keep existing status - don't reset promoted patterns to sandbox
                )
            )
        else:
            status = "pending_review" if sandbox else "active"
            pm = PatternMemory(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                pattern_key=pattern_key,
                pattern_data=pattern_data,
                success_rate=1.0 if success else 0.0,
                sample_size=1,
                pattern_status=status,
            )
            self._db.add(pm)
 
        await self._db.commit()
 
    async def promote_pattern(self, tenant_id: str, pattern_key: str) -> bool:
        """Promote a pending_review pattern to active (God View admin action)."""
        result = await self._db.execute(
            update(PatternMemory)
            .where(PatternMemory.tenant_id == tenant_id)
            .where(PatternMemory.pattern_key == pattern_key)
            .where(PatternMemory.pattern_status == "pending_review")
            .values(pattern_status="active")
        )
        await self._db.commit()
        return result.rowcount > 0
 
    async def get_active_patterns(self, tenant_id: str, pattern_key: str) -> list[PatternMemory]:
        """Get only promoted/active patterns for RAG injection (sandbox excluded)."""
        result = await self._db.execute(
            select(PatternMemory)
            .where(PatternMemory.tenant_id == tenant_id)
            .where(PatternMemory.pattern_key.like(f"{pattern_key}%"))
            .where(PatternMemory.pattern_status == "active")  # ← Only active
            .order_by(PatternMemory.last_updated.desc())
            .limit(10)
        )
        return list(result.scalars().all())
        
    
