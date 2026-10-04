"""
api/auth.py
===========
JWT-based authentication with Role-Based Access Control.
Roles: super_admin (full system access), tenant_user (tenant-scoped).

CONSTANT — do not modify for business customization.
"""

from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime, timedelta
from typing import Any, Optional

import bcrypt
import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

try:
    from dotenv import load_dotenv
    load_dotenv(override=False)
except ImportError:
    pass

log = structlog.get_logger()

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────

SECRET_KEY = os.getenv("SECRET_KEY", "opsgrid-dev-secret-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24h

def get_supabase_jwt_secret() -> str:
    raw_secret = os.getenv("SUPABASE_JWT_SECRET", "")
    return raw_secret if (raw_secret and not raw_secret.startswith("YOUR_")) else SECRET_KEY

security = HTTPBearer()


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic Models
# ─────────────────────────────────────────────────────────────────────────────

class TokenData(BaseModel):
    user_id: str
    email: str
    role: str
    tenant_id: Optional[str] = None
    organization_id: Optional[str] = None
    full_name: Optional[str] = None

    def model_post_init(self, __context: Any) -> None:
        if not self.organization_id and self.tenant_id:
            self.organization_id = self.tenant_id
        elif not self.tenant_id and self.organization_id:
            self.tenant_id = self.organization_id



class UserInDB(BaseModel):
    id: str
    email: str
    full_name: Optional[str]
    role: str
    tenant_id: Optional[str]
    is_active: bool


class LoginRequest(BaseModel):
    email: str
    password: str


class SignupRequest(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None
    tenant_name: Optional[str] = None   # Creates tenant if provided
    industry: Optional[str] = "saas"
    website: Optional[str] = None
    company_size: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


# ─────────────────────────────────────────────────────────────────────────────
# Password helpers
#
# Uses the ``bcrypt`` library directly rather than passlib's CryptContext.
# passlib 1.7.4 performs a backend self-probe on first use that is incompatible
# with bcrypt >= 4.1 (it reads ``bcrypt.__about__`` and hashes a >72-byte probe
# string), which raises at import/verify time under bcrypt 5.x. Calling bcrypt
# directly preserves identical semantics: the same 2b/2a/2y hashes verify, the
# same 72-byte truncation is applied, and the default work factor (12 rounds) is
# unchanged. Existing stored hashes remain valid; no credential is weakened.
# ─────────────────────────────────────────────────────────────────────────────

# bcrypt operates on the first 72 bytes of the UTF-8 encoded password; longer
# inputs are truncated (this matches passlib's prior behavior exactly).
_BCRYPT_MAX_BYTES = 72


def _to_bcrypt_bytes(password: str) -> bytes:
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_to_bcrypt_bytes(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(_to_bcrypt_bytes(plain), hashed.encode("utf-8"))
    except ValueError:
        # Malformed / unrecognized stored hash — treat as non-match, not a 500.
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Token helpers
# ─────────────────────────────────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode["exp"] = expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


_jwks_cache: dict[str, Any] = {"keys": None, "fetched_at": 0}


def get_supabase_jwks() -> Optional[dict]:
    """Fetch and cache Supabase Auth JWKS public keys."""
    import time
    now = time.time()
    if _jwks_cache["keys"] and (now - _jwks_cache["fetched_at"] < 3600):
        return _jwks_cache["keys"]

    supabase_url = os.getenv("SUPABASE_URL") or os.getenv("VITE_SUPABASE_URL")
    if not supabase_url:
        return None
    url = f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SMBFlow-Auth"})
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                _jwks_cache["keys"] = data
                _jwks_cache["fetched_at"] = now
                return data
    except Exception as e:
        log.debug("Failed to fetch Supabase JWKS", error=str(e))
    return None


def _verify_supabase_jwks(token: str) -> Optional[dict]:
    """
    Cryptographically verify Supabase Auth ES256/RS256 JWT signature using JWKS.
    """
    try:
        from jose import jwk
        header = jwt.get_unverified_header(token)
        alg = header.get("alg", "ES256")
        kid = header.get("kid")
        jwks = get_supabase_jwks()
        if not jwks or "keys" not in jwks:
            return None

        target_key = None
        if kid:
            for k in jwks["keys"]:
                if k.get("kid") == kid:
                    target_key = k
                    break
        if not target_key and jwks["keys"]:
            target_key = jwks["keys"][0]

        if not target_key:
            return None

        key_obj = jwk.construct(target_key, alg)
        return jwt.decode(
            token,
            key_obj,
            algorithms=[alg, "ES256", "RS256", "HS256"],
            options={"verify_aud": False}
        )
    except Exception as e:
        log.debug("Supabase JWKS signature verification skipped/failed", error=str(e))
        return None


def _verify_supabase_token_online(token: str) -> Optional[dict]:
    """
    Cryptographically validates a Supabase Auth Bearer token by querying the
    Supabase Auth server API endpoint (/auth/v1/user).
    
    The Supabase Auth server verifies the JWT signature and expiration against
    its internal signing keys. Returns the authenticated user object if valid,
    or None if the token is invalid, forged, or expired.
    """
    supabase_url = os.getenv("SUPABASE_URL") or os.getenv("VITE_SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_ANON_KEY") or os.getenv("VITE_SUPABASE_ANON_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not supabase_key:
        return None
    url = f"{supabase_url.rstrip('/')}/auth/v1/user"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "apikey": supabase_key,
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            if resp.status == 200:
                return json.loads(resp.read().decode("utf-8"))
    except Exception:
        pass
    return None


def decode_token(token: str) -> TokenData:
    """
    Strictly verifies and decodes a Bearer JWT access token.
    
    Verification hierarchy (ALL require cryptographic proof):
    1. Direct ES256/RS256 signature verification using Supabase JWKS
    2. Direct HMAC-SHA256 signature verification using SUPABASE_JWT_SECRET
    3. Direct HMAC-SHA256 signature verification using SECRET_KEY
    4. Server-side token validation against Supabase Auth API (/auth/v1/user)
    
    Unverified claims are NEVER accepted. Invalid or forged tokens return HTTP 401.
    """
    # 1. Attempt ES256/RS256 signature verification via Supabase JWKS
    payload = _verify_supabase_jwks(token)
    if payload:
        user_id = payload.get("sub") or payload.get("user_id")
        email = payload.get("email", f"{user_id}@smbflow.com")
        user_meta = payload.get("user_metadata") or {}
        role = payload.get("role") or user_meta.get("role", "org_user")
        if role == "super_admin":
            role = "platform_admin"
        elif role in ("tenant_user", "authenticated"):
            role = "org_user"
        org_id = payload.get("organization_id") or payload.get("tenant_id") or user_meta.get("organization_id") or user_meta.get("tenant_id")
        full_name = payload.get("full_name") or user_meta.get("full_name") or user_meta.get("name")
        return TokenData(
            user_id=str(user_id),
            email=email,
            role=role,
            organization_id=str(org_id) if org_id else None,
            tenant_id=str(org_id) if org_id else None,
            full_name=full_name,
        )

    key = get_supabase_jwt_secret()

    # 2. Attempt signature verification using SUPABASE_JWT_SECRET
    try:
        payload = jwt.decode(token, key, algorithms=["HS256", "ES256", "RS256"], options={"verify_aud": False})
        user_id = payload.get("sub") or payload.get("user_id")
        email = payload.get("email", "user@smbflow.com")
        role = payload.get("role") or payload.get("user_metadata", {}).get("role", "org_user")
        if role == "super_admin":
            role = "platform_admin"
        elif role in ("tenant_user", "authenticated"):
            role = "org_user"
        org_id = payload.get("organization_id") or payload.get("tenant_id") or payload.get("user_metadata", {}).get("organization_id")
        user_meta = payload.get("user_metadata") or {}
        full_name = payload.get("full_name") or user_meta.get("full_name") or user_meta.get("name")
        return TokenData(
            user_id=str(user_id),
            email=email,
            role=role,
            organization_id=str(org_id) if org_id else None,
            tenant_id=str(org_id) if org_id else None,
            full_name=full_name,
        )
    except JWTError:
        pass

    # 3. Attempt signature verification using local SECRET_KEY (if distinct from key)
    if key != SECRET_KEY:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256", "ES256", "RS256"], options={"verify_aud": False})
            role = payload.get("role", "org_user")
            if role == "super_admin":
                role = "platform_admin"
            org_id = payload.get("tenant_id") or payload.get("organization_id")
            user_meta = payload.get("user_metadata") or {}
            full_name = payload.get("full_name") or user_meta.get("full_name") or user_meta.get("name")
            return TokenData(
                user_id=str(payload["sub"]),
                email=payload.get("email") or payload.get("sub") or "user@smbflow.com",
                role=role,
                organization_id=str(org_id) if org_id else None,
                tenant_id=str(org_id) if org_id else None,
                full_name=full_name,
            )
        except JWTError:
            pass

    # 4. Server-side online validation against Supabase Auth API (/auth/v1/user)
    user_data = _verify_supabase_token_online(token)
    if user_data and user_data.get("id"):
        user_id = user_data["id"]
        email = user_data.get("email", f"{user_id}@smbflow.com")
        user_meta = user_data.get("user_metadata") or {}
        role = user_data.get("role") or user_meta.get("role", "org_user")
        if role == "super_admin":
            role = "platform_admin"
        elif role in ("tenant_user", "authenticated"):
            role = "org_user"
        org_id = user_meta.get("organization_id") or user_meta.get("tenant_id")
        full_name = user_meta.get("full_name") or user_meta.get("name")
        return TokenData(
            user_id=str(user_id),
            email=email,
            role=role,
            organization_id=str(org_id) if org_id else None,
            tenant_id=str(org_id) if org_id else None,
            full_name=full_name,
        )

    # All verification mechanisms failed — reject with 401 Unauthorized
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI Dependencies
# ─────────────────────────────────────────────────────────────────────────────

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> TokenData:
    """Extract and validate JWT from Authorization header and resolve canonical organization context."""
    user = decode_token(credentials.credentials)
    if not user.organization_id and (user.user_id or user.email):
        from api.deps.auth import _resolve_org_context
        db_org_id, db_role = await _resolve_org_context(user.user_id, user.email)
        if db_org_id:
            user.organization_id = db_org_id
            user.tenant_id = db_org_id
        if db_role and user.role == "org_user":
            user.role = db_role
    return user


async def require_admin(current_user: TokenData = Depends(get_current_user)) -> TokenData:
    """Require platform_admin or super_admin role."""
    if current_user.role not in ("platform_admin", "super_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform Admin access required",
        )
    return current_user



async def require_any_auth(current_user: TokenData = Depends(get_current_user)) -> TokenData:
    """Any authenticated user."""
    return current_user


def get_tenant_filter(current_user: TokenData) -> Optional[str]:
    """
    Returns tenant_id filter:
    - super_admin / platform_admin: None (can see everything across all organizations)
    - tenant_user: their tenant_id (scoped)
    """
    if current_user.role in ("super_admin", "platform_admin"):
        return None
    return current_user.tenant_id


def assert_tenant_access(current_user: TokenData, tenant_id: str) -> None:
    """Raise 403 if a tenant_user tries to access another tenant's data."""
    if current_user.role in ("platform_admin", "super_admin"):
        return
    if not tenant_id or str(tenant_id).lower() in ("me", "null", "undefined"):
        return
    user_org = current_user.organization_id or current_user.tenant_id
    # Allow if tenant_id matches the user's organization_id, tenant_id, or user_id
    allowed_ids = {str(i) for i in (user_org, current_user.user_id, current_user.tenant_id) if i}
    if allowed_ids and str(tenant_id) not in allowed_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this tenant's data",
        )


# ─────────────────────────────────────────────────────────────────────────────
# In-memory user store (replace with DB queries in production)
# Used alongside the DB — auth checks use this for fast lookups
# ─────────────────────────────────────────────────────────────────────────────

# This is populated by the API startup and updated on user creation
_user_cache: dict[str, dict] = {}


def cache_user(user_dict: dict) -> None:
    _user_cache[user_dict["email"]] = user_dict


def get_cached_user(email: str) -> Optional[dict]:
    return _user_cache.get(email)


def build_token_for_user(user: dict) -> str:
    return create_access_token({
        "sub": str(user["id"]),
        "email": user["email"],
        "role": user["role"],
        "tenant_id": str(user["tenant_id"]) if user.get("tenant_id") else None,
    })