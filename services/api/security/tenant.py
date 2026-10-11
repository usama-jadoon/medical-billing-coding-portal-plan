from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from services.api.db.session import get_db
from services.api.db.models import User, Organization
from services.api.security.auth import decode_access_token
from services.api.config import settings
import time

security_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials required."
        )

    token = credentials.credentials
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token."
        )

    user_id = payload["sub"]
    stmt = select(User).where(User.id == user_id, User.status == "active")
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or account deactivated."
        )

    if settings.OWNER_EMAIL and (user.email.lower() != settings.OWNER_EMAIL.lower() or user.role != "Owner"):
        raise HTTPException(403, "This private workspace is restricted to its named owner.")

    return user


async def get_current_tenant(
    current_user: User = Depends(get_current_user)
) -> str:
    """
    Returns the organization_id from the authenticated user's session.
    Never trusts client-supplied organization_id.
    """
    return current_user.organization_id


async def get_fresh_user(current_user: User = Depends(get_current_user),
                         credentials: HTTPAuthorizationCredentials = Depends(security_scheme)) -> User:
    payload = decode_access_token(credentials.credentials)
    if not payload or time.time() - payload.get('iat', 0) > settings.STEP_UP_MAX_AGE_SECONDS:
        raise HTTPException(401, "Approval or export requires a fresh sign-in. Sign in again, then reload the case.")
    if settings.OWNER_TOTP_SECRET and not payload.get('mfa'):
        raise HTTPException(401, "Approval or export requires multi-factor authentication.")
    return current_user
