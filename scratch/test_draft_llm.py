import sys
import os
sys.path.insert(0, os.path.abspath("."))
from dotenv import load_dotenv
load_dotenv()
import asyncio
import json
import uuid
from sqlalchemy import select
from core.database import AsyncSessionLocal
from db.models.core import WorkflowInstance, RelationshipContact, RelationshipConversation
from core.llm_router import LLMRouter, LLMMessage

async def test_llm():
    async with AsyncSessionLocal() as db:
        inst_id = uuid.UUID('c0eaf648-1fce-4f73-99ef-8f8e244c8659')
        stmt = select(WorkflowInstance).where(WorkflowInstance.id == inst_id)
        inst = (await db.execute(stmt)).scalar_one_or_none()
        if not inst:
            print("Instance not found!")
            return
        
        ctx = inst.context or {}
        n4 = ctx.get("node4_action_generator") or {}
        our_cmts = n4.get("our_commitments", [])
        contact_cmts = n4.get("contact_commitments", [])
        ai_suggs = n4.get("ai_suggestions", [])
        open_q = n4.get("open_questions", [])

        n2 = ctx.get("node2_process_conversation") or {}
        extraction = n2.get("extraction") or {}
        summary = extraction.get("summary", "")

        cc = ctx.get("conversation_capture") or {}
        contact_name = cc.get("contact_name", "Rahul Sharma")
        conv_title = cc.get("conversation_title", "")
        conv_date = cc.get("conversation_date", "")

        our_cmts_text = "\n".join([f"- {c['action']} (Due: {c.get('due_date_display') or c.get('due_date') or 'No due date'})" for c in our_cmts]) or "None"
        contact_cmts_text = "\n".join([f"- {c['action']} (Due: {c.get('due_date_display') or c.get('due_date') or 'No due date'})" for c in contact_cmts]) or "None"
        ai_suggs_text = "\n".join([f"- {s['action']}: {s.get('reason', '')}" for s in ai_suggs]) or "None"
        open_q_text = "\n".join([f"- {q['question'] if isinstance(q, dict) else str(q)}" for q in open_q]) or "None"

        print("=== PROMPT INPUTS ===")
        print("Contact:", contact_name)
        print("Our Commitments:", our_cmts_text)
        print("Contact Commitments:", contact_cmts_text)
        print("AI Suggestions:", ai_suggs_text)
        print("Open Questions:", open_q_text)

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

        llm = LLMRouter()
        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt),
        ]

        print("\nCalling LLMRouter with drafting_agent...")
        raw_resp, record = await llm.call(
            agent_name="drafting_agent",
            messages=messages,
            tier_override="balanced",
        )
        print("\n=== RAW LLM RESPONSE ===")
        print(raw_resp)

        cleaned = raw_resp.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        parsed = json.loads(cleaned.strip())
        print("\n=== PARSED DRAFT ===")
        print("SUBJECT:", parsed.get("subject"))
        print("BODY:\n", parsed.get("body"))

if __name__ == '__main__':
    asyncio.run(test_llm())
