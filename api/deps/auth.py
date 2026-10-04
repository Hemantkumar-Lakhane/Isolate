"""
api/deps/auth.py
================
Supabase Auth Bearer Token validation and Organization & Role resolution.
Supports roles: platform_admin, org_admin, org_user.
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Optional

import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from api.auth import TokenData, SECRET_KEY, ALGORITHM

try:
    from dotenv import load_dotenv
    load_dotenv(override=False)
except ImportError:
    pass

log = structlog.get_logger()
security = HTTPBearer(auto_error=False)


def _verify_supabase_token_online(token: str) -> Optional[dict]:
    """
    Cryptographically validates a Supabase Auth Bearer token by querying the
    Supabase Auth server API endpoint (/auth/v1/user).
    Returns the authenticated user object if valid, or None if invalid/expired.
    """
    supabase_url = os.getenv("SUPABASE_URL") or os.getenv("VITE_SUPABASE_URL")
    supabase_key = (
        os.getenv("SUPABASE_ANON_KEY")
        or os.getenv("VITE_SUPABASE_ANON_KEY")
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    )
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

def get_supabase_jwt_secret() -> str:
    raw = os.getenv("SUPABASE_JWT_SECRET", "")
    if raw and not raw.startswith("YOUR_"):
        return raw
    return SECRET_KEY

SUPABASE_JWT_SECRET = get_supabase_jwt_secret()

async def _resolve_org_context(user_id: Optional[str], email: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """Resolve organization_id and role from organization_users DB table if not in JWT."""
    try:
        import uuid
        from sqlalchemy import text
        from core.database import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            uid_val = None
            if user_id:
                try:
                    uid_val = uuid.UUID(str(user_id))
                except Exception:
                    pass

            if uid_val and email:
                stmt = text(
                    "SELECT organization_id, role FROM organization_users "
                    "WHERE user_id = :uid OR email = :email LIMIT 1"
                )
                res = await db.execute(stmt, {"uid": uid_val, "email": email})
            elif uid_val:
                stmt = text(
                    "SELECT organization_id, role FROM organization_users "
                    "WHERE user_id = :uid LIMIT 1"
                )
                res = await db.execute(stmt, {"uid": uid_val})
            elif email:
                stmt = text(
                    "SELECT organization_id, role FROM organization_users "
                    "WHERE email = :email LIMIT 1"
                )
                res = await db.execute(stmt, {"email": email})
            else:
                return None, None

            row = res.fetchone()
            if row:
                return str(row[0]), str(row[1])
    except Exception as e:
        log.debug("DB organization lookup fallback skipped", error=str(e))
    return None, None


async def get_current_user_from_token(token: str) -> TokenData:
    """Validate token using api.auth.decode_token and resolve DB organization context."""
    from api.auth import decode_token
    user = decode_token(token)
    if user.user_id or user.email:
        db_org_id, db_role = await _resolve_org_context(user.user_id, user.email)
        if db_org_id:
            user.organization_id = db_org_id
            user.tenant_id = db_org_id
        if db_role:
            user.role = db_role
    return user


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> TokenData:
    """Validate Supabase / SMBFlow bearer JWT token and extract identity."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization Header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await get_current_user_from_token(credentials.credentials)

async def require_platform_admin(current_user: TokenData = Depends(get_current_user)) -> TokenData:
    if current_user.role not in ("platform_admin", "super_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform Admin access required",
        )
    return current_user

async def require_org_admin(current_user: TokenData = Depends(get_current_user)) -> TokenData:
    if current_user.role not in ("platform_admin", "super_admin", "org_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization Admin access required",
        )
    return current_user

async def require_authenticated_user(current_user: TokenData = Depends(get_current_user)) -> TokenData:
    return current_user
