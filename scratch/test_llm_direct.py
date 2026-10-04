import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import asyncio
from dotenv import load_dotenv
load_dotenv()
from core.llm_router import LLMRouter, LLMMessage

async def test_llm():
    router = LLMRouter()
    messages = [
        LLMMessage(role="system", content="You are a helpful assistant."),
        LLMMessage(role="user", content="Respond with valid JSON only: {\"status\": \"ok\"}")
    ]
    resp, call_record = await router.call(
        agent_name="reasoning_agent",
        messages=messages,
        tier_override="balanced"
    )
    print("Response:", resp)
    print("Call record:", call_record.model, call_record.provider, call_record.success, "cost:", call_record.cost_usd)

if __name__ == "__main__":
    asyncio.run(test_llm())
