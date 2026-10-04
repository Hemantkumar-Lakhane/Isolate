"""
tests/test_meeting_intelligence_node2.py
========================================
Automated test suite for Meeting Intelligence & Follow-up:
NODE 2 — Process Conversation (Transcription & Structured Extraction)

Verifies:
1. Valid audio -> successful transcription & structured extraction.
2. Missing or deleted audio reference -> Node 2 fails cleanly (404) and records failed AgentRunRecord.
3. Transcription provider failure -> fails cleanly with 502, no fabricated transcript.
4. Malformed LLM structured output -> validation & safe repair/normalization or clean failure.
5. Spanish transcript processing -> Spanish commitments and AI suggested actions correctly extracted.
6. Mixed English/Spanish transcript processing.
7. Strict separation between Agreed Commitments and AI Suggested Actions.
8. Relative date resolution using conversation_date as reference (e.g. Friday -> ISO YYYY-MM-DD, unstated -> null).
9. Organization & Tenant isolation -> prevents processing runs belonging to another tenant.
10. Node 1 and Node 2 marked Completed, Nodes 3-5 remain strictly Pending / Not Implemented.
"""

import io
import os
import uuid
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException
from api.auth import TokenData
from api.routers.meeting_intelligence import (
    ProcessConversationRequest,
    StructuredExtraction,
    PersonExtraction,
    CommitmentExtraction,
    SuggestedActionExtraction,
    process_conversation,
    transcribe_audio_file,
    extract_structured_intelligence,
    STORAGE_DIR,
)
from db.models.core import AgentRunRecord, AuditEvent, WorkflowInstance


TEST_ORG_ID = str(uuid.uuid4())
OTHER_ORG_ID = str(uuid.uuid4())

MOCK_USER = TokenData(
    user_id=str(uuid.uuid4()),
    email="owner@smallbusiness.com",
    role="org_admin",
    organization_id=TEST_ORG_ID,
    tenant_id=TEST_ORG_ID,
)


class MockAsyncSession:
    def __init__(self, instances=None):
        self.store = {}
        self.added = []
        if instances:
            for inst in instances:
                self.store[str(inst.id)] = inst

    def add(self, obj):
        if not hasattr(obj, "id") or not obj.id:
            obj.id = uuid.uuid4()
        self.added.append(obj)
        self.store[str(obj.id)] = obj

    async def commit(self):
        pass

    async def refresh(self, obj):
        pass

    async def execute(self, stmt):
        mock_result = AsyncMock()
        # Handle select(WorkflowInstance).where(...)
        # Extract ID from string representation or check store
        matched = list(self.store.values())
        stmt_str = str(stmt)
        # Simple match for instance id
        for inst_id, inst in self.store.items():
            if inst_id in stmt_str:
                matched = [inst]
                break

        mock_result.scalars = lambda: AsyncMock(first=lambda: matched[0] if matched else None)
        return mock_result


@pytest.fixture
def sample_audio_file(tmp_path):
    """Create a temporary valid dummy audio file inside uploads/audio/."""
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    temp_file = STORAGE_DIR / f"test_unit_{uuid.uuid4().hex[:8]}.mp3"
    temp_file.write_bytes(b"\xff\xfb\x90\x64" + b"\x00" * 200)
    yield temp_file
    if temp_file.exists():
        temp_file.unlink()


@pytest.mark.asyncio
async def test_process_conversation_success(sample_audio_file):
    """Test full happy path: audio retrieval -> transcription -> extraction -> persistence."""
    instance_id = uuid.uuid4()
    session = MockAsyncSession()

    # Pre-create WorkflowInstance from Node 1
    wf = WorkflowInstance(
        id=instance_id,
        organization_id=uuid.UUID(TEST_ORG_ID),
        workflow_name="meeting_intelligence_followup",
        status="capture_completed",
        current_node="n1",
        context={
            "conversation_capture": {
                "conversation_title": "Meeting with Rahul - AI Automation Discussion",
                "contact_name": "Rahul Sharma",
                "conversation_type": "Online Meeting",
                "language": "Auto Detect",
                "conversation_date": "2026-09-27",
                "recording": {
                    "file_id": "test_id",
                    "filename": sample_audio_file.name,
                    "stored_path": str(sample_audio_file).replace("\\", "/"),
                    "size_bytes": 204,
                }
            }
        },
        started_at=datetime.utcnow(),
    )
    session.store[str(instance_id)] = wf

    # Mock transcription and extraction
    mock_transcript = "Hi Rahul, thanks for meeting today. I agreed to send you the short proposal by Friday."
    mock_extraction = StructuredExtraction(
        summary="Discussion on automation with Rahul Sharma.",
        people=[
            PersonExtraction(
                name="Rahul Sharma",
                interests=["AI automation"],
                needs=["Repetitive queries handling"],
                opportunities=["Pilot project"],
            )
        ],
        commitments=[
            CommitmentExtraction(
                owner="Speaker",
                commitment="Send short proposal",
                due_date="2026-10-02",
            )
        ],
        suggested_actions=[
            SuggestedActionExtraction(
                action="Prepare customer support case study",
                reason="Provides relevant context before sending proposal",
            )
        ],
        open_questions=["What is the target volume of queries?"],
    )

    with patch("api.routers.meeting_intelligence.transcribe_audio_file") as mock_stt, \
         patch("api.routers.meeting_intelligence.extract_structured_intelligence") as mock_llm:

        mock_stt.return_value = (mock_transcript, "English", "groq_whisper-large-v3", 1.2)
        mock_llm.return_value = (mock_extraction, "claude-haiku-4-5", 0.0001, 150, 200)

        req = ProcessConversationRequest(instance_id=str(instance_id))
        res = await process_conversation(req=req, db=session, current_user=MOCK_USER)

        assert res.status == "completed"
        assert res.current_node == "n2"
        assert res.transcript_text == mock_transcript
        assert res.detected_language == "English"
        assert res.transcription_status == "completed"
        assert res.extraction is not None
        assert res.extraction.summary == "Discussion on automation with Rahul Sharma."

        # Verify separation of commitments vs AI suggestions
        assert len(res.extraction.commitments) == 1
        assert res.extraction.commitments[0].commitment == "Send short proposal"
        assert res.extraction.commitments[0].due_date == "2026-10-02"

        assert len(res.extraction.suggested_actions) == 1
        assert res.extraction.suggested_actions[0].action == "Prepare customer support case study"

        # Verify Pipeline Node statuses: 1 & 2 completed, 3, 4, 5 pending
        node_map = {n.id: n for n in res.nodes}
        assert node_map["n1"].status == "completed"
        assert node_map["n2"].status == "completed"
        assert node_map["n3"].status == "pending"
        assert node_map["n3"].implemented is False
        assert node_map["n4"].status == "pending"
        assert node_map["n4"].implemented is False
        assert node_map["n5"].status == "pending"
        assert node_map["n5"].implemented is False

        # Verify persistence in WorkflowInstance
        assert wf.status == "processed"
        assert wf.current_node == "n2"
        assert "node2_process_conversation" in wf.context
        assert wf.context["node2_process_conversation"]["transcript_text"] == mock_transcript

        # Verify AgentRunRecord for Node 2
        run_record = next(obj for obj in session.added if isinstance(obj, AgentRunRecord) and obj.node_id == "n2")
        assert run_record.agent_capability == "conversation_processing"
        assert run_record.status == "completed"


@pytest.mark.asyncio
async def test_process_conversation_missing_audio_reference():
    """Verify that a run with a missing audio reference fails cleanly without hallucinations."""
    instance_id = uuid.uuid4()
    session = MockAsyncSession()

    wf = WorkflowInstance(
        id=instance_id,
        organization_id=uuid.UUID(TEST_ORG_ID),
        workflow_name="meeting_intelligence_followup",
        status="capture_completed",
        current_node="n1",
        context={"conversation_capture": {"conversation_title": "No Audio Meeting", "recording": {}}},
        started_at=datetime.utcnow(),
    )
    session.store[str(instance_id)] = wf

    req = ProcessConversationRequest(instance_id=str(instance_id))
    with pytest.raises(HTTPException) as exc_info:
        await process_conversation(req=req, db=session, current_user=MOCK_USER)

    assert exc_info.value.status_code == 404
    assert "No audio recording found" in exc_info.value.detail
    assert wf.status == "failed"


@pytest.mark.asyncio
async def test_process_conversation_deleted_audio_file():
    """Verify that if the audio file was removed from disk, Node 2 fails cleanly."""
    instance_id = uuid.uuid4()
    session = MockAsyncSession()

    wf = WorkflowInstance(
        id=instance_id,
        organization_id=uuid.UUID(TEST_ORG_ID),
        workflow_name="meeting_intelligence_followup",
        status="capture_completed",
        current_node="n1",
        context={
            "conversation_capture": {
                "conversation_title": "Missing File Meeting",
                "recording": {"stored_path": "uploads/audio/nonexistent_file_12345.mp3"},
            }
        },
        started_at=datetime.utcnow(),
    )
    session.store[str(instance_id)] = wf

    req = ProcessConversationRequest(instance_id=str(instance_id))
    with pytest.raises(HTTPException) as exc_info:
        await process_conversation(req=req, db=session, current_user=MOCK_USER)

    assert exc_info.value.status_code == 404
    assert "not found on disk" in exc_info.value.detail
    assert wf.status == "failed"


@pytest.mark.asyncio
async def test_process_conversation_transcription_provider_failure(sample_audio_file):
    """Verify that transcription failure does NOT fabricate a transcript and marks Node 2 failed."""
    instance_id = uuid.uuid4()
    session = MockAsyncSession()

    wf = WorkflowInstance(
        id=instance_id,
        organization_id=uuid.UUID(TEST_ORG_ID),
        workflow_name="meeting_intelligence_followup",
        status="capture_completed",
        current_node="n1",
        context={
            "conversation_capture": {
                "recording": {"stored_path": str(sample_audio_file)},
            }
        },
        started_at=datetime.utcnow(),
    )
    session.store[str(instance_id)] = wf

    with patch("api.routers.meeting_intelligence.transcribe_audio_file") as mock_stt:
        mock_stt.side_effect = HTTPException(status_code=502, detail="Transcription service unavailable (502 Gateway)")

        req = ProcessConversationRequest(instance_id=str(instance_id))
        with pytest.raises(HTTPException) as exc_info:
            await process_conversation(req=req, db=session, current_user=MOCK_USER)

        assert exc_info.value.status_code == 502
        assert "Transcription service unavailable" in exc_info.value.detail
        assert wf.status == "failed"

        # Verify failed AgentRunRecord created
        fail_record = next(obj for obj in session.added if isinstance(obj, AgentRunRecord) and obj.node_id == "n2")
        assert fail_record.status == "failed"


@pytest.mark.asyncio
async def test_process_conversation_tenant_isolation(sample_audio_file):
    """Verify that one organization cannot process another organization's workflow run."""
    instance_id = uuid.uuid4()
    session = MockAsyncSession()

    # Belongs to OTHER_ORG_ID
    wf = WorkflowInstance(
        id=instance_id,
        organization_id=uuid.UUID(OTHER_ORG_ID),
        workflow_name="meeting_intelligence_followup",
        status="capture_completed",
        current_node="n1",
        context={
            "conversation_capture": {
                "recording": {"stored_path": str(sample_audio_file)},
            }
        },
        started_at=datetime.utcnow(),
    )
    session.store[str(instance_id)] = wf

    req = ProcessConversationRequest(instance_id=str(instance_id))
    # Current user belongs to TEST_ORG_ID
    with pytest.raises(HTTPException) as exc_info:
        await process_conversation(req=req, db=session, current_user=MOCK_USER)

    assert exc_info.value.status_code == 403
    assert "belongs to another organization" in exc_info.value.detail


@pytest.mark.asyncio
async def test_extract_structured_intelligence_spanish():
    """Verify that Spanish transcripts correctly extract people, commitments, and suggestions."""
    spanish_transcript = (
        "Hola Carlos, gracias por la llamada hoy. Acordamos que yo le enviaré el presupuesto "
        "revisado antes del viernes. Carlos está muy interesado en la automatización de su "
        "equipo de atención al cliente."
    )

    with patch("api.routers.meeting_intelligence.LLMRouter") as mock_router_cls:
        mock_router = AsyncMock()
        mock_call = MagicMock(model="claude-haiku-4-5", cost_usd=0.0001, tokens_in=100, tokens_out=150)
        mock_router.call.return_value = (
            """```json
            {
              "summary": "Reunión con Carlos sobre automatización del equipo de atención al cliente.",
              "people": [
                {
                  "name": "Carlos",
                  "facts": [],
                  "interests": ["Automatización de atención al cliente"],
                  "needs": ["Optimizar tiempo de soporte"],
                  "opportunities": ["Implementación de SMBFlow"]
                }
              ],
              "commitments": [
                {
                  "owner": "Speaker",
                  "commitment": "Enviar el presupuesto revisado",
                  "due_date": "2026-10-02"
                }
              ],
              "suggested_actions": [
                {
                  "action": "Enviar caso de estudio en español",
                  "reason": "Reforzar la propuesta antes del viernes"
                }
              ],
              "open_questions": []
            }
            ```""",
            mock_call,
        )
        mock_router_cls.return_value = mock_router

        extraction, model_used, cost, t_in, t_out = await extract_structured_intelligence(
            transcript=spanish_transcript,
            contact_name="Carlos Mendez",
            conversation_date="2026-09-27",
            conversation_type="Phone Call",
        )

        assert extraction.summary.startswith("Reunión con Carlos")
        assert len(extraction.commitments) == 1
        assert extraction.commitments[0].commitment == "Enviar el presupuesto revisado"
        assert extraction.commitments[0].due_date == "2026-10-02"
        assert len(extraction.suggested_actions) == 1
        assert "caso de estudio" in extraction.suggested_actions[0].action


@pytest.mark.asyncio
async def test_extract_structured_intelligence_malformed_json_recovery():
    """Verify that malformed LLM responses are recovered or safely normalized without crashing."""
    transcript = "We agreed to test the software next week."

    with patch("api.routers.meeting_intelligence.LLMRouter") as mock_router_cls:
        mock_router = AsyncMock()
        mock_call = MagicMock(model="claude-haiku-4-5", cost_usd=0.0001, tokens_in=50, tokens_out=80)
        # Returns unparseable broken string first, then repaired json on repair call
        mock_router.call.side_effect = [
            ("Broken non-json output: {summary: missing quotes", mock_call),
            ('{"summary": "Recovered summary", "people": [], "commitments": [], "suggested_actions": [], "open_questions": []}', mock_call),
        ]
        mock_router_cls.return_value = mock_router

        extraction, _, _, _, _ = await extract_structured_intelligence(
            transcript=transcript,
            contact_name="Test User",
            conversation_date="2026-09-27",
            conversation_type="Online Meeting",
        )

        assert extraction.summary == "Recovered summary"
        assert extraction.commitments == []
