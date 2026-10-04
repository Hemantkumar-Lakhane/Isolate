-- =============================================================================
-- Migration 002: Medical Tourism Domain DDL & RLS Policies
-- Target: Supabase Managed PostgreSQL
-- =============================================================================

-- Patient Contacts (Anonymized Alias for public/private separation)
CREATE TABLE IF NOT EXISTS patient_contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    alias_name VARCHAR(255) NOT NULL,
    country VARCHAR(100) NOT NULL,
    consent_status VARCHAR(50) NOT NULL DEFAULT 'granted',
    consent_timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Medical Cases
CREATE TABLE IF NOT EXISTS medical_cases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    case_number VARCHAR(100) NOT NULL UNIQUE,
    patient_contact_id UUID REFERENCES patient_contacts(id),
    specialty VARCHAR(100) NOT NULL DEFAULT 'fertility_ivf', -- fertility_ivf, revision_orthopedics
    stage VARCHAR(100) NOT NULL DEFAULT 'intake', -- intake, extraction, review, quotes, brief, comms, journey, completed
    assigned_coordinator_id VARCHAR(255),
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Case Documents (Confidential Records)
CREATE TABLE IF NOT EXISTS case_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES medical_cases(id) ON DELETE CASCADE,
    document_type VARCHAR(100) NOT NULL, -- medical_report, imaging_report, prescription, quote_pdf, passport
    file_path VARCHAR(500) NOT NULL,
    access_class VARCHAR(50) NOT NULL DEFAULT 'confidential_health',
    uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Document Extractions
CREATE TABLE IF NOT EXISTS document_extractions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES case_documents(id) ON DELETE CASCADE,
    schema_type VARCHAR(100) NOT NULL,
    extracted_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    confidence_scores JSONB DEFAULT '{}'::jsonb,
    page_citations JSONB DEFAULT '[]'::jsonb,
    review_status VARCHAR(50) NOT NULL DEFAULT 'pending_review', -- pending_review, approved, corrected
    reviewed_by VARCHAR(255),
    reviewed_at TIMESTAMP WITH TIME ZONE
);

-- Provider Facilities (Vetted Hospitals/Clinics)
CREATE TABLE IF NOT EXISTS provider_facilities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    city VARCHAR(100) NOT NULL,
    specialties JSONB NOT NULL DEFAULT '["fertility_ivf"]'::jsonb,
    accreditation_evidence JSONB DEFAULT '[]'::jsonb,
    verification_status VARCHAR(50) NOT NULL DEFAULT 'independently_verified',
    last_verified_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Medical Quotes
CREATE TABLE IF NOT EXISTS medical_quotes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES medical_cases(id) ON DELETE CASCADE,
    provider_id UUID REFERENCES provider_facilities(id),
    raw_amount DOUBLE PRECISION NOT NULL,
    currency VARCHAR(10) NOT NULL DEFAULT 'USD',
    validity_date DATE,
    review_status VARCHAR(50) NOT NULL DEFAULT 'pending_approval'
);

-- Quote Line Items (Normalized Taxonomy)
CREATE TABLE IF NOT EXISTS quote_line_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quote_id UUID NOT NULL REFERENCES medical_quotes(id) ON DELETE CASCADE,
    canonical_category VARCHAR(100) NOT NULL, -- consultation, stimulation_meds, retrieval_procedure, embryology, facility_charges, exclusions
    raw_label VARCHAR(255) NOT NULL,
    amount DOUBLE PRECISION NOT NULL,
    is_included BOOLEAN DEFAULT TRUE,
    is_exclusion BOOLEAN DEFAULT FALSE,
    notes TEXT
);

-- Communication Drafts (Coordinator Review Queue)
CREATE TABLE IF NOT EXISTS communication_drafts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES medical_cases(id) ON DELETE CASCADE,
    recipient_email VARCHAR(255) NOT NULL,
    subject VARCHAR(255) NOT NULL,
    body_text TEXT NOT NULL,
    drafted_by_agent VARCHAR(100) NOT NULL DEFAULT 'CustomerOutreachAgent',
    status VARCHAR(50) NOT NULL DEFAULT 'pending_approval', -- pending_approval, approved, rejected, sent
    reviewed_by VARCHAR(255),
    reviewed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================================================
-- Row-Level Security (RLS) Policies
-- =============================================================================

ALTER TABLE patient_contacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE medical_cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE provider_facilities ENABLE ROW LEVEL SECURITY;

CREATE POLICY patient_contacts_isolation ON patient_contacts
    FOR ALL USING (organization_id = current_organization_id());

CREATE POLICY medical_cases_isolation ON medical_cases
    FOR ALL USING (organization_id = current_organization_id());

CREATE POLICY provider_facilities_isolation ON provider_facilities
    FOR ALL USING (organization_id = current_organization_id());
