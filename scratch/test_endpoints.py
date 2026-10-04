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

async def run_tests():
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

    print("=== TESTING FASTAPI ENDPOINTS WITH SUPABASE TOKEN ===")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Test 1: /api/v1/auth/me
        res_me = await client.get("/api/v1/auth/me", headers=headers)
        print("\n1. GET /api/v1/auth/me:")
        print("Status:", res_me.status_code)
        print("Response:", res_me.json() if res_me.status_code == 200 else res_me.text)

        user_data = res_me.json() if res_me.status_code == 200 else {}
        tenant_id = user_data.get("organization_id") or user_data.get("tenant_id")
        print("Resolved Tenant ID from /auth/me:", tenant_id)

        # Test 2: /api/v1/dashboard/{tenant_id}
        if tenant_id:
            res_dash = await client.get(f"/api/v1/dashboard/{tenant_id}", headers=headers)
            print(f"\n2. GET /api/v1/dashboard/{tenant_id}:")
            print("Status:", res_dash.status_code)
            print("Response:", res_dash.text[:200])

        # Test 3: /api/v1/connections/available
        res_avail = await client.get("/api/v1/connections/available", headers=headers)
        print("\n3. GET /api/v1/connections/available:")
        print("Status:", res_avail.status_code)
        print("Response:", res_avail.text[:200])

        # Test 4: /api/v1/connections
        res_conn = await client.get("/api/v1/connections", headers=headers)
        print("\n4. GET /api/v1/connections:")
        print("Status:", res_conn.status_code)
        print("Response:", res_conn.text[:200])

if __name__ == "__main__":
    asyncio.run(run_tests())
