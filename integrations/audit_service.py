"""
integrations/audit_service.py
=============================
Integration Audit Trail Service for SMBFlow Tool Connections.
Records safe, privacy-compliant audit events for tool connection lifecycles:
- connection_created
- oauth_started
- oauth_completed
- oauth_failed
- permission_granted
- permission_revoked
- token_refreshed
- connection_tested
- connection_disconnected
- capability_executed
- connection_error

STRICT SECURITY RULE:
Never record access tokens, refresh tokens, client secrets, or API keys in audit logs.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import structlog
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.core import ApprovalItem

log = structlog.get_logger()

# In-memory transient audit store (for fast retrieval & DB fallback)
_AUDIT_LOG_STORE: List[Dict[str, Any]] = []
_MAX_AUDIT_ITEMS = 500


async def record_audit_event(
    db: Optional[AsyncSession],
    org_id: uuid.UUID | str,
    user_id: Optional[uuid.UUID | str],
    provider: str,
    connection_id: Optional[uuid.UUID | str],
    event: str,
    capability: Optional[str] = None,
    success: bool = True,
    error_code: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Record an integration lifecycle audit event.
    Saves to memory buffer and PostgreSQL audit log entity.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    org_str = str(org_id) if org_id else None
    user_str = str(user_id) if user_id else None
    conn_str = str(connection_id) if connection_id else None

    # Sanitize details (ensure zero credential leakage)
    safe_details = {}
    if details:
        for k, v in details.items():
            if any(secret_term in k.lower() for secret_term in ("token", "secret", "password", "key", "credential", "auth")):
                safe_details[k] = "[REDACTED]"
            else:
                safe_details[k] = v

    audit_entry = {
        "id": str(uuid.uuid4()),
        "organization_id": org_str,
        "user_id": user_str,
        "provider": provider,
        "connection_id": conn_str,
        "event": event,
        "capability": capability,
        "success": success,
        "error_code": error_code,
        "details": safe_details,
        "ip_address": ip_address,
        "timestamp": now_iso,
    }

    # Store in fast memory ring buffer
    _AUDIT_LOG_STORE.append(audit_entry)
    if len(_AUDIT_LOG_STORE) > _MAX_AUDIT_ITEMS:
        _AUDIT_LOG_STORE.pop(0)

    # Persist in DB via ApprovalItem (review_type="integration_audit") if db session provided
    if db and org_str:
        try:
            org_uuid = uuid.UUID(org_str)
            item = ApprovalItem(
                id=uuid.UUID(audit_entry["id"]),
                organization_id=org_uuid,
                instance_id=None,
                node_id="integration_audit",
                review_type="integration_audit",
                reason=f"{provider.title()} {event.replace('_', ' ').title()}",
                context_brief=f"Event: {event} | Capability: {capability or 'N/A'} | Status: {'SUCCESS' if success else 'FAILED'}",
                payload=audit_entry,
                status="approved" if success else "rejected",
                required_signatures=0,
                signatures=[],
                created_at=datetime.now(timezone.utc),
            )
            db.add(item)
            await db.commit()
        except Exception as e:
            log.warning("Failed to persist audit item to DB", error=str(e), audit_event=event)

    log.info(
        "Integration audit event recorded",
        provider=provider,
        audit_event=event,
        success=success,
        org_id=org_str,
        capability=capability,
    )

    return audit_entry


async def get_connection_audit_logs(
    db: Optional[AsyncSession],
    org_id: uuid.UUID | str,
    connection_id: Optional[uuid.UUID | str] = None,
    provider: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Retrieve audit logs for a connection or organization."""
    org_str = str(org_id) if org_id else None
    conn_str = str(connection_id) if connection_id else None

    # First check database records
    if db and org_str:
        try:
            org_uuid = uuid.UUID(org_str)
            stmt = (
                select(ApprovalItem)
                .where(
                    ApprovalItem.organization_id == org_uuid,
                    ApprovalItem.review_type == "integration_audit",
                )
                .order_by(desc(ApprovalItem.created_at))
                .limit(limit)
            )
            res = await db.execute(stmt)
            db_items = res.scalars().all()
            if db_items:
                results = []
                for item in db_items:
                    payload = item.payload or {}
                    if conn_str and payload.get("connection_id") != conn_str:
                        continue
                    if provider and payload.get("provider") != provider:
                        continue
                    results.append(payload)
                if results:
                    return results
        except Exception as e:
            log.warning("Failed to query DB audit logs, falling back to memory buffer", error=str(e))

    # Fallback to memory buffer
    matched = []
    for item in reversed(_AUDIT_LOG_STORE):
        if org_str and item.get("organization_id") != org_str:
            continue
        if conn_str and item.get("connection_id") != conn_str:
            continue
        if provider and item.get("provider") != provider:
            continue
        matched.append(item)
        if len(matched) >= limit:
            break

    return matched
