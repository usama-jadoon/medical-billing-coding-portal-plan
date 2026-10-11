from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from services.api.config import settings
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from services.api.db.session import get_db
from services.api.db.models import User, Organization, AuditEvent
from services.api.security.auth import hash_password, verify_password, create_access_token, verify_totp
from services.api.security.tenant import get_current_user
from services.api.utils.logging import audit_logger

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    otp_code: str = ""


class RegisterRequest(BaseModel):
    organization_name: str
    email: EmailStr
    password: str = Field(min_length=12, max_length=72)


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    stmt = select(User).join(Organization).where(User.email == req.email)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    if not user or not verify_password(req.password, user.password_hash):
        audit_logger.log(
            level="warning",
            action="LOGIN_FAILED",
            status="failed",
            error_code="INVALID_CREDENTIALS",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive.",
        )

    if settings.OWNER_EMAIL and user.email.lower() != settings.OWNER_EMAIL.lower():
        raise HTTPException(403, "This private workspace is restricted to its named owner.")
    if settings.OWNER_TOTP_SECRET and not verify_totp(settings.OWNER_TOTP_SECRET, req.otp_code):
        raise HTTPException(401, "A valid authenticator code is required.")

    token = create_access_token(
        data={"sub": user.id, "org": user.organization_id, "role": user.role, "mfa": bool(settings.OWNER_TOTP_SECRET)}
    )

    # Record login audit
    audit = AuditEvent(
        organization_id=user.organization_id,
        actor_id=user.id,
        event_type="user_login",
        entity_type="user",
        entity_id=user.id,
        metadata_json={"role": user.role},
    )
    db.add(audit)
    await db.commit()

    audit_logger.log(
        level="info",
        action="LOGIN_SUCCESS",
        actor_id=user.id,
        organization_id=user.organization_id,
        status="success",
    )

    return AuthResponse(
        access_token=token,
        user={
            "id": user.id,
            "email": user.email,
            "role": user.role,
            "organization_id": user.organization_id,
        },
    )


@router.post("/register", response_model=AuthResponse)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    if settings.OWNER_TOTP_SECRET:
        raise HTTPException(403, "Create the MFA-protected owner account using the local setup script.")
    if settings.OWNER_EMAIL and req.email.lower() != settings.OWNER_EMAIL.lower():
        raise HTTPException(403, "Only the configured workspace owner may register.")
    if (await db.execute(select(User.id).where(User.role == "Owner"))).first():
        raise HTTPException(403, "Owner already configured. Sign in to the private workspace.")
    # Check if email exists
    stmt = select(User).where(User.email == req.email)
    res = await db.execute(stmt)
    if res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already registered.",
        )

    # Create Organization
    org = Organization(name=req.organization_name)
    db.add(org)
    await db.flush()

    # Create Owner User
    user = User(
        organization_id=org.id,
        email=req.email,
        password_hash=hash_password(req.password),
        role="Owner",
        status="active",
    )
    db.add(user)
    await db.flush()

    audit = AuditEvent(
        organization_id=org.id,
        actor_id=user.id,
        event_type="organization_registered",
        entity_type="organization",
        entity_id=org.id,
        metadata_json={"org_name": org.name},
    )
    db.add(audit)
    await db.commit()

    token = create_access_token(
        data={"sub": user.id, "org": user.organization_id, "role": user.role}
    )

    return AuthResponse(
        access_token=token,
        user={
            "id": user.id,
            "email": user.email,
            "role": user.role,
            "organization_id": user.organization_id,
        },
    )


@router.get("/me")
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Organization).where(Organization.id == current_user.organization_id)
    res = await db.execute(stmt)
    org = res.scalar_one_or_none()

    return {
        "id": current_user.id,
        "email": current_user.email,
        "role": current_user.role,
        "organization_id": current_user.organization_id,
        "organization_name": org.name if org else "",
    }
