import asyncio
import json
import os
import time
import urllib.request
import urllib.error
import dotenv
from jose import jwt
from fastapi.testclient import TestClient

dotenv.load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")

async def run_auth_tests():
    report = {
        "Signup": "FAIL",
        "Login": "FAIL",
        "Access token": "FAIL",
        "FastAPI JWT validation": "FAIL",
        "/me": "FAIL",
        "Role": "FAIL",
        "Organization context": "FAIL",
        "Protected routes": "FAIL",
        "Logout": "FAIL",
        "Invalid/expired token rejection": "FAIL",
        "Google OAuth readiness": "NOT READY",
        "failures": []
    }

    # Sanity check keys present
    if not SUPABASE_URL or not SUPABASE_ANON_KEY or SUPABASE_ANON_KEY.startswith("YOUR_"):
        report["failures"].append(("SUPABASE_ANON_KEY", "Key is missing or still placeholder in .env", ".env"))
        return report

    if not SUPABASE_JWT_SECRET or SUPABASE_JWT_SECRET.startswith("YOUR_"):
        report["failures"].append(("SUPABASE_JWT_SECRET", "Secret is missing or still placeholder in .env", ".env"))
        return report

    test_email = f"dev_test_{int(time.time())}@smbflow.com"
    test_password = "TestPassword123!"

    # 1. Supabase Signup
    signup_url = f"{SUPABASE_URL}/auth/v1/signup"
    signup_data = json.dumps({
        "email": test_email,
        "password": test_password,
        "data": {
            "full_name": "Dev Test User",
            "role": "org_user",
            "organization_id": "00000000-0000-0000-0000-000000000000"
        }
    }).encode("utf-8")

    signup_req = urllib.request.Request(signup_url, data=signup_data, method="POST")
    signup_req.add_header("apikey", SUPABASE_ANON_KEY)
    signup_req.add_header("Content-Type", "application/json")

    user_id = None
    access_token = None

    try:
        with urllib.request.urlopen(signup_req) as resp:
            resp_body = json.loads(resp.read().decode("utf-8"))
            user_id = resp_body.get("id") or resp_body.get("user", {}).get("id")
            access_token = resp_body.get("access_token")
            report["Signup"] = "PASS"
    except urllib.error.HTTPError as e:
        err_text = e.read().decode("utf-8")
        report["failures"].append(("Signup", f"Supabase Signup returned HTTP {e.code}: {err_text}", "Supabase Auth REST API"))
    except Exception as e:
        report["failures"].append(("Signup", f"Signup request error: {type(e).__name__}: {str(e)}", "Supabase Auth REST API"))

    # 2. Supabase Login
    login_url = f"{SUPABASE_URL}/auth/v1/token?grant_type=password"
    login_data = json.dumps({
        "email": test_email,
        "password": test_password
    }).encode("utf-8")

    login_req = urllib.request.Request(login_url, data=login_data, method="POST")
    login_req.add_header("apikey", SUPABASE_ANON_KEY)
    login_req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(login_req) as resp:
            resp_body = json.loads(resp.read().decode("utf-8"))
            access_token = resp_body.get("access_token")
            if access_token:
                report["Login"] = "PASS"
                report["Access token"] = "PASS"
            else:
                report["failures"].append(("Login", "Supabase login succeeded but no access_token in response", "Supabase Auth REST API"))
    except urllib.error.HTTPError as e:
        err_text = e.read().decode("utf-8")
        report["failures"].append(("Login", f"Supabase Login returned HTTP {e.code}: {err_text}", "Supabase Auth REST API"))
    except Exception as e:
        report["failures"].append(("Login", f"Login request error: {type(e).__name__}: {str(e)}", "Supabase Auth REST API"))

    # If login succeeded and access_token obtained, test FastAPI Bearer JWT validation & /me
    if access_token:
        # 3. FastAPI Bearer JWT validation
        try:
            from api.deps.auth import SUPABASE_JWT_SECRET as BACKEND_JWT_SECRET
            payload = jwt.decode(access_token, BACKEND_JWT_SECRET, algorithms=["HS256"], options={"verify_aud": False})
            report["FastAPI JWT validation"] = "PASS"
            
            # Check user role & organization context
            role = payload.get("role") or payload.get("user_metadata", {}).get("role")
            org_id = payload.get("organization_id") or payload.get("user_metadata", {}).get("organization_id")
            
            if role:
                report["Role"] = "PASS"
            else:
                report["failures"].append(("Role", "JWT token does not contain role claim", "api/deps/auth.py"))
                
            if org_id is not None:
                report["Organization context"] = "PASS"
            else:
                report["failures"].append(("Organization context", "JWT token does not contain organization_id claim", "api/deps/auth.py"))
        except Exception as e:
            report["failures"].append(("FastAPI JWT validation", f"JWT decode failed: {type(e).__name__}: {str(e)}", "api/deps/auth.py"))

        # 4. FastAPI TestClient for /me and protected routes
        try:
            from api.main import app
            client = TestClient(app)
            headers = {"Authorization": f"Bearer {access_token}"}
            
            # Test /me endpoint
            res_me = client.get("/api/v1/auth/me", headers=headers)
            if res_me.status_code == 200:
                report["/me"] = "PASS"
            else:
                report["failures"].append(("/me", f"/me endpoint returned HTTP {res_me.status_code}: {res_me.text}", "api/main.py"))

            # Test protected route
            res_protected = client.get("/api/v1/health", headers=headers)
            if res_protected.status_code == 200:
                report["Protected routes"] = "PASS"
            else:
                report["failures"].append(("Protected routes", f"Protected route returned HTTP {res_protected.status_code}", "api/main.py"))

        except Exception as e:
            report["failures"].append(("/me & Protected routes", f"FastAPI TestClient error: {type(e).__name__}: {str(e)}", "api/main.py"))

        # 5. Test Logout / Session clearing
        try:
            logout_url = f"{SUPABASE_URL}/auth/v1/logout"
            logout_req = urllib.request.Request(logout_url, method="POST")
            logout_req.add_header("apikey", SUPABASE_ANON_KEY)
            logout_req.add_header("Authorization", f"Bearer {access_token}")
            with urllib.request.urlopen(logout_req) as resp:
                if resp.status in (200, 204):
                    report["Logout"] = "PASS"
        except Exception as e:
            report["failures"].append(("Logout", f"Logout request error: {type(e).__name__}: {str(e)}", "Supabase Auth REST API"))

    # 6. Test Invalid/expired token rejection
    try:
        from api.main import app
        client = TestClient(app)
        res_invalid = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid.jwt.token"})
        if res_invalid.status_code == 401:
            report["Invalid/expired token rejection"] = "PASS"
        else:
            report["failures"].append(("Invalid/expired token rejection", f"Invalid token returned HTTP {res_invalid.status_code} instead of 401", "api/deps/auth.py"))
    except Exception as e:
        report["failures"].append(("Invalid/expired token rejection", f"Invalid token test error: {type(e).__name__}: {str(e)}", "api/deps/auth.py"))

    # 7. Check Google OAuth status
    try:
        settings_url = f"{SUPABASE_URL}/auth/v1/settings"
        settings_req = urllib.request.Request(settings_url)
        settings_req.add_header("apikey", SUPABASE_ANON_KEY)
        with urllib.request.urlopen(settings_req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            google_enabled = data.get("external", {}).get("google", False)
            report["Google OAuth readiness"] = "READY" if google_enabled else "NOT READY"
    except Exception as e:
        report["failures"].append(("Google OAuth readiness", f"Failed to fetch Auth settings: {type(e).__name__}: {str(e)}", "Supabase Auth REST API"))

    return report

if __name__ == "__main__":
    rep = asyncio.run(run_auth_tests())
    print("\n=================== PHASE 3 AUTH TEST REPORT ===================")
    for k, v in rep.items():
        if k != "failures":
            print(f"- {k}: {v}")
            
    if rep["failures"]:
        print("\n[EXACT CAUSE & FILES INVOLVED FOR FAILURES]")
        for item in rep["failures"]:
            print(f"  • Item: {item[0]}")
            print(f"    Cause: {item[1]}")
            print(f"    File/Module: {item[2]}")
    print("================================================================")
