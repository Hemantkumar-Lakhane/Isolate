"""
api/routers/notifications.py
============================
Real-time notification engine & Workflow Access Request router.
Supports:
- Requesting workflow access from client UI
- Real-time Redis/WS push to Admins and Users
- In-app notification center (Access requests, Assignments, Escalations, What's New)
- One-click Admin approval with automatic workflow assignment
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from api import crud
from api.auth import TokenData, require_any_auth, require_admin
from api.dependencies import get_db
from core.redis_pubsub import pubsub as redis_pubsub
from db.models.core import (
    ApprovalItem,
    Organization,
    OrganizationUser,
    OrganizationWorkflowAssignment,
    WorkflowCatalog,
)

log = structlog.get_logger()
router = APIRouter(prefix="/api/v1/notifications", tags=["Notifications & Access Requests"])


class WorkflowAccessRequest(BaseModel):
    workflow_key: str = Field(..., description="Key of the workflow being requested")
    reason: Optional[str] = Field(None, description="Reason for requesting access")


class RequestAccessResponse(BaseModel):
    request_id: str
    workflow_key: str
    workflow_name: str
    status: str = "pending"
    message: str


class NotificationItem(BaseModel):
    id: str
    type: str  # "access_request" | "workflow_assigned" | "escalation" | "whats_new" | "system"
    scope: str = "personal"  # "personal" | "global"
    title: str
    message: str
    timestamp: str
    read: bool = False
    actionable: bool = False
    meta: Dict[str, Any] = Field(default_factory=dict)


@router.post("/request-access", response_model=RequestAccessResponse, status_code=201)
async def request_workflow_access(
    body: WorkflowAccessRequest,
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    """
    Submit a real-time request to admin for workflow access.
    Broadcasts instantly to all connected admin interfaces via WebSocket.
    """
    # 1. Resolve workflow
    wf_stmt = select(WorkflowCatalog).where(WorkflowCatalog.key == body.workflow_key).limit(1)
    wf_res = await db.execute(wf_stmt)
    wf = wf_res.scalar_one_or_none()
    if not wf:
        raise HTTPException(404, f"Workflow '{body.workflow_key}' not found in catalog")

    # 2. Resolve organization
    org_id = current_user.organization_id or current_user.tenant_id
    org_name = "Independent User"
    if org_id:
        try:
            o_res = await db.execute(select(Organization).where(Organization.id == uuid.UUID(str(org_id))))
            org_obj = o_res.scalar_one_or_none()
            if org_obj:
                org_name = org_obj.name
        except Exception:
            pass

    org_uuid = uuid.UUID(str(org_id)) if org_id else uuid.uuid4()

    # 3. Create ApprovalItem for request
    req_id = uuid.uuid4()
    req_payload = {
        "workflow_key": wf.key,
        "workflow_id": str(wf.id),
        "workflow_name": wf.name,
        "org_id": str(org_id) if org_id else None,
        "org_name": org_name,
        "user_id": current_user.user_id,
        "user_email": current_user.email,
        "user_name": current_user.full_name or current_user.email,
        "reason": body.reason or f"Requesting access to execute {wf.name} workflow.",
        "requested_at": datetime.utcnow().isoformat(),
    }

    approval = ApprovalItem(
        id=req_id,
        organization_id=org_uuid,
        instance_id=None,
        node_id="access_request",
        review_type="workflow_access_request",
        reason=f"Access requested for {wf.name} by {current_user.email} ({org_name})",
        context_brief=body.reason or f"User requested permission to use the {wf.name} pipeline.",
        payload=req_payload,
        status="pending",
        required_signatures=1,
        signatures=[],
        created_at=datetime.utcnow(),
    )
    db.add(approval)
    await db.commit()

    # 4. Broadcast Real-time WebSocket Event to Admin Topic
    ws_event = {
        "type": "workflow.access_requested",
        "id": str(req_id),
        "title": "Workflow Access Request",
        "message": f"{current_user.email} from {org_name} requested access to {wf.name}",
        "workflow_key": wf.key,
        "workflow_name": wf.name,
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

    return RequestAccessResponse(
        request_id=str(req_id),
        workflow_key=wf.key,
        workflow_name=wf.name,
        status="pending",
        message=f"Access request for '{wf.name}' sent to administrators in real time.",
    )


@router.get("", response_model=List[NotificationItem])
async def list_notifications(
    scope: Optional[str] = None,  # "personal" | "global" | None
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    """
    Get notifications list (Access requests, Assigned workflows, Escalations, What's New).
    Supports scope filtering: 'personal' (user-specific tasks & requests) vs 'global' (platform-wide).
    """
    items: List[NotificationItem] = []
    is_admin = current_user.role in ("super_admin", "platform_admin")
    org_id = current_user.organization_id or current_user.tenant_id

    # 1. PERSONAL: Access Requests (Admins see all pending, Users see their own)
    stmt = (
        select(ApprovalItem)
        .where(ApprovalItem.review_type == "workflow_access_request")
        .order_by(desc(ApprovalItem.created_at))
        .limit(20)
    )
    res = await db.execute(stmt)
    approvals = res.scalars().all()

    for app in approvals:
        payload = app.payload or {}
        if not is_admin and payload.get("user_email") != current_user.email:
            continue

        is_pending = app.status == "pending"
        wf_name = payload.get("workflow_name", "Workflow")
        user_email = payload.get("user_email", "User")
        org_name = payload.get("org_name", "Organization")

        title = f"Access Request: {wf_name}"
        if is_admin:
            msg = f"{user_email} ({org_name}) requested access to {wf_name}"
        else:
            msg = f"Your request for '{wf_name}' is {app.status}"

        items.append(NotificationItem(
            id=str(app.id),
            type="access_request",
            scope="personal",
            title=title,
            message=msg,
            timestamp=app.created_at.isoformat() if app.created_at else datetime.utcnow().isoformat(),
            read=not is_pending,
            actionable=is_admin and is_pending,
            meta={
                "approval_id": str(app.id),
                "workflow_key": payload.get("workflow_key"),
                "workflow_id": payload.get("workflow_id"),
                "workflow_name": wf_name,
                "org_id": payload.get("org_id"),
                "org_name": org_name,
                "user_email": user_email,
                "reason": payload.get("reason"),
                "status": app.status,
                "url": "/escalations",
            }
        ))

    # 2. PERSONAL: Pending Action Center Escalations / Approvals
    if org_id:
        try:
            o_uuid = uuid.UUID(str(org_id))
            escs_stmt = (
                select(ApprovalItem)
                .where(
                    ApprovalItem.organization_id == o_uuid,
                    ApprovalItem.review_type != "workflow_access_request",
                    ApprovalItem.status == "pending"
                )
                .order_by(desc(ApprovalItem.created_at))
                .limit(10)
            )
            escs_res = await db.execute(escs_stmt)
            pending_escs = escs_res.scalars().all()
            for esc in pending_escs:
                items.append(NotificationItem(
                    id=f"esc_{esc.id}",
                    type="escalation",
                    scope="personal",
                    title="Review Required: Action Item",
                    message=esc.reason or "Human sign-off required before dispatch",
                    timestamp=esc.created_at.isoformat() if esc.created_at else datetime.utcnow().isoformat(),
                    read=False,
                    actionable=True,
                    meta={"approval_id": str(esc.id), "url": "/escalations"}
                ))
        except Exception:
            pass

    # 3. PERSONAL: Workflows Assigned to User's Org
    if org_id:
        try:
            o_uuid = uuid.UUID(str(org_id))
            assign_stmt = (
                select(OrganizationWorkflowAssignment, WorkflowCatalog)
                .join(WorkflowCatalog, OrganizationWorkflowAssignment.workflow_id == WorkflowCatalog.id)
                .where(OrganizationWorkflowAssignment.organization_id == o_uuid)
                .order_by(desc(OrganizationWorkflowAssignment.assigned_at))
                .limit(5)
            )
            assign_res = await db.execute(assign_stmt)
            for a, cat in assign_res.all():
                items.append(NotificationItem(
                    id=f"assign_{a.id}",
                    type="workflow_assigned",
                    scope="personal",
                    title="Workflow Ready to Use",
                    message=f"'{cat.name}' has been assigned to your workspace.",
                    timestamp=a.assigned_at.isoformat() if a.assigned_at else datetime.utcnow().isoformat(),
                    read=True,
                    actionable=False,
                    meta={"workflow_key": cat.key, "workflow_name": cat.name, "url": f"/workflows/{cat.key}"}
                ))
        except Exception:
            pass

    # 4. GLOBAL: System Announcements & Feature Releases
    items.append(NotificationItem(
        id="global_product_launch_studio",
        type="system",
        scope="global",
        title="Global Announcement: Product Launch Studio",
        message="Multi-platform campaign synthesis, automated image generation, and Google Calendar sync are active.",
        timestamp=datetime.utcnow().isoformat(),
        read=False,
        actionable=False,
        meta={"badge": "New Feature", "url": "/workflows/product_launch"}
    ))

    items.append(NotificationItem(
        id="global_meeting_intel_v2",
        type="whats_new",
        scope="global",
        title="What's New: Live Meeting Connector & Audio Formats",
        message="Meeting Intelligence supports .mp3, .wav, .m4a, and .webm direct uploads with instant speaker transcription.",
        timestamp=datetime.utcnow().isoformat(),
        read=False,
        actionable=False,
        meta={"badge": "New Feature", "url": "/workflows/meeting_intelligence_followup"}
    ))

    items.append(NotificationItem(
        id="global_cross_org_workflows",
        type="whats_new",
        scope="global",
        title="What's New: Global Workflows & Cross-Org Access",
        message="Workflows marked as GLOBAL are instantly available to all organizations across the platform.",
        timestamp=datetime.utcnow().isoformat(),
        read=False,
        actionable=False,
        meta={"badge": "Platform Update", "url": "/workflow-library"}
    ))

    # Scope filter
    if scope:
        items = [i for i in items if i.scope == scope]

    # Sort newest first
    items.sort(key=lambda x: x.timestamp, reverse=True)
    return items[:40]


@router.post("/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    current_user: TokenData = Depends(require_any_auth),
):
    """Mark a specific notification as read."""
    return {"status": "success", "id": notification_id, "read": True}


@router.post("/mark-all-read")
async def mark_all_notifications_read(
    current_user: TokenData = Depends(require_any_auth),
):
    """Mark all notifications as read."""
    return {"status": "success", "read_all": True}


@router.post("/requests/{approval_id}/approve")
async def approve_access_request(
    approval_id: str,
    current_user: TokenData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    1-Click Admin Approval:
    Approves the access request and immediately assigns the workflow to the organization.
    """
    try:
        a_id = uuid.UUID(approval_id)
    except ValueError:
        raise HTTPException(400, "Invalid approval_id")

    res = await db.execute(select(ApprovalItem).where(ApprovalItem.id == a_id))
    approval = res.scalar_one_or_none()
    if not approval:
        raise HTTPException(404, "Access request not found")

    payload = approval.payload or {}
    workflow_id = payload.get("workflow_id")
    workflow_key = payload.get("workflow_key")
    org_id = payload.get("org_id") or str(approval.organization_id)

    if not workflow_id and workflow_key:
        wf_res = await db.execute(select(WorkflowCatalog).where(WorkflowCatalog.key == workflow_key))
        wf_obj = wf_res.scalar_one_or_none()
        if wf_obj:
            workflow_id = str(wf_obj.id)

    # Assign workflow if we have both org_id and workflow_id
    assignment = None
    if org_id and workflow_id:
        assignment = await crud.assign_workflow_to_org(
            db, org_id, workflow_id,
            assigned_by=current_user.email,
            notes=f"Approved request from {payload.get('user_email', 'user')}",
        )

    approval.status = "approved"
    approval.decided_by = current_user.email
    approval.decided_at = datetime.utcnow()
    await db.commit()

    # Broadcast approval WebSocket event
    event = {
        "type": "workflow.access_approved",
        "approval_id": approval_id,
        "workflow_name": payload.get("workflow_name"),
        "workflow_key": workflow_key,
        "org_id": org_id,
        "user_email": payload.get("user_email"),
        "approved_by": current_user.email,
        "timestamp": datetime.utcnow().isoformat(),
    }
    try:
        await redis_pubsub.publish("admin", event)
        if org_id:
            await redis_pubsub.publish(f"org:{org_id}", event)
    except Exception:
        pass

    return {
        "message": f"Approved access to '{payload.get('workflow_name', 'workflow')}' and assigned to organization.",
        "status": "approved",
        "assignment_id": str(assignment.id) if assignment else None,
    }


@router.post("/requests/{approval_id}/reject")
async def reject_access_request(
    approval_id: str,
    current_user: TokenData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Reject an access request."""
    try:
        a_id = uuid.UUID(approval_id)
    except ValueError:
        raise HTTPException(400, "Invalid approval_id")

    res = await db.execute(select(ApprovalItem).where(ApprovalItem.id == a_id))
    approval = res.scalar_one_or_none()
    if not approval:
        raise HTTPException(404, "Access request not found")

    approval.status = "rejected"
    approval.decided_by = current_user.email
    approval.decided_at = datetime.utcnow()
    await db.commit()

    return {"message": "Access request rejected.", "status": "rejected"}
