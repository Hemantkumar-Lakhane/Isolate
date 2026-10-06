"""
tests/test_notifications.py
===========================
End-to-end integration tests for Real-time Notification Center:
- User submits workflow access request
- Real-time approval item creation and notification payload verification
- Admin retrieves notification list with dual personal/global scope filtering
- Admin 1-click approval assigns workflow to organization
- User receives approval notification and assigned workflow status
- Mark as read and mark all as read endpoints
"""

import uuid
from datetime import datetime
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON

@compiles(JSONB, "sqlite")
def _jsonb_sqlite(type_, compiler, **kw):
    return compiler.visit_JSON(JSON(), **kw)

from db.models.core import (
    Base as OrgBase,
    Organization,
    WorkflowCatalog,
    ApprovalItem,
)
from api.routers.notifications import (
    request_workflow_access,
    list_notifications,
    approve_access_request,
    reject_access_request,
    mark_notification_read,
    mark_all_notifications_read,
    WorkflowAccessRequest,
)
from api.auth import TokenData

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.mark.asyncio
async def test_end_to_end_notification_lifecycle():
    """
    Test end-to-end workflow access request, admin notification, 1-click approval,
    and user assignment notification.
    """
    engine = create_async_engine(TEST_DB_URL, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with engine.begin() as conn:
        await conn.run_sync(OrgBase.metadata.create_all)

    async with session_factory() as session:
        org_id = uuid.uuid4()
        wf_id = uuid.uuid4()

        # 1. Seed org and catalog workflow
        org = Organization(
            id=org_id,
            name="Acme Health Corp",
            industry="healthcare",
            enabled_modules=["healthcare"],
            active=True,
            created_at=datetime.utcnow(),
        )
        session.add(org)

        wf = WorkflowCatalog(
            id=wf_id,
            key="patient_clinic_booking_reminder",
            name="Patient Clinic Booking Reminder",
            description="Automated clinical scheduling, triage and SMS reminders.",
            category="healthcare",
            industry="healthcare",
            scope="CUSTOM",
            active=True,
            status="active",
        )
        session.add(wf)
        await session.commit()

        # User & Admin Tokens
        user_token = TokenData(
            sub="user@acmehealth.com",
            email="user@acmehealth.com",
            user_id=str(uuid.uuid4()),
            role="org_user",
            organization_id=str(org_id),
            tenant_id=str(org_id),
            full_name="Dr. Alex Vance",
        )

        admin_token = TokenData(
            sub="admin@smbflow.test",
            email="admin@smbflow.test",
            user_id=str(uuid.uuid4()),
            role="super_admin",
            organization_id=str(org_id),
            tenant_id=str(org_id),
            full_name="Platform Admin",
        )

        # ── Step 1: User submits workflow access request ─────────────────────
        req_body = WorkflowAccessRequest(
            workflow_key="patient_clinic_booking_reminder",
            reason="Need this for clinical patient scheduling triage.",
        )
        req_res = await request_workflow_access(
            body=req_body,
            current_user=user_token,
            db=session,
        )
        assert req_res.status == "pending"
        assert req_res.workflow_key == "patient_clinic_booking_reminder"
        req_id = req_res.request_id

        # ── Step 2: Admin retrieves notification list ────────────────────────
        admin_notifs = await list_notifications(
            scope="personal",
            current_user=admin_token,
            db=session,
        )
        assert len(admin_notifs) > 0

        target_notif = next((n for n in admin_notifs if n.id == str(req_id)), None)
        assert target_notif is not None
        assert target_notif.type == "access_request"
        assert target_notif.actionable is True
        assert "user@acmehealth.com" in target_notif.message

        # ── Step 3: Admin 1-Click Approve ────────────────────────────────────
        approve_data = await approve_access_request(
            approval_id=str(req_id),
            current_user=admin_token,
            db=session,
        )
        assert approve_data["status"] == "approved"
        assert approve_data["assignment_id"] is not None

        # ── Step 4: User fetches notifications and sees assignment ───────────
        user_notifs = await list_notifications(
            scope="personal",
            current_user=user_token,
            db=session,
        )
        assigned_notif = next((n for n in user_notifs if n.type == "workflow_assigned"), None)
        assert assigned_notif is not None
        assert "Patient Clinic Booking Reminder" in assigned_notif.message

        # ── Step 5: Mark notification as read ────────────────────────────────
        read_data = await mark_notification_read(
            notification_id=str(req_id),
            current_user=user_token,
        )
        assert read_data["read"] is True

        # ── Step 6: Mark all notifications as read ───────────────────────────
        read_all_data = await mark_all_notifications_read(
            current_user=user_token,
        )
        assert read_all_data["read_all"] is True

    await engine.dispose()
