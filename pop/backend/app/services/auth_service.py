"""Authentication and credential lifecycle services."""

from datetime import datetime, timedelta, timezone
import logging
from typing import Optional, Tuple
import uuid
from fastapi import HTTPException, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_jwt_token,
    generate_raw_device_key,
    get_password_hash,
    hash_device_key,
    verify_password,
)
from app.models.device_key import DeviceKey
from app.models.user import User, UserRole
from app.schemas.device_key import DeviceKeyCreate, DeviceKeyCreatedResponse
from app.schemas.token import TokenRefreshResponse, TokenResponse, TokenUser
from app.schemas.user import UserCreate

logger = logging.getLogger("pop.services.auth")


async def authenticate_user(
    db: AsyncSession,
    email: str,
    password: str,
) -> User:
    """Authenticate a user by email and password.

    Raises:
        HTTPException: 401 if credentials are invalid or user is inactive.
    """
    query = select(User).where(User.email == email.strip().lower())
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user or not verify_password(password, user.hashed_password):
        logger.warning(f"Failed login attempt for email: {email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "INVALID_CREDENTIALS", "message": "Incorrect email or password."}},
        )

    if not user.is_active:
        logger.warning(f"Deactivated user login attempt: {email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "USER_DEACTIVATED", "message": "This account has been deactivated."}},
        )

    return user


def issue_user_tokens(user: User) -> TokenResponse:
    """Issue a fresh pair of access and refresh JWT tokens for an authenticated user."""
    token_claims = {
        "sub": user.email,
        "user_id": str(user.id),
        "role": user.role.value,
    }
    access_token = create_access_token(token_claims)
    refresh_token = create_refresh_token(token_claims)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=TokenUser(id=user.id, email=user.email, role=user.role),
    )


async def refresh_user_token(
    db: AsyncSession,
    refresh_token: str,
) -> TokenRefreshResponse:
    """Validate a refresh token and issue a fresh access token."""
    try:
        payload = decode_jwt_token(refresh_token)
        if payload.get("token_type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": {"code": "INVALID_REFRESH_TOKEN", "message": "Provided token is not a refresh token."}},
            )
        user_id_str = payload.get("user_id")
        if not user_id_str:
            raise ValueError("Missing user_id")
        user_uuid = uuid.UUID(user_id_str)
    except (JWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "INVALID_REFRESH_TOKEN", "message": "The refresh token is invalid or has expired."}},
        )

    query = select(User).where(User.id == user_uuid, User.is_active.is_(True))
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "USER_NOT_FOUND", "message": "User associated with token no longer exists."}},
        )

    access_token = create_access_token(
        {
            "sub": user.email,
            "user_id": str(user.id),
            "role": user.role.value,
        }
    )

    return TokenRefreshResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


async def register_user(
    db: AsyncSession,
    user_in: UserCreate,
) -> User:
    """Create a new user account with hashed password.

    Raises:
        HTTPException: 400 if email is already registered.
    """
    clean_email = user_in.email.strip().lower()
    existing = await db.execute(select(User).where(User.email == clean_email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "EMAIL_EXISTS", "message": "Email is already registered."}},
        )

    user = User(
        email=clean_email,
        hashed_password=get_password_hash(user_in.password),
        role=user_in.role,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    logger.info(f"Created new user {user.email} with role {user.role.value}")
    return user


async def provision_device_key(
    db: AsyncSession,
    device_in: DeviceKeyCreate,
) -> DeviceKeyCreatedResponse:
    """Generate and store a new device key.

    Returns:
        DeviceKeyCreatedResponse with the plaintext secret key included only once.
    """
    plaintext_key = generate_raw_device_key()
    key_hash = hash_device_key(plaintext_key)

    expires_at = None
    if device_in.expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=device_in.expires_in_days)

    device_key_obj = DeviceKey(
        key_hash=key_hash,
        name=device_in.name,
        centre_id=device_in.centre_id,
        camera_id=device_in.camera_id,
        is_active=True,
        expires_at=expires_at,
    )
    db.add(device_key_obj)
    await db.flush()
    await db.refresh(device_key_obj)

    logger.info(f"Provisioned device key '{device_key_obj.name}' (ID: {device_key_obj.id})")

    return DeviceKeyCreatedResponse(
        id=device_key_obj.id,
        name=device_key_obj.name,
        centre_id=device_key_obj.centre_id,
        camera_id=device_key_obj.camera_id,
        plaintext_key=plaintext_key,
        is_active=device_key_obj.is_active,
        created_at=device_key_obj.created_at,
        expires_at=device_key_obj.expires_at,
    )
