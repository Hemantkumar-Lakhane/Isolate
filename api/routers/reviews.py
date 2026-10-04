"""
api/routers/reviews.py
======================
Action Center & Human-in-the-Loop (HITL) Review Queue API router.
Allows human operators/coordinators to decide pending escalations, edit email drafts, approve, or reject actions.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from api.auth import TokenData, require_any_auth
from api.dependencies import get_db
from core.redis_pubsub import pubsub as redis_pubsub

log = structlog.get_logger()
router = APIRouter(prefix="/api/v1/reviews", tags=["Review Queue & HITL"])


class ApprovalDecisionRequest(BaseModel):
    action_chosen: str  # e.g. 'approve', 'approve_draft', 'reject', 'send_email'
    decision_notes: Optional[str] = None
    patch_payload: Optional[dict] = None
    decided_by: Optional[str] = None


@router.get("")
async def list_reviews(
    status: str = Query("pending"),
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_any_auth),
):
    """List review queue items for the user's organization or tenant."""
    from db.models.core import ApprovalItem

    org_id = current_user.organization_id or current_user.tenant_id

    stmt = select(ApprovalItem)
    if org_id:
        try:
            org_uuid = uuid.UUID(org_id)
            stmt = stmt.where(ApprovalItem.organization_id == org_uuid)
        except (ValueError, TypeError):
            pass

    if status and status != "all":
        stmt = stmt.where(ApprovalItem.status == status)

    stmt = stmt.order_by(ApprovalItem.created_at.desc())
    result = await db.execute(stmt)
    items = result.scalars().all()

    output = []
    for item in items:
        output.append({
            "id": str(item.id),
            "escalation_id": str(item.id),
            "instance_id": str(item.instance_id) if item.instance_id else None,
            "run_id": str(item.instance_id) if item.instance_id else None,
            "node_id": item.node_id or "evaluate_actions",
            "review_type": item.review_type or "approval",
            "reason": item.reason or "Action requires review",
            "recommended_action": (item.payload or {}).get("action_type") or "approve_draft",
            "context_brief": item.context_brief or "",
            "payload": item.payload or {},
            "status": item.status,
            "required_signatures": item.required_signatures or 1,
            "signatures": item.signatures or [],
            "decided_by": item.decided_by,
            "decided_at": item.decided_at.isoformat() if item.decided_at else None,
            "created_at": item.created_at.isoformat() if item.created_at else None,
        })
    return output


@router.post("/{approval_id}/decide")
async def decide_approval_item(
    approval_id: str,
    body: ApprovalDecisionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_any_auth),
):
    """Approve or reject a pending review queue item."""
    from db.models.core import ApprovalItem

    try:
        appr_uuid = uuid.UUID(approval_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid approval ID format")

    stmt = select(ApprovalItem).where(ApprovalItem.id == appr_uuid)
    result = await db.execute(stmt)
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")

    action_lower = body.action_chosen.lower()
    new_status = "approved" if ("approve" in action_lower or "send" in action_lower) else "rejected"

    item.status = new_status
    item.decided_by = body.decided_by or current_user.email
    item.decided_at = datetime.utcnow()
    
    current_payload = item.payload or {}
    if body.decision_notes:
        current_payload["decision_notes"] = body.decision_notes
    if body.patch_payload:
        current_payload = {**current_payload, **body.patch_payload}
    item.payload = current_payload

    await db.commit()
    await db.refresh(item)

    # Safe test execution boundary — do not send real outbound emails
    if new_status == "approved":
        recipient = current_payload.get("to_address") or current_payload.get("to") or "client@enterprise.com"
        subject = current_payload.get("subject") or "Service Level Agreement Incident Update"
        log.info(
            "[TEST MODE] Approval executed safely — Simulated email action approved",
            approval_id=approval_id,
            recipient=recipient,
            subject=subject,
            simulated=True,
        )

    event_payload = {
        "approval_id": approval_id,
        "status": new_status,
        "action_chosen": body.action_chosen,
        "decided_by": item.decided_by,
        "organization_id": str(item.organization_id) if item.organization_id else None,
    }

    try:
        await redis_pubsub.publish_event("approval_decided", event_payload)
    except Exception as e:
        log.debug("Redis pub/sub publish failed (non-fatal)", error=str(e))

    log.info(
        "Review decision recorded",
        approval_id=approval_id,
        decided_by=item.decided_by,
        status=new_status,
        action=body.action_chosen,
    )

    return {
        "id": str(item.id),
        "status": item.status,
        "action_chosen": body.action_chosen,
        "decided_by": item.decided_by,
        "decided_at": item.decided_at.isoformat() if item.decided_at else None,
    }
