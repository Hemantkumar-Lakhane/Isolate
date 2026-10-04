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

    print("=== AUDITING ALL APP SHELL & PAGE ENDPOINTS ===", flush=True)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. /auth/me
        res_me = await client.get("/api/v1/auth/me", headers=headers)
        print("\n1. GET /api/v1/auth/me:", res_me.status_code, flush=True)
        user_data = res_me.json() if res_me.status_code == 200 else {}
        tid = user_data.get("organization_id") or user_data.get("tenant_id")
        print("   Resolved Tenant ID:", tid, flush=True)

        # 2. AppShell endpoints
        endpoints = [
            ("/api/v1/escalations?status=pending", "GET"),
            ("/api/v1/a2a/requests", "GET"),
            (f"/api/v1/tenants/{tid}/email-queue?status=pending", "GET"),
            (f"/api/v1/tenants/{tid}/patterns?status=pending_review", "GET"),
            (f"/api/v1/dashboard/{tid}", "GET"),
            ("/api/v1/connections/available", "GET"),
            ("/api/v1/connections", "GET"),
        ]

        for path, method in endpoints:
            try:
                res = await client.request(method, path, headers=headers)
                print(f"-> {method} {path} => Status: {res.status_code}", flush=True)
                if res.status_code != 200:
                    print("   Body:", res.text[:200], flush=True)
            except Exception as e:
                print(f"-> {method} {path} => EXCEPTION: {e}", flush=True)

if __name__ == "__main__":
    asyncio.run(run_tests())
