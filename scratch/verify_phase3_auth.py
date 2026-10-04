import os
import dotenv
import urllib.request
import urllib.error
import json
import asyncio
from jose import jwt

dotenv.load_dotenv()

supabase_url = os.getenv("SUPABASE_URL", "https://vyudjoaaqhtqstqcwkjk.supabase.co")
anon_key = os.getenv("SUPABASE_ANON_KEY", "")
jwt_secret = os.getenv("SUPABASE_JWT_SECRET", "")

async def verify_auth_phase():
    results = {
        "AUTH": "FAILURE",
        "SIGNUP": "FAILURE",
        "LOGIN": "FAILURE",
        "JWT_TO_FASTAPI": "FAILURE",
        "ME_ENDPOINT": "FAILURE",
        "ROLE_ORG": "FAILURE",
        "LOGOUT": "FAILURE",
        "GOOGLE_OAUTH": "NOT CONFIGURED",
        "errors": []
    }

    # 1. Check keys presence
    if not anon_key or anon_key == "YOUR_SUPABASE_PUBLISHABLE_KEY":
        results["errors"].append("SUPABASE_ANON_KEY is not configured in .env (currently default placeholder).")
    
    if not jwt_secret or jwt_secret == "YOUR_SUPABASE_LEGACY_JWT_SECRET":
        results["errors"].append("SUPABASE_JWT_SECRET is not configured in .env (currently default placeholder).")

    if results["errors"]:
        print("--- PHASE 3 AUTHENTICATION AUDIT REPORT ---")
        for k, v in results.items():
            if k != "errors":
                print(f"{k}: {v}")
        print("\n[EXACT NON-SECRET ERRORS]")
        for err in results["errors"]:
            print(f"  - {err}")
        return

    # Fetch settings if keys present
    try:
        req = urllib.request.Request(f"{supabase_url}/auth/v1/settings")
        req.add_header("apikey", anon_key)
        with urllib.request.urlopen(req) as resp:
            settings_data = json.loads(resp.read().decode('utf-8'))
            google_enabled = settings_data.get("external", {}).get("google", False)
            results["GOOGLE_OAUTH"] = "CONFIGURED" if google_enabled else "NOT CONFIGURED"
    except Exception as e:
        results["errors"].append(f"Failed to fetch Supabase Auth settings: {type(e).__name__}: {str(e)}")

    print("--- PHASE 3 AUTHENTICATION AUDIT REPORT ---")
    for k, v in results.items():
        if k != "errors":
            print(f"{k}: {v}")
    print("\n[EXACT NON-SECRET ERRORS]")
    for err in results["errors"]:
        print(f"  - {err}")

if __name__ == "__main__":
    asyncio.run(verify_auth_phase())
