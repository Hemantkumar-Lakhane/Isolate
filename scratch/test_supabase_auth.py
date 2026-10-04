import os
import dotenv
import urllib.request
import json
from jose import jwt

dotenv.load_dotenv()

supabase_url = os.getenv("SUPABASE_URL", "https://vyudjoaaqhtsqcwkjk.supabase.co")
anon_key = os.getenv("SUPABASE_ANON_KEY", "")
jwt_secret = os.getenv("SUPABASE_JWT_SECRET", "")

print("--- SUPABASE AUTH CONFIGURATION INSPECTION ---")
print(f"Supabase URL: {supabase_url}")
print(f"Anon Key Present: {bool(anon_key and anon_key != 'YOUR_SUPABASE_PUBLISHABLE_KEY')}")
print(f"JWT Secret Present: {bool(jwt_secret and jwt_secret != 'YOUR_SUPABASE_LEGACY_JWT_SECRET')}")

# Test fetching Supabase Auth public settings
try:
    req = urllib.request.Request(f"{supabase_url}/auth/v1/settings")
    if anon_key and anon_key != 'YOUR_SUPABASE_PUBLISHABLE_KEY':
        req.add_header("apikey", anon_key)
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        print("\n[SUPABASE AUTH SETTINGS]")
        print(f"Disable Signup: {data.get('disable_signup')}")
        print(f"External Providers: {data.get('external', {})}")
        google_enabled = data.get('external', {}).get('google', False)
        print(f"Google OAuth Enabled: {google_enabled}")
except Exception as e:
    print(f"\nCould not fetch /auth/v1/settings: {e}")
