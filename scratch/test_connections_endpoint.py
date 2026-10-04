import os
import sys
import json
import asyncio
from jose import jwt
from dotenv import load_dotenv

load_dotenv(override=True)
sys.path.insert(0, os.getcwd())

import httpx
from api.main import app
from api.auth import get_supabase_jwt_secret

async def run_test():
    jwt_secret = get_supabase_jwt_secret()

    supabase_payload = {
      "iss": "supabase",
      "sub": "5b80d106-cac7-4711-b891-34d51548da10",
      "aud": "authenticated",
      "exp": 1888950000,
      "iat": 1788910000,
      "email": "lakhanehemant@gmail.com",
      "app_metadata": {
        "provider": "google",
        "providers": ["google"]
      },
      "user_metadata": {
        "full_name": "hemant lakhane"
      },
      "role": "authenticated"
    }

    supabase_token = jwt.encode(supabase_payload, jwt_secret, algorithm="HS256")
    headers = {"Authorization": f"Bearer {supabase_token}"}

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Test GET /api/v1/connections/available
        r1 = await client.get("/api/v1/connections/available", headers=headers)
        print("GET /api/v1/connections/available status:", r1.status_code, r1.text[:200])

        # Test GET /api/v1/connections
        r2 = await client.get("/api/v1/connections", headers=headers)
        print("GET /api/v1/connections status:", r2.status_code, r2.text[:200])

if __name__ == "__main__":
    asyncio.run(run_test())
