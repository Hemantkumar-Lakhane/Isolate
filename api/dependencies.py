"""
api/dependencies.py
===================
FastAPI dependency injection: DB sessions, authenticated user context.
Import these into route modules instead of repeating the boilerplate.

CONSTANT — do not modify for business customization.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import TokenData, get_current_user, require_admin, require_any_auth
from core.database import get_db
from core.state_manager import StateManager


async def get_state_manager(
    db: AsyncSession = Depends(get_db),
) -> StateManager:
    """Yield a request-scoped StateManager backed by the request DB session."""
    return StateManager(session=db)


async def get_admin_user(
    current_user: TokenData = Depends(require_admin),
) -> TokenData:
    """Shorthand: require super_admin role."""
    return current_user


async def get_auth_user(
    current_user: TokenData = Depends(require_any_auth),
) -> TokenData:
    """Shorthand: require any authenticated user."""
    return current_user


async def get_current_organization(
    current_user: TokenData = Depends(require_any_auth),
    db: AsyncSession = Depends(get_db),
):
    """
    Canonical organization resolver — Phase 0.

    Derives the authenticated user's (OrganizationUser, Organization) pair from
    the ``organization_users`` → ``organizations`` chain.  Never trusts an
    organization_id supplied by the frontend; always derives it from the JWT
    user_id.

    Returns: (org_user: OrganizationUser, org: Organization)
    Raises: 404 if the user has no organization membership.
    """
    import api.crud as crud

    org_user, org = await crud.ensure_user_organization_provisioned(
        db,
        user_id=current_user.user_id,
        email=current_user.email,
        full_name=current_user.full_name,
    )
    if not org:
        raise HTTPException(
            status_code=404,
            detail="No organization found for authenticated user. Complete onboarding first.",
        )
    return org_user, org


# Re-export for convenience so callers only need to import from here
__all__ = [
    "get_db",
    "get_state_manager",
    "get_admin_user",
    "get_auth_user",
    "get_current_user",
    "get_current_organization",
    "require_admin",
    "require_any_auth",
]