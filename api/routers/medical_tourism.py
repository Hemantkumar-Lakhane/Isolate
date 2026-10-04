"""
api/routers/medical_tourism.py
==============================
Medical Tourism Vertical Pilot #1 API Router.
Strict Non-Clinical Scope: No diagnosis, no prescription, no clinical treatment recommendations,
no clinical hospital ranking. Coordinator assistance & document intelligence only.
"""

from __future__ import annotations

import uuid
from datetime import datetime, date
from typing import Any, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps.auth import TokenData, require_authenticated_user
from api.dependencies import get_db

log = structlog.get_logger()
router = APIRouter(prefix="/api/v1/medical", tags=["Medical Tourism Pilot #1"])

class InquiryIntakeRequest(BaseModel):
    patient_alias: str
    country: str
    specialty: str = "fertility_ivf" # fertility_ivf, revision_orthopedics
    initial_notes: Optional[str] = None

class QuoteNormalizationRequest(BaseModel):
    provider_name: str
    city: str
    raw_amount: float
    currency: str = "USD"
    line_items: list[dict] = Field(default_factory=list) # [{category, label, amount, is_included}]

class DraftCommunicationRequest(BaseModel):
    recipient_email: str
    subject: str
    message_intent: str # intake_ack, quote_clarification, document_request, journey_update

@router.get("/cases")
async def list_medical_cases(
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_authenticated_user),
):
    """List active medical coordination cases for the organization."""
    from sqlalchemy import select
    from db.models.medical_tourism import MedicalCase, PatientContact

    org_id = current_user.organization_id
    if not org_id:
        return []

    stmt = select(MedicalCase).where(MedicalCase.organization_id == uuid.UUID(org_id)).order_by(MedicalCase.created_at.desc())
    result = await db.execute(stmt)
    cases = result.scalars().all()

    output = []
    for c in cases:
        output.append({
            "id": str(c.id),
            "case_number": c.case_number,
            "specialty": c.specialty,
            "stage": c.stage,
            "assigned_coordinator": c.assigned_coordinator_id or "Unassigned",
            "status": c.status,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })
    return output

@router.post("/cases")
async def create_patient_intake(
    body: InquiryIntakeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_authenticated_user),
):
    """Intake triage: Create patient contact alias & operational medical case (Non-Clinical)."""
    from db.models.medical_tourism import PatientContact, MedicalCase

    org_id = current_user.organization_id
    if not org_id:
        raise HTTPException(status_code=400, detail="Missing Organization ID")

    org_uuid = uuid.UUID(org_id)
    contact = PatientContact(
        id=uuid.uuid4(),
        organization_id=org_uuid,
        alias_name=body.patient_alias,
        country=body.country,
        consent_status="granted",
    )
    db.add(contact)

    case_num = f"CASE-{uuid.uuid4().hex[:6].upper()}"
    m_case = MedicalCase(
        id=uuid.uuid4(),
        organization_id=org_uuid,
        case_number=case_num,
        patient_contact_id=contact.id,
        specialty=body.specialty,
        stage="intake",
        assigned_coordinator_id=current_user.email,
        status="active",
    )
    db.add(m_case)
    await db.commit()
    await db.refresh(m_case)

    return {
        "id": str(m_case.id),
        "case_number": m_case.case_number,
        "specialty": m_case.specialty,
        "stage": m_case.stage,
        "patient_alias": body.patient_alias,
        "country": body.country,
        "message": "Patient intake case created successfully.",
    }

@router.post("/cases/{case_id}/quote-comparison")
async def normalize_medical_quote(
    case_id: str,
    body: QuoteNormalizationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_authenticated_user),
):
    """Normalize provider quote into canonical taxonomy for coordinator comparison."""
    from db.models.medical_tourism import MedicalCase, MedicalQuote, QuoteLineItem, ProviderFacility

    org_id = current_user.organization_id
    org_uuid = uuid.UUID(org_id) if org_id else uuid.uuid4()

    # Create/get provider facility
    provider = ProviderFacility(
        id=uuid.uuid4(),
        organization_id=org_uuid,
        name=body.provider_name,
        city=body.city,
        verification_status="independently_verified",
    )
    db.add(provider)

    quote = MedicalQuote(
        id=uuid.uuid4(),
        case_id=uuid.UUID(case_id),
        provider_id=provider.id,
        raw_amount=body.raw_amount,
        currency=body.currency,
        review_status="pending_approval",
    )
    db.add(quote)

    items_created = []
    for item in body.line_items:
        q_item = QuoteLineItem(
            id=uuid.uuid4(),
            quote_id=quote.id,
            canonical_category=item.get("category", "consultation"),
            raw_label=item.get("label", "Service item"),
            amount=float(item.get("amount", 0.0)),
            is_included=bool(item.get("is_included", True)),
        )
        db.add(q_item)
        items_created.append(q_item.canonical_category)

    await db.commit()

    return {
        "quote_id": str(quote.id),
        "provider_name": body.provider_name,
        "total_amount": body.raw_amount,
        "currency": body.currency,
        "normalized_categories": items_created,
        "status": quote.review_status,
        "disclaimer": "Operational quote comparison for coordinator review. Not a clinical treatment recommendation.",
    }

@router.post("/cases/{case_id}/draft-comm")
async def generate_coordinator_communication_draft(
    case_id: str,
    body: DraftCommunicationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_authenticated_user),
):
    """Generate communication draft for coordinator human approval (No autonomous send)."""
    from db.models.medical_tourism import CommunicationDraft, MedicalCase

    draft = CommunicationDraft(
        id=uuid.uuid4(),
        case_id=uuid.UUID(case_id),
        recipient_email=body.recipient_email,
        subject=body.subject,
        body_text=(
            f"Dear Patient,\n\n"
            f"Thank you for contacting our care coordination team. "
            f"We have compiled your coordinator-reviewed journey details and quote comparisons.\n\n"
            f"Please review the attached journey workspace.\n\n"
            f"Warm regards,\nCare Coordination Team"
        ),
        drafted_by_agent="CustomerOutreachAgent",
        status="pending_approval",
    )
    db.add(draft)
    await db.commit()
    await db.refresh(draft)

    return {
        "draft_id": str(draft.id),
        "recipient_email": draft.recipient_email,
        "subject": draft.subject,
        "status": draft.status,
        "requires_human_approval": True,
    }
