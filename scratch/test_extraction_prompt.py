import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import asyncio
import json
from dotenv import load_dotenv
load_dotenv()
from core.llm_router import LLMRouter, LLMMessage

EXTRACTION_SYSTEM_PROMPT = """You are an expert conversation intelligence analyst for SMBFlow.
Your task is to analyze a professional conversation transcript and extract structured intelligence in STRICT JSON format.

RULES:
1. "commitments": Contain ONLY explicit promises and agreements made during the conversation by the participants.
   - Example: "I will send the proposal by Friday" -> {"owner": "Speaker", "commitment": "Send short proposal", "due_date": "2026-10-02"}
   - Do NOT include general ideas, suggestions, or advice in commitments.
2. "suggested_actions": Contain AI recommendations, strategic follow-ups, or best practices that were NOT explicitly promised.
   - Never confuse an agreed commitment with an AI suggested action.
3. "people": Extract key individuals mentioned or participating.
   - Include their facts, interests, needs, and opportunities mentioned in the conversation.
   - If contact_name is provided in context, use it accurately but do NOT invent false attributions.
4. "due_date": Use the provided conversation_date as reference to resolve relative dates (e.g. "tomorrow", "Friday", "next week") to ISO "YYYY-MM-DD". If uncertain or not stated, set due_date to null. Never invent dates.
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

async def test_extraction():
    transcript = "Hi Rahul, Thanks for meeting today we discussed using AI automation for customer support. Rahul is interested in automating repetitive customer queries and wants to explore a pilot project next month. I agreed to it. Send him a short proposal by Friday. We will schedule another meeting next week to discuss the implementation."
    conversation_date = "2026-09-27"
    contact_name = "Rahul Sharma"
    conversation_type = "Online Meeting"

    user_prompt = f"""CONVERSATION CONTEXT:
- Contact Name: {contact_name}
- Conversation Date: {conversation_date}
- Conversation Type: {conversation_type}

TRANSCRIPT:
\"\"\"
{transcript}
\"\"\"

Extract the structured intelligence following all rules and output strictly valid JSON."""

    messages = [
        LLMMessage(role="system", content=EXTRACTION_SYSTEM_PROMPT),
        LLMMessage(role="user", content=user_prompt),
    ]

    router = LLMRouter()
    resp, call = await router.call(
        agent_name="reasoning_agent",
        messages=messages,
        tier_override="balanced",
    )

    print("RAW RESPONSE:\n", resp)
    cleaned = resp.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    parsed = json.loads(cleaned)
    print("\nPARSED JSON:\n", json.dumps(parsed, indent=2))

if __name__ == "__main__":
    asyncio.run(test_extraction())
