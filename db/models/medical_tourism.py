"""
db/models/medical_tourism.py
=============================
Domain ORM Models for Medical Tourism Vertical Pilot #1.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, Column, Date, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from db.models.core import Base

class PatientContact(Base):
    __tablename__ = "patient_contacts"

    id                 = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id    = Column(UUID(as_uuid=True), nullable=False)
    alias_name         = Column(String(255), nullable=False)
    country            = Column(String(100), nullable=False)
    consent_status     = Column(String(50), default="granted")
    consent_timestamp  = Column(DateTime, default=datetime.utcnow)
    created_at         = Column(DateTime, default=datetime.utcnow)

class MedicalCase(Base):
    __tablename__ = "medical_cases"

    id                      = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id         = Column(UUID(as_uuid=True), nullable=False)
    case_number             = Column(String(100), nullable=False, unique=True)
    patient_contact_id      = Column(UUID(as_uuid=True))
    specialty               = Column(String(100), nullable=False, default="fertility_ivf")
    stage                   = Column(String(100), nullable=False, default="intake")
    assigned_coordinator_id = Column(String(255))
    status                  = Column(String(50), default="active")
    created_at              = Column(DateTime, default=datetime.utcnow)
    updated_at              = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class CaseDocument(Base):
    __tablename__ = "case_documents"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id      = Column(UUID(as_uuid=True), nullable=False)
    document_type= Column(String(100), nullable=False)
    file_path    = Column(String(500), nullable=False)
    access_class = Column(String(50), default="confidential_health")
    uploaded_at  = Column(DateTime, default=datetime.utcnow)

class DocumentExtraction(Base):
    __tablename__ = "document_extractions"

    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id       = Column(UUID(as_uuid=True), nullable=False)
    schema_type       = Column(String(100), nullable=False)
    extracted_data    = Column(JSONB, nullable=False, default={})
    confidence_scores = Column(JSONB, default={})
    page_citations    = Column(JSONB, default=list)
    review_status     = Column(String(50), default="pending_review")
    reviewed_by       = Column(String(255))
    reviewed_at       = Column(DateTime)

class ProviderFacility(Base):
    __tablename__ = "provider_facilities"

    id                    = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id       = Column(UUID(as_uuid=True), nullable=False)
    name                  = Column(String(255), nullable=False)
    city                  = Column(String(100), nullable=False)
    specialties           = Column(JSONB, default=["fertility_ivf"])
    accreditation_evidence= Column(JSONB, default=list)
    verification_status   = Column(String(50), default="independently_verified")
    last_verified_at      = Column(DateTime, default=datetime.utcnow)

class MedicalQuote(Base):
    __tablename__ = "medical_quotes"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id      = Column(UUID(as_uuid=True), nullable=False)
    provider_id  = Column(UUID(as_uuid=True))
    raw_amount   = Column(Float, nullable=False)
    currency     = Column(String(10), default="USD")
    validity_date= Column(Date)
    review_status= Column(String(50), default="pending_approval")

class QuoteLineItem(Base):
    __tablename__ = "quote_line_items"

    id                 = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    quote_id           = Column(UUID(as_uuid=True), nullable=False)
    canonical_category = Column(String(100), nullable=False)
    raw_label          = Column(String(255), nullable=False)
    amount             = Column(Float, nullable=False)
    is_included        = Column(Boolean, default=True)
    is_exclusion       = Column(Boolean, default=False)
    notes              = Column(Text)

class CommunicationDraft(Base):
    __tablename__ = "communication_drafts"

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id          = Column(UUID(as_uuid=True), nullable=False)
    recipient_email  = Column(String(255), nullable=False)
    subject          = Column(String(255), nullable=False)
    body_text        = Column(Text, nullable=False)
    drafted_by_agent = Column(String(100), default="CustomerOutreachAgent")
    status           = Column(String(50), default="pending_approval")
    reviewed_by      = Column(String(255))
    reviewed_at      = Column(DateTime)
    created_at       = Column(DateTime, default=datetime.utcnow)
