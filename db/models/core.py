"""
db/models/core.py
=================
Core Platform ORM Models: Organizations, Users, Tool Connections, Workflows, Agents, Approvals, Evidence, Audit.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, synonym

class Base(DeclarativeBase):
    pass

class Organization(Base):
    __tablename__ = "organizations"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name            = Column(String(255), nullable=False)
    industry        = Column(String(100), nullable=False, default="saas")
    enabled_modules = Column(JSONB, nullable=False, default=["medical_tourism"])
    profile_config  = Column(JSONB, nullable=False, default={})
    active          = Column(Boolean, default=True)
    created_at      = Column(DateTime, default=datetime.utcnow)
    updated_at      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class OrganizationUser(Base):
    __tablename__ = "organization_users"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), nullable=False)
    tenant_id       = synonym("organization_id")
    user_id         = Column(UUID(as_uuid=True), nullable=False)
    email           = Column(String(255), nullable=False)
    full_name       = Column(String(255))
    role            = Column(String(50), nullable=False, default="org_user") # platform_admin, org_admin, org_user
    created_at      = Column(DateTime, default=datetime.utcnow)

class ToolConnection(Base):
    __tablename__ = "tool_connections"

    id                    = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id       = Column(UUID(as_uuid=True), nullable=False)
    tenant_id             = synonym("organization_id")
    tool_name             = Column(String(100), nullable=False)
    display_name          = Column(String(255))
    status                = Column(String(50), nullable=False, default="not_connected") # not_connected, connected, error
    encrypted_credentials = Column(Text)
    config                = Column(JSONB, default={})
    last_tested_at        = Column(DateTime)
    created_at            = Column(DateTime, default=datetime.utcnow)

class WorkflowDefinition(Base):
    __tablename__ = "workflow_definitions"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), nullable=True)
    tenant_id       = synonym("organization_id")
    name            = Column(String(255), nullable=False)
    industry        = Column(String(100), nullable=False, default="general")
    version         = Column(String(20), nullable=False, default="1.0.0")
    dag_definition  = Column(JSONB, nullable=False)
    is_template     = Column(Boolean, default=False)
    active          = Column(Boolean, default=True)
    created_at      = Column(DateTime, default=datetime.utcnow)

class WorkflowInstance(Base):
    __tablename__ = "workflow_instances"

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id  = Column(UUID(as_uuid=True), nullable=False)
    tenant_id        = synonym("organization_id")
    definition_id    = Column(UUID(as_uuid=True), nullable=True)
    workflow_name    = Column(String(255), nullable=False)
    status           = Column(String(50), nullable=False, default="pending")
    trigger_payload  = Column(JSONB, nullable=False, default={})
    current_node     = Column(String(100))
    context          = Column(JSONB, default={})
    started_at       = Column(DateTime, default=datetime.utcnow)
    completed_at     = Column(DateTime)
    outcome          = Column(JSONB)
    error_log        = Column(Text)
    total_tokens_in  = Column(Integer, default=0)
    total_tokens_out = Column(Integer, default=0)
    total_cost_usd   = Column(Float, default=0.0)

class AgentRunRecord(Base):
    __tablename__ = "agent_run_records"

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    instance_id      = Column(UUID(as_uuid=True), nullable=False)
    node_id          = Column(String(100), nullable=False)
    agent_capability = Column(String(100), nullable=False)
    status           = Column(String(50), default="pending")
    cost_usd         = Column(Float, default=0.0)
    tokens_in        = Column(Integer, default=0)
    tokens_out       = Column(Integer, default=0)
    model_used       = Column(String(200))
    confidence       = Column(Float)
    duration_ms      = Column(Integer)
    error            = Column(Text)
    tools_used       = Column(JSONB, default=list)
    completed_at     = Column(DateTime, default=datetime.utcnow)

class ApprovalItem(Base):
    __tablename__ = "approval_items"

    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id     = Column(UUID(as_uuid=True), nullable=False)
    tenant_id           = synonym("organization_id")
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

class EvidenceRecord(Base):
    __tablename__ = "evidence_records"

    id                 = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id    = Column(UUID(as_uuid=True), nullable=False)
    tenant_id          = synonym("organization_id")
    instance_id        = Column(UUID(as_uuid=True), nullable=False)
    evidence_json_path = Column(String(500), nullable=False)
    checksum           = Column(String(64))
    created_at         = Column(DateTime, default=datetime.utcnow)

class AuditEvent(Base):
    __tablename__ = "audit_events"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True))
    tenant_id       = synonym("organization_id")
    actor_id        = Column(String(255), nullable=False)
    action          = Column(String(100), nullable=False)
    entity_type     = Column(String(100), nullable=False)
    entity_id       = Column(String(255))
    metadata_       = Column("metadata", JSONB, default={})
    created_at      = Column(DateTime, default=datetime.utcnow)

class ProcessedEmailEvent(Base):
    __tablename__ = "processed_email_events"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), nullable=True)
    message_id      = Column(String(255), unique=True, nullable=False, index=True)
    batch_id        = Column(String(255), nullable=True, index=True)
    instance_id     = Column(UUID(as_uuid=True), nullable=True)
    source          = Column(String(100), default="synthetic_email")
    processed_at    = Column(DateTime, default=datetime.utcnow)


# =============================================================================
# Billing & Entitlement Models (Migration 003)
# =============================================================================

from sqlalchemy import Numeric, UniqueConstraint

class WorkflowCatalog(Base):
    """Platform-level catalog of all workflow products SMBFlow offers."""
    __tablename__ = "workflow_catalog"

    id                    = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name                  = Column(String(255), nullable=False)
    key                   = Column(String(100), nullable=False, unique=True)
    description           = Column(Text)
    category              = Column(String(100), nullable=False, default="general")
    status                = Column(String(50),  nullable=False, default="active")   # active | beta | deprecated
    version               = Column(String(20),  nullable=False, default="1.0.0")
    pricing_model         = Column(String(50),  nullable=False, default="included")  # included | per_run | metered
    required_integrations = Column(JSONB, nullable=False, default=list)
    supported_modules     = Column(JSONB, nullable=False, default=list)
    metadata_             = Column("metadata", JSONB, nullable=False, default=dict)
    active                = Column(Boolean, nullable=False, default=True)
    # ── Industry applicability (Migration 004) ────────────────────────────────
    # scope:    'GLOBAL'   — available to all orgs subject to plan + assignment
    #           'INDUSTRY' — only available when org.industry == workflow.industry
    scope                 = Column(String(20),  nullable=False, default="GLOBAL")
    industry              = Column(String(100), nullable=True)   # NULL for GLOBAL scope
    created_at            = Column(DateTime, default=datetime.utcnow)
    updated_at            = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BillingPlan(Base):
    """SaaS billing plans (Free, Starter, Growth, Enterprise)."""
    __tablename__ = "billing_plans"

    id                      = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name                    = Column(String(100), nullable=False)
    slug                    = Column(String(100), nullable=False, unique=True)
    description             = Column(Text)
    monthly_price_usd       = Column(Numeric(10, 2), nullable=False, default=0)
    annual_price_usd        = Column(Numeric(10, 2), nullable=False, default=0)
    included_workflow_runs  = Column(Integer, nullable=False, default=0)
    included_ai_tokens      = Column(Integer, nullable=False, default=0)
    included_image_gens     = Column(Integer, nullable=False, default=0)
    included_users          = Column(Integer, nullable=False, default=1)
    overage_run_price_usd   = Column(Numeric(10, 6), nullable=False, default=0)
    overage_token_price_usd = Column(Numeric(10, 9), nullable=False, default=0)
    overage_image_price_usd = Column(Numeric(10, 6), nullable=False, default=0)
    max_workflow_runs       = Column(Integer, nullable=False, default=0)  # 0 = unlimited
    max_users               = Column(Integer, nullable=False, default=0)  # 0 = unlimited
    status                  = Column(String(50), nullable=False, default="active")  # active | archived | hidden
    is_public               = Column(Boolean, nullable=False, default=True)
    sort_order              = Column(Integer, nullable=False, default=0)
    metadata_               = Column("metadata", JSONB, nullable=False, default=dict)
    created_at              = Column(DateTime, default=datetime.utcnow)
    updated_at              = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PlanWorkflowEntitlement(Base):
    """Which workflow catalog entries a billing plan includes."""
    __tablename__ = "plan_workflow_entitlements"
    __table_args__ = (UniqueConstraint("plan_id", "workflow_id"),)

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id     = Column(UUID(as_uuid=True), nullable=False)
    workflow_id = Column(UUID(as_uuid=True), nullable=False)
    created_at  = Column(DateTime, default=datetime.utcnow)


class OrganizationSubscription(Base):
    """One active subscription per organization, linking org → plan."""
    __tablename__ = "organization_subscriptions"
    __table_args__ = (UniqueConstraint("organization_id"),)

    id                   = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id      = Column(UUID(as_uuid=True), nullable=False)
    plan_id              = Column(UUID(as_uuid=True), nullable=False)
    status               = Column(String(50), nullable=False, default="active")  # active | trialing | past_due | cancelled | paused
    billing_cycle        = Column(String(20), nullable=False, default="monthly")  # monthly | annual
    current_period_start = Column(DateTime, default=datetime.utcnow)
    current_period_end   = Column(DateTime)
    trial_ends_at        = Column(DateTime)
    cancelled_at         = Column(DateTime)
    cancel_reason        = Column(Text)
    notes                = Column(Text)
    metadata_            = Column("metadata", JSONB, nullable=False, default=dict)
    created_at           = Column(DateTime, default=datetime.utcnow)
    updated_at           = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class OrganizationWorkflowAssignment(Base):
    """Admin-assigned workflow → organization mapping. Both plan entitlement AND this record are required."""
    __tablename__ = "organization_workflow_assignments"
    __table_args__ = (UniqueConstraint("organization_id", "workflow_id"),)

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), nullable=False)
    workflow_id     = Column(UUID(as_uuid=True), nullable=False)
    assigned_by     = Column(String(255))
    status          = Column(String(50), nullable=False, default="active")  # active | suspended
    config_override = Column(JSONB, nullable=False, default=dict)
    notes           = Column(Text)
    assigned_at     = Column(DateTime, default=datetime.utcnow)
    updated_at      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BillingPeriod(Base):
    """Billing period per organization; aggregated totals populated at period close."""
    __tablename__ = "billing_periods"

    id                   = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id      = Column(UUID(as_uuid=True), nullable=False)
    tenant_id            = synonym("organization_id")
    subscription_id      = Column(UUID(as_uuid=True))
    period_start         = Column(DateTime, nullable=False)
    period_end           = Column(DateTime, nullable=False)
    status               = Column(String(50), nullable=False, default="open")  # open | closed | invoiced
    total_workflow_runs  = Column(Integer, nullable=False, default=0)
    total_tokens_in      = Column(Integer, nullable=False, default=0)
    total_tokens_out     = Column(Integer, nullable=False, default=0)
    total_token_cost_usd = Column(Numeric(12, 6), nullable=False, default=0)
    total_image_gens     = Column(Integer, nullable=False, default=0)
    total_image_cost_usd = Column(Numeric(12, 6), nullable=False, default=0)
    total_cost_usd       = Column(Numeric(12, 6), nullable=False, default=0)
    billable_runs        = Column(Integer, nullable=False, default=0)
    billable_tokens      = Column(Integer, nullable=False, default=0)
    billable_amount_usd  = Column(Numeric(12, 6), nullable=False, default=0)
    created_at           = Column(DateTime, default=datetime.utcnow)
    updated_at           = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UsageRecord(Base):
    """Granular per-event usage — one row per billable event. cost_usd=NULL means provider did not report cost."""
    __tablename__ = "usage_records"

    id                   = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id      = Column(UUID(as_uuid=True), nullable=False)
    tenant_id            = synonym("organization_id")
    billing_period_id    = Column(UUID(as_uuid=True))
    workflow_id          = Column(UUID(as_uuid=True))
    workflow_key         = Column(String(100))
    workflow_instance_id = Column(UUID(as_uuid=True))
    agent_run_id         = Column(UUID(as_uuid=True))
    usage_type           = Column(String(50), nullable=False)   # workflow_run | llm_tokens | image_gen | tool_call
    provider             = Column(String(100))
    model                = Column(String(200))
    quantity             = Column(Integer, nullable=False, default=1)
    tokens_in            = Column(Integer, nullable=False, default=0)
    tokens_out           = Column(Integer, nullable=False, default=0)
    cost_usd             = Column(Numeric(12, 9))   # NULL = not reported; do NOT default to 0
    recorded_at          = Column(DateTime, default=datetime.utcnow)


class Invoice(Base):
    """Invoice / billing ledger per organization per period."""
    __tablename__ = "invoices"

    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id     = Column(UUID(as_uuid=True), nullable=False)
    tenant_id           = synonym("organization_id")
    billing_period_id   = Column(UUID(as_uuid=True))
    subscription_id     = Column(UUID(as_uuid=True))
    invoice_number      = Column(String(50), unique=True)
    status              = Column(String(50), nullable=False, default="draft")  # draft | open | paid | void | uncollectible
    subtotal_usd        = Column(Numeric(12, 2), nullable=False, default=0)
    tax_usd             = Column(Numeric(12, 2), nullable=False, default=0)
    total_usd           = Column(Numeric(12, 2), nullable=False, default=0)
    due_date            = Column(DateTime)
    paid_at             = Column(DateTime)
    voided_at           = Column(DateTime)
    payment_provider    = Column(String(50))
    external_invoice_id = Column(String(255))
    line_items          = Column(JSONB, nullable=False, default=list)
    notes               = Column(Text)
    created_at          = Column(DateTime, default=datetime.utcnow)
    updated_at          = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PlatformSetting(Base):
    """Key-value store for platform-wide admin settings."""
    __tablename__ = "platform_settings"

    key         = Column(String(255), primary_key=True)
    value       = Column(JSONB, nullable=False, default=dict)
    description = Column(Text)
    updated_by  = Column(String(255))
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# =============================================================================
# Relationship Intelligence & Central Memory Models (Node 3)
# =============================================================================

class RelationshipContact(Base):
    """
    Persistent, organization-scoped contact entity for relationship intelligence.
    Enforces deterministic contact resolution via normalized_name scoped by organization_id.
    """
    __tablename__ = "relationship_contacts"
    __table_args__ = (
        UniqueConstraint("organization_id", "normalized_name", name="uq_relationship_contacts_org_normalized_name"),
    )

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    name            = Column(String(255), nullable=False)
    normalized_name = Column(String(255), nullable=False, index=True)
    role            = Column(String(255), nullable=True)
    company         = Column(String(255), nullable=True)
    metadata_       = Column("metadata", JSONB, nullable=False, default=dict)
    created_at      = Column(DateTime, default=datetime.utcnow)
    updated_at      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RelationshipConversation(Base):
    """
    Append-only persistent record of a single conversation associated with a contact and workflow instance.
    Survives page refresh, server restarts, and future workflow runs.
    """
    __tablename__ = "relationship_conversations"
    __table_args__ = (
        UniqueConstraint("organization_id", "workflow_instance_id", name="uq_relationship_conv_org_instance"),
    )

    id                   = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id      = Column(UUID(as_uuid=True), nullable=False, index=True)
    contact_id           = Column(UUID(as_uuid=True), ForeignKey("relationship_contacts.id", ondelete="CASCADE"), nullable=False, index=True)
    workflow_instance_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    title                = Column(String(255), nullable=False)
    conversation_type    = Column(String(100), nullable=False, default="meeting")
    conversation_date    = Column(String(50), nullable=True)
    detected_language    = Column(String(20), nullable=False, default="en")
    transcript           = Column(Text, nullable=False)
    summary              = Column(Text, nullable=True)
    structured_memory    = Column(JSONB, nullable=False, default=dict)
    created_at           = Column(DateTime, default=datetime.utcnow)
    updated_at           = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RelationshipMemoryItem(Base):
    """
    Granular, traceable memory element (fact, interest, need, opportunity, commitment, AI suggestion, open question).
    Maintains provenance to source conversation, workflow instance, and conversation date.
    Preserves strict separation between factual extracted knowledge and AI-generated suggestions.
    """
    __tablename__ = "relationship_memory_items"

    id                   = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id      = Column(UUID(as_uuid=True), nullable=False, index=True)
    contact_id           = Column(UUID(as_uuid=True), ForeignKey("relationship_contacts.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id      = Column(UUID(as_uuid=True), ForeignKey("relationship_conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    workflow_instance_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    category             = Column(String(50), nullable=False, index=True)
    content              = Column(Text, nullable=False)
    details              = Column(JSONB, nullable=False, default=dict)
    source_date          = Column(String(50), nullable=True)
    is_ai_generated      = Column(Boolean, nullable=False, default=False)
    created_at           = Column(DateTime, default=datetime.utcnow)

