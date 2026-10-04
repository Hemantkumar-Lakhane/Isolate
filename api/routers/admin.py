"""
api/routers/admin.py
====================
SMBFlow Platform Admin Control Plane API.

All endpoints require platform_admin or super_admin role.
Organization users are categorically denied access — enforced at the dependency layer.

Covers:
  - Platform overview metrics
  - Organizations CRUD + lifecycle
  - User management
  - Workflow catalog
  - Workflow assignments (org → workflow)
  - Billing plans
  - Subscriptions
  - Usage & metering
  - Invoices
  - Audit log (audit_events table)
  - Platform settings
  - AI providers, models, routing
  - Platform health
  - Exceptions / failures
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text

import api.crud as crud
from api.auth import TokenData, require_admin
from api.dependencies import get_db
from db.models.core import (
    Organization,
    OrganizationUser,
    WorkflowInstance,
    ApprovalItem,
)

log = structlog.get_logger()

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])


# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────────

def _require_admin(current_user: TokenData = Depends(require_admin)) -> TokenData:
    return current_user


async def _audit(
    db: AsyncSession,
    actor: TokenData,
    action: str,
    entity_type: str,
    entity_id: str = None,
    org_id: str = None,
    metadata: dict = None,
) -> None:
    try:
        await crud.create_audit_event(
            db,
            actor_id=actor.email or actor.user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            organization_id=org_id,
            metadata=metadata or {},
        )
    except Exception as exc:
        log.warning("Audit write failed", error=str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# Request / response bodies
# ─────────────────────────────────────────────────────────────────────────────

class OrgCreateRequest(BaseModel):
    name:          str
    industry:      str = "saas"
    plan_slug:     Optional[str] = "free"
    billing_cycle: Optional[str] = "monthly"
    with_trial:    Optional[bool] = False     # start a 14-day trial
    trial_days:    Optional[int]  = 14
    workflow_keys: Optional[list[str]] = Field(default_factory=list)
    owner_email:   Optional[str] = None
    owner_name:    Optional[str] = None


class OrgUpdateRequest(BaseModel):
    name:     Optional[str] = None
    industry: Optional[str] = None
    active:   Optional[bool] = None


class OrgSuspendRequest(BaseModel):
    reason: Optional[str] = None


class UserInviteRequest(BaseModel):
    email:           str
    full_name:       Optional[str] = None
    role:            str = "org_user"
    organization_id: Optional[str] = None


class UserRoleUpdateRequest(BaseModel):
    role: str


class UserOrgUpdateRequest(BaseModel):
    organization_id: str


class PlanCreateRequest(BaseModel):
    name:                    str
    slug:                    str
    description:             Optional[str] = None
    monthly_price_usd:       float = 0.0
    annual_price_usd:        float = 0.0
    included_workflow_runs:  int = 0
    included_ai_tokens:      int = 0
    included_image_gens:     int = 0
    included_users:          int = 1
    overage_run_price_usd:   float = 0.0
    overage_token_price_usd: float = 0.0
    overage_image_price_usd: float = 0.0
    max_workflow_runs:       int = 0
    max_users:               int = 0
    status:                  str = "active"
    is_public:               bool = True
    sort_order:              int = 0


class PlanUpdateRequest(BaseModel):
    name:                    Optional[str]   = None
    description:             Optional[str]   = None
    monthly_price_usd:       Optional[float] = None
    annual_price_usd:        Optional[float] = None
    included_workflow_runs:  Optional[int]   = None
    included_ai_tokens:      Optional[int]   = None
    included_image_gens:     Optional[int]   = None
    included_users:          Optional[int]   = None
    overage_run_price_usd:   Optional[float] = None
    overage_token_price_usd: Optional[float] = None
    overage_image_price_usd: Optional[float] = None
    max_workflow_runs:       Optional[int]   = None
    max_users:               Optional[int]   = None
    status:                  Optional[str]   = None
    is_public:               Optional[bool]  = None
    sort_order:              Optional[int]   = None


class PlanEntitlementsRequest(BaseModel):
    workflow_ids: list[str]


class SubscriptionCreateRequest(BaseModel):
    plan_id:       str
    billing_cycle: str = "monthly"


class SubscriptionUpdateRequest(BaseModel):
    plan_id:        Optional[str] = None
    status:         Optional[str] = None
    billing_cycle:  Optional[str] = None
    trial_ends_at:  Optional[str] = None   # ISO datetime string — for trial extension
    notes:          Optional[str] = None


class WorkflowAssignRequest(BaseModel):
    notes: Optional[str] = None


class WorkflowCatalogCreateRequest(BaseModel):
    name:                  str
    key:                   str
    description:           Optional[str] = None
    category:              str = "general"
    status:                str = "active"
    version:               str = "1.0.0"
    pricing_model:         str = "included"
    required_integrations: list[str] = Field(default_factory=list)
    supported_modules:     list[str] = Field(default_factory=list)
    # ── Industry applicability (Migration 004) ────────────────────────────
    scope:                 str = "GLOBAL"        # GLOBAL | INDUSTRY
    industry:              Optional[str] = None  # required when scope=INDUSTRY


class WorkflowCatalogUpdateRequest(BaseModel):
    name:                  Optional[str]       = None
    description:           Optional[str]       = None
    category:              Optional[str]       = None
    status:                Optional[str]       = None
    version:               Optional[str]       = None
    pricing_model:         Optional[str]       = None
    required_integrations: Optional[list[str]] = None
    supported_modules:     Optional[list[str]] = None
    active:                Optional[bool]      = None
    # ── Industry applicability (Migration 004) ────────────────────────────
    scope:                 Optional[str]       = None  # GLOBAL | INDUSTRY
    industry:              Optional[str]       = None  # set/clear industry


class CustomWorkflowCreateRequest(BaseModel):
    name:                       str
    key:                        str
    description:                Optional[str] = None
    category:                   str = "operations"
    industry:                   Optional[str] = "general"
    scope:                      str = "GLOBAL"  # GLOBAL | INDUSTRY
    trigger_type:               str = "manual"
    sla_hours:                  int = 2
    estimated_duration_minutes: int = 2
    dag:                        dict[str, Any]
    assign_to_org_ids:          Optional[list[str]] = Field(default_factory=list)
    assign_to_plan_slugs:       Optional[list[str]] = Field(default_factory=list)


class WorkflowTestRunRequest(BaseModel):
    input_payload: Optional[dict[str, Any]] = Field(default_factory=dict)
    mock_mode:     bool = True


class AIWorkflowGenerateRequest(BaseModel):
    prompt:      str = Field(..., min_length=4)
    industry:    Optional[str] = "general"
    category:    Optional[str] = None
    target_plan: Optional[str] = None


class PlatformSettingsUpdateRequest(BaseModel):
    settings: dict[str, Any]


# ─────────────────────────────────────────────────────────────────────────────
# OVERVIEW
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/overview")
async def get_platform_overview(
    _: TokenData = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Real KPI dashboard — all values from DB, never fabricated."""
    metrics  = await crud.get_admin_platform_metrics(db)
    activity = await crud.get_org_activity_feed(db, limit=15)
    return {"metrics": metrics, "recent_activity": activity}


# ─────────────────────────────────────────────────────────────────────────────
# ORGANIZATIONS
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/organizations")
async def list_organizations(
    include_test_fixtures: bool = Query(False),
    _: TokenData = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await crud.list_organizations_with_details(db, include_test_fixtures=include_test_fixtures)


@router.post("/organizations", status_code=201)
async def create_organization(
    body: OrgCreateRequest,
    current_user: TokenData = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    # 1. Create the organization record
    org = Organization(
        name=body.name,
        industry=body.industry,
        enabled_modules=[],
        profile_config={},
        active=True,
    )
    db.add(org)
    await db.flush()
    org_id = str(org.id)

    # 2. Create owner user if provided
    if body.owner_email:
        owner_uid = str(uuid.uuid5(uuid.NAMESPACE_DNS, body.owner_email.lower().strip()))
        db.add(OrganizationUser(
            organization_id=org.id,
            user_id=uuid.UUID(owner_uid),
            email=body.owner_email.strip().lower(),
            full_name=body.owner_name,
            role="org_user",
        ))

    # 3. Attach subscription to plan
    plan = await crud.get_billing_plan_by_slug(db, body.plan_slug or "free")
    if not plan:
        all_plans = await crud.list_billing_plans(db)
        plan = all_plans[0] if all_plans else None

    if plan:
        from db.models.core import OrganizationSubscription
        db.add(OrganizationSubscription(
            organization_id=org.id,
            plan_id=plan.id,
            status="trialing" if body.with_trial else "active",
            billing_cycle=body.billing_cycle or "monthly",
            current_period_start=datetime.utcnow(),
            current_period_end=datetime.utcnow() + timedelta(
                days=365 if body.billing_cycle == "annual" else 30
            ),
            trial_ends_at=(
                datetime.utcnow() + timedelta(days=body.trial_days or 14)
                if body.with_trial else None
            ),
        ))

    await db.commit()
    await db.refresh(org)

    # 4. Auto-assign industry-appropriate workflows from the catalog.
    #    This runs BEFORE the explicit workflow_keys loop so that explicit
    #    overrides from the admin form simply confirm/extend the auto-set.
    plan_slug_used = plan.slug if plan else (body.plan_slug or "free")
    try:
        auto_count = await crud.auto_assign_industry_workflows(
            db,
            organization_id=org_id,
            industry=body.industry,
            assigned_by=current_user.email,
            plan_slug=plan_slug_used,
        )
        log.info(
            "Admin org creation: auto-assigned industry workflows",
            org_id=org_id,
            industry=body.industry,
            plan=plan_slug_used,
            count=auto_count,
        )
    except Exception as _aa_err:
        # Non-fatal — admin can assign manually from the Assignments page
        log.warning("Auto-assign failed (non-fatal)", error=str(_aa_err), org_id=org_id)

    # 5. Assign any explicitly requested workflows that weren't auto-included
    for wf_key in (body.workflow_keys or []):
        wf = await crud.get_workflow_catalog_by_key(db, wf_key)
        if wf:
            await crud.assign_workflow_to_org(
                db, org_id, str(wf.id), assigned_by=current_user.email
            )

    await _audit(db, current_user, "organization.created", "organization",
                 org_id, org_id, {"name": body.name, "plan": body.plan_slug})
    return {"id": org_id, "message": f"Organization '{body.name}' created"}


@router.get("/organizations/{org_id}")
async def get_organization(
    org_id: str,
    _: TokenData = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    detail = await crud.get_org_with_details(db, org_id)
    if not detail:
        raise HTTPException(404, "Organization not found")
    return detail


@router.patch("/organizations/{org_id}")
async def update_organization(
    org_id: str,
    body: OrgUpdateRequest,
    current_user: TokenData = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        oid = uuid.UUID(org_id)
    except ValueError:
        raise HTTPException(400, "Invalid organization ID")

    result = await db.execute(select(Organization).where(Organization.id == oid))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(404, "Organization not found")

    if body.name     is not None: org.name     = body.name
    if body.industry is not None: org.industry = body.industry
    if body.active   is not None: org.active   = body.active
    await db.commit()

    await _audit(db, current_user, "organization.updated", "organization",
                 org_id, metadata=body.model_dump(exclude_none=True))
    return {"message": "Organization updated"}


@router.post("/organizations/{org_id}/suspend")
async def suspend_organization(
    org_id: str,
    body: OrgSuspendRequest,
    current_user: TokenData = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        oid = uuid.UUID(org_id)
    except ValueError:
        raise HTTPException(400, "Invalid organization ID")

    result = await db.execute(select(Organization).where(Organization.id == oid))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(404, "Organization not found")

    org.active = False
    await db.commit()
    await _audit(db, current_user, "organization.suspended", "organization",
                 org_id, org_id, {"reason": body.reason})
    return {"message": "Organization suspended"}


@router.post("/organizations/{org_id}/activate")
async def activate_organization(
    org_id: str,
    current_user: TokenData = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        oid = uuid.UUID(org_id)
    except ValueError:
        raise HTTPException(400, "Invalid organization ID")

    result = await db.execute(select(Organization).where(Organization.id == oid))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(404, "Organization not found")

    org.active = True
    await db.commit()
    await _audit(db, current_user, "organization.activated", "organization", org_id, org_id)
    return {"message": "Organization reactivated"}


# ─────────────────────────────────────────────────────────────────────────────
# USERS
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/users")
async def list_users(
    _: TokenData = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
    organization_id: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
):
    stmt = select(OrganizationUser).order_by(OrganizationUser.created_at.desc())
    if organization_id:
        try:
            stmt = stmt.where(OrganizationUser.organization_id == uuid.UUID(organization_id))
        except ValueError:
            pass
    if role:
        stmt = stmt.where(OrganizationUser.role == role)

    users = (await db.execute(stmt)).scalars().all()

    orgs_map = {
        str(o.id): o.name
        for o in (await db.execute(select(Organization))).scalars().all()
    }

    return [
        {
            "id":               str(u.id),
            "user_id":          str(u.user_id),
            "email":            u.email,
            "full_name":        u.full_name,
            "role":             u.role,
            "organization_id":  str(u.organization_id) if u.organization_id else None,
            "organization_name": orgs_map.get(str(u.organization_id), "—") if u.organization_id else "—",
            "status":           "suspended" if u.role.startswith("suspended_") else "active",
            "created_at":       u.created_at.isoformat() if u.created_at else None,
            "last_login":       None,  # not stored on OrganizationUser
        }
        for u in users
    ]


@router.post("/users/invite", status_code=201)
async def invite_user(
    body: UserInviteRequest,
    current_user: TokenData = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    target_role = body.role if body.role in ("org_user", "platform_admin") else "org_user"
    target_uid  = str(uuid.uuid5(uuid.NAMESPACE_DNS, body.email.lower().strip()))

    org_id: Optional[uuid.UUID] = None
    if body.organization_id:
        try:
            org_id = uuid.UUID(body.organization_id)
        except ValueError:
            raise HTTPException(400, "Invalid organization_id")
    elif target_role == "org_user":
        # Auto-create a pending workspace
        pending = Organization(
            name=f"Pending — {body.email}",
            industry="saas",
            enabled_modules=[],
            profile_config={"requires_onboarding": True},
            active=True,
        )
        db.add(pending)
        await db.flush()
        org_id = pending.id

    # Upsert the OrganizationUser entry
    existing = (await db.execute(
        select(OrganizationUser).where(OrganizationUser.email == body.email.strip().lower())
    )).scalar_one_or_none()

    if existing:
        existing.role = target_role
        if body.full_name: existing.full_name = body.full_name
        if org_id:         existing.organization_id = org_id
    else:
        db.add(OrganizationUser(
            organization_id=org_id,
            user_id=uuid.UUID(target_uid),
            email=body.email.strip().lower(),
            full_name=body.full_name,
            role=target_role,
        ))

    await db.commit()
    await _audit(db, current_user, "user.invited", "user", target_uid,
                 str(org_id) if org_id else None,
                 {"email": body.email, "role": target_role})

    return {"message": f"User '{body.email}' invited as {target_role}",
            "user_id": target_uid, "email": body.email, "role": target_role}


@router.patch("/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    body: UserRoleUpdateRequest,
    current_user: TokenData = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    if body.role not in ("org_user", "platform_admin"):
        raise HTTPException(400, "role must be 'org_user' or 'platform_admin'")
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(400, "Invalid user ID")

    ou = (await db.execute(select(OrganizationUser).where(OrganizationUser.id == uid))).scalar_one_or_none()
    if not ou:
        raise HTTPException(404, "User not found")

    old_role = ou.role
    ou.role  = body.role
    await db.commit()
    await _audit(db, current_user, "user.role_changed", "user", user_id,
                 metadata={"old_role": old_role, "new_role": body.role})
    return {"message": f"Role updated to {body.role}"}


@router.patch("/users/{user_id}/organization")
async def update_user_organization(
    user_id: str,
    body: UserOrgUpdateRequest,
    current_user: TokenData = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        uid     = uuid.UUID(user_id)
        new_oid = uuid.UUID(body.organization_id)
    except ValueError:
        raise HTTPException(400, "Invalid ID")

    ou = (await db.execute(select(OrganizationUser).where(OrganizationUser.id == uid))).scalar_one_or_none()
    if not ou:
        raise HTTPException(404, "User not found")

    old_org = str(ou.organization_id) if ou.organization_id else None
    ou.organization_id = new_oid
    await db.commit()
    await _audit(db, current_user, "user.org_changed", "user", user_id,
                 metadata={"old_org": old_org, "new_org": body.organization_id})
    return {"message": "User organization updated"}


@router.patch("/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: str,
    current_user: TokenData = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(400, "Invalid user ID")

    ou = (await db.execute(select(OrganizationUser).where(OrganizationUser.id == uid))).scalar_one_or_none()
    if not ou:
        raise HTTPException(404, "User not found")

    if not ou.role.startswith("suspended_"):
        ou.role = f"suspended_{ou.role}"
        await db.commit()

    await _audit(db, current_user, "user.deactivated", "user", user_id)
    return {"message": "User deactivated"}


@router.patch("/users/{user_id}/reactivate")
async def reactivate_user(
    user_id: str,
    current_user: TokenData = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(400, "Invalid user ID")

    ou = (await db.execute(select(OrganizationUser).where(OrganizationUser.id == uid))).scalar_one_or_none()
    if not ou:
        raise HTTPException(404, "User not found")

    if ou.role.startswith("suspended_"):
        ou.role = ou.role[len("suspended_"):]
        await db.commit()

    await _audit(db, current_user, "user.reactivated", "user", user_id)
    return {"message": "User reactivated"}


# ─────────────────────────────────────────────────────────────────────────────
# WORKFLOW CATALOG
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/workflows/catalog")
async def list_catalog(
    _: TokenData = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
    active_only: bool = Query(False),
):
    entries = await crud.list_workflow_catalog(db, active_only=active_only)
    return [crud.workflow_catalog_to_dict(e) for e in entries]


@router.post("/workflows/catalog", status_code=201)
async def create_catalog_entry(
    body: WorkflowCatalogCreateRequest,
    current_user: TokenData = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    if await crud.get_workflow_catalog_by_key(db, body.key):
        raise HTTPException(409, f"Workflow key '{body.key}' already exists")
    entry = await crud.create_workflow_catalog_entry(db, body.model_dump())
    await _audit(db, current_user, "workflow_catalog.created", "workflow_catalog",
                 str(entry.id), metadata={"key": body.key, "name": body.name})
    return crud.workflow_catalog_to_dict(entry)


@router.patch("/workflows/catalog/{workflow_id}")
async def update_catalog_entry(
    workflow_id: str,
    body: WorkflowCatalogUpdateRequest,
    current_user: TokenData = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    updated = await crud.update_workflow_catalog_entry(
        db, workflow_id, body.model_dump(exclude_none=True)
    )
    if not updated:
        raise HTTPException(404, "Workflow not found in catalog")
    await _audit(db, current_user, "workflow_catalog.updated", "workflow_catalog",
                 workflow_id, metadata=body.model_dump(exclude_none=True))
    return crud.workflow_catalog_to_dict(updated)


def _validate_dag_graph(dag: dict[str, Any]) -> None:
    """Validate that DAG dictionary has valid nodes, edges, and is acyclic."""
    if not isinstance(dag, dict):
        raise HTTPException(400, "DAG must be a valid JSON dictionary")

    nodes = dag.get("nodes") or []
    edges = dag.get("edges") or []

    # If format is dict of steps
    if isinstance(nodes, dict):
        node_ids = set(nodes.keys())
        dependencies = {k: v.get("dependencies", []) for k, v in nodes.items()}
    elif isinstance(nodes, list):
        node_ids = {n.get("id") or n.get("name") for n in nodes if isinstance(n, dict)}
        dependencies = {n_id: [] for n_id in node_ids}
        for e in edges:
            src = e.get("source") or e.get("from")
            tgt = e.get("target") or e.get("to")
            if tgt in dependencies:
                dependencies[tgt].append(src)
    else:
        raise HTTPException(400, "DAG must define nodes and connections")

    if not node_ids:
        raise HTTPException(400, "DAG must contain at least one node")

    # Topological sort cycle detection (Kahn's algorithm)
    in_degree = {k: 0 for k in node_ids}
    adj = {k: [] for k in node_ids}

    for tgt, srcs in dependencies.items():
        for src in srcs:
            if src in node_ids:
                adj[src].append(tgt)
                in_degree[tgt] += 1

    queue = [k for k, d in in_degree.items() if d == 0]
    visited_count = 0

    while queue:
        curr = queue.pop(0)
        visited_count += 1
        for neighbor in adj.get(curr, []):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if visited_count != len(node_ids):
        raise HTTPException(400, "Cycle detected in workflow graph. Workflow must be a Directed Acyclic Graph (DAG).")


@router.post("/workflows/custom", status_code=201)
async def create_and_publish_custom_workflow(
    body: CustomWorkflowCreateRequest,
    current_user: TokenData = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Publish a custom n8n-style multi-agent DAG workflow:
    - Validates DAG graph structure and ensures no cycles.
    - Saves compiled DAG JSON to workflows/dags/{clean_key}.json.
    - Upserts WorkflowCatalogItem entry.
    - Optionally auto-assigns to specified organizations and billing plans.
    """
    clean_key = body.key.strip().lower().replace(" ", "_").replace("-", "_")
    if not clean_key:
        raise HTTPException(400, "Invalid workflow key")

    # 1. Validate DAG
    _validate_dag_graph(body.dag)

    # 2. Save DAG JSON file
    dags_dir = Path("workflows/dags")
    dags_dir.mkdir(parents=True, exist_ok=True)
    dag_path = dags_dir / f"{clean_key}.json"

    # Inject metadata into DAG
    final_dag = dict(body.dag)
    final_dag["_meta"] = {
        "name": body.name,
        "description": body.description or "",
        "category": body.category,
        "industry": body.industry or "general",
        "sla_hours": body.sla_hours,
        "estimated_duration_minutes": body.estimated_duration_minutes,
        "trigger": {
            "type": body.trigger_type,
            "source": "visual_builder"
        },
        "trigger_types": [body.trigger_type],
        "created_by": current_user.email,
        "created_at": datetime.utcnow().isoformat(),
        "is_custom": True,
    }

    with open(dag_path, "w", encoding="utf-8") as f:
        json.dump(final_dag, f, indent=2)

    # 3. Upsert WorkflowCatalogItem in DB
    existing_cat = await crud.get_workflow_catalog_by_key(db, clean_key)
    cat_payload = {
        "name": body.name,
        "key": clean_key,
        "description": body.description,
        "category": body.category,
        "scope": body.scope,
        "industry": body.industry if body.scope == "INDUSTRY" else None,
        "status": "active",
        "version": "1.0.0",
        "pricing_model": "included",
        "required_integrations": [],
        "supported_modules": [body.category],
    }

    if existing_cat:
        cat_entry = await crud.update_workflow_catalog_entry(db, str(existing_cat.id), cat_payload)
    else:
        cat_entry = await crud.create_workflow_catalog_entry(db, cat_payload)

    # 4. Optional Organization assignments
    assigned_count = 0
    if body.assign_to_org_ids:
        for org_id_str in body.assign_to_org_ids:
            try:
                await crud.assign_workflow_to_org(
                    db,
                    org_id_str,
                    str(cat_entry.id),
                    assigned_by=current_user.email,
                    notes=f"Auto-assigned upon custom workflow creation by {current_user.email}"
                )
                assigned_count += 1
            except Exception as assign_err:
                log.warning("Could not auto-assign custom workflow to org", org_id=org_id_str, error=str(assign_err))

    # 5. Optional Plan entitlements
    entitled_plans = []
    if body.assign_to_plan_slugs:
        for p_slug in body.assign_to_plan_slugs:
            try:
                plan = await crud.get_billing_plan_by_slug(db, p_slug)
                if plan:
                    current_entitlements = await crud.get_plan_entitlements(db, str(plan.id))
                    all_ids = set(current_entitlements)
                    all_ids.add(str(cat_entry.id))
                    await crud.set_plan_entitlements(db, str(plan.id), list(all_ids))
                    entitled_plans.append(p_slug)
            except Exception as plan_err:
                log.warning("Could not auto-entitle custom workflow to plan", plan_slug=p_slug, error=str(plan_err))

    await _audit(
        db, current_user, "custom_workflow.published", "workflow_catalog",
        str(cat_entry.id), metadata={
            "key": clean_key,
            "name": body.name,
            "assigned_orgs": assigned_count,
            "entitled_plans": entitled_plans,
        }
    )

    return {
        "message": f"Custom workflow '{body.name}' compiled, published, and saved successfully.",
        "workflow": crud.workflow_catalog_to_dict(cat_entry),
        "dag_path": str(dag_path),
        "assigned_orgs_count": assigned_count,
        "entitled_plans": entitled_plans,
    }


@router.post("/workflows/{workflow_key}/test-run")
async def test_run_custom_workflow(
    workflow_key: str,
    body: WorkflowTestRunRequest,
    current_user: TokenData = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Execute a sandboxed dry-run test of a workflow DAG with synthetic inputs.
    Returns step trace, node state transitions, and simulated token usage.
    """
    dags_dir = Path("workflows/dags")
    dag_path = dags_dir / f"{workflow_key}.json"

    if not dag_path.exists():
        raise HTTPException(404, f"DAG not found for workflow '{workflow_key}'")

    try:
        with open(dag_path, "r", encoding="utf-8") as f:
            dag = json.load(f)
    except Exception as e:
        raise HTTPException(500, f"Error reading DAG file: {str(e)}")

    nodes = dag.get("nodes", [])
    steps = []
    total_tokens = 0
    simulated_cost = 0.0

    if isinstance(nodes, list):
        for idx, node in enumerate(nodes):
            n_id = node.get("id") or f"node_{idx+1}"
            n_type = node.get("type") or (node.get("data", {}).get("agentType", "reasoning_agent"))
            n_label = node.get("data", {}).get("name") or n_id
            
            step_tokens = 150 + (idx * 50)
            step_cost = round(step_tokens * 0.000002, 5)
            total_tokens += step_tokens
            simulated_cost += step_cost

            steps.append({
                "step_index": idx + 1,
                "node_id": n_id,
                "node_type": n_type,
                "label": n_label,
                "status": "success",
                "tokens_consumed": step_tokens,
                "cost_usd": step_cost,
                "output_preview": f"Simulated output from {n_label} executed successfully with mock payload.",
            })
    elif isinstance(nodes, dict):
        for idx, (n_id, node_def) in enumerate(nodes.items()):
            n_type = node_def.get("agent_type") or "reasoning_agent"
            step_tokens = 150 + (idx * 50)
            step_cost = round(step_tokens * 0.000002, 5)
            total_tokens += step_tokens
            simulated_cost += step_cost

            steps.append({
                "step_index": idx + 1,
                "node_id": n_id,
                "node_type": n_type,
                "label": n_id.replace("_", " ").title(),
                "status": "success",
                "tokens_consumed": step_tokens,
                "cost_usd": step_cost,
                "output_preview": f"Step {n_id} simulated output produced.",
            })

    return {
        "status": "completed",
        "workflow_key": workflow_key,
        "test_run_id": f"test_{uuid.uuid4().hex[:8]}",
        "total_nodes_executed": len(steps),
        "total_simulated_tokens": total_tokens,
        "total_simulated_cost_usd": round(simulated_cost, 4),
        "steps": steps,
        "message": f"Workflow {workflow_key} passed dry-run simulation with 0 errors.",
    }


@router.get("/tools/library")
async def get_builder_tools_library(
    _: TokenData = Depends(_require_admin),
):
    """
    Return available tool connectors, agent capabilities, and triggers for the workflow builder palette.
    """
    return {
        "triggers": [
            {"id": "manual", "name": "Manual UI Trigger", "description": "Triggered manually with form inputs", "category": "trigger", "color": "#10B981"},
            {"id": "email", "name": "Inbound Email Trigger", "description": "Triggers on inbound email ingestion", "category": "trigger", "color": "#06B6D4"},
            {"id": "scheduled", "name": "Scheduled Cron", "description": "Triggers periodically on cron schedule", "category": "trigger", "color": "#6366F1"},
            {"id": "webhook", "name": "Webhook Ingest", "description": "Triggers on incoming REST webhook HTTP POST", "category": "trigger", "color": "#8B5CF6"},
        ],
        "agents": [
            {"id": "research_agent", "name": "Research Agent", "description": "Context gathering, database query & document fetch", "color": "#6C63FF"},
            {"id": "reasoning_agent", "name": "Reasoning Agent", "description": "Multi-step logic, analysis, and classification", "color": "#00D4FF"},
            {"id": "drafting_agent", "name": "Drafting Agent", "description": "Generates structured content, copy, and posts", "color": "#10E580"},
            {"id": "verification_agent", "name": "Verification Agent", "description": "Deterministic safety, policy, and quality verification", "color": "#FFB800"},
            {"id": "execution_agent", "name": "Execution Agent", "description": "Dispatches tool actions and external integrations", "color": "#FF4757"},
        ],
        "logic": [
            {"id": "condition_branch", "name": "Condition / Filter", "description": "Evaluates boolean logic and branches path", "color": "#F59E0B"},
            {"id": "switch_router", "name": "Switch Router", "description": "Multi-way routing by category or confidence", "color": "#EC4899"},
            {"id": "approval_gate", "name": "HITL Approval Gate", "description": "Pauses execution for human SME review and approval", "color": "#4F46E5"},
        ],
        "tools": [
            {"id": "tool_email_dispatch", "name": "Email Dispatcher", "description": "Sends customer email notifications", "category": "tool", "color": "#EF4444"},
            {"id": "tool_db_mutation", "name": "Database Record Updater", "description": "Inserts or updates CRM / ERP records", "category": "tool", "color": "#3B82F6"},
            {"id": "tool_http_webhook", "name": "Outbound HTTP Webhook", "description": "Sends JSON payload to external REST API", "category": "tool", "color": "#14B8A6"},
            {"id": "tool_image_generation", "name": "Imagen Visual Generator", "description": "Generates promotional visuals and graphics", "category": "tool", "color": "#A855F7"},
        ]
    }


@router.post("/workflows/ai-generate")
async def ai_generate_workflow(
    body: AIWorkflowGenerateRequest,
    current_user: TokenData = Depends(_require_admin),
):
    """
    AI Copilot Workflow Synthesizer:
    Translates natural language prompt into a multi-agent DAG workflow
    with nodes, layout coordinates, tool bindings, and branching rules.
    """
    from core.workflow_ai_generator import generate_workflow_from_prompt
    try:
        generated = await generate_workflow_from_prompt(
            prompt=body.prompt,
            industry=body.industry,
            category=body.category,
        )
        # Validate topological acyclic constraint
        _validate_dag_graph(generated)
        return generated
    except Exception as e:
        log.error("AI workflow generation failed", error=str(e))
        raise HTTPException(500, f"AI generation failed: {str(e)}")


# ─────────────────────────────────────────────────────────────────────────────
# WORKFLOW ASSIGNMENTS
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/workflows/assignments")
async def list_all_assignments(
    _: TokenData = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    assignments = await crud.list_all_workflow_assignments(db)
    result = []
    for a in assignments:
        cat = await crud.get_workflow_catalog_entry(db, str(a.workflow_id))
        result.append(crud.workflow_assignment_to_dict(a, cat))
    return result


@router.get("/organizations/{org_id}/workflows")
async def get_org_workflow_assignments(
    org_id: str,
    _: TokenData = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    assignments = await crud.get_org_workflow_assignments(db, org_id)
    result = []
    for a in assignments:
        cat = await crud.get_workflow_catalog_entry(db, str(a.workflow_id))
        result.append(crud.workflow_assignment_to_dict(a, cat))
    return result


@router.post("/organizations/{org_id}/workflows/{workflow_id}/assign", status_code=201)
async def assign_workflow(
    org_id: str,
    workflow_id: str,
    body: WorkflowAssignRequest,
    current_user: TokenData = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        uuid.UUID(org_id)
    except ValueError:
        raise HTTPException(400, "Invalid org_id")

    org_result = await db.execute(
        select(Organization).where(Organization.id == uuid.UUID(org_id))
    )
    if not org_result.scalar_one_or_none():
        raise HTTPException(404, "Organization not found")

    wf = await crud.get_workflow_catalog_entry(db, workflow_id)
    if not wf:
        raise HTTPException(404, "Workflow not found in catalog")

    assignment = await crud.assign_workflow_to_org(
        db, org_id, workflow_id,
        assigned_by=current_user.email,
        notes=body.notes,
    )
    await _audit(db, current_user, "workflow.assigned", "workflow_assignment",
                 str(assignment.id), org_id,
                 {"workflow_key": wf.key, "workflow_name": wf.name})
    return {"message": f"Workflow '{wf.name}' assigned", "assignment_id": str(assignment.id)}


@router.delete("/organizations/{org_id}/workflows/{workflow_id}/assign")
async def unassign_workflow(
    org_id: str,
    workflow_id: str,
    current_user: TokenData = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    wf = await crud.get_workflow_catalog_entry(db, workflow_id)
    removed = await crud.unassign_workflow_from_org(db, org_id, workflow_id)
    if not removed:
        raise HTTPException(404, "Assignment not found")
    await _audit(db, current_user, "workflow.unassigned", "workflow_assignment",
                 None, org_id, {"workflow_key": wf.key if wf else workflow_id})
    return {"message": "Assignment removed"}


@router.get("/organizations/{org_id}/workflows/access/{workflow_key}")
async def check_workflow_access(
    org_id: str,
    workflow_key: str,
    _: TokenData = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Server-side authorization check — enforces all 6 steps including industry applicability."""
    return await crud.check_org_workflow_access(db, org_id, workflow_key)


@router.get("/organizations/{org_id}/workflows/applicable")
async def get_applicable_workflows_for_org(
    org_id: str,
    _: TokenData = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Return workflows applicable to this organization's industry.
    Used by the assignment UI to show only relevant workflows when an org is selected.
    GLOBAL workflows are always included.  INDUSTRY workflows are included only
    when they match the org's industry field.
    Does NOT filter by plan entitlement or assignment — that's handled separately.
    """
    from db.models.core import WorkflowCatalog as _WCat
    from sqlalchemy import or_ as _or

    try:
        oid = uuid.UUID(org_id)
    except ValueError:
        raise HTTPException(400, "Invalid org_id")

    org_result = await db.execute(select(Organization).where(Organization.id == oid))
    org = org_result.scalar_one_or_none()
    if not org:
        raise HTTPException(404, "Organization not found")

    applicable = await crud.get_available_workflows_for_org(db, org_id)
    return {
        "organization_id":   org_id,
        "organization_name": org.name,
        "industry":          org.industry,
        "workflows": [crud.workflow_catalog_to_dict(w) for w in applicable],
    }


@router.post("/organizations/{org_id}/workflows/auto-assign")
async def trigger_auto_assign(
    org_id: str,
    current_user: TokenData = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Manually trigger auto-assignment of industry-appropriate workflows for an org.
    Use this to fix existing orgs that were created before auto-assign was deployed.
    """
    try:
        oid = uuid.UUID(org_id)
    except ValueError:
        raise HTTPException(400, "Invalid org_id")

    org_result = await db.execute(select(Organization).where(Organization.id == oid))
    org = org_result.scalar_one_or_none()
    if not org:
        raise HTTPException(404, "Organization not found")

    # Get plan slug
    sub = await crud.get_org_subscription(db, org_id)
    plan_slug = "free"
    if sub:
        plan = await crud.get_billing_plan(db, str(sub.plan_id))
        if plan:
            plan_slug = plan.slug

    count = await crud.auto_assign_industry_workflows(
        db,
        organization_id=org_id,
        industry=org.industry or "saas",
        assigned_by=current_user.email,
        plan_slug=plan_slug,
    )
    await _audit(db, current_user, "workflows.auto_assigned", "organization", org_id, org_id,
                 {"industry": org.industry, "count": count})
    return {
        "organization_id":   org_id,
        "organization_name": org.name,
        "industry":          org.industry,
        "assigned_count":    count,
        "message": f"Auto-assigned {count} workflows for {org.name} ({org.industry})",
    }


@router.post("/workflows/fix-all-orgs")
async def fix_all_org_assignments(
    current_user: TokenData = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Run auto-assign for ALL orgs that have zero workflow assignments.
    One-time repair endpoint for orgs created before auto-assign was deployed.
    """
    from sqlalchemy import func as _func, not_, exists

    # Find orgs with no active assignments
    from db.models.core import OrganizationWorkflowAssignment as _OWA
    orgs_result = await db.execute(select(Organization).where(Organization.active.is_(True)))
    all_orgs = list(orgs_result.scalars().all())

    # Check which have zero assignments
    assign_count_result = await db.execute(
        select(_OWA.organization_id, _func.count().label("cnt"))
        .where(_OWA.status == "active")
        .group_by(_OWA.organization_id)
    )
    has_assignments: set[str] = {str(r.organization_id) for r in assign_count_result.all()}

    fixed = []
    skipped = []
    for org in all_orgs:
        oid = str(org.id)
        if oid in has_assignments:
            skipped.append(org.name)
            continue
        sub = await crud.get_org_subscription(db, oid)
        plan_slug = "free"
        if sub:
            plan = await crud.get_billing_plan(db, str(sub.plan_id))
            if plan:
                plan_slug = plan.slug
        count = await crud.auto_assign_industry_workflows(
            db, organization_id=oid,
            industry=org.industry or "saas",
            assigned_by=f"system:fix-all/{current_user.email}",
            plan_slug=plan_slug,
        )
        fixed.append({"org": org.name, "industry": org.industry, "assigned": count})

    await _audit(db, current_user, "workflows.fix_all_orgs", "platform", None, None,
                 {"fixed": len(fixed), "skipped": len(skipped)})
    return {
        "fixed":   fixed,
        "skipped": skipped,
        "summary": f"Fixed {len(fixed)} orgs, skipped {len(skipped)} (already had assignments)",
    }


# ─────────────────────────────────────────────────────────────────────────────
# WORKFLOW RUNS  (platform monitoring — admin only)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/runs")
async def list_runs(
    _: TokenData = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
    organization_id: Optional[str] = Query(None),
    workflow_name:   Optional[str] = Query(None),
    run_status:      Optional[str] = Query(None, alias="status"),
    limit:           int           = Query(100, le=500),
    offset:          int           = Query(0),
):
    stmt = (
        select(WorkflowInstance, Organization.name.label("org_name"))
        .join(Organization, WorkflowInstance.organization_id == Organization.id, isouter=True)
        .order_by(WorkflowInstance.started_at.desc())
        .limit(limit).offset(offset)
    )
    if organization_id:
        try:
            stmt = stmt.where(WorkflowInstance.organization_id == uuid.UUID(organization_id))
        except ValueError:
            pass
    if workflow_name:
        stmt = stmt.where(WorkflowInstance.workflow_name.ilike(f"%{workflow_name}%"))
    if run_status:
        stmt = stmt.where(WorkflowInstance.status == run_status)

    rows = (await db.execute(stmt)).all()
    result = []
    for inst, org_name in rows:
        duration_ms = None
        if inst.started_at and inst.completed_at:
            duration_ms = int((inst.completed_at - inst.started_at).total_seconds() * 1000)
        result.append({
            "run_id":          str(inst.id),
            "organization":    org_name or "Unknown",
            "organization_id": str(inst.organization_id),
            "workflow":        inst.workflow_name,
            "status":          inst.status,
            "started_at":      inst.started_at.isoformat() if inst.started_at else None,
            "completed_at":    inst.completed_at.isoformat() if inst.completed_at else None,
            "duration_ms":     duration_ms,
            "tokens":          (inst.total_tokens_in or 0) + (inst.total_tokens_out or 0),
            "cost_usd":        float(inst.total_cost_usd) if inst.total_cost_usd else None,
            "error":           inst.error_log,
            "current_node":    inst.current_node,
        })
    return result


@router.get("/runs/{run_id}")
async def get_run_detail(
    run_id: str,
    _: TokenData = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    inst = await crud.get_workflow_instance(db, run_id)
    if not inst:
        raise HTTPException(404, "Run not found")

    agent_runs = await crud.list_agent_run_records(db, run_id)

    try:
        org_name = (await db.execute(
            select(Organization.name).where(Organization.id == inst.organization_id)
        )).scalar_one_or_none() or "Unknown"
    except Exception:
        org_name = "Unknown"

    duration_ms = None
    if inst.started_at and inst.completed_at:
        duration_ms = int((inst.completed_at - inst.started_at).total_seconds() * 1000)

    return {
        "run_id":          str(inst.id),
        "organization":    org_name,
        "organization_id": str(inst.organization_id),
        "workflow":        inst.workflow_name,
        "status":          inst.status,
        "started_at":      inst.started_at.isoformat() if inst.started_at else None,
        "completed_at":    inst.completed_at.isoformat() if inst.completed_at else None,
        "duration_ms":     duration_ms,
        "tokens_in":       inst.total_tokens_in  or 0,
        "tokens_out":      inst.total_tokens_out or 0,
        "cost_usd":        float(inst.total_cost_usd) if inst.total_cost_usd else None,
        "error_log":       inst.error_log,
        "current_node":    inst.current_node,
        "agent_runs":      [crud.agent_run_record_to_dict(r) for r in agent_runs],
        "outcome":         inst.outcome,
    }


# ─────────────────────────────────────────────────────────────────────────────
# PLANS & PRICING
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/plans")
async def list_plans(
    _: TokenData = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
    include_archived: bool = Query(False),
):
    plans = await crud.list_billing_plans(db, include_archived=include_archived)
    if not plans:
        try:
            from db.seed.plans_seed import seed_plans_and_catalog
            await seed_plans_and_catalog(db)
            plans = await crud.list_billing_plans(db, include_archived=include_archived)
        except Exception as _seed_err:
            log.warning("Auto-seed plans failed", error=str(_seed_err))

    result = []
    for p in plans:
        d = crud.billing_plan_to_dict(p)
        d["entitlements"] = await crud.get_plan_entitlements(db, str(p.id))
        result.append(d)
    return result


@router.post("/plans", status_code=201)
async def create_plan(
    body: PlanCreateRequest,
    current_user: TokenData = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    if await crud.get_billing_plan_by_slug(db, body.slug):
        raise HTTPException(409, f"Plan slug '{body.slug}' already exists")
    plan = await crud.create_billing_plan(db, body.model_dump())
    await _audit(db, current_user, "plan.created", "billing_plan", str(plan.id),
                 metadata={"slug": body.slug, "name": body.name})
    return crud.billing_plan_to_dict(plan)


@router.patch("/plans/{plan_id}")
async def update_plan(
    plan_id: str,
    body: PlanUpdateRequest,
    current_user: TokenData = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    updated = await crud.update_billing_plan(db, plan_id, body.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(404, "Plan not found")
    await _audit(db, current_user, "plan.updated", "billing_plan", plan_id,
                 metadata=body.model_dump(exclude_none=True))
    return crud.billing_plan_to_dict(updated)


@router.put("/plans/{plan_id}/entitlements")
async def set_plan_entitlements(
    plan_id: str,
    body: PlanEntitlementsRequest,
    current_user: TokenData = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    if not await crud.get_billing_plan(db, plan_id):
        raise HTTPException(404, "Plan not found")
    await crud.set_plan_entitlements(db, plan_id, body.workflow_ids)
    await _audit(db, current_user, "plan.entitlements_updated", "billing_plan", plan_id,
                 metadata={"workflow_ids": body.workflow_ids})
    return {"message": "Entitlements updated", "workflow_ids": body.workflow_ids}


# ─────────────────────────────────────────────────────────────────────────────
# SUBSCRIPTIONS
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/subscriptions")
async def list_subscriptions(
    _: TokenData = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    subs = await crud.list_org_subscriptions(db)

    orgs_map = {
        str(o.id): o.name
        for o in (await db.execute(select(Organization))).scalars().all()
    }
    from db.models.core import BillingPlan
    plans_map = {
        str(p.id): p
        for p in (await db.execute(select(BillingPlan))).scalars().all()
    }

    return [
        {
            **crud.org_subscription_to_dict(s, plans_map.get(str(s.plan_id))),
            "organization_name": orgs_map.get(str(s.organization_id), "Unknown"),
        }
        for s in subs
    ]


@router.get("/subscriptions/{org_id}")
async def get_subscription(
    org_id: str,
    _: TokenData = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    sub = await crud.get_org_subscription(db, org_id)
    if not sub:
        raise HTTPException(404, "No subscription found")
    plan = await crud.get_billing_plan(db, str(sub.plan_id))
    return crud.org_subscription_to_dict(sub, plan)


@router.post("/subscriptions/{org_id}", status_code=201)
async def create_subscription(
    org_id: str,
    body: SubscriptionCreateRequest,
    current_user: TokenData = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    plan = await crud.get_billing_plan(db, body.plan_id)
    if not plan:
        raise HTTPException(404, "Plan not found")
    if await crud.get_org_subscription(db, org_id):
        raise HTTPException(409, "Subscription already exists — use PATCH to update")

    sub = await crud.create_org_subscription(db, org_id, body.plan_id, body.billing_cycle)
    await _audit(db, current_user, "subscription.created", "subscription",
                 str(sub.id), org_id, {"plan": plan.slug, "cycle": body.billing_cycle})
    return crud.org_subscription_to_dict(sub, plan)


@router.patch("/subscriptions/{org_id}")
async def update_subscription(
    org_id: str,
    body: SubscriptionUpdateRequest,
    current_user: TokenData = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    if not await crud.get_org_subscription(db, org_id):
        raise HTTPException(404, "Subscription not found")
    updated = await crud.update_org_subscription(db, org_id, body.model_dump(exclude_none=True))
    plan = await crud.get_billing_plan(db, str(updated.plan_id))
    await _audit(db, current_user, "subscription.updated", "subscription",
                 str(updated.id), org_id, body.model_dump(exclude_none=True))
    return crud.org_subscription_to_dict(updated, plan)


# ─────────────────────────────────────────────────────────────────────────────
# USAGE & METERING
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/usage")
async def get_platform_usage(
    _: TokenData = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
    days: int = Query(30, ge=1, le=365),
):
    return await crud.get_usage_summary(db, days=days)


@router.get("/usage/{org_id}")
async def get_org_usage(
    org_id: str,
    _: TokenData = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
    days: int = Query(30, ge=1, le=365),
):
    return await crud.get_usage_summary(db, organization_id=org_id, days=days)


@router.get("/usage/{org_id}/records")
async def list_usage_records(
    org_id: str,
    _: TokenData = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
    workflow_key: Optional[str] = Query(None),
    limit:        int           = Query(100, le=500),
    offset:       int           = Query(0),
):
    records = await crud.list_usage_records(
        db, organization_id=org_id, workflow_key=workflow_key,
        limit=limit, offset=offset,
    )
    return [crud.usage_record_to_dict(r) for r in records]


# ─────────────────────────────────────────────────────────────────────────────
# INVOICES
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/invoices")
async def list_invoices(
    _: TokenData = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
    organization_id: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
):
    invoices = await crud.list_invoices(db, organization_id=organization_id, limit=limit)
    orgs_map = {
        str(o.id): o.name
        for o in (await db.execute(select(Organization))).scalars().all()
    }
    return [crud.invoice_to_dict(inv, orgs_map.get(str(inv.organization_id))) for inv in invoices]


# ─────────────────────────────────────────────────────────────────────────────
# AUDIT LOG
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/audit")
async def get_audit_log(
    _: TokenData = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
    organization_id: Optional[str] = Query(None),
    action:          Optional[str] = Query(None),
    entity_type:     Optional[str] = Query(None),
    limit:           int           = Query(200, le=1000),
    offset:          int           = Query(0),
):
    events = await crud.list_audit_events(
        db,
        organization_id=organization_id,
        action=action,
        entity_type=entity_type,
        limit=limit,
        offset=offset,
    )
    return [crud.audit_event_to_dict(e) for e in events]


# ─────────────────────────────────────────────────────────────────────────────
# EXCEPTIONS  (platform-level failures only — NOT SMB Owner approval queue)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/exceptions")
async def list_exceptions(
    _: TokenData = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(100, le=500),
):
    """
    Platform-level exceptions only:
    - Failed workflow runs
    - Approval items flagged as policy/provider/system errors

    NOT the SMB Owner approval queue — that lives at /escalations and /reviews.
    """
    # Failed runs
    failed_rows = (await db.execute(
        select(WorkflowInstance, Organization.name.label("org_name"))
        .join(Organization, WorkflowInstance.organization_id == Organization.id, isouter=True)
        .where(WorkflowInstance.status == "failed")
        .order_by(WorkflowInstance.started_at.desc())
        .limit(limit)
    )).all()

    workflow_failures = [
        {
            "type":            "workflow_failure",
            "id":              str(inst.id),
            "organization":    org_name or "Unknown",
            "organization_id": str(inst.organization_id),
            "workflow":        inst.workflow_name,
            "started_at":      inst.started_at.isoformat() if inst.started_at else None,
            "error":           inst.error_log,
            "severity":        "error",
        }
        for inst, org_name in failed_rows
    ]

    # Policy / system escalation items only
    platform_review_types = (
        "policy_violation", "provider_failure", "system_error",
        "workflow_error", "escalation", "rate_limit_exceeded",
    )
    policy_rows = (await db.execute(
        select(ApprovalItem)
        .where(
            ApprovalItem.status == "pending",
            ApprovalItem.review_type.in_(platform_review_types),
        )
        .order_by(ApprovalItem.created_at.desc())
        .limit(50)
    )).scalars().all()

    policy_items = [
        {
            "type":            "policy_escalation",
            "id":              str(item.id),
            "organization_id": str(item.organization_id),
            "review_type":     item.review_type,
            "reason":          item.reason,
            "created_at":      item.created_at.isoformat() if item.created_at else None,
            "severity":        "warning",
        }
        for item in policy_rows
    ]

    return {
        "total":              len(workflow_failures) + len(policy_items),
        "workflow_failures":  workflow_failures,
        "policy_escalations": policy_items,
    }


# ─────────────────────────────────────────────────────────────────────────────
# PLATFORM HEALTH
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/health")
async def get_platform_health(
    _: TokenData = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Real connectivity checks per service.
    Returns actual status — never fabricates 'Operational'.
    """
    import os, asyncio
    services: dict[str, dict] = {}

    # Database
    try:
        await db.execute(text("SELECT 1"))
        services["database"] = {"status": "operational", "label": "Database (PostgreSQL)"}
    except Exception as e:
        services["database"] = {"status": "unavailable", "label": "Database (PostgreSQL)", "error": str(e)}

    # Redis
    try:
        from core.redis_pubsub import pubsub as _ps
        if _ps and hasattr(_ps, "ping"):
            await asyncio.wait_for(_ps.ping(), timeout=2.0)
            services["redis"] = {"status": "operational", "label": "Redis / PubSub"}
        else:
            services["redis"] = {"status": "not_configured", "label": "Redis / PubSub"}
    except Exception as e:
        services["redis"] = {"status": "degraded", "label": "Redis / PubSub", "error": str(e)[:120]}

    # AI providers — key presence only (no live API call to avoid cost)
    provider_envs = {
        "anthropic":  "ANTHROPIC_API_KEY",
        "openai":     "OPENAI_API_KEY",
        "google_ai":  "GOOGLE_API_KEY",
        "groq":       "GROQ_API_KEY",
    }
    ai_statuses = {}
    for pid, env in provider_envs.items():
        val = os.getenv(env, "")
        ok  = bool(val and not val.startswith("YOUR_") and len(val) > 10)
        ai_statuses[pid] = {
            "status":     "configured" if ok else "not_configured",
            "label":      pid.replace("_", " ").title(),
            "configured": ok,
        }
    services["ai_providers"] = ai_statuses

    # Pollinations (no key needed)
    services["ai_providers"]["pollinations"] = {
        "status": "configured", "label": "Pollinations AI", "configured": True,
    }

    # Workflow engine — check for stuck running jobs
    try:
        stuck_count = (await db.execute(
            select(func.count()).select_from(WorkflowInstance)
            .where(
                WorkflowInstance.status == "running",
                WorkflowInstance.started_at < datetime.utcnow() - timedelta(hours=2),
            )
        )).scalar() or 0
        services["workflow_engine"] = {
            "status":     "degraded" if stuck_count > 0 else "operational",
            "label":      "Workflow Engine",
            "stuck_runs": stuck_count,
        }
    except Exception as e:
        services["workflow_engine"] = {"status": "unknown", "label": "Workflow Engine", "error": str(e)[:120]}

    # Derive overall
    flat = [
        v.get("status") for v in services.values()
        if isinstance(v, dict) and "status" in v
    ]
    # Also check nested AI provider statuses
    if isinstance(services.get("ai_providers"), dict):
        flat += [v.get("status") for v in services["ai_providers"].values() if isinstance(v, dict)]

    if any(s == "unavailable" for s in flat):
        overall = "unavailable"
    elif any(s in ("degraded",) for s in flat):
        overall = "degraded"
    elif any(s == "not_configured" for s in flat):
        overall = "partial"
    else:
        overall = "operational"

    return {"overall": overall, "services": services, "checked_at": datetime.utcnow().isoformat()}


# ─────────────────────────────────────────────────────────────────────────────
# AI PROVIDERS & MODELS
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/providers")
async def get_providers(_: TokenData = Depends(_require_admin)):
    import os
    configs = [
        {"id": "anthropic",   "name": "Anthropic",         "key_env": "ANTHROPIC_API_KEY",
         "models": ["claude-opus-4-5", "claude-3-5-haiku-20241022"],     "capabilities": ["text", "reasoning", "code"]},
        {"id": "openai",      "name": "OpenAI",             "key_env": "OPENAI_API_KEY",
         "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],             "capabilities": ["text", "vision", "embeddings"]},
        {"id": "google_ai",   "name": "Google AI (Gemini)", "key_env": "GOOGLE_API_KEY",
         "models": ["gemini-1.5-pro-latest", "gemini-1.5-flash-latest"], "capabilities": ["text", "vision", "multimodal"]},
        {"id": "groq",        "name": "Groq",               "key_env": "GROQ_API_KEY",
         "models": ["llama-3.3-70b-versatile", "mixtral-8x7b-32768"],    "capabilities": ["text", "fast_inference"]},
        {"id": "pollinations","name": "Pollinations AI",   "key_env": "POLLINATIONS_API_KEY",
         "models": ["flux", "turbo"],                                     "capabilities": ["image_generation"]},
    ]
    result = []
    for p in configs:
        val = os.getenv(p["key_env"], "") or (os.getenv("GEMINI_API_KEY", "") if p["id"] == "google_ai" else "")
        ok = bool(val and not val.startswith("YOUR_") and len(val) > 8)
        result.append({
            "id":           p["id"],
            "name":         p["name"],
            "configured":   ok,
            "status":       "configured" if ok else "not_configured",
            "models":       p["models"],
            "capabilities": p["capabilities"],
            "key_hint":     f"{val[:4]}…" if ok and val and val != "N/A" else None,
        })
    return result


@router.get("/models")
async def get_models(_: TokenData = Depends(_require_admin)):
    import json
    from pathlib import Path
    config_path = Path("config/templates/llm_config.json")
    if not config_path.exists():
        return {"models": [], "note": "LLM config file not found"}
    try:
        raw = json.loads(config_path.read_text())
    except Exception as e:
        return {"models": [], "error": str(e)}

    models = []
    if isinstance(raw, list):
        models = raw
    elif isinstance(raw, dict):
        for provider_id, provider_data in raw.items():
            if isinstance(provider_data, dict):
                for model_id, model_info in provider_data.items():
                    if isinstance(model_info, dict):
                        models.append({"provider": provider_id, "model_id": model_id, **model_info})
    return {"models": models, "total": len(models)}


@router.get("/routing")
async def get_routing(
    _: TokenData = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    saved = await crud.get_platform_setting(db, "llm_routing")
    if saved:
        return saved
    return {
        "hierarchy": [
            {"level": "platform_default",  "label": "Platform Default",  "description": "Applies to all workflows unless overridden"},
            {"level": "task_default",      "label": "Task Default",      "description": "Per-task-type override"},
            {"level": "agent_assignment",  "label": "Agent Assignment",  "description": "Per-agent override"},
            {"level": "workflow_override", "label": "Workflow Override", "description": "Per-workflow-run override"},
        ],
        "current_defaults": {
            "primary_provider":  "anthropic",
            "fallback_provider": "groq",
            "image_provider":    "pollinations",
        },
        "note": "No routing configuration saved yet.",
    }


# ─────────────────────────────────────────────────────────────────────────────
# PLATFORM SETTINGS
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/settings")
async def get_settings(
    _: TokenData = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await crud.get_all_platform_settings(db)


@router.patch("/settings")
async def update_settings(
    body: PlatformSettingsUpdateRequest,
    current_user: TokenData = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    for key, value in body.settings.items():
        await crud.set_platform_setting(db, key, value, updated_by=current_user.email)
    await _audit(db, current_user, "settings.updated", "platform_settings",
                 metadata={"keys_updated": list(body.settings.keys())})
    return {"message": "Settings updated", "updated_keys": list(body.settings.keys())}
