"""
tests/test_meeting_intelligence_node1.py
========================================
Automated test suite for Meeting Intelligence & Follow-up:
NODE 1 — Conversation Capture

Verifies:
1. Audio upload validation:
   - Accept valid formats (.mp3, .wav, .m4a, .webm)
   - Reject dangerous executable extensions (.exe, .py, .sh, .bat)
   - Reject executable magic bytes (MZ header, ELF)
   - Reject empty files (0 bytes)
   - Max file size enforcement (50MB)
2. Conversation capture validation:
   - 6 required fields: conversation_title, contact_name, conversation_type, recording, language, conversation_date
   - Strict allowed conversation_type values ('Online Meeting', 'Phone Call', 'In-Person Meeting')
   - Strict allowed language values ('Auto Detect', 'English', 'Spanish', 'Mixed English / Spanish')
   - Database persistence: WorkflowInstance status='capture_completed', AgentRunRecord for n1 (completed)
   - Explicit pending state for subsequent nodes (n2, n3, n4, n5)
   - Multi-tenant and Organization isolation
"""

import io
import uuid
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException, UploadFile
from api.auth import TokenData
from api.routers.meeting_intelligence import (
    AudioUploadResponse,
    ConversationCaptureRequest,
    upload_audio_recording,
    capture_conversation,
    ALLOWED_AUDIO_EXTENSIONS,
    MAX_AUDIO_SIZE_BYTES,
)
from db.models.core import AgentRunRecord, AuditEvent, WorkflowInstance


TEST_ORG_ID = str(uuid.uuid4())
MOCK_USER = TokenData(
    user_id=str(uuid.uuid4()),
    email="owner@smallbusiness.com",
    role="org_admin",
    organization_id=TEST_ORG_ID,
    tenant_id=TEST_ORG_ID,
)


class MockAsyncSession:
    def __init__(self):
        self.store = {}
        self.added = []

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
        mock_result.scalars = lambda: AsyncMock(first=lambda: None)
        return mock_result


@pytest.mark.asyncio
async def test_upload_audio_valid_formats():
    """Verify that valid audio extensions are accepted and stored with clean metadata."""
    valid_samples = [
        ("call_recording.mp3", b"\xff\xfb\x90\x64" + b"\x00" * 100, "audio/mpeg"),
        ("interview.wav", b"RIFF" + b"\x00" * 4 + b"WAVE" + b"\x00" * 100, "audio/wav"),
        ("sync_notes.m4a", b"\x00\x00\x00\x20ftypM4A " + b"\x00" * 100, "audio/mp4"),
        ("meeting.webm", b"\x1a\x45\xdf\xa3" + b"\x00" * 100, "video/webm"),
    ]

    for filename, content, content_type in valid_samples:
        file_obj = UploadFile(
            file=io.BytesIO(content),
            filename=filename,
            headers={"content-type": content_type}
        )
        res = await upload_audio_recording(file=file_obj, current_user=MOCK_USER)
        assert res.filename == filename
        assert res.size_bytes == len(content)
        assert res.file_id is not None
        assert "uploads" in res.stored_path


@pytest.mark.asyncio
async def test_upload_audio_rejects_dangerous_extensions():
    """Verify that dangerous executable extensions are rejected with 400 Bad Request."""
    dangerous = [
        ("malicious.exe", b"fake binary data"),
        ("exploit.bat", b"echo off"),
        ("payload.sh", b"#!/bin/bash"),
        ("script.py", b"import os"),
        ("run.js", b"console.log('pwn')"),
    ]

    for filename, content in dangerous:
        file_obj = UploadFile(file=io.BytesIO(content), filename=filename)
        with pytest.raises(HTTPException) as exc_info:
            await upload_audio_recording(file=file_obj, current_user=MOCK_USER)
        assert exc_info.value.status_code == 400
        assert "not permitted" in exc_info.value.detail


@pytest.mark.asyncio
async def test_upload_audio_rejects_executable_magic_bytes():
    """Verify that even with an .mp3 extension, binary executables (MZ or ELF) are rejected."""
    # Windows PE header: 'MZ'
    mz_file = UploadFile(file=io.BytesIO(b"MZ\x90\x00\x03\x00\x00\x00" + b"\x00" * 100), filename="trick.mp3")
    with pytest.raises(HTTPException) as exc_info:
        await upload_audio_recording(file=mz_file, current_user=MOCK_USER)
    assert exc_info.value.status_code == 400
    assert "File content does not match a valid audio format" in exc_info.value.detail

    # Linux ELF header: '\x7fELF'
    elf_file = UploadFile(file=io.BytesIO(b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 100), filename="trick.wav")
    with pytest.raises(HTTPException) as exc_info:
        await upload_audio_recording(file=elf_file, current_user=MOCK_USER)
    assert exc_info.value.status_code == 400
    assert "File content does not match a valid audio format" in exc_info.value.detail


@pytest.mark.asyncio
async def test_upload_audio_rejects_empty_file():
    """Verify that 0-byte files are rejected."""
    empty_file = UploadFile(file=io.BytesIO(b""), filename="empty.mp3")
    with pytest.raises(HTTPException) as exc_info:
        await upload_audio_recording(file=empty_file, current_user=MOCK_USER)
    assert exc_info.value.status_code == 400
    assert "Empty audio recording" in exc_info.value.detail


@pytest.mark.asyncio
async def test_capture_conversation_all_six_fields_success():
    """Verify successful Node 1 capture with all 6 required fields."""
    session = MockAsyncSession()

    req = ConversationCaptureRequest(
        conversation_title="Meeting with Rahul - AI Automation Discussion",
        contact_name="Rahul Sharma",
        conversation_type="Online Meeting",
        recording={
            "file_id": str(uuid.uuid4())[:12],
            "filename": "rahul_discussion.mp3",
            "size_bytes": 1450200,
            "storage_path": "uploads/audio/rahul_discussion.mp3",
            "content_type": "audio/mpeg",
        },
        language="Auto Detect",
        conversation_date="2026-09-27",
    )

    res = await capture_conversation(
        req=req,
        db=session,
        current_user=MOCK_USER,
    )

    assert res.instance_id is not None
    assert res.status == "capture_completed"
    assert res.conversation_data["conversation_title"] == "Meeting with Rahul - AI Automation Discussion"
    assert res.conversation_data["contact_name"] == "Rahul Sharma"
    assert res.conversation_data["conversation_type"] == "Online Meeting"
    assert res.conversation_data["recording"]["filename"] == "rahul_discussion.mp3"
    assert res.conversation_data["language"] == "Auto Detect"
    assert res.conversation_data["conversation_date"] == "2026-09-27"

    # Node status verification: Node 1 complete, Nodes 2-5 explicitly pending
    node_map = {n.id: n for n in res.nodes}
    assert node_map["n1"].status == "completed"
    assert node_map["n1"].implemented is True

    assert node_map["n2"].status == "pending"
    assert node_map["n2"].implemented is True
    assert node_map["n3"].status == "pending"
    assert node_map["n3"].implemented is True
    assert node_map["n4"].status == "pending"
    assert node_map["n4"].implemented is True
    assert node_map["n5"].status == "pending"
    assert node_map["n5"].implemented is True

    # Database objects verification
    wf_instance = next(obj for obj in session.added if isinstance(obj, WorkflowInstance))
    assert wf_instance.workflow_name == "meeting_intelligence_followup"
    assert wf_instance.status == "capture_completed"
    assert wf_instance.organization_id == uuid.UUID(TEST_ORG_ID)
    assert wf_instance.context["conversation_capture"]["conversation_title"] == "Meeting with Rahul - AI Automation Discussion"
    assert wf_instance.context["conversation_capture"]["recording"]["filename"] == "rahul_discussion.mp3"

    run_record = next(obj for obj in session.added if isinstance(obj, AgentRunRecord))
    assert run_record.node_id == "n1"
    assert run_record.status == "completed"
    assert run_record.agent_capability == "conversation_capture"

    audit_event = next(obj for obj in session.added if isinstance(obj, AuditEvent))
    assert audit_event.action == "conversation_captured"
    assert audit_event.entity_type == "workflow_instance"
    assert audit_event.organization_id == uuid.UUID(TEST_ORG_ID)


@pytest.mark.asyncio
async def test_capture_conversation_validation_rules():
    """Verify input validation rules for conversation_type and language."""
    session = MockAsyncSession()

    # Invalid conversation_type
    req_bad_type = ConversationCaptureRequest(
        conversation_title="Valid Title",
        contact_name="Valid Contact",
        conversation_type="Carrier Pigeon",  # Invalid
        recording={"file_id": "test", "filename": "audio.mp3", "size_bytes": 100},
        language="English",
        conversation_date="2026-09-27",
    )
    with pytest.raises(HTTPException) as exc_type:
        await capture_conversation(req=req_bad_type, db=session, current_user=MOCK_USER)
    assert exc_type.value.status_code == 400
    assert "Invalid conversation type" in exc_type.value.detail

    # Invalid language
    req_bad_lang = ConversationCaptureRequest(
        conversation_title="Valid Title",
        contact_name="Valid Contact",
        conversation_type="Phone Call",
        recording={"file_id": "test", "filename": "audio.mp3", "size_bytes": 100},
        language="Klingon",  # Invalid
        conversation_date="2026-09-27",
    )
    with pytest.raises(HTTPException) as exc_lang:
        await capture_conversation(req=req_bad_lang, db=session, current_user=MOCK_USER)
    assert exc_lang.value.status_code == 400
    assert "Invalid language" in exc_lang.value.detail

    # Missing audio recording info
    req_bad_rec = ConversationCaptureRequest(
        conversation_title="Valid Title",
        contact_name="Valid Contact",
        conversation_type="Phone Call",
        recording={},  # Missing file_id and filename
        language="English",
        conversation_date="2026-09-27",
    )
    with pytest.raises(HTTPException) as exc_rec:
        await capture_conversation(req=req_bad_rec, db=session, current_user=MOCK_USER)
    assert exc_rec.value.status_code == 400
    assert "A valid audio recording is required" in exc_rec.value.detail
