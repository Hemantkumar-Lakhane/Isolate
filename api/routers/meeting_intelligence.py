"""
api/routers/meeting_intelligence.py
===================================
Backend endpoints for SMBFlow Meeting Intelligence & Follow-up workflow.

Phase 1 (Node 1 — Conversation Capture):
- Secure audio file upload & validation (.mp3, .wav, .m4a, .webm, max 50MB)
- Audio preservation in uploads/audio/
- Conversation capture ingestion & workflow run record creation
- Explicit pending status for unimplemented Nodes 2–5
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiofiles
import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import TokenData, require_any_auth
from api.dependencies import get_db
from core.llm_router import LLMRouter, LLMMessage
from db.models.core import (
    AgentRunRecord,
    ApprovalItem,
    AuditEvent,
    Organization,
    RelationshipContact,
    RelationshipConversation,
    RelationshipMemoryItem,
    WorkflowInstance,
)

log = structlog.get_logger()
router = APIRouter(prefix="/api/v1/workflows/meeting-intelligence", tags=["Meeting Intelligence & Follow-up"])

# ── Allowed Audio Configurations ─────────────────────────────────────────────
ALLOWED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".webm"}
MAX_AUDIO_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
STORAGE_DIR = Path("uploads/audio")

DANGEROUS_EXTENSIONS = {
    ".exe", ".bat", ".cmd", ".sh", ".php", ".py", ".js", ".dll",
    ".scr", ".msi", ".vbs", ".ps1", ".jar", ".com", ".pif", ".hta",
}


# ── Request / Response Schemas ────────────────────────────────────────────────

class AudioUploadResponse(BaseModel):
    file_id: str
    filename: str
    content_type: str
    size_bytes: int
    stored_path: str
    message: str = "Audio uploaded and preserved successfully."


class AudioReference(BaseModel):
    file_id: Optional[str] = None
    filename: str
    size_bytes: Optional[int] = None
    content_type: Optional[str] = None
    stored_path: Optional[str] = None


class ConversationCaptureRequest(BaseModel):
    conversation_title: str = Field(..., min_length=1, description="Title or topic of the conversation")
    contact_name: str = Field(..., min_length=1, description="Primary contact or attendee name")
    conversation_type: str = Field(..., description="Online Meeting, Phone Call, or In-Person Meeting")
    recording: Dict[str, Any] = Field(..., description="Audio upload reference data")
    language: str = Field(default="Auto Detect", description="Spoken language")
    conversation_date: str = Field(..., description="Date of the conversation (YYYY-MM-DD)")


class PipelineNodeStatus(BaseModel):
    id: str
    title: str
    status: str  # "completed" | "pending" | "failed"
    implemented: bool
    note: str


class ConversationCaptureResponse(BaseModel):
    instance_id: str
    workflow_name: str = "meeting_intelligence_followup"
    status: str = "capture_completed"
    current_node: str = "n1"
    nodes: List[PipelineNodeStatus]
    conversation_data: Dict[str, Any]
    message: str


# ── Node 2: Process Conversation Schemas ──────────────────────────────────────

class PersonExtraction(BaseModel):
    name: str = Field(..., description="Full Name of participant or mentioned entity")
    facts: List[str] = Field(default_factory=list, description="Factual attributes learned about this person")
    interests: List[str] = Field(default_factory=list, description="Topics, products, or subjects this person showed interest in")
    needs: List[str] = Field(default_factory=list, description="Explicit problems, pain points, or requirements")
    opportunities: List[str] = Field(default_factory=list, description="Business or collaboration opportunities identified")


class CommitmentExtraction(BaseModel):
    owner: str = Field(..., description="Speaker or participant who explicitly committed/promised")
    commitment: str = Field(..., description="The exact commitment or promise agreed")
    due_date: Optional[str] = Field(default=None, description="ISO YYYY-MM-DD or null if undetermined")


class SuggestedActionExtraction(BaseModel):
    action: str = Field(..., description="Recommended follow-up action (AI suggestion, NOT an agreed promise)")
    reason: str = Field(..., description="Strategic reason or rationale for the suggestion")


class StructuredExtraction(BaseModel):
    summary: str = Field(..., description="Executive summary of the conversation")
    people: List[PersonExtraction] = Field(default_factory=list)
    commitments: List[CommitmentExtraction] = Field(default_factory=list)
    suggested_actions: List[SuggestedActionExtraction] = Field(default_factory=list)
    open_questions: List[str] = Field(default_factory=list)


class ProcessConversationRequest(BaseModel):
    instance_id: str = Field(..., description="WorkflowInstance ID to process")


class ProcessConversationResponse(BaseModel):
    instance_id: str
    workflow_name: str = "meeting_intelligence_followup"
    status: str  # "completed" | "failed"
    current_node: str = "n2"
    transcript_text: str
    detected_language: str
    transcription_status: str  # "completed" | "failed"
    extraction: Optional[StructuredExtraction] = None
    nodes: List[PipelineNodeStatus]
    summary_text: Optional[str] = None
    model_used: Optional[str] = None
    cost_usd: float = 0.0
    duration_ms: int = 0
    message: str
    error_message: Optional[str] = None


# ── Node 3: Central Memory Schemas ───────────────────────────────────────────

class ContactMemoryItem(BaseModel):
    id: str
    category: str
    content: str
    details: Dict[str, Any] = Field(default_factory=dict)
    source_date: Optional[str] = None
    source_conversation_id: str
    source_conversation_title: Optional[str] = None
    source_workflow_instance_id: str
    is_ai_generated: bool = False


class ConversationHistoryItem(BaseModel):
    conversation_id: str
    workflow_instance_id: str
    title: str
    conversation_type: str
    conversation_date: Optional[str] = None
    detected_language: str
    summary: Optional[str] = None
    created_at: Optional[str] = None


class ContactMemorySnapshot(BaseModel):
    contact_id: str
    contact_name: str
    contact_role: Optional[str] = None
    organization_id: str
    total_conversations: int
    conversations: List[ConversationHistoryItem] = Field(default_factory=list)
    latest_conversation_title: str
    latest_conversation_date: Optional[str] = None
    latest_conversation_summary: Optional[str] = None
    facts: List[ContactMemoryItem] = Field(default_factory=list)
    interests: List[ContactMemoryItem] = Field(default_factory=list)
    needs: List[ContactMemoryItem] = Field(default_factory=list)
    opportunities: List[ContactMemoryItem] = Field(default_factory=list)
    commitments: List[ContactMemoryItem] = Field(default_factory=list)
    suggested_actions: List[ContactMemoryItem] = Field(default_factory=list)
    open_questions: List[ContactMemoryItem] = Field(default_factory=list)
    source_reference: Dict[str, Any] = Field(default_factory=dict)


class CentralMemoryRequest(BaseModel):
    instance_id: str = Field(..., description="WorkflowInstance ID to process for Central Memory")


class CentralMemoryResponse(BaseModel):
    instance_id: str
    workflow_name: str = "meeting_intelligence_followup"
    status: str = "completed"
    current_node: str = "n3"
    contact_id: str
    conversation_id: str
    memory: ContactMemorySnapshot
    nodes: List[PipelineNodeStatus]
    message: str
    idempotent_reused: bool = False


# ── Node 4: Action Generator Schemas ─────────────────────────────────────────

class GeneratedActionItem(BaseModel):
    id: str
    approval_id: Optional[str] = None
    action_type: str  # "our_commitment" | "contact_commitment" | "ai_suggestion"
    action: str
    owner_type: str   # "internal" | "contact" | "unknown"
    owner_display: str # "You / Internal" | contact_name | "Unassigned / Unknown"
    owner: Optional[str] = None
    due_date: Optional[str] = None
    due_date_display: str
    status: str       # "pending" | "waiting" | "suggested" | "completed" | "dismissed"
    reason: Optional[str] = None
    source: str = "current_conversation"
    source_title: Optional[str] = None
    source_date: Optional[str] = None
    conversation_id: Optional[str] = None
    workflow_instance_id: Optional[str] = None
    provenance: Dict[str, Any] = Field(default_factory=dict)


class GeneratedOpenQuestionItem(BaseModel):
    id: str
    question: str
    source_date: Optional[str] = None
    source_title: Optional[str] = None
    workflow_instance_id: Optional[str] = None
    conversation_id: Optional[str] = None
    provenance: Dict[str, Any] = Field(default_factory=dict)


class ActionGeneratorRequest(BaseModel):
    instance_id: str = Field(..., description="WorkflowInstance ID to generate actions for")


class ActionGeneratorResponse(BaseModel):
    instance_id: str
    workflow_name: str = "meeting_intelligence_followup"
    status: str = "completed"
    current_node: str = "n4"
    contact_id: str
    contact_name: str
    our_commitments: List[GeneratedActionItem] = Field(default_factory=list)
    contact_commitments: List[GeneratedActionItem] = Field(default_factory=list)
    ai_suggestions: List[GeneratedActionItem] = Field(default_factory=list)
    open_questions: List[GeneratedOpenQuestionItem] = Field(default_factory=list)
    historical_commitments: List[GeneratedActionItem] = Field(default_factory=list)
    nodes: List[PipelineNodeStatus] = Field(default_factory=list)
    message: str = "Action items generated and persisted successfully."
    idempotent_reused: bool = False


class FollowupDraftItem(BaseModel):
    id: str = Field(..., description="ApprovalItem ID in PostgreSQL")
    approval_id: Optional[str] = None
    instance_id: str
    review_type: str = "followup_email_draft"
    status: str = Field("awaiting_review", description="awaiting_review | approved | snoozed | discarded")
    subject: str
    body: str
    recipient_name: str
    recipient_email: Optional[str] = None
    recipient_email_available: bool = False
    contact_id: Optional[str] = None
    conversation_title: Optional[str] = None
    our_commitments_count: int = 0
    contact_commitments_count: int = 0
    ai_suggestions_count: int = 0
    open_questions_count: int = 0
    original_generated_subject: Optional[str] = None
    original_generated_body: Optional[str] = None
    original_subject: Optional[str] = None
    original_body: Optional[str] = None
    snoozed_until: Optional[str] = None
    snooze_reason: Optional[str] = None
    snoozed_reason: Optional[str] = None
    model_used: Optional[str] = None
    decided_by: Optional[str] = None
    decided_at: Optional[str] = None
    created_at: Optional[str] = None
    provenance: Dict[str, Any] = Field(default_factory=dict)


class FollowupDraftRequest(BaseModel):
    instance_id: str = Field(..., description="WorkflowInstance ID to generate follow-up draft for")


class FollowupDraftResponse(BaseModel):
    instance_id: str
    workflow_name: str = "meeting_intelligence_followup"
    status: str = "awaiting_review"
    current_node: str = "n5"
    draft: FollowupDraftItem
    nodes: List[PipelineNodeStatus] = Field(default_factory=list)
    message: str = "Follow-up email draft generated and awaiting human review."
    idempotent_reused: bool = False


class FollowupDraftActionRequest(BaseModel):
    action: str = Field(..., description="approve | edit | snooze | discard")
    subject: Optional[str] = Field(None, description="Updated subject (for edit action)")
    body: Optional[str] = Field(None, description="Updated body (for edit action)")
    snoozed_until: Optional[str] = Field(None, description="ISO timestamp or reminder label (for snooze action)")
    snooze_until: Optional[str] = Field(None, description="Alias for snoozed_until")
    snooze_reason: Optional[str] = Field(None, description="Reason for snoozing (for snooze action)")
    snoozed_reason: Optional[str] = Field(None, description="Alias for snooze_reason")
    notes: Optional[str] = Field(None, description="Review notes")


class FollowupDraftActionResponse(BaseModel):
    instance_id: str
    draft: FollowupDraftItem
    status: str = "awaiting_review"
    action: str
    message: str
    nodes: List[PipelineNodeStatus] = Field(default_factory=list)


class WorkflowRunDetailResponse(BaseModel):
    instance_id: str
    workflow_name: str = "meeting_intelligence_followup"
    status: str
    current_node: str
    conversation_data: Dict[str, Any]
    transcript_text: Optional[str] = None
    detected_language: Optional[str] = None
    transcription_status: Optional[str] = None
    extraction: Optional[StructuredExtraction] = None
    central_memory: Optional[ContactMemorySnapshot] = None
    actions: Optional[ActionGeneratorResponse] = None
    followup_draft: Optional[FollowupDraftItem] = None
    nodes: List[PipelineNodeStatus]
    model_used: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


# ── Helper Functions ──────────────────────────────────────────────────────────

async def _resolve_org_uuid(current_user: TokenData, db: AsyncSession) -> uuid.UUID:
    """Resolve the organization UUID from user token or find the active org."""
    org_id_str = getattr(current_user, "organization_id", None) or getattr(current_user, "tenant_id", None)
    if org_id_str:
        try:
            return uuid.UUID(str(org_id_str))
        except (ValueError, TypeError):
            pass

    stmt = select(Organization).where(Organization.active == True).limit(1)
    res = await db.execute(stmt)
    org = res.scalars().first()
    if org:
        return org.id

    return uuid.uuid4()


def _sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent directory traversal and remove dangerous characters."""
    base = os.path.basename(filename or "recording.mp3")
    clean = re.sub(r'[^a-zA-Z0-9_.-]', '_', base)
    return clean or "recording.mp3"


def _format_due_date_display(due_date: Optional[str]) -> str:
    """Format due date string for display (e.g. '2026-10-02' -> 'Oct 2, 2026'). If null/empty returns 'No due date'."""
    if not due_date or str(due_date).strip().lower() in ("null", "none", ""):
        return "No due date"
    clean_date = str(due_date).strip()
    try:
        dt = datetime.strptime(clean_date[:10], "%Y-%m-%d")
        return dt.strftime("%b %d, %Y").replace(" 0", " ")
    except Exception:
        return clean_date


def _classify_commitment_owner(
    owner_raw: Optional[str],
    contact_name: str,
    action: str = "",
) -> tuple[str, str]:
    """
    Deterministically classify commitment owner into:
    - ('internal', 'You / Internal') for SMB user/speaker side
    - ('contact', contact_name) for external contact commitments
    - ('unknown', 'Unassigned / Unknown' or owner_raw) for uncertain attribution
    """
    c_name = (contact_name or "").strip()
    c_name_norm = c_name.lower()
    c_tokens = set(re.findall(r'[a-z0-9]+', c_name_norm))

    raw_val = (owner_raw or "").strip()
    o_norm = raw_val.lower()
    o_tokens = set(re.findall(r'[a-z0-9]+', o_norm))

    # 1. Check if owner indicates the external contact
    if o_norm in (c_name_norm, "contact", "client", "customer", "partner", "prospect", "attendee", "lead"):
        return "contact", c_name

    # Check if contact tokens overlap with owner tokens (e.g. "Rahul" in "Rahul Sharma")
    if c_tokens and (c_tokens.intersection(o_tokens) or any(t in o_norm for t in c_tokens if len(t) > 2)):
        return "contact", c_name

    # 2. Check if owner indicates the internal SMB user / speaker side
    internal_keywords = {
        "speaker", "speaker 1", "speaker 2", "me", "i", "myself", "us", "we",
        "self", "user", "internal", "host", "agent", "my side", "our side",
        "you", "smb", "smbflow", "founder", "sales rep", "rep"
    }
    if o_norm in internal_keywords or o_norm.startswith("speaker"):
        return "internal", "You / Internal"

    # 3. Uncertain or empty attribution
    if not o_norm:
        return "unknown", "Unassigned / Unknown"

    uncertain_keywords = {"both", "team", "all", "unknown", "tbd", "unassigned", "anyone", "someone", "party"}
    if o_norm in uncertain_keywords:
        return "unknown", "Unassigned / Unknown"

    # If it's another person's name not matching contact, keep it as unknown attribution
    return "unknown", raw_val


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/upload-audio", response_model=AudioUploadResponse)
async def upload_audio_recording(
    file: UploadFile = File(...),
    current_user: TokenData = Depends(require_any_auth),
):
    """
    Upload and securely preserve an audio recording for Meeting Intelligence.
    Validates file extension (.mp3, .wav, .m4a, .webm) and maximum size (50MB).
    Does NOT transcribe or send audio to an LLM.
    """
    raw_filename = file.filename or ""
    sanitized_filename = _sanitize_filename(raw_filename)
    _, ext = os.path.splitext(sanitized_filename.lower())

    # 1. Reject dangerous executable/script extensions
    if ext in DANGEROUS_EXTENSIONS:
        log.warning("Audio upload rejected: dangerous extension", filename=raw_filename, ext=ext)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Security rejection: file extension '{ext}' is not permitted."
        )

    # 2. Enforce allowed audio extensions
    if ext not in ALLOWED_AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type '{ext}'. Supported audio formats: .mp3, .wav, .m4a, .webm"
        )

    # 3. Read content and validate size
    try:
        content = await file.read()
    except Exception as read_err:
        log.error("Failed to read uploaded audio file", error=str(read_err))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to read uploaded audio file."
        )

    size_bytes = len(content)
    if size_bytes == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty audio recording received (0 bytes)."
        )

    if size_bytes > MAX_AUDIO_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Audio file exceeds maximum allowed limit (50 MB). Received: {round(size_bytes / (1024 * 1024), 2)} MB."
        )

    # 4. Check magic bytes to reject executables masquerading as audio
    if content.startswith(b"MZ") or content.startswith(b"\x7fELF"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File content does not match a valid audio format."
        )

    # 5. Persist to disk in uploads/audio/
    file_id = str(uuid.uuid4())[:12]
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    stored_filename = f"{file_id}_{sanitized_filename}"
    target_path = STORAGE_DIR / stored_filename

    # Ensure path stays within STORAGE_DIR
    resolved_path = target_path.resolve()
    if not str(resolved_path).startswith(str(STORAGE_DIR.resolve())):
        raise HTTPException(status_code=400, detail="Invalid storage path resolution.")

    try:
        async with aiofiles.open(target_path, "wb") as f:
            await f.write(content)
    except Exception as write_err:
        log.error("Failed to write audio file to storage", error=str(write_err), path=str(target_path))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to preserve audio file on storage."
        )

    content_type = file.content_type or f"audio/{ext.lstrip('.')}"

    log.info(
        "Audio recording preserved for Meeting Intelligence",
        file_id=file_id,
        filename=sanitized_filename,
        size_bytes=size_bytes,
        stored_path=str(target_path),
    )

    return AudioUploadResponse(
        file_id=file_id,
        filename=sanitized_filename,
        content_type=content_type,
        size_bytes=size_bytes,
        stored_path=str(target_path).replace("\\", "/"),
        message="Audio uploaded and preserved successfully.",
    )


@router.post("/capture", response_model=ConversationCaptureResponse)
async def capture_conversation(
    req: ConversationCaptureRequest,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_any_auth),
):
    """
    Execute Node 1: Conversation Capture for Meeting Intelligence & Follow-up.
    - Validates all 6 required fields.
    - Preserves input metadata and audio reference for the workflow run in PostgreSQL.
    - Marks Node 1 (Conversation Capture) as completed.
    - Marks Nodes 2–5 as pending / not implemented.
    - Does NOT transcribe, generate fake summaries, or execute later nodes.
    """
    # 1. Validation of required inputs
    title = req.conversation_title.strip()
    contact = req.contact_name.strip()
    conv_type = req.conversation_type.strip()
    lang = req.language.strip() or "Auto Detect"
    conv_date = req.conversation_date.strip()
    recording = req.recording

    if not title:
        raise HTTPException(status_code=400, detail="Conversation Title is required.")
    if not contact:
        raise HTTPException(status_code=400, detail="Contact Name is required.")
    if conv_type not in ["Online Meeting", "Phone Call", "In-Person Meeting"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid conversation type '{conv_type}'. Must be 'Online Meeting', 'Phone Call', or 'In-Person Meeting'."
        )
    if not recording or not isinstance(recording, dict) or not (recording.get("filename") or recording.get("file_id")):
        raise HTTPException(status_code=400, detail="A valid audio recording is required.")
    if not conv_date:
        raise HTTPException(status_code=400, detail="Conversation Date is required.")

    valid_languages = ["Auto Detect", "English", "Spanish", "Mixed English / Spanish"]
    if lang not in valid_languages:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid language '{lang}'. Allowed options: {', '.join(valid_languages)}."
        )

    # 2. Resolve organization UUID
    org_uuid = await _resolve_org_uuid(current_user, db)

    # 3. Create canonical WorkflowInstance
    instance_id = uuid.uuid4()
    captured_data = {
        "conversation_title": title,
        "contact_name": contact,
        "conversation_type": conv_type,
        "recording": {
            "file_id": recording.get("file_id"),
            "filename": recording.get("filename"),
            "size_bytes": recording.get("size_bytes"),
            "content_type": recording.get("content_type"),
            "stored_path": recording.get("stored_path"),
        },
        "language": lang,
        "conversation_date": conv_date,
        "captured_at": datetime.utcnow().isoformat(),
    }

    workflow_inst = WorkflowInstance(
        id=instance_id,
        organization_id=org_uuid,
        workflow_name="meeting_intelligence_followup",
        status="capture_completed",
        current_node="n1",
        trigger_payload={
            "source": "manual_conversation_capture",
            **captured_data,
        },
        context={
            "conversation_capture": captured_data,
            "implemented_nodes": ["n1"],
            "pending_nodes": ["n2", "n3", "n4", "n5"],
        },
        started_at=datetime.utcnow(),
    )
    db.add(workflow_inst)

    # 4. Create AgentRunRecord for Node 1 (Conversation Capture)
    node1_run = AgentRunRecord(
        id=uuid.uuid4(),
        instance_id=instance_id,
        node_id="n1",
        agent_capability="conversation_capture",
        status="completed",
        duration_ms=45,
        tools_used=["audio_storage"],
        completed_at=datetime.utcnow(),
    )
    db.add(node1_run)

    # 5. Create AuditEvent for provenance
    actor = getattr(current_user, "email", None) or getattr(current_user, "user_id", "user")
    audit_evt = AuditEvent(
        id=uuid.uuid4(),
        organization_id=org_uuid,
        actor_id=str(actor),
        action="conversation_captured",
        entity_type="workflow_instance",
        entity_id=str(instance_id),
        metadata_={
            "workflow": "meeting_intelligence_followup",
            "conversation_title": title,
            "contact_name": contact,
            "audio_filename": recording.get("filename"),
        },
    )
    db.add(audit_evt)

    await db.commit()
    await db.refresh(workflow_inst)

    log.info(
        "Conversation captured successfully",
        instance_id=str(instance_id),
        title=title,
        contact=contact,
        audio=recording.get("filename"),
    )

    nodes_status = [
        PipelineNodeStatus(
            id="n1",
            title="Conversation Capture",
            status="completed",
            implemented=True,
            note="Audio recording and metadata preserved successfully for this run.",
        ),
        PipelineNodeStatus(
            id="n2",
            title="Process Conversation",
            status="pending",
            implemented=True,
            note="Transcription & Entity Extraction (Gemini / Whisper).",
        ),
        PipelineNodeStatus(
            id="n3",
            title="Central Memory",
            status="pending",
            implemented=True,
            note="Vector Knowledge & Structured Memory Store (PostgreSQL).",
        ),
        PipelineNodeStatus(
            id="n4",
            title="Action Generator",
            status="pending",
            implemented=True,
            note="Task & Decision Synthesis (Claude / Action Center).",
        ),
        PipelineNodeStatus(
            id="n5",
            title="Follow-up & Meeting Prep",
            status="pending",
            implemented=True,
            note="Dispatch & Briefing Sync (Email Drafts & Calendar Sync).",
        ),
    ]

    return ConversationCaptureResponse(
        instance_id=str(instance_id),
        workflow_name="meeting_intelligence_followup",
        status="capture_completed",
        current_node="n1",
        nodes=nodes_status,
        conversation_data=captured_data,
        message="Conversation Capture executed successfully. Audio recording and metadata preserved for the run.",
    )


# ── Node 2: Transcription & Extraction Services ───────────────────────────────

async def transcribe_audio_file(
    file_path: Path,
    language_hint: Optional[str] = None,
) -> tuple[str, str, str, float]:
    """
    Transcribe audio using Groq Whisper (whisper-large-v3) with fallback to OpenAI Whisper (whisper-1).
    Returns: (transcript_text, detected_language, provider_model, duration_seconds)
    Raises: HTTPException if file is missing, empty, or transcription fails.
    Never fabricates a mock transcript.
    """
    if not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audio file '{file_path.name}' does not exist on disk.",
        )

    try:
        with open(file_path, "rb") as f:
            audio_bytes = f.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read audio file from disk: {str(e)}",
        )

    if not audio_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audio recording file is empty (0 bytes).",
        )

    # Map language preferences
    lang_code = None
    if language_hint:
        normalized = language_hint.strip().lower()
        if "english" in normalized and "spanish" not in normalized:
            lang_code = "en"
        elif "spanish" in normalized and "english" not in normalized:
            lang_code = "es"
        # "Auto Detect" or "Mixed English / Spanish" leaves lang_code as None for automatic detection

    ext = file_path.suffix.lower()
    content_type_map = {
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".m4a": "audio/mp4",
        ".webm": "audio/webm",
    }
    content_type = content_type_map.get(ext, "audio/mpeg")

    start_time = time.time()
    errors: List[str] = []

    # 1. Primary: Groq Whisper (whisper-large-v3)
    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key:
        try:
            headers = {"Authorization": f"Bearer {groq_key}"}
            files = {"file": (file_path.name, audio_bytes, content_type)}
            data = {"model": "whisper-large-v3", "response_format": "verbose_json"}
            if lang_code:
                data["language"] = lang_code

            async with httpx.AsyncClient(timeout=45.0) as client:
                resp = await client.post(
                    "https://api.groq.com/openai/v1/audio/transcriptions",
                    headers=headers,
                    files=files,
                    data=data,
                )
                if resp.status_code == 200:
                    res_json = resp.json()
                    transcript = res_json.get("text", "").strip()
                    if transcript:
                        detected_lang = res_json.get("language") or language_hint or "en"
                        duration_sec = round(time.time() - start_time, 2)
                        return transcript, detected_lang, "groq_whisper-large-v3", duration_sec
                else:
                    errors.append(f"Groq API {resp.status_code}: {resp.text[:200]}")
        except Exception as groq_err:
            log.warning("Groq Whisper transcription failed, attempting fallback", error=str(groq_err))
            errors.append(f"Groq error: {str(groq_err)}")

    # 2. Secondary: OpenAI Whisper (whisper-1)
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        try:
            headers = {"Authorization": f"Bearer {openai_key}"}
            files = {"file": (file_path.name, audio_bytes, content_type)}
            data = {"model": "whisper-1", "response_format": "verbose_json"}
            if lang_code:
                data["language"] = lang_code

            async with httpx.AsyncClient(timeout=45.0) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers=headers,
                    files=files,
                    data=data,
                )
                if resp.status_code == 200:
                    res_json = resp.json()
                    transcript = res_json.get("text", "").strip()
                    if transcript:
                        detected_lang = res_json.get("language") or language_hint or "en"
                        duration_sec = round(time.time() - start_time, 2)
                        return transcript, detected_lang, "openai_whisper-1", duration_sec
                else:
                    errors.append(f"OpenAI API {resp.status_code}: {resp.text[:200]}")
        except Exception as openai_err:
            log.warning("OpenAI Whisper transcription failed", error=str(openai_err))
            errors.append(f"OpenAI error: {str(openai_err)}")

    error_summary = "; ".join(errors) if errors else "No transcription provider credentials available (GROQ_API_KEY / OPENAI_API_KEY)."
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"Transcription failed: {error_summary}",
    )


EXTRACTION_SYSTEM_PROMPT = """You are an expert conversation intelligence analyst for SMBFlow.
Your task is to analyze a professional conversation transcript and extract structured intelligence in STRICT JSON format.

RULES:
1. "commitments": Contain ONLY explicit promises and agreements made during the conversation by the participants.
   - Example: "I will send the proposal by Friday" -> {"owner": "<speaker>", "commitment": "Send short proposal", "due_date": "2026-10-02"}
   - Do NOT include general ideas, suggestions, or advice in commitments.
2. "suggested_actions": Contain AI recommendations, strategic follow-ups, or best practices that were NOT explicitly promised.
   - Never confuse an agreed commitment with an AI suggested action.
3. "people": Extract key individuals mentioned or participating.
   - Include their facts, interests, needs, and opportunities mentioned in the conversation.
   - If contact_name is provided in context, use it accurately but do NOT force speaker attribution if ambiguous. Represent uncertainty rather than inventing false attribution.
4. "due_date": Use the provided Reference Calendar and Conversation Date to resolve relative phrases like "tomorrow", "Friday", "next week" to ISO "YYYY-MM-DD". If uncertain or not stated, set due_date to null. Never invent dates.
5. "open_questions": Unresolved questions or topics that require further clarification.
6. Output MUST be valid JSON matching the exact schema below without any extra markdown or explanation outside the JSON:

{
  "summary": "Concise executive summary of conversation",
  "people": [
    {
      "name": "Full Name",
      "facts": ["..."],
      "interests": ["..."],
      "needs": ["..."],
      "opportunities": ["..."]
    }
  ],
  "commitments": [
    {
      "owner": "Person name or Speaker",
      "commitment": "Action promised",
      "due_date": "YYYY-MM-DD or null"
    }
  ],
  "suggested_actions": [
    {
      "action": "Recommended next step",
      "reason": "Why this recommendation is valuable"
    }
  ],
  "open_questions": ["..."]
}
"""


async def extract_structured_intelligence(
    transcript: str,
    contact_name: str,
    conversation_date: str,
    conversation_type: str,
) -> tuple[StructuredExtraction, str, float, int, int]:
    """
    Extract structured intelligence from conversation transcript using LLMRouter.
    Returns: (StructuredExtraction, model_name, cost_usd, tokens_in, tokens_out)
    """
    try:
        ref_dt = datetime.strptime(conversation_date, "%Y-%m-%d")
        day_of_week = ref_dt.strftime("%A")
    except Exception:
        day_of_week = "Unknown"

    user_prompt = f"""REFERENCE CALENDAR:
- Conversation Date: {conversation_date} (Day of week: {day_of_week})
- Primary Contact: {contact_name}
- Conversation Type: {conversation_type}

TRANSCRIPT:
\"\"\"
{transcript}
\"\"\"

Extract structured intelligence following all rules and output strictly valid JSON."""

    messages = [
        LLMMessage(role="system", content=EXTRACTION_SYSTEM_PROMPT),
        LLMMessage(role="user", content=user_prompt),
    ]

    llm = LLMRouter()
    try:
        raw_resp, call_record = await llm.call(
            agent_name="reasoning_agent",
            messages=messages,
            tier_override="balanced",
        )
    except Exception as llm_err:
        log.error("LLMRouter failed during structured extraction", error=str(llm_err))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM extraction service unavailable: {str(llm_err)}",
        )

    # Clean markdown code fences if present
    cleaned = raw_resp.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    try:
        parsed_dict = json.loads(cleaned)
    except Exception as parse_err:
        log.warning("JSON parse failed on raw LLM output, attempting repair", error=str(parse_err))
        try:
            repair_messages = [
                LLMMessage(role="system", content="You fix invalid JSON strings so they conform strictly to valid JSON."),
                LLMMessage(role="user", content=f"Fix and return ONLY valid JSON without markdown fences:\n{cleaned}"),
            ]
            repaired_resp, _ = await llm.call(
                agent_name="mini",
                messages=repair_messages,
                tier_override="mini",
            )
            r_cleaned = repaired_resp.strip()
            if r_cleaned.startswith("```json"):
                r_cleaned = r_cleaned[7:]
            if r_cleaned.startswith("```"):
                r_cleaned = r_cleaned[3:]
            if r_cleaned.endswith("```"):
                r_cleaned = r_cleaned[:-3]
            parsed_dict = json.loads(r_cleaned.strip())
        except Exception as repair_err:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to parse structured output from AI model: {str(parse_err)}",
            )

    try:
        extraction = StructuredExtraction(**parsed_dict)
    except Exception as val_err:
        log.warning("Pydantic validation failed on structured extraction, applying safe normalization", error=str(val_err))
        people_raw = parsed_dict.get("people", [])
        people_list = []
        for p in (people_raw if isinstance(people_raw, list) else []):
            if isinstance(p, dict):
                people_list.append(PersonExtraction(
                    name=str(p.get("name") or contact_name),
                    facts=[str(x) for x in p.get("facts", []) if x],
                    interests=[str(x) for x in p.get("interests", []) if x],
                    needs=[str(x) for x in p.get("needs", []) if x],
                    opportunities=[str(x) for x in p.get("opportunities", []) if x],
                ))
        if not people_list and contact_name:
            people_list.append(PersonExtraction(name=contact_name))

        commitments_raw = parsed_dict.get("commitments", [])
        commitments_list = []
        for c in (commitments_raw if isinstance(commitments_raw, list) else []):
            if isinstance(c, dict) and c.get("commitment"):
                commitments_list.append(CommitmentExtraction(
                    owner=str(c.get("owner") or "Speaker"),
                    commitment=str(c.get("commitment")),
                    due_date=str(c.get("due_date")) if c.get("due_date") else None,
                ))

        actions_raw = parsed_dict.get("suggested_actions", [])
        actions_list = []
        for a in (actions_raw if isinstance(actions_raw, list) else []):
            if isinstance(a, dict) and a.get("action"):
                actions_list.append(SuggestedActionExtraction(
                    action=str(a.get("action")),
                    reason=str(a.get("reason") or "Identified as beneficial next step"),
                ))

        questions_raw = parsed_dict.get("open_questions", [])
        questions_list = [str(q) for q in (questions_raw if isinstance(questions_raw, list) else []) if q]

        extraction = StructuredExtraction(
            summary=str(parsed_dict.get("summary") or "Discussion notes extracted from conversation."),
            people=people_list,
            commitments=commitments_list,
            suggested_actions=actions_list,
            open_questions=questions_list,
        )

    model_name = getattr(call_record, "model", "claude-haiku-4-5")
    cost_usd = getattr(call_record, "cost_usd", 0.0)
    tokens_in = getattr(call_record, "tokens_in", 0)
    tokens_out = getattr(call_record, "tokens_out", 0)

    return extraction, model_name, cost_usd, tokens_in, tokens_out


# ── Node 2: Process Conversation Endpoint ─────────────────────────────────────

@router.post("/process-conversation", response_model=ProcessConversationResponse)
async def process_conversation(
    req: ProcessConversationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_any_auth),
):
    """
    Execute Node 2: Process Conversation for Meeting Intelligence & Follow-up.
    1. Loads the WorkflowInstance created by Node 1.
    2. Validates tenant and organization isolation.
    3. Retrieves the preserved audio recording.
    4. Transcribes audio using Groq Whisper (with OpenAI Whisper fallback).
    5. Extracts structured intelligence using LLMRouter (strict JSON schema).
    6. Persists transcript and structured extraction to the WorkflowInstance context.
    7. Records an AgentRunRecord for Node 2 (conversation_processing).
    8. Updates Node 1 and Node 2 as completed, keeping Nodes 3–5 strictly pending.
    """
    start_time = time.time()
    org_uuid = await _resolve_org_uuid(current_user, db)

    # 1. Parse instance UUID
    try:
        instance_uuid = uuid.UUID(req.instance_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid instance_id format.")

    # 2. Retrieve WorkflowInstance
    stmt = select(WorkflowInstance).where(WorkflowInstance.id == instance_uuid)
    res = await db.execute(stmt)
    workflow_inst = res.scalars().first()
    if not workflow_inst:
        raise HTTPException(status_code=404, detail="Workflow run instance not found.")

    # 3. Enforce tenant & organization isolation
    if workflow_inst.organization_id != org_uuid:
        log.warning(
            "Unauthorized access attempt to workflow run",
            instance_id=str(instance_uuid),
            user_org=str(org_uuid),
            instance_org=str(workflow_inst.organization_id),
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: workflow run belongs to another organization.",
        )

    # 4. Extract conversation parameters and audio reference
    context_data = workflow_inst.context or {}
    capture_data = context_data.get("conversation_capture") or workflow_inst.trigger_payload or {}
    recording_info = capture_data.get("recording") or {}

    contact_name = capture_data.get("contact_name") or "Primary Contact"
    conversation_date = capture_data.get("conversation_date") or datetime.utcnow().strftime("%Y-%m-%d")
    conversation_type = capture_data.get("conversation_type") or "Online Meeting"
    language_hint = capture_data.get("language") or "Auto Detect"

    stored_path_str = recording_info.get("stored_path")
    if not stored_path_str:
        # Mark failure on instance
        workflow_inst.status = "failed"
        fail_run = AgentRunRecord(
            id=uuid.uuid4(),
            instance_id=instance_uuid,
            node_id="n2",
            agent_capability="conversation_processing",
            status="failed",
            error="Missing audio recording reference in workflow instance.",
            completed_at=datetime.utcnow(),
        )
        db.add(fail_run)
        await db.commit()
        raise HTTPException(status_code=404, detail="No audio recording found for this workflow run.")

    audio_file_path = Path(stored_path_str)
    # Check directory boundary to prevent traversal
    resolved_audio_path = audio_file_path.resolve()
    if not str(resolved_audio_path).startswith(str(STORAGE_DIR.resolve())):
        workflow_inst.status = "failed"
        fail_run = AgentRunRecord(
            id=uuid.uuid4(),
            instance_id=instance_uuid,
            node_id="n2",
            agent_capability="conversation_processing",
            status="failed",
            error="Audio file path traversal violation.",
            completed_at=datetime.utcnow(),
        )
        db.add(fail_run)
        await db.commit()
        raise HTTPException(status_code=400, detail="Invalid audio file path.")

    if not audio_file_path.is_file():
        workflow_inst.status = "failed"
        fail_run = AgentRunRecord(
            id=uuid.uuid4(),
            instance_id=instance_uuid,
            node_id="n2",
            agent_capability="conversation_processing",
            status="failed",
            error=f"Audio file '{audio_file_path.name}' not found on disk.",
            completed_at=datetime.utcnow(),
        )
        db.add(fail_run)
        await db.commit()
        raise HTTPException(status_code=404, detail=f"Audio file '{audio_file_path.name}' not found on disk.")

    # 5. Transcription
    try:
        transcript_text, detected_lang, stt_provider, stt_duration = await transcribe_audio_file(
            file_path=audio_file_path,
            language_hint=language_hint,
        )
    except HTTPException as stt_http_err:
        workflow_inst.status = "failed"
        fail_run = AgentRunRecord(
            id=uuid.uuid4(),
            instance_id=instance_uuid,
            node_id="n2",
            agent_capability="conversation_processing",
            status="failed",
            error=stt_http_err.detail,
            completed_at=datetime.utcnow(),
        )
        db.add(fail_run)
        await db.commit()
        raise stt_http_err
    except Exception as stt_generic_err:
        workflow_inst.status = "failed"
        fail_run = AgentRunRecord(
            id=uuid.uuid4(),
            instance_id=instance_uuid,
            node_id="n2",
            agent_capability="conversation_processing",
            status="failed",
            error=str(stt_generic_err),
            completed_at=datetime.utcnow(),
        )
        db.add(fail_run)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Transcription failed: {str(stt_generic_err)}",
        )

    # 6. Structured Intelligence Extraction
    try:
        extraction, model_used, cost_usd, t_in, t_out = await extract_structured_intelligence(
            transcript=transcript_text,
            contact_name=contact_name,
            conversation_date=conversation_date,
            conversation_type=conversation_type,
        )
    except HTTPException as llm_http_err:
        workflow_inst.status = "failed"
        fail_run = AgentRunRecord(
            id=uuid.uuid4(),
            instance_id=instance_uuid,
            node_id="n2",
            agent_capability="conversation_processing",
            status="failed",
            error=llm_http_err.detail,
            completed_at=datetime.utcnow(),
        )
        db.add(fail_run)
        await db.commit()
        raise llm_http_err
    except Exception as llm_generic_err:
        workflow_inst.status = "failed"
        fail_run = AgentRunRecord(
            id=uuid.uuid4(),
            instance_id=instance_uuid,
            node_id="n2",
            agent_capability="conversation_processing",
            status="failed",
            error=str(llm_generic_err),
            completed_at=datetime.utcnow(),
        )
        db.add(fail_run)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Extraction failed: {str(llm_generic_err)}",
        )

    total_duration_ms = int((time.time() - start_time) * 1000)

    # 7. Update WorkflowInstance state & context
    workflow_inst.status = "processed"
    workflow_inst.current_node = "n2"
    workflow_inst.total_tokens_in = (workflow_inst.total_tokens_in or 0) + t_in
    workflow_inst.total_tokens_out = (workflow_inst.total_tokens_out or 0) + t_out
    workflow_inst.total_cost_usd = (workflow_inst.total_cost_usd or 0.0) + cost_usd

    updated_context = dict(context_data)
    updated_context["node2_process_conversation"] = {
        "status": "completed",
        "transcript_text": transcript_text,
        "detected_language": detected_lang,
        "transcription_status": "completed",
        "transcription_provider": stt_provider,
        "extraction": extraction.model_dump(),
        "model_used": model_used,
        "cost_usd": cost_usd,
        "duration_ms": total_duration_ms,
        "processed_at": datetime.utcnow().isoformat(),
    }
    updated_context["implemented_nodes"] = ["n1", "n2"]
    updated_context["pending_nodes"] = ["n3", "n4", "n5"]
    workflow_inst.context = updated_context

    # 8. Record AgentRunRecord for Node 2
    node2_run = AgentRunRecord(
        id=uuid.uuid4(),
        instance_id=instance_uuid,
        node_id="n2",
        agent_capability="conversation_processing",
        status="completed",
        tokens_in=t_in,
        tokens_out=t_out,
        cost_usd=cost_usd,
        model_used=model_used,
        duration_ms=total_duration_ms,
        tools_used=["transcription_whisper", "llm_router"],
        completed_at=datetime.utcnow(),
    )
    db.add(node2_run)

    # 9. Audit Event
    audit_evt = AuditEvent(
        id=uuid.uuid4(),
        organization_id=org_uuid,
        actor_id=str(getattr(current_user, "email", None) or getattr(current_user, "user_id", "system")),
        action="conversation_processed",
        entity_type="workflow_instance",
        entity_id=str(instance_uuid),
        metadata_={
            "workflow": "meeting_intelligence_followup",
            "transcript_length": len(transcript_text),
            "detected_language": detected_lang,
            "commitments_count": len(extraction.commitments),
            "suggested_actions_count": len(extraction.suggested_actions),
            "people_count": len(extraction.people),
            "model_used": model_used,
        },
    )
    db.add(audit_evt)

    await db.commit()
    await db.refresh(workflow_inst)

    log.info(
        "Conversation processing completed successfully",
        instance_id=str(instance_uuid),
        detected_language=detected_lang,
        commitments=len(extraction.commitments),
        suggested_actions=len(extraction.suggested_actions),
    )

    nodes_status = [
        PipelineNodeStatus(
            id="n1",
            title="Conversation Capture",
            status="completed",
            implemented=True,
            note="Audio recording and metadata preserved successfully.",
        ),
        PipelineNodeStatus(
            id="n2",
            title="Process Conversation",
            status="completed",
            implemented=True,
            note=f"Transcription ({detected_lang}) and structured extraction completed.",
        ),
        PipelineNodeStatus(
            id="n3",
            title="Central Memory",
            status="pending",
            implemented=True,
            note="Structured relationship memory and context index ready.",
        ),
        PipelineNodeStatus(
            id="n4",
            title="Action Generator",
            status="pending",
            implemented=True,
            note="Task & decision synthesis pipeline configured.",
        ),
        PipelineNodeStatus(
            id="n5",
            title="Follow-up & Meeting Prep",
            status="pending",
            implemented=True,
            note="Email drafts, calendar briefings, and action sync ready.",
        ),
    ]

    return ProcessConversationResponse(
        instance_id=str(instance_uuid),
        workflow_name="meeting_intelligence_followup",
        status="completed",
        current_node="n2",
        transcript_text=transcript_text,
        detected_language=detected_lang,
        transcription_status="completed",
        extraction=extraction,
        nodes=nodes_status,
        summary_text=extraction.summary,
        model_used=model_used,
        cost_usd=cost_usd,
        duration_ms=total_duration_ms,
        message="Conversation transcribed and structured intelligence extracted successfully.",
    )


# ── Node 3: Central Memory Helper Functions ───────────────────────────────────

async def _build_contact_memory_snapshot(
    contact: RelationshipContact,
    current_conv_id: Optional[uuid.UUID],
    org_uuid: uuid.UUID,
    db: AsyncSession,
    instance_uuid: Optional[uuid.UUID],
) -> ContactMemorySnapshot:
    """Build aggregated contact snapshot including conversation history and distinct memory categories."""
    stmt_convs = (
        select(RelationshipConversation)
        .where(
            RelationshipConversation.organization_id == org_uuid,
            RelationshipConversation.contact_id == contact.id,
        )
        .order_by(RelationshipConversation.created_at.desc())
    )
    res_convs = await db.execute(stmt_convs)
    convs = res_convs.scalars().all()

    conv_titles = {str(c.id): c.title for c in convs}
    history_items = [
        ConversationHistoryItem(
            conversation_id=str(c.id),
            workflow_instance_id=str(c.workflow_instance_id),
            title=c.title,
            conversation_type=c.conversation_type,
            conversation_date=c.conversation_date,
            detected_language=c.detected_language,
            summary=c.summary,
            created_at=c.created_at.isoformat() if c.created_at else None,
        )
        for c in convs
    ]

    latest_conv = convs[0] if convs else None

    stmt_items = (
        select(RelationshipMemoryItem)
        .where(
            RelationshipMemoryItem.organization_id == org_uuid,
            RelationshipMemoryItem.contact_id == contact.id,
        )
        .order_by(RelationshipMemoryItem.created_at.asc())
    )
    res_items = await db.execute(stmt_items)
    items = res_items.scalars().all()

    def _to_memory_item(item: RelationshipMemoryItem) -> ContactMemoryItem:
        return ContactMemoryItem(
            id=str(item.id),
            category=item.category,
            content=item.content,
            details=item.details or {},
            source_date=item.source_date,
            source_conversation_id=str(item.conversation_id),
            source_conversation_title=conv_titles.get(str(item.conversation_id), "Conversation"),
            source_workflow_instance_id=str(item.workflow_instance_id),
            is_ai_generated=item.is_ai_generated,
        )

    facts = [_to_memory_item(m) for m in items if m.category == "fact"]
    interests = [_to_memory_item(m) for m in items if m.category == "interest"]
    needs = [_to_memory_item(m) for m in items if m.category == "need"]
    opportunities = [_to_memory_item(m) for m in items if m.category == "opportunity"]
    commitments = [_to_memory_item(m) for m in items if m.category == "commitment"]
    suggested_actions = [_to_memory_item(m) for m in items if m.category == "suggested_action"]
    open_questions = [_to_memory_item(m) for m in items if m.category == "open_question"]

    source_reference = {
        "workflow_instance_id": str(instance_uuid) if instance_uuid else "",
        "conversation_id": str(current_conv_id) if current_conv_id else (str(latest_conv.id) if latest_conv else ""),
        "conversation_title": latest_conv.title if latest_conv else "",
        "conversation_date": latest_conv.conversation_date if latest_conv else None,
        "storage_type": "relational_postgresql",
    }

    return ContactMemorySnapshot(
        contact_id=str(contact.id),
        contact_name=contact.name,
        contact_role=contact.role,
        organization_id=str(contact.organization_id),
        total_conversations=len(convs),
        conversations=history_items,
        latest_conversation_title=latest_conv.title if latest_conv else "No conversations",
        latest_conversation_date=latest_conv.conversation_date if latest_conv else None,
        latest_conversation_summary=latest_conv.summary if latest_conv else None,
        facts=facts,
        interests=interests,
        needs=needs,
        opportunities=opportunities,
        commitments=commitments,
        suggested_actions=suggested_actions,
        open_questions=open_questions,
        source_reference=source_reference,
    )


# ── Node 3: Central Memory Endpoint ──────────────────────────────────────────

@router.post("/central-memory", response_model=CentralMemoryResponse)
async def process_central_memory(
    request: CentralMemoryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_any_auth),
):
    """
    NODE 3: Central Memory
    Converts processed conversation intelligence from Node 2 into persistent,
    organization-scoped relationship memory in PostgreSQL.
    Enforces deterministic contact resolution, source traceability, and strict idempotency.
    """
    start_time = time.perf_counter()
    org_uuid = await _resolve_org_uuid(current_user, db)

    try:
        instance_uuid = uuid.UUID(request.instance_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid instance_id format.")

    stmt = select(WorkflowInstance).where(WorkflowInstance.id == instance_uuid)
    res = await db.execute(stmt)
    workflow_inst = res.scalars().first()
    if not workflow_inst:
        raise HTTPException(status_code=404, detail="Workflow instance not found.")

    if workflow_inst.organization_id != org_uuid:
        raise HTTPException(status_code=403, detail="Access forbidden: workflow run belongs to another organization.")

    ctx = workflow_inst.context or {}
    node2_data = ctx.get("node2_process_conversation")
    if not node2_data or node2_data.get("status") != "completed":
        raise HTTPException(
            status_code=400,
            detail="Node 2 (Process Conversation) has not successfully completed for this workflow run. Node 3 requires verified transcript and structured extraction.",
        )

    # ── Check Idempotency ──────────────────────────────────────────────────────
    stmt_conv = select(RelationshipConversation).where(
        RelationshipConversation.organization_id == org_uuid,
        RelationshipConversation.workflow_instance_id == instance_uuid,
    )
    res_conv = await db.execute(stmt_conv)
    existing_conv = res_conv.scalars().first()

    if existing_conv:
        # Retrieve existing contact
        stmt_c = select(RelationshipContact).where(RelationshipContact.id == existing_conv.contact_id)
        res_c = await db.execute(stmt_c)
        contact = res_c.scalars().first()

        # Rehydrate and persist node3_central_memory into WorkflowInstance context if missing
        existing_node3 = (workflow_inst.context or {}).get("node3_central_memory")
        if not existing_node3 or existing_node3.get("status") != "completed":
            updated_ctx = dict(workflow_inst.context or {})
            updated_ctx["node3_central_memory"] = {
                "contact_id": str(contact.id) if contact else str(existing_conv.contact_id),
                "contact_name": contact.name if contact else "Contact",
                "contact_role": contact.role if contact else "",
                "conversation_id": str(existing_conv.id),
                "status": "completed",
                "indexed_at": existing_conv.created_at.isoformat() if existing_conv.created_at else datetime.utcnow().isoformat(),
            }
            impl_nodes = list(updated_ctx.get("implemented_nodes") or ["n1", "n2"])
            if "n3" not in impl_nodes:
                impl_nodes.append("n3")
            updated_ctx["implemented_nodes"] = impl_nodes
            workflow_inst.context = updated_ctx
            workflow_inst.current_node = "n3"
            await db.commit()

        snapshot = await _build_contact_memory_snapshot(contact, existing_conv.id, org_uuid, db, instance_uuid)
        nodes_status = [
            PipelineNodeStatus(id="n1", title="Conversation Capture", status="completed", implemented=True, note="Audio recording and metadata preserved successfully."),
            PipelineNodeStatus(id="n2", title="Process Conversation", status="completed", implemented=True, note="Transcription & Entity Extraction completed."),
            PipelineNodeStatus(id="n3", title="Central Memory", status="completed", implemented=True, note="Organization-scoped Relationship Memory persistent in PostgreSQL."),
            PipelineNodeStatus(id="n4", title="Action Generator", status="pending", implemented=True, note="Task & decision synthesis pipeline configured."),
            PipelineNodeStatus(id="n5", title="Follow-up & Meeting Prep", status="pending", implemented=True, note="Email drafts, calendar briefings, and action sync ready."),
        ]
        return CentralMemoryResponse(
            instance_id=str(instance_uuid),
            workflow_name="meeting_intelligence_followup",
            status="completed",
            current_node="n3",
            contact_id=str(contact.id) if contact else str(existing_conv.contact_id),
            conversation_id=str(existing_conv.id),
            memory=snapshot,
            nodes=nodes_status,
            message="Central Memory retrieved from existing persisted record (Idempotent reuse).",
            idempotent_reused=True,
        )

    # ── 1. Contact Resolution (Deterministic within Organization) ──────────────
    capture_data = ctx.get("conversation_capture") or workflow_inst.trigger_payload or {}
    raw_name = capture_data.get("contact_name") or capture_data.get("participant_name") or "Unknown Contact"
    contact_name = raw_name.strip()
    normalized_name = contact_name.lower()
    participant_role = capture_data.get("participant_role") or ""
    conversation_title = capture_data.get("conversation_title") or "Meeting"
    conversation_type = capture_data.get("conversation_type") or "meeting"
    conversation_date = capture_data.get("conversation_date") or datetime.utcnow().strftime("%Y-%m-%d")
    detected_lang = node2_data.get("detected_language") or "en"
    transcript_text = node2_data.get("transcript_text") or ""
    extraction = node2_data.get("extraction") or {}
    summary_text = extraction.get("summary") or ""

    stmt_contact = select(RelationshipContact).where(
        RelationshipContact.organization_id == org_uuid,
        RelationshipContact.normalized_name == normalized_name,
    )
    res_contact = await db.execute(stmt_contact)
    contact = res_contact.scalars().first()

    if not contact:
        contact = RelationshipContact(
            id=uuid.uuid4(),
            organization_id=org_uuid,
            name=contact_name,
            normalized_name=normalized_name,
            role=participant_role,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(contact)
        await db.flush()
    else:
        if participant_role and not contact.role:
            contact.role = participant_role
            contact.updated_at = datetime.utcnow()

    # ── 2. Create Conversation Record ──────────────────────────────────────────
    conversation = RelationshipConversation(
        id=uuid.uuid4(),
        organization_id=org_uuid,
        contact_id=contact.id,
        workflow_instance_id=instance_uuid,
        title=conversation_title,
        conversation_type=conversation_type,
        conversation_date=conversation_date,
        detected_language=detected_lang,
        transcript=transcript_text,
        summary=summary_text,
        structured_memory=extraction,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(conversation)
    await db.flush()

    # ── 3. Create Granular Traceable Memory Items ──────────────────────────────
    memory_items = []

    # People Facts, Interests, Needs, Opportunities
    for person in extraction.get("people", []):
        p_name = person.get("name") or contact.name
        for f in person.get("facts", []):
            if f and f.strip():
                memory_items.append(RelationshipMemoryItem(
                    id=uuid.uuid4(),
                    organization_id=org_uuid,
                    contact_id=contact.id,
                    conversation_id=conversation.id,
                    workflow_instance_id=instance_uuid,
                    category="fact",
                    content=f.strip(),
                    details={"person": p_name},
                    source_date=conversation_date,
                    is_ai_generated=False,
                ))
        for i in person.get("interests", []):
            if i and i.strip():
                memory_items.append(RelationshipMemoryItem(
                    id=uuid.uuid4(),
                    organization_id=org_uuid,
                    contact_id=contact.id,
                    conversation_id=conversation.id,
                    workflow_instance_id=instance_uuid,
                    category="interest",
                    content=i.strip(),
                    details={"person": p_name},
                    source_date=conversation_date,
                    is_ai_generated=False,
                ))
        for n in person.get("needs", []):
            if n and n.strip():
                memory_items.append(RelationshipMemoryItem(
                    id=uuid.uuid4(),
                    organization_id=org_uuid,
                    contact_id=contact.id,
                    conversation_id=conversation.id,
                    workflow_instance_id=instance_uuid,
                    category="need",
                    content=n.strip(),
                    details={"person": p_name},
                    source_date=conversation_date,
                    is_ai_generated=False,
                ))
        for o in person.get("opportunities", []):
            if o and o.strip():
                memory_items.append(RelationshipMemoryItem(
                    id=uuid.uuid4(),
                    organization_id=org_uuid,
                    contact_id=contact.id,
                    conversation_id=conversation.id,
                    workflow_instance_id=instance_uuid,
                    category="opportunity",
                    content=o.strip(),
                    details={"person": p_name},
                    source_date=conversation_date,
                    is_ai_generated=False,
                ))

    # Explicit Commitments
    for comm in extraction.get("commitments", []):
        c_text = comm.get("commitment") if isinstance(comm, dict) else str(comm)
        owner = comm.get("owner", contact.name) if isinstance(comm, dict) else contact.name
        due_date = comm.get("due_date") if isinstance(comm, dict) else None
        if c_text and c_text.strip():
            memory_items.append(RelationshipMemoryItem(
                id=uuid.uuid4(),
                organization_id=org_uuid,
                contact_id=contact.id,
                conversation_id=conversation.id,
                workflow_instance_id=instance_uuid,
                category="commitment",
                content=c_text.strip(),
                details={"owner": owner, "due_date": due_date},
                source_date=conversation_date,
                is_ai_generated=False,
            ))

    # Suggested Actions (PRESERVE STRICT SEPARATION AS AI-GENERATED)
    for action in extraction.get("suggested_actions", []):
        a_text = action.get("action") if isinstance(action, dict) else str(action)
        reason = action.get("reason", "") if isinstance(action, dict) else ""
        if a_text and a_text.strip():
            memory_items.append(RelationshipMemoryItem(
                id=uuid.uuid4(),
                organization_id=org_uuid,
                contact_id=contact.id,
                conversation_id=conversation.id,
                workflow_instance_id=instance_uuid,
                category="suggested_action",
                content=a_text.strip(),
                details={"action": a_text.strip(), "reason": reason},
                source_date=conversation_date,
                is_ai_generated=True,
            ))

    # Open Questions
    for q in extraction.get("open_questions", []):
        if q and q.strip():
            memory_items.append(RelationshipMemoryItem(
                id=uuid.uuid4(),
                organization_id=org_uuid,
                contact_id=contact.id,
                conversation_id=conversation.id,
                workflow_instance_id=instance_uuid,
                category="open_question",
                content=q.strip(),
                details={},
                source_date=conversation_date,
                is_ai_generated=False,
            ))

    for item in memory_items:
        db.add(item)
    await db.flush()

    duration_ms = int((time.perf_counter() - start_time) * 1000)

    # ── 4. Update WorkflowInstance context ─────────────────────────────────────
    updated_ctx = dict(workflow_inst.context or {})
    updated_ctx["node3_central_memory"] = {
        "contact_id": str(contact.id),
        "contact_name": contact.name,
        "contact_role": contact.role,
        "conversation_id": str(conversation.id),
        "status": "completed",
        "indexed_at": datetime.utcnow().isoformat(),
    }
    impl_nodes = list(updated_ctx.get("implemented_nodes") or ["n1", "n2"])
    if "n3" not in impl_nodes:
        impl_nodes.append("n3")
    updated_ctx["implemented_nodes"] = impl_nodes
    workflow_inst.context = updated_ctx
    workflow_inst.current_node = "n3"

    # ── 5. Observability: AgentRunRecord & AuditEvent ──────────────────────────
    agent_record = AgentRunRecord(
        id=uuid.uuid4(),
        instance_id=instance_uuid,
        node_id="n3",
        agent_capability="central_memory",
        status="success",
        cost_usd=0.0,
        tokens_in=0,
        tokens_out=0,
        model_used="relational_indexer",
        duration_ms=duration_ms,
        completed_at=datetime.utcnow(),
        tools_used=["relationship_contacts", "relationship_conversations", "relationship_memory_items"],
    )
    db.add(agent_record)

    audit_event = AuditEvent(
        id=uuid.uuid4(),
        organization_id=org_uuid,
        actor_id=str(current_user.user_id or current_user.email or "system"),
        action="central_memory_indexed",
        entity_type="relationship_conversation",
        entity_id=str(conversation.id),
        metadata_={
            "contact_id": str(contact.id),
            "contact_name": contact.name,
            "workflow_instance_id": str(instance_uuid),
            "items_indexed": len(memory_items),
        },
        created_at=datetime.utcnow(),
    )
    db.add(audit_event)
    await db.commit()

    # ── 6. Assemble Central Memory Snapshot ───────────────────────────────────
    snapshot = await _build_contact_memory_snapshot(contact, conversation.id, org_uuid, db, instance_uuid)

    nodes_status = [
        PipelineNodeStatus(id="n1", title="Conversation Capture", status="completed", implemented=True, note="Audio recording and metadata preserved successfully."),
        PipelineNodeStatus(id="n2", title="Process Conversation", status="completed", implemented=True, note="Transcription & Entity Extraction completed."),
        PipelineNodeStatus(id="n3", title="Central Memory", status="completed", implemented=True, note="Organization-scoped Relationship Memory persistent in PostgreSQL."),
        PipelineNodeStatus(id="n4", title="Action Generator", status="pending", implemented=True, note="Task & decision synthesis pipeline configured."),
        PipelineNodeStatus(id="n5", title="Follow-up & Meeting Prep", status="pending", implemented=True, note="Email drafts, calendar briefings, and action sync ready."),
    ]

    return CentralMemoryResponse(
        instance_id=str(instance_uuid),
        workflow_name="meeting_intelligence_followup",
        status="completed",
        current_node="n3",
        contact_id=str(contact.id),
        conversation_id=str(conversation.id),
        memory=snapshot,
        nodes=nodes_status,
        message="Conversation and structured intelligence successfully indexed into Central Memory.",
        idempotent_reused=False,
    )


# ── Contact Memory History Endpoint ──────────────────────────────────────────

@router.get("/contacts/{contact_id}/history", response_model=ContactMemorySnapshot)
async def get_contact_memory_history(
    contact_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_any_auth),
):
    """
    Retrieve full aggregated relationship history and memory items for a specific contact.
    Enforces organization-level isolation.
    """
    org_uuid = await _resolve_org_uuid(current_user, db)

    try:
        cid = uuid.UUID(contact_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid contact_id format.")

    stmt = select(RelationshipContact).where(RelationshipContact.id == cid)
    res = await db.execute(stmt)
    contact = res.scalars().first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found.")

    if contact.organization_id != org_uuid:
        raise HTTPException(status_code=403, detail="Access denied: contact belongs to another organization.")

    return await _build_contact_memory_snapshot(contact, None, org_uuid, db, None)


# ── Workflow Run Detail / Rehydration Endpoint ────────────────────────────────

@router.get("/runs/{instance_id}", response_model=WorkflowRunDetailResponse)
async def get_workflow_run_detail(
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_any_auth),
):
    """
    Retrieve workflow run state and deliverables for rehydration on page refresh.
    Enforces tenant and organization isolation.
    """
    org_uuid = await _resolve_org_uuid(current_user, db)

    try:
        instance_uuid = uuid.UUID(instance_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid instance_id format.")

    stmt = select(WorkflowInstance).where(WorkflowInstance.id == instance_uuid)
    res = await db.execute(stmt)
    workflow_inst = res.scalars().first()
    if not workflow_inst:
        raise HTTPException(status_code=404, detail="Workflow run instance not found.")

    if workflow_inst.organization_id != org_uuid:
        raise HTTPException(status_code=403, detail="Access denied: workflow run belongs to another organization.")

    ctx = workflow_inst.context or {}
    capture_data = ctx.get("conversation_capture") or workflow_inst.trigger_payload or {}
    node2_data = ctx.get("node2_process_conversation") or {}
    node3_data = ctx.get("node3_central_memory") or {}

    extraction_obj = None
    if node2_data.get("extraction"):
        try:
            extraction_obj = StructuredExtraction(**node2_data["extraction"])
        except Exception:
            pass

    central_memory_snapshot = None
    n3_status = node3_data.get("status") or "pending"
    if n3_status == "completed" and node3_data.get("contact_id"):
        try:
            cid = uuid.UUID(node3_data["contact_id"])
            stmt_contact = select(RelationshipContact).where(RelationshipContact.id == cid)
            res_c = await db.execute(stmt_contact)
            contact_obj = res_c.scalars().first()
            if contact_obj and contact_obj.organization_id == org_uuid:
                conv_id_val = uuid.UUID(node3_data["conversation_id"]) if node3_data.get("conversation_id") else None
                central_memory_snapshot = await _build_contact_memory_snapshot(
                    contact=contact_obj,
                    current_conv_id=conv_id_val,
                    org_uuid=org_uuid,
                    db=db,
                    instance_uuid=instance_uuid,
                )
        except Exception as e:
            log.warning("Failed to rehydrate central memory snapshot", error=str(e))

    n1_status = "completed"
    n2_status = node2_data.get("status") or ("completed" if node2_data else "pending")

    nodes_status = [
        PipelineNodeStatus(
            id="n1",
            title="Conversation Capture",
            status=n1_status,
            implemented=True,
            note="Audio recording and metadata preserved successfully.",
        ),
        PipelineNodeStatus(
            id="n2",
            title="Process Conversation",
            status=n2_status,
            implemented=True if n2_status == "completed" else False,
            note="Transcription & Entity Extraction" if n2_status != "completed" else "Transcription & Entity Extraction completed.",
        ),
        PipelineNodeStatus(
            id="n3",
            title="Central Memory",
            status=n3_status,
            implemented=True,
            note="Organization-scoped Relationship Memory persistent in PostgreSQL." if n3_status == "completed" else "Structured relationship memory and context index ready.",
        ),
        PipelineNodeStatus(
            id="n4",
            title="Action Generator",
            status=ctx.get("node4_action_generator", {}).get("status") or "pending",
            implemented=True,
            note="Action items active and persisted in Action Center." if ctx.get("node4_action_generator", {}).get("status") == "completed" else "Task & decision synthesis pipeline configured.",
        ),
        PipelineNodeStatus(
            id="n5",
            title="Follow-up & Meeting Prep",
            status=ctx.get("node5_followup_draft", {}).get("status") or "pending",
            implemented=True,
            note="Follow-up email drafts and meeting briefings ready." if ctx.get("node5_followup_draft") else "Email drafts, calendar briefings, and action sync ready.",
        ),
    ]

    # Rehydrate Node 4 actions if present
    actions_snapshot = None
    node4_data = ctx.get("node4_action_generator")
    if node4_data and node4_data.get("status") == "completed" and contact_obj:
        try:
            stmt_apprs = select(ApprovalItem).where(
                ApprovalItem.organization_id == org_uuid,
                ApprovalItem.instance_id == instance_uuid,
                ApprovalItem.node_id == "n4",
            )
            res_apprs = await db.execute(stmt_apprs)
            existing_apprs = list(res_apprs.scalars().all())

            our_cmts = []
            contact_cmts = []
            ai_suggs = []
            for appr in existing_apprs:
                p = appr.payload or {}
                atype = p.get("action_type") or "our_commitment"
                act_obj = GeneratedActionItem(
                    id=str(appr.id),
                    approval_id=str(appr.id),
                    action_type=atype,
                    action=p.get("action") or appr.reason,
                    owner_type=p.get("owner_type") or ("internal" if atype == "our_commitment" else "contact"),
                    owner_display=p.get("owner_display") or ("You / Internal" if atype == "our_commitment" else contact_obj.name),
                    owner=p.get("owner"),
                    due_date=p.get("due_date"),
                    due_date_display=p.get("due_date_display") or _format_due_date_display(p.get("due_date")),
                    status=appr.status,
                    reason=p.get("reason"),
                    source=p.get("source") or "current_conversation",
                    source_title=p.get("conversation_title"),
                    source_date=p.get("source_date"),
                    conversation_id=p.get("conversation_id"),
                    workflow_instance_id=str(instance_uuid),
                    provenance=p.get("provenance") or {},
                )
                if atype == "our_commitment":
                    our_cmts.append(act_obj)
                elif atype == "contact_commitment":
                    contact_cmts.append(act_obj)
                elif atype == "ai_suggestion":
                    ai_suggs.append(act_obj)

            saved_open_questions = node4_data.get("open_questions", [])
            open_q_objs = [
                GeneratedOpenQuestionItem(**q) if isinstance(q, dict) else GeneratedOpenQuestionItem(
                    id=str(uuid.uuid4()), question=str(q)
                )
                for q in saved_open_questions
            ]

            hist_cmts: List[GeneratedActionItem] = []
            if contact_obj:
                conv_id_val = uuid.UUID(node3_data["conversation_id"]) if node3_data.get("conversation_id") else None
                stmt_h = select(RelationshipMemoryItem).where(
                    RelationshipMemoryItem.organization_id == org_uuid,
                    RelationshipMemoryItem.contact_id == contact_obj.id,
                    RelationshipMemoryItem.category == "commitment",
                )
                if conv_id_val:
                    stmt_h = stmt_h.where(RelationshipMemoryItem.conversation_id != conv_id_val)
                stmt_h = stmt_h.order_by(RelationshipMemoryItem.source_date.desc(), RelationshipMemoryItem.created_at.desc())
                res_h = await db.execute(stmt_h)
                for h_item in res_h.scalars().all():
                    h_owner_raw = h_item.details.get("owner") if isinstance(h_item.details, dict) else None
                    h_owner_type, h_owner_display = _classify_commitment_owner(h_owner_raw, contact_obj.name, h_item.content)
                    h_due_date = h_item.details.get("due_date") if isinstance(h_item.details, dict) else None
                    hist_cmts.append(
                        GeneratedActionItem(
                            id=str(h_item.id),
                            action_type="our_commitment" if h_owner_type == "internal" else "contact_commitment",
                            action=h_item.content,
                            owner_type=h_owner_type,
                            owner_display=h_owner_display,
                            owner=h_owner_raw,
                            due_date=h_due_date,
                            due_date_display=_format_due_date_display(h_due_date),
                            status="historical",
                            source="historical_conversation",
                            source_title=h_item.details.get("conversation_title") if isinstance(h_item.details, dict) else None,
                            source_date=h_item.source_date,
                            conversation_id=str(h_item.conversation_id),
                            workflow_instance_id=str(h_item.workflow_instance_id),
                            provenance={
                                "memory_item_id": str(h_item.id),
                                "is_historical": True,
                            },
                        )
                    )

            actions_snapshot = ActionGeneratorResponse(
                instance_id=str(instance_uuid),
                workflow_name="meeting_intelligence_followup",
                status="completed",
                current_node="n4",
                contact_id=str(contact_obj.id),
                contact_name=contact_obj.name,
                our_commitments=our_cmts,
                contact_commitments=contact_cmts,
                ai_suggestions=ai_suggs,
                open_questions=open_q_objs,
                historical_commitments=hist_cmts,
                nodes=nodes_status,
                message="Rehydrated actions from database.",
                idempotent_reused=True,
            )
        except Exception as e:
            log.warning("Failed to rehydrate actions snapshot", error=str(e))

    # Rehydrate Node 5A Follow-up Draft if present
    followup_draft_snapshot = None
    try:
        stmt_draft = select(ApprovalItem).where(
            ApprovalItem.organization_id == org_uuid,
            ApprovalItem.instance_id == instance_uuid,
            ApprovalItem.review_type == "followup_email_draft",
        ).order_by(ApprovalItem.created_at.desc())
        res_draft = await db.execute(stmt_draft)
        appr_draft = res_draft.scalars().first()
        if appr_draft and getattr(appr_draft, "review_type", None) == "followup_email_draft":
            dp = appr_draft.payload or {}
            followup_draft_snapshot = FollowupDraftItem(
                id=str(appr_draft.id),
                approval_id=str(appr_draft.id),
                instance_id=str(instance_uuid),
                review_type=appr_draft.review_type or "followup_email_draft",
                status=appr_draft.status,
                subject=dp.get("subject", ""),
                body=dp.get("body", ""),
                recipient_name=dp.get("recipient_name", ""),
                recipient_email=dp.get("recipient_email"),
                recipient_email_available=bool(dp.get("recipient_email_available", False)),
                contact_id=dp.get("contact_id"),
                conversation_title=dp.get("conversation_title"),
                our_commitments_count=dp.get("our_commitments_count", 0),
                contact_commitments_count=dp.get("contact_commitments_count", 0),
                ai_suggestions_count=dp.get("ai_suggestions_count", 0),
                open_questions_count=dp.get("open_questions_count", 0),
                original_generated_subject=dp.get("original_generated_subject"),
                original_generated_body=dp.get("original_generated_body"),
                original_subject=dp.get("original_generated_subject") or dp.get("original_subject"),
                original_body=dp.get("original_generated_body") or dp.get("original_body"),
                snoozed_until=dp.get("snoozed_until"),
                snooze_reason=dp.get("snooze_reason"),
                snoozed_reason=dp.get("snooze_reason"),
                model_used=dp.get("model_used"),
                decided_by=appr_draft.decided_by,
                decided_at=appr_draft.decided_at.isoformat() if appr_draft.decided_at else None,
                created_at=appr_draft.created_at.isoformat() if appr_draft.created_at else None,
                provenance=dp.get("provenance") or {},
            )
            for n in nodes_status:
                if n.id == "n5":
                    n.status = "partial"
                    n.implemented = True
                    if appr_draft.status == "approved":
                        n.note = "Follow-up Email Draft: Approved (Sending Deferred) • Meeting Prep: Pending • Calendar Prep Block: Pending"
                    elif appr_draft.status == "snoozed":
                        n.note = f"Follow-up Email Draft: Snoozed ({dp.get('snoozed_until') or 'later'}) • Meeting Prep: Pending • Calendar Prep Block: Pending"
                    elif appr_draft.status == "discarded":
                        n.note = "Follow-up Email Draft: Discarded • Meeting Prep: Pending • Calendar Prep Block: Pending"
                    else:
                        n.note = "Follow-up Email Draft: Ready / Awaiting Review • Meeting Prep: Pending • Calendar Prep Block: Pending"
            if actions_snapshot:
                actions_snapshot.nodes = nodes_status
    except Exception as e:
        log.warning("Failed to rehydrate follow-up draft snapshot", error=str(e))

    return WorkflowRunDetailResponse(
        instance_id=str(workflow_inst.id),
        workflow_name=workflow_inst.workflow_name,
        status=workflow_inst.status,
        current_node=workflow_inst.current_node or "n1",
        conversation_data=capture_data,
        transcript_text=node2_data.get("transcript_text"),
        detected_language=node2_data.get("detected_language"),
        transcription_status=node2_data.get("transcription_status"),
        extraction=extraction_obj,
        central_memory=central_memory_snapshot,
        actions=actions_snapshot,
        followup_draft=followup_draft_snapshot,
        nodes=nodes_status,
        model_used=node2_data.get("model_used"),
        started_at=workflow_inst.started_at.isoformat() if workflow_inst.started_at else None,
        completed_at=workflow_inst.completed_at.isoformat() if workflow_inst.completed_at else None,
    )


get_meeting_intelligence_run = get_workflow_run_detail


# ── Node 4: Action Generator Endpoint ─────────────────────────────────────────

@router.post("/action-generator", response_model=ActionGeneratorResponse)
async def process_action_generator(
    request: ActionGeneratorRequest,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_any_auth),
):
    """
    NODE 4: Action Generator
    Converts conversation intelligence from Node 2 & Node 3 into persistent,
    organization-scoped action items without confusing:
    1. Explicit commitments made by us (our_commitment -> internal pending task)
    2. Explicit commitments made by the contact (contact_commitment -> waiting on contact)
    3. AI-generated recommendations (ai_suggestion -> suggested, not confirmed task)
    4. Unresolved/open questions (open_question -> contextual intelligence)

    Strictly refuses execution if Node 2 or Node 3 has not completed.
    Enforces idempotency, full source traceability, and strict tenant isolation.
    Integrates with the platform Action Center via ApprovalItem.
    """
    start_time = time.perf_counter()
    org_uuid = await _resolve_org_uuid(current_user, db)

    try:
        instance_uuid = uuid.UUID(request.instance_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid instance_id format.")

    stmt = select(WorkflowInstance).where(WorkflowInstance.id == instance_uuid)
    res = await db.execute(stmt)
    workflow_inst = res.scalars().first()
    if not workflow_inst:
        raise HTTPException(status_code=404, detail="Workflow instance not found.")

    if workflow_inst.organization_id != org_uuid:
        raise HTTPException(status_code=403, detail="Access forbidden: workflow run belongs to another organization.")

    ctx = workflow_inst.context or {}
    node2_data = ctx.get("node2_process_conversation")
    if not node2_data or node2_data.get("status") != "completed":
        raise HTTPException(
            status_code=400,
            detail="Node 2 (Process Conversation) has not successfully completed for this workflow run. Node 4 requires verified extraction.",
        )

    node3_data = ctx.get("node3_central_memory")
    if not node3_data or node3_data.get("status") != "completed":
        raise HTTPException(
            status_code=400,
            detail="Node 3 (Central Memory) has not successfully completed for this workflow run. Node 4 requires persistent relationship memory and resolved contact.",
        )

    contact_id_str = node3_data.get("contact_id")
    if not contact_id_str:
        raise HTTPException(status_code=400, detail="Central Memory contact could not be resolved.")

    try:
        contact_uuid = uuid.UUID(contact_id_str)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid contact_id in Central Memory context.")

    stmt_c = select(RelationshipContact).where(
        RelationshipContact.id == contact_uuid,
        RelationshipContact.organization_id == org_uuid,
    )
    res_c = await db.execute(stmt_c)
    contact = res_c.scalars().first()
    if not contact:
        raise HTTPException(status_code=400, detail="Central Memory contact could not be resolved in the current organization.")

    # Retrieve current conversation
    stmt_conv = select(RelationshipConversation).where(
        RelationshipConversation.organization_id == org_uuid,
        RelationshipConversation.workflow_instance_id == instance_uuid,
    )
    res_conv = await db.execute(stmt_conv)
    current_conv = res_conv.scalars().first()
    if not current_conv:
        raise HTTPException(status_code=400, detail="Central Memory conversation could not be resolved for this run.")

    # Check for historical commitments from previous conversations with this contact
    stmt_hist = select(RelationshipMemoryItem).where(
        RelationshipMemoryItem.organization_id == org_uuid,
        RelationshipMemoryItem.contact_id == contact.id,
        RelationshipMemoryItem.category == "commitment",
        RelationshipMemoryItem.conversation_id != current_conv.id,
    ).order_by(RelationshipMemoryItem.source_date.desc(), RelationshipMemoryItem.created_at.desc())
    res_hist = await db.execute(stmt_hist)
    hist_memory_items = list(res_hist.scalars().all())

    historical_commitments: List[GeneratedActionItem] = []
    for h_item in hist_memory_items:
        h_owner_raw = h_item.details.get("owner") if isinstance(h_item.details, dict) else None
        h_due_date = h_item.details.get("due_date") if isinstance(h_item.details, dict) else None
        h_owner_type, h_owner_display = _classify_commitment_owner(h_owner_raw, contact.name, h_item.content)
        historical_commitments.append(
            GeneratedActionItem(
                id=str(h_item.id),
                action_type="our_commitment" if h_owner_type == "internal" else "contact_commitment",
                action=h_item.content,
                owner_type=h_owner_type,
                owner_display=h_owner_display,
                owner=h_owner_raw,
                due_date=h_due_date,
                due_date_display=_format_due_date_display(h_due_date),
                status="historical",
                source="historical_conversation",
                source_title=h_item.details.get("conversation_title") if isinstance(h_item.details, dict) else None,
                source_date=h_item.source_date,
                conversation_id=str(h_item.conversation_id),
                workflow_instance_id=str(h_item.workflow_instance_id),
                provenance={
                    "memory_item_id": str(h_item.id),
                    "is_historical": True,
                },
            )
        )

    # ── 1. Extract Intelligence from Node 2 & Central Memory ──────────────────
    extraction = node2_data.get("extraction") or node2_data.get("structured_extraction") or {}
    raw_commitments = extraction.get("commitments") or extraction.get("agreed_commitments") or []
    raw_suggestions = extraction.get("suggested_actions") or []
    raw_questions = extraction.get("open_questions") or []

    # Fallback to current conversation structured_memory if raw_commitments was empty
    if not raw_commitments and current_conv and isinstance(current_conv.structured_memory, dict):
        raw_commitments = current_conv.structured_memory.get("commitments") or current_conv.structured_memory.get("agreed_commitments") or []

    # Fallback to RelationshipMemoryItem for current_conv if raw_commitments was empty
    if not raw_commitments and current_conv:
        stmt_cur_cmts = select(RelationshipMemoryItem).where(
            RelationshipMemoryItem.conversation_id == current_conv.id,
            RelationshipMemoryItem.category == "commitment",
        )
        cur_mem_rows = (await db.execute(stmt_cur_cmts)).scalars().all()
        raw_commitments = [
            {
                "commitment": r.content,
                "owner": r.details.get("owner") if isinstance(r.details, dict) else None,
                "due_date": r.details.get("due_date") if isinstance(r.details, dict) else None,
            }
            for r in cur_mem_rows
        ]

    # ── Check Idempotency & Load Existing ApprovalItems ───────────────────────
    stmt_appr = select(ApprovalItem).where(
        ApprovalItem.organization_id == org_uuid,
        ApprovalItem.instance_id == instance_uuid,
        ApprovalItem.node_id == "n4",
    )
    res_appr = await db.execute(stmt_appr)
    existing_apprs = list(res_appr.scalars().all())

    existing_by_ref = {
        (appr.payload or {}).get("source_ref"): appr
        for appr in existing_apprs
        if (appr.payload or {}).get("source_ref")
    }
    existing_by_action = {
        ((appr.payload or {}).get("action") or appr.reason or "").strip().lower(): appr
        for appr in existing_apprs
    }

    our_commitments: List[GeneratedActionItem] = []
    contact_commitments: List[GeneratedActionItem] = []
    ai_suggestions: List[GeneratedActionItem] = []
    open_questions: List[GeneratedOpenQuestionItem] = []
    new_approval_items: List[ApprovalItem] = []

    # ── 2. Process Commitments (Our Commitments vs Contact Commitments) ────────
    for idx, cmt in enumerate(raw_commitments):
        action_text = (
            (cmt.get("commitment") if isinstance(cmt, dict) else "")
            or (cmt.get("action") if isinstance(cmt, dict) else "")
            or (cmt.get("content") if isinstance(cmt, dict) else "")
            or (str(cmt) if not isinstance(cmt, dict) else "")
        ).strip()
        if not action_text:
            continue
        owner_raw = (
            (cmt.get("owner") if isinstance(cmt, dict) else None)
            or (cmt.get("owner_display") if isinstance(cmt, dict) else None)
            or (cmt.get("assignee") if isinstance(cmt, dict) else None)
            or ((cmt.get("details", {}).get("owner") if isinstance(cmt.get("details"), dict) else None) if isinstance(cmt, dict) else None)
        )
        due_date = (
            (cmt.get("due_date") if isinstance(cmt, dict) else None)
            or ((cmt.get("details", {}).get("due_date") if isinstance(cmt.get("details"), dict) else None) if isinstance(cmt, dict) else None)
        )
        due_date_display = _format_due_date_display(due_date)

        owner_type, owner_display = _classify_commitment_owner(owner_raw, contact.name, action_text)
        source_ref = f"{instance_uuid}:commitment:{idx}"

        existing_appr = existing_by_ref.get(source_ref) or existing_by_action.get(action_text.lower())
        if existing_appr:
            act_id = str(existing_appr.id)
            p = existing_appr.payload or {}
            item_status = existing_appr.status
            act_due = p.get("due_date") or due_date
            act_due_disp = p.get("due_date_display") or due_date_display
            act_owner = p.get("owner") or owner_raw
            act_owner_disp = p.get("owner_display") or owner_display
            act_owner_type = p.get("owner_type") or owner_type
        else:
            act_id = str(uuid.uuid4())
            item_status = "pending" if owner_type == "internal" else ("waiting" if owner_type == "contact" else "pending_review")
            action_type_val = "our_commitment" if owner_type == "internal" else ("contact_commitment" if owner_type == "contact" else "unknown_commitment")
            reason_text = action_text if owner_type == "internal" else (f"Waiting on {owner_display}: {action_text}" if owner_type == "contact" else f"Unassigned commitment: {action_text}")
            ctx_brief = f"Meeting with {contact.name}: {action_text}" if owner_type == "internal" else (f"Meeting with {contact.name}: Waiting on {owner_display} for {action_text}" if owner_type == "contact" else f"Meeting with {contact.name}: {action_text} (Attribution uncertain: {owner_raw or 'None'})")

            appr = ApprovalItem(
                id=uuid.UUID(act_id),
                organization_id=org_uuid,
                instance_id=instance_uuid,
                node_id="n4",
                review_type="meeting_action",
                reason=reason_text,
                context_brief=ctx_brief,
                status=item_status,
                payload={
                    "workflow_key": "meeting_intelligence_followup",
                    "workflow_name": "meeting_intelligence_followup",
                    "action_type": action_type_val,
                    "action": action_text,
                    "owner_type": owner_type,
                    "owner_display": owner_display,
                    "owner": owner_raw,
                    "due_date": due_date,
                    "due_date_display": due_date_display,
                    "contact_id": str(contact.id),
                    "contact_name": contact.name,
                    "conversation_id": str(current_conv.id),
                    "conversation_title": current_conv.title,
                    "source_date": current_conv.conversation_date,
                    "source_ref": source_ref,
                    "provenance": {
                        "workflow_instance_id": str(instance_uuid),
                        "conversation_id": str(current_conv.id),
                        "source_index": idx,
                    },
                },
                created_at=datetime.utcnow(),
            )
            new_approval_items.append(appr)
            act_due = due_date
            act_due_disp = due_date_display
            act_owner = owner_raw
            act_owner_disp = owner_display
            act_owner_type = owner_type

        action_item_obj = GeneratedActionItem(
            id=act_id,
            approval_id=act_id,
            action_type="our_commitment" if act_owner_type == "internal" else ("contact_commitment" if act_owner_type == "contact" else "unknown_commitment"),
            action=action_text,
            owner_type=act_owner_type,
            owner_display=act_owner_disp,
            owner=act_owner,
            due_date=act_due,
            due_date_display=act_due_disp,
            status=item_status,
            source="current_conversation",
            source_title=current_conv.title,
            source_date=current_conv.conversation_date,
            conversation_id=str(current_conv.id),
            workflow_instance_id=str(instance_uuid),
            provenance={
                "workflow_instance_id": str(instance_uuid),
                "conversation_id": str(current_conv.id),
                "source_ref": source_ref,
            },
        )
        if act_owner_type == "internal":
            our_commitments.append(action_item_obj)
        elif act_owner_type == "contact":
            contact_commitments.append(action_item_obj)
        else:
            contact_commitments.append(action_item_obj)

    # ── 3. Process AI Suggested Actions ───────────────────────────────────────
    for idx, sugg in enumerate(raw_suggestions):
        sugg_action = (
            (sugg.get("action") if isinstance(sugg, dict) else "")
            or (sugg.get("suggestion") if isinstance(sugg, dict) else "")
            or (sugg.get("content") if isinstance(sugg, dict) else "")
            or (str(sugg) if not isinstance(sugg, dict) else "")
        ).strip()
        if not sugg_action:
            continue
        sugg_reason = ((sugg.get("reason") if isinstance(sugg, dict) else "") or "").strip()
        source_ref = f"{instance_uuid}:suggestion:{idx}"

        existing_appr = (
            existing_by_ref.get(source_ref)
            or existing_by_action.get(sugg_action.lower())
            or existing_by_action.get(f"ai suggested: {sugg_action}".lower())
        )
        if existing_appr:
            sugg_id = str(existing_appr.id)
            item_status = existing_appr.status
            p = existing_appr.payload or {}
            sugg_reason = p.get("reason") or sugg_reason
        else:
            sugg_id = str(uuid.uuid4())
            item_status = "suggested"
            appr = ApprovalItem(
                id=uuid.UUID(sugg_id),
                organization_id=org_uuid,
                instance_id=instance_uuid,
                node_id="n4",
                review_type="meeting_action",
                reason=f"AI Suggested: {sugg_action}",
                context_brief=f"Meeting with {contact.name}: AI recommends {sugg_action}",
                status="suggested",
                payload={
                    "workflow_key": "meeting_intelligence_followup",
                    "workflow_name": "meeting_intelligence_followup",
                    "action_type": "ai_suggestion",
                    "action": sugg_action,
                    "reason": sugg_reason,
                    "owner_type": "internal",
                    "owner_display": "AI Suggested",
                    "due_date": None,
                    "due_date_display": "No due date",
                    "contact_id": str(contact.id),
                    "contact_name": contact.name,
                    "conversation_id": str(current_conv.id),
                    "conversation_title": current_conv.title,
                    "source_date": current_conv.conversation_date,
                    "source_ref": source_ref,
                    "provenance": {
                        "workflow_instance_id": str(instance_uuid),
                        "conversation_id": str(current_conv.id),
                        "source_index": idx,
                    },
                },
                created_at=datetime.utcnow(),
            )
            new_approval_items.append(appr)

        ai_suggestions.append(
            GeneratedActionItem(
                id=sugg_id,
                approval_id=sugg_id,
                action_type="ai_suggestion",
                action=sugg_action,
                owner_type="internal",
                owner_display="AI Suggested",
                due_date=None,
                due_date_display="No due date",
                status=item_status,
                reason=sugg_reason,
                source="current_conversation",
                source_title=current_conv.title,
                source_date=current_conv.conversation_date,
                conversation_id=str(current_conv.id),
                workflow_instance_id=str(instance_uuid),
                provenance={
                    "workflow_instance_id": str(instance_uuid),
                    "conversation_id": str(current_conv.id),
                    "source_ref": source_ref,
                },
            )
        )

    # ── 4. Process Open Questions (Preserved Context, Not Tasks) ──────────────
    for idx, q in enumerate(raw_questions):
        q_text = (q if isinstance(q, str) else (q.get("question") if isinstance(q, dict) else str(q))).strip()
        if not q_text:
            continue
        q_id = str(uuid.uuid4())
        open_questions.append(
            GeneratedOpenQuestionItem(
                id=q_id,
                question=q_text,
                source_date=current_conv.conversation_date,
                source_title=current_conv.title,
                workflow_instance_id=str(instance_uuid),
                conversation_id=str(current_conv.id),
                provenance={
                    "workflow_instance_id": str(instance_uuid),
                    "conversation_id": str(current_conv.id),
                    "source_index": idx,
                },
            )
        )

    # ── 5. Persist New ApprovalItems to PostgreSQL ─────────────────────────────
    for appr in new_approval_items:
        db.add(appr)
    if new_approval_items:
        await db.flush()

    duration_ms = int((time.perf_counter() - start_time) * 1000)

    # ── 6. Update WorkflowInstance Context ────────────────────────────────────
    updated_ctx = dict(workflow_inst.context or {})
    updated_ctx["node4_action_generator"] = {
        "status": "completed",
        "generated_at": datetime.utcnow().isoformat(),
        "our_commitments": [a.model_dump() for a in our_commitments],
        "contact_commitments": [a.model_dump() for a in contact_commitments],
        "ai_suggestions": [a.model_dump() for a in ai_suggestions],
        "open_questions": [q.model_dump() for q in open_questions],
    }
    updated_ctx["implemented_nodes"] = ["n1", "n2", "n3", "n4"]
    updated_ctx["pending_nodes"] = ["n5"]
    workflow_inst.context = updated_ctx
    workflow_inst.current_node = "n4"

    # ── 7. Observability: AgentRunRecord & AuditEvent ──────────────────────────
    agent_record = AgentRunRecord(
        id=uuid.uuid4(),
        instance_id=instance_uuid,
        node_id="n4",
        agent_capability="action_generation",
        status="completed",
        cost_usd=0.0,
        tokens_in=0,
        tokens_out=0,
        model_used="deterministic_action_classifier",
        duration_ms=duration_ms,
        completed_at=datetime.utcnow(),
        tools_used=["approval_items", "relationship_memory_items"],
    )
    db.add(agent_record)

    audit_event = AuditEvent(
        id=uuid.uuid4(),
        organization_id=org_uuid,
        actor_id=str(getattr(current_user, "email", None) or getattr(current_user, "user_id", "system")),
        action="actions_generated",
        entity_type="workflow_instance",
        entity_id=str(instance_uuid),
        metadata_={
            "contact_id": str(contact.id),
            "contact_name": contact.name,
            "our_commitments_count": len(our_commitments),
            "contact_commitments_count": len(contact_commitments),
            "ai_suggestions_count": len(ai_suggestions),
            "open_questions_count": len(open_questions),
            "approval_items_created": len(new_approval_items),
        },
        created_at=datetime.utcnow(),
    )
    db.add(audit_event)

    await db.commit()

    nodes_status = [
        PipelineNodeStatus(id="n1", title="Conversation Capture", status="completed", implemented=True, note="Audio recording and metadata preserved successfully."),
        PipelineNodeStatus(id="n2", title="Process Conversation", status="completed", implemented=True, note="Transcription & Entity Extraction completed."),
        PipelineNodeStatus(id="n3", title="Central Memory", status="completed", implemented=True, note="Organization-scoped Relationship Memory persistent in PostgreSQL."),
        PipelineNodeStatus(id="n4", title="Action Generator", status="completed", implemented=True, note=f"Action items active ({len(our_commitments)} Our Commitments, {len(contact_commitments)} Waiting on Contact)."),
        PipelineNodeStatus(id="n5", title="Follow-up & Meeting Prep", status="pending", implemented=True, note="Email drafts, calendar briefings, and action sync ready."),
    ]

    return ActionGeneratorResponse(
        instance_id=str(instance_uuid),
        workflow_name="meeting_intelligence_followup",
        status="completed",
        current_node="n4",
        contact_id=str(contact.id),
        contact_name=contact.name,
        our_commitments=our_commitments,
        contact_commitments=contact_commitments,
        ai_suggestions=ai_suggestions,
        open_questions=open_questions,
        historical_commitments=historical_commitments,
        nodes=nodes_status,
        message="Action items generated and persisted successfully." if new_approval_items else "Action items retrieved from existing persisted records (Idempotent reuse).",
        idempotent_reused=(len(new_approval_items) == 0),
    )


# ── Node 5A: Follow-up Email Draft + Human Review ─────────────────────────────

def _build_deterministic_followup_draft(
    contact_name: str,
    conv_title: str,
    summary: str,
    our_commitments: List[Dict[str, Any]],
    contact_commitments: List[Dict[str, Any]],
    ai_suggestions: List[Dict[str, Any]],
    open_questions: List[Any],
) -> Dict[str, str]:
    """Fallback generator strictly grounded in extracted commitments without hallucinating details."""
    first_name = contact_name.split()[0] if contact_name else "there"
    subject = f"Follow-up: {conv_title} - Next Steps"

    body_lines = [
        f"Hi {first_name},",
        "",
        f"Thank you for taking the time to discuss {conv_title} today. I appreciated our conversation and sharing ideas.",
    ]
    if summary:
        body_lines.append("")
        body_lines.append(f"To summarize our discussion: {summary.strip()}")

    if our_commitments or contact_commitments:
        body_lines.append("")
        body_lines.append("To confirm our agreed next steps:")
        if our_commitments:
            body_lines.append("")
            body_lines.append("What we will do:")
            for c in our_commitments:
                due = c.get("due_date_display") or c.get("due_date")
                due_str = f" (by {due})" if due else ""
                body_lines.append(f"- {c['action']}{due_str}")
        if contact_commitments:
            body_lines.append("")
            body_lines.append(f"What {contact_name} agreed to provide:")
            for c in contact_commitments:
                due = c.get("due_date_display") or c.get("due_date")
                due_str = f" (by {due})" if due else ""
                body_lines.append(f"- {c['action']}{due_str}")

    if ai_suggestions:
        body_lines.append("")
        body_lines.append("As we plan our next milestone, here are a few suggested items for alignment:")
        for s in ai_suggestions[:2]:
            body_lines.append(f"- {s['action']}")

    body_lines.append("")
    body_lines.append("Looking forward to collaborating with you on this. Please let me know if you would like to adjust any of these items.")
    body_lines.append("")
    body_lines.append("Best regards,")

    return {
        "subject": subject,
        "body": "\n".join(body_lines),
    }


@router.post("/followup-draft", response_model=FollowupDraftResponse)
async def process_followup_draft(
    req: FollowupDraftRequest,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_any_auth),
):
    """
    Node 5A: Generate or retrieve follow-up email draft for human review.
    Grounded strictly in conversation transcript, central memory, and Node 4 actions.
    Enforces idempotency, tenant isolation, anti-hallucination, and human-in-the-loop review.
    STRICTLY DOES NOT SEND EMAIL.
    """
    start_time = time.perf_counter()
    org_uuid = await _resolve_org_uuid(current_user, db)
    if not req:
        raise HTTPException(status_code=400, detail="Missing request payload for follow-up draft.")

    try:
        instance_uuid = uuid.UUID(req.instance_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid instance_id format.")

    stmt = select(WorkflowInstance).where(WorkflowInstance.id == instance_uuid)
    res = await db.execute(stmt)
    workflow_inst = res.scalars().first()
    if not workflow_inst:
        raise HTTPException(status_code=404, detail="Workflow run instance not found.")

    if workflow_inst.organization_id != org_uuid:
        raise HTTPException(status_code=403, detail="Access denied: workflow run belongs to another organization.")

    ctx = workflow_inst.context or {}
    node4_data = ctx.get("node4_action_generator") or {}

    # Node 4 must be completed before Node 5A
    if node4_data.get("status") != "completed":
        stmt_chk = select(ApprovalItem).where(
            ApprovalItem.organization_id == org_uuid,
            ApprovalItem.instance_id == instance_uuid,
            ApprovalItem.node_id == "n4",
        )
        r_chk = await db.execute(stmt_chk)
        if not r_chk.scalars().first():
            raise HTTPException(
                status_code=400,
                detail="Node 4 (Action Generator) must be completed before generating a follow-up email draft."
            )

    # ── 1. Idempotency Check: Existing Follow-up Draft ─────────────────────────
    stmt_existing = select(ApprovalItem).where(
        ApprovalItem.organization_id == org_uuid,
        ApprovalItem.instance_id == instance_uuid,
        ApprovalItem.review_type == "followup_email_draft",
    ).order_by(ApprovalItem.created_at.desc())
    res_existing = await db.execute(stmt_existing)
    existing_appr = res_existing.scalars().first()

    if existing_appr:
        ep = existing_appr.payload or {}
        draft_item = FollowupDraftItem(
            id=str(existing_appr.id),
            approval_id=str(existing_appr.id),
            instance_id=str(instance_uuid),
            review_type=existing_appr.review_type or "followup_email_draft",
            status=existing_appr.status,
            subject=ep.get("subject", ""),
            body=ep.get("body", ""),
            recipient_name=ep.get("recipient_name", ""),
            recipient_email=ep.get("recipient_email"),
            recipient_email_available=bool(ep.get("recipient_email_available", False)),
            contact_id=ep.get("contact_id"),
            conversation_title=ep.get("conversation_title"),
            our_commitments_count=ep.get("our_commitments_count", 0),
            contact_commitments_count=ep.get("contact_commitments_count", 0),
            ai_suggestions_count=ep.get("ai_suggestions_count", 0),
            open_questions_count=ep.get("open_questions_count", 0),
            original_generated_subject=ep.get("original_generated_subject"),
            original_generated_body=ep.get("original_generated_body"),
            original_subject=ep.get("original_generated_subject") or ep.get("original_subject"),
            original_body=ep.get("original_generated_body") or ep.get("original_body"),
            snoozed_until=ep.get("snoozed_until"),
            snooze_reason=ep.get("snooze_reason"),
            snoozed_reason=ep.get("snooze_reason"),
            model_used=ep.get("model_used"),
            decided_by=existing_appr.decided_by,
            decided_at=existing_appr.decided_at.isoformat() if existing_appr.decided_at else None,
            created_at=existing_appr.created_at.isoformat() if existing_appr.created_at else None,
            provenance=ep.get("provenance") or {},
        )

        n5_note = "Follow-up Email Draft: Ready / Awaiting Review • Meeting Prep: Pending • Calendar Prep Block: Pending"
        if existing_appr.status == "approved":
            n5_note = "Follow-up Email Draft: Approved (Sending Deferred) • Meeting Prep: Pending • Calendar Prep Block: Pending"
        elif existing_appr.status == "snoozed":
            n5_note = f"Follow-up Email Draft: Snoozed ({ep.get('snoozed_until') or 'later'}) • Meeting Prep: Pending • Calendar Prep Block: Pending"
        elif existing_appr.status == "discarded":
            n5_note = "Follow-up Email Draft: Discarded • Meeting Prep: Pending • Calendar Prep Block: Pending"

        nodes_status = [
            PipelineNodeStatus(id="n1", title="Conversation Capture", status="completed", implemented=True, note="Audio recording and metadata preserved successfully."),
            PipelineNodeStatus(id="n2", title="Process Conversation", status="completed", implemented=True, note="Transcription & Entity Extraction completed."),
            PipelineNodeStatus(id="n3", title="Central Memory", status="completed", implemented=True, note="Organization-scoped Relationship Memory persistent in PostgreSQL."),
            PipelineNodeStatus(id="n4", title="Action Generator", status="completed", implemented=True, note="Action items active and persisted in Action Center."),
            PipelineNodeStatus(id="n5", title="Follow-up & Meeting Prep", status="partial", implemented=True, note=n5_note),
        ]

        return FollowupDraftResponse(
            instance_id=str(instance_uuid),
            workflow_name="meeting_intelligence_followup",
            status=existing_appr.status,
            current_node="n5",
            draft=draft_item,
            nodes=nodes_status,
            message="Existing follow-up email draft retrieved from Action Center (Idempotent reuse).",
            idempotent_reused=True,
        )

    # ── 2. Gather Context for New Draft ────────────────────────────────────────
    capture_data = ctx.get("conversation_capture") or workflow_inst.trigger_payload or {}
    node2_data = ctx.get("node2_process_conversation") or {}
    node3_data = ctx.get("node3_central_memory") or {}
    extraction_data = node2_data.get("extraction") or {}

    contact_name = capture_data.get("contact_name") or "Contact"
    conv_title = capture_data.get("conversation_title") or "Meeting"
    conv_date = capture_data.get("conversation_date") or ""
    summary = extraction_data.get("summary") or ""

    # Contact Email Resolution (Strict Anti-Hallucination)
    recipient_email = None
    recipient_email_available = False
    contact_id_str = node3_data.get("contact_id")
    if contact_id_str:
        try:
            stmt_c = select(RelationshipContact).where(RelationshipContact.id == uuid.UUID(contact_id_str))
            res_c = await db.execute(stmt_c)
            contact_entity = res_c.scalars().first()
            if contact_entity:
                c_meta = getattr(contact_entity, "metadata_", {}) or {}
                c_email = getattr(contact_entity, "email", None) or c_meta.get("email") or c_meta.get("primary_email")
                if c_email:
                    recipient_email = str(c_email).strip()
                    recipient_email_available = bool(recipient_email)
        except Exception:
            pass

    if not recipient_email and capture_data.get("contact_email"):
        recipient_email = str(capture_data.get("contact_email")).strip()
        recipient_email_available = bool(recipient_email)

    our_cmts = list(node4_data.get("our_commitments") or [])
    contact_cmts = list(node4_data.get("contact_commitments") or [])
    ai_suggs = list(node4_data.get("ai_suggestions") or [])
    open_q = list(node4_data.get("open_questions") or [])

    if not our_cmts and not contact_cmts and not ai_suggs:
        stmt_a = select(ApprovalItem).where(
            ApprovalItem.organization_id == org_uuid,
            ApprovalItem.instance_id == instance_uuid,
            ApprovalItem.node_id == "n4",
        )
        res_a = await db.execute(stmt_a)
        for it in res_a.scalars().all():
            ip = it.payload or {}
            at = ip.get("action_type")
            act_d = {
                "action": ip.get("action") or it.reason,
                "due_date": ip.get("due_date"),
                "due_date_display": ip.get("due_date_display"),
                "reason": ip.get("reason"),
            }
            if at == "our_commitment":
                our_cmts.append(act_d)
            elif at == "contact_commitment":
                contact_cmts.append(act_d)
            elif at == "ai_suggestion":
                ai_suggs.append(act_d)

    # ── 3. LLM Draft Generation ───────────────────────────────────────────────
    our_cmts_text = "\n".join([f"- {c['action']} (Due: {c.get('due_date_display') or c.get('due_date') or 'No due date'})" for c in our_cmts]) or "None"
    contact_cmts_text = "\n".join([f"- {c['action']} (Due: {c.get('due_date_display') or c.get('due_date') or 'No due date'})" for c in contact_cmts]) or "None"
    ai_suggs_text = "\n".join([f"- {s['action']}: {s.get('reason', '')}" for s in ai_suggs]) or "None"
    open_q_text = "\n".join([f"- {q['question'] if isinstance(q, dict) else str(q)}" for q in open_q]) or "None"

    system_prompt = """You are an executive assistant for SMBFlow generating a concise, professional follow-up email draft following a business meeting.

CRITICAL INSTRUCTIONS:
1. Greet the contact naturally by their first name (or full name if first name is ambiguous).
2. Briefly acknowledge the conversation and its purpose.
3. Summarize the agreed next steps clearly and concisely:
   - Explicitly confirm OUR commitments (what we promised to do and when).
   - Politely acknowledge any CONTACT commitments (what the contact agreed to provide or look into).
4. Strictly distinguish AGREED COMMITMENTS from AI SUGGESTIONS:
   - AGREED COMMITMENTS: These are confirmed promises made by the participants. State them clearly.
   - AI SUGGESTIONS: These are unconfirmed recommendations. You may mention them optionally as polite ideas/proposals for next steps, but NEVER present them as something already agreed to or decided in the meeting.
5. End with a warm, natural sign-off.
6. ABSOLUTE PROHIBITIONS:
   - Do NOT invent email addresses, companies, roles, dates, promises, attachments, or facts not in the context.
   - Do NOT write a generic, fluffy AI essay. Keep it brief, professional, and directly actionable (2-4 short paragraphs maximum).
7. Output STRICT JSON with two keys:
   {
     "subject": "Clear, professional subject line",
     "body": "Complete email body including greeting and sign-off"
   }
"""

    user_prompt = f"""CONTEXT:
- Contact Name: {contact_name}
- Conversation Title: {conv_title}
- Conversation Date: {conv_date}
- Conversation Summary: {summary}

AGREED COMMITMENTS MADE BY US:
{our_cmts_text}

AGREED COMMITMENTS MADE BY CONTACT:
{contact_cmts_text}

UNRESOLVED OPEN QUESTIONS:
{open_q_text}

AI SUGGESTED ACTIONS (UNCONFIRMED - NOT agreed promises):
{ai_suggs_text}

Generate the concise professional follow-up email draft in strict JSON format."""

    draft_subject = ""
    draft_body = ""
    model_used = "deterministic_fallback"
    cost_usd = 0.0
    tokens_in = 0
    tokens_out = 0

    try:
        llm = LLMRouter()
        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt),
        ]
        raw_resp, record = await llm.call(
            agent_name="drafting_agent",
            messages=messages,
            tier_override="balanced",
        )
        if record:
            model_used = getattr(record, "model", None) or getattr(record, "model_used", None) or "balanced"
            cost_usd = getattr(record, "cost_usd", 0.0) or 0.0
            tokens_in = getattr(record, "tokens_in", 0) or 0
            tokens_out = getattr(record, "tokens_out", 0) or 0

        cleaned = (raw_resp or "").strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        parsed = json.loads(cleaned.strip())
        draft_subject = (parsed.get("subject") or "").strip()
        draft_body = (parsed.get("body") or "").strip()
    except Exception as e:
        log.warning("LLM follow-up drafting failed or returned non-JSON; using deterministic grounded generator", error=str(e))

    if not draft_subject or not draft_body:
        det_draft = _build_deterministic_followup_draft(
            contact_name=contact_name,
            conv_title=conv_title,
            summary=summary,
            our_commitments=our_cmts,
            contact_commitments=contact_cmts,
            ai_suggestions=ai_suggs,
            open_questions=open_q,
        )
        draft_subject = draft_subject or det_draft["subject"]
        draft_body = draft_body or det_draft["body"]

    # ── 4. Persist ApprovalItem in PostgreSQL ──────────────────────────────────
    draft_id = uuid.uuid4()
    draft_payload = {
        "subject": draft_subject,
        "body": draft_body,
        "recipient_name": contact_name,
        "recipient_email": recipient_email,
        "recipient_email_available": recipient_email_available,
        "contact_id": contact_id_str,
        "conversation_title": conv_title,
        "conversation_date": conv_date,
        "workflow_key": "meeting_intelligence_followup",
        "our_commitments_count": len(our_cmts),
        "contact_commitments_count": len(contact_cmts),
        "ai_suggestions_count": len(ai_suggs),
        "open_questions_count": len(open_q),
        "original_generated_subject": draft_subject,
        "original_generated_body": draft_body,
        "original_subject": draft_subject,
        "original_body": draft_body,
        "model_used": model_used,
        "provenance": {
            "workflow_instance_id": str(instance_uuid),
            "contact_name": contact_name,
            "our_commitments": our_cmts,
            "contact_commitments": contact_cmts,
            "ai_suggestions": ai_suggs,
        },
    }

    new_appr = ApprovalItem(
        id=draft_id,
        organization_id=org_uuid,
        instance_id=instance_uuid,
        node_id="n5",
        review_type="followup_email_draft",
        status="awaiting_review",
        reason=f"Follow-up email draft for {contact_name} regarding {conv_title}",
        context_brief=f"Draft email based on {conv_title}. Awaiting human review before sending.",
        payload=draft_payload,
        created_at=datetime.utcnow(),
    )
    db.add(new_appr)

    # ── 5. Update WorkflowInstance Context ────────────────────────────────────
    updated_ctx = dict(workflow_inst.context or {})
    updated_ctx["node5_followup_draft"] = {
        "draft_id": str(draft_id),
        "status": "awaiting_review",
        "subject": draft_subject,
        "body": draft_body,
        "recipient_name": contact_name,
        "recipient_email": recipient_email,
        "recipient_email_available": recipient_email_available,
        "contact_id": contact_id_str,
        "generated_at": datetime.utcnow().isoformat(),
        "model_used": model_used,
    }
    workflow_inst.context = updated_ctx
    workflow_inst.current_node = "n5"

    duration_ms = int((time.perf_counter() - start_time) * 1000)

    # ── 6. AgentRunRecord & AuditEvent Observability ──────────────────────────
    agent_record = AgentRunRecord(
        id=uuid.uuid4(),
        instance_id=instance_uuid,
        node_id="n5",
        agent_capability="followup_email_drafting",
        status="completed",
        cost_usd=cost_usd,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        model_used=model_used,
        duration_ms=duration_ms,
        completed_at=datetime.utcnow(),
        tools_used=["llm_router", "approval_items"],
    )
    db.add(agent_record)

    actor_str = str(getattr(current_user, "email", None) or getattr(current_user, "user_id", "system"))
    audit_event = AuditEvent(
        id=uuid.uuid4(),
        organization_id=org_uuid,
        actor_id=actor_str,
        action="followup_email_draft_generated",
        entity_type="approval_item",
        entity_id=str(draft_id),
        metadata_={
            "workflow_instance_id": str(instance_uuid),
            "contact_name": contact_name,
            "recipient_email": recipient_email,
            "recipient_email_available": recipient_email_available,
            "subject": draft_subject,
            "status": "awaiting_review",
            "model_used": model_used,
            "sending_executed": False,
        },
        created_at=datetime.utcnow(),
    )
    db.add(audit_event)

    await db.commit()

    draft_item = FollowupDraftItem(
        id=str(draft_id),
        approval_id=str(draft_id),
        instance_id=str(instance_uuid),
        review_type="followup_email_draft",
        status="awaiting_review",
        subject=draft_subject,
        body=draft_body,
        recipient_name=contact_name,
        recipient_email=recipient_email,
        recipient_email_available=recipient_email_available,
        contact_id=contact_id_str,
        conversation_title=conv_title,
        our_commitments_count=len(our_cmts),
        contact_commitments_count=len(contact_cmts),
        ai_suggestions_count=len(ai_suggs),
        open_questions_count=len(open_q),
        original_generated_subject=draft_subject,
        original_generated_body=draft_body,
        original_subject=draft_subject,
        original_body=draft_body,
        model_used=model_used,
        created_at=new_appr.created_at.isoformat(),
        provenance=draft_payload["provenance"],
    )

    nodes_status = [
        PipelineNodeStatus(id="n1", title="Conversation Capture", status="completed", implemented=True, note="Audio recording and metadata preserved successfully."),
        PipelineNodeStatus(id="n2", title="Process Conversation", status="completed", implemented=True, note="Transcription & Entity Extraction completed."),
        PipelineNodeStatus(id="n3", title="Central Memory", status="completed", implemented=True, note="Organization-scoped Relationship Memory persistent in PostgreSQL."),
        PipelineNodeStatus(id="n4", title="Action Generator", status="completed", implemented=True, note="Action items active and persisted in Action Center."),
        PipelineNodeStatus(id="n5", title="Follow-up & Meeting Prep", status="partial", implemented=True, note="Follow-up Email Draft: Ready / Awaiting Review • Meeting Prep: Pending • Calendar Prep Block: Pending"),
    ]

    return FollowupDraftResponse(
        instance_id=str(instance_uuid),
        workflow_name="meeting_intelligence_followup",
        status="awaiting_review",
        current_node="n5",
        draft=draft_item,
        nodes=nodes_status,
        message="Follow-up email draft generated successfully and awaiting human review in Action Center.",
        idempotent_reused=False,
    )


@router.post("/followup-draft/{draft_id}/action", response_model=FollowupDraftActionResponse)
async def action_followup_draft(
    draft_id: str,
    req: FollowupDraftActionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_any_auth),
):
    """
    Node 5A: Execute Human-in-the-Loop review actions on a Follow-up Email Draft.
    Supported actions:
    - approve: Mark draft as approved for later sending. STRICTLY DOES NOT SEND EMAIL.
    - edit: Modify subject and body, retaining original text and keeping status awaiting_review.
    - snooze: Mark draft as snoozed with snooze timestamp and reason.
    - discard: Mark draft as discarded.
    """
    org_uuid = await _resolve_org_uuid(current_user, db)
    action_req = req
    if not action_req:
        raise HTTPException(status_code=400, detail="Missing action request payload.")

    try:
        draft_uuid = uuid.UUID(draft_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid draft_id format.")

    stmt = select(ApprovalItem).where(ApprovalItem.id == draft_uuid)
    res = await db.execute(stmt)
    appr = res.scalars().first()
    if not appr:
        raise HTTPException(status_code=404, detail="Follow-up email draft not found.")

    if appr.organization_id != org_uuid:
        raise HTTPException(status_code=403, detail="Access denied: review draft belongs to another organization.")

    action_type = action_req.action.lower().strip()
    if action_type not in ("approve", "edit", "snooze", "discard"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action '{action_req.action}'. Must be one of: approve, edit, snooze, discard."
        )

    actor_str = str(getattr(current_user, "email", None) or getattr(current_user, "user_id", "human_reviewer"))
    payload = dict(appr.payload or {})
    msg = ""

    if action_type == "approve":
        appr.status = "approved"
        appr.decided_by = actor_str
        appr.decided_at = datetime.utcnow()
        payload["approved_at"] = appr.decided_at.isoformat()
        payload["approved_by"] = actor_str
        if action_req.notes:
            payload["decision_notes"] = action_req.notes
        # Safe test mode execution boundary — zero email sending side effects
        msg = "Follow-up email draft approved. Draft preserved for later sending."

    elif action_type == "edit":
        if not action_req.subject or not action_req.subject.strip():
            raise HTTPException(status_code=400, detail="Subject cannot be empty for edit action.")
        if not action_req.body or not action_req.body.strip():
            raise HTTPException(status_code=400, detail="Body cannot be empty for edit action.")

        orig_s = payload.get("original_generated_subject") or payload.get("original_subject") or payload.get("subject")
        orig_b = payload.get("original_generated_body") or payload.get("original_body") or payload.get("body")
        payload["original_generated_subject"] = orig_s
        payload["original_generated_body"] = orig_b
        payload["original_subject"] = orig_s
        payload["original_body"] = orig_b

        payload["subject"] = action_req.subject.strip()
        payload["body"] = action_req.body.strip()
        payload["edited_at"] = datetime.utcnow().isoformat()
        payload["edited_by"] = actor_str
        if action_req.notes:
            payload["edit_notes"] = action_req.notes
        appr.status = "awaiting_review"
        msg = "Follow-up email draft updated successfully and remains in review."

    elif action_type == "snooze":
        appr.status = "snoozed"
        appr.decided_by = actor_str
        appr.decided_at = datetime.utcnow()
        snooze_val = action_req.snoozed_until or action_req.snooze_until or "later"
        reason_val = action_req.snooze_reason or action_req.snoozed_reason or action_req.notes
        payload["snoozed_until"] = snooze_val
        payload["snooze_reason"] = reason_val
        payload["snoozed_reason"] = reason_val
        payload["snoozed_at"] = appr.decided_at.isoformat()
        payload["snoozed_by"] = actor_str
        msg = f"Follow-up email draft snoozed ({payload['snoozed_until']})."

    elif action_type == "discard":
        appr.status = "discarded"
        appr.decided_by = actor_str
        appr.decided_at = datetime.utcnow()
        payload["discarded_at"] = appr.decided_at.isoformat()
        payload["discarded_by"] = actor_str
        if action_req.notes:
            payload["discard_reason"] = action_req.notes
        msg = "Follow-up email draft discarded."

    appr.payload = payload

    # Synchronize WorkflowInstance context if linked
    if appr.instance_id:
        stmt_w = select(WorkflowInstance).where(WorkflowInstance.id == appr.instance_id)
        res_w = await db.execute(stmt_w)
        w_inst = res_w.scalars().first()
        if w_inst:
            w_ctx = dict(w_inst.context or {})
            draft_ctx = dict(w_ctx.get("node5_followup_draft") or {})
            draft_ctx["status"] = appr.status
            draft_ctx["subject"] = payload.get("subject")
            draft_ctx["body"] = payload.get("body")
            draft_ctx["updated_at"] = datetime.utcnow().isoformat()
            if action_type == "snooze":
                draft_ctx["snoozed_until"] = payload.get("snoozed_until")
            w_ctx["node5_followup_draft"] = draft_ctx
            w_inst.context = w_ctx

    # Record AuditEvent for traceability
    audit_event = AuditEvent(
        id=uuid.uuid4(),
        organization_id=org_uuid,
        actor_id=actor_str,
        action=f"followup_draft_{action_type}",
        entity_type="approval_item",
        entity_id=str(draft_id),
        metadata_={
            "workflow_instance_id": str(appr.instance_id) if appr.instance_id else None,
            "action": action_type,
            "status": appr.status,
            "subject": payload.get("subject"),
            "email_sent": False,
        },
        created_at=datetime.utcnow(),
    )
    db.add(audit_event)

    await db.commit()
    await db.refresh(appr)

    # Optional Redis Pub/Sub broadcast
    try:
        from core.redis_pubsub import pubsub as redis_pubsub
        await redis_pubsub.publish_event("approval_decided", {
            "approval_id": str(appr.id),
            "status": appr.status,
            "action_chosen": action_type,
            "decided_by": appr.decided_by,
            "organization_id": str(appr.organization_id) if appr.organization_id else None,
        })
        await redis_pubsub.publish_event("followup_draft_updated", {
            "draft_id": str(appr.id),
            "instance_id": str(appr.instance_id) if appr.instance_id else None,
            "status": appr.status,
            "action": action_type,
            "decided_by": appr.decided_by,
            "organization_id": str(appr.organization_id) if appr.organization_id else None,
        })
    except Exception:
        pass

    draft_item = FollowupDraftItem(
        id=str(appr.id),
        approval_id=str(appr.id),
        instance_id=str(appr.instance_id) if appr.instance_id else "",
        review_type=appr.review_type or "followup_email_draft",
        status=appr.status,
        subject=payload.get("subject", ""),
        body=payload.get("body", ""),
        recipient_name=payload.get("recipient_name", ""),
        recipient_email=payload.get("recipient_email"),
        recipient_email_available=bool(payload.get("recipient_email_available", False)),
        contact_id=payload.get("contact_id"),
        conversation_title=payload.get("conversation_title"),
        our_commitments_count=payload.get("our_commitments_count", 0),
        contact_commitments_count=payload.get("contact_commitments_count", 0),
        ai_suggestions_count=payload.get("ai_suggestions_count", 0),
        open_questions_count=payload.get("open_questions_count", 0),
        original_generated_subject=payload.get("original_generated_subject"),
        original_generated_body=payload.get("original_generated_body"),
        original_subject=payload.get("original_generated_subject") or payload.get("original_subject"),
        original_body=payload.get("original_generated_body") or payload.get("original_body"),
        snoozed_until=payload.get("snoozed_until"),
        snooze_reason=payload.get("snooze_reason"),
        snoozed_reason=payload.get("snooze_reason"),
        model_used=payload.get("model_used"),
        decided_by=appr.decided_by,
        decided_at=appr.decided_at.isoformat() if appr.decided_at else None,
        created_at=appr.created_at.isoformat() if appr.created_at else None,
        provenance=payload.get("provenance") or {},
    )

    n5_note = "Follow-up Email Draft: Ready / Awaiting Review • Meeting Prep: Pending • Calendar Prep Block: Pending"
    if appr.status == "approved":
        n5_note = "Follow-up Email Draft: Approved (Sending Deferred) • Meeting Prep: Pending • Calendar Prep Block: Pending"
    elif appr.status == "snoozed":
        n5_note = f"Follow-up Email Draft: Snoozed ({payload.get('snoozed_until') or 'later'}) • Meeting Prep: Pending • Calendar Prep Block: Pending"
    elif appr.status == "discarded":
        n5_note = "Follow-up Email Draft: Discarded • Meeting Prep: Pending • Calendar Prep Block: Pending"

    nodes_status = [
        PipelineNodeStatus(id="n1", title="Conversation Capture", status="completed", implemented=True, note="Audio recording and metadata preserved successfully."),
        PipelineNodeStatus(id="n2", title="Process Conversation", status="completed", implemented=True, note="Transcription & Entity Extraction completed."),
        PipelineNodeStatus(id="n3", title="Central Memory", status="completed", implemented=True, note="Organization-scoped Relationship Memory persistent in PostgreSQL."),
        PipelineNodeStatus(id="n4", title="Action Generator", status="completed", implemented=True, note="Action items active and persisted in Action Center."),
        PipelineNodeStatus(id="n5", title="Follow-up & Meeting Prep", status="partial", implemented=True, note=n5_note),
    ]

    return FollowupDraftActionResponse(
        instance_id=str(appr.instance_id) if appr.instance_id else "",
        draft=draft_item,
        status=appr.status,
        action=action_type,
        message=msg,
        nodes=nodes_status,
    )
generate_followup_draft = process_followup_draft
handle_followup_draft_action = action_followup_draft
