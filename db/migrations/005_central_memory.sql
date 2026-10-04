-- =============================================================================
-- Migration 005: Meeting Intelligence — Central Memory Models
-- Adds relationship_contacts, relationship_conversations, and relationship_memory_items
-- =============================================================================

CREATE TABLE IF NOT EXISTS relationship_contacts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    name            VARCHAR(255) NOT NULL,
    normalized_name VARCHAR(255) NOT NULL,
    role            VARCHAR(255),
    company         VARCHAR(255),
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uq_relationship_contacts_org_normalized_name UNIQUE (organization_id, normalized_name)
);

CREATE INDEX IF NOT EXISTS idx_relationship_contacts_org ON relationship_contacts(organization_id);
CREATE INDEX IF NOT EXISTS idx_relationship_contacts_norm_name ON relationship_contacts(normalized_name);

CREATE TABLE IF NOT EXISTS relationship_conversations (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id      UUID NOT NULL,
    contact_id           UUID NOT NULL REFERENCES relationship_contacts(id) ON DELETE CASCADE,
    workflow_instance_id UUID NOT NULL,
    title                VARCHAR(255) NOT NULL,
    conversation_type    VARCHAR(100) NOT NULL DEFAULT 'meeting',
    conversation_date    VARCHAR(50),
    detected_language    VARCHAR(20) NOT NULL DEFAULT 'en',
    transcript           TEXT NOT NULL,
    summary              TEXT,
    structured_memory    JSONB NOT NULL DEFAULT '{}',
    created_at           TIMESTAMPTZ DEFAULT now(),
    updated_at           TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uq_relationship_conv_org_instance UNIQUE (organization_id, workflow_instance_id)
);

CREATE INDEX IF NOT EXISTS idx_relationship_conv_org ON relationship_conversations(organization_id);
CREATE INDEX IF NOT EXISTS idx_relationship_conv_contact ON relationship_conversations(contact_id);
CREATE INDEX IF NOT EXISTS idx_relationship_conv_instance ON relationship_conversations(workflow_instance_id);

CREATE TABLE IF NOT EXISTS relationship_memory_items (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id      UUID NOT NULL,
    contact_id           UUID NOT NULL REFERENCES relationship_contacts(id) ON DELETE CASCADE,
    conversation_id      UUID NOT NULL REFERENCES relationship_conversations(id) ON DELETE CASCADE,
    workflow_instance_id UUID NOT NULL,
    category             VARCHAR(50) NOT NULL,
    content              TEXT NOT NULL,
    details              JSONB NOT NULL DEFAULT '{}',
    source_date          VARCHAR(50),
    is_ai_generated      BOOLEAN NOT NULL DEFAULT false,
    created_at           TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_relationship_mem_org ON relationship_memory_items(organization_id);
CREATE INDEX IF NOT EXISTS idx_relationship_mem_contact ON relationship_memory_items(contact_id);
CREATE INDEX IF NOT EXISTS idx_relationship_mem_conv ON relationship_memory_items(conversation_id);
CREATE INDEX IF NOT EXISTS idx_relationship_mem_category ON relationship_memory_items(category);
