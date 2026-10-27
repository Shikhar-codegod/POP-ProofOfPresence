"""Authentication, authorization, and device validation dependencies."""

from datetime import datetime, timezone
from typing import Callable, List
import uuid
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_jwt_token, hash_device_key
from app.models.device_key import DeviceKey
from app.models.user import User, UserRole

# HTTP Bearer scheme for JWT authentication
security_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Validate Bearer JWT access token and return authenticated User entity.

    Raises:
        HTTPException: 401 Unauthorized if token is missing, invalid, or expired.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "UNAUTHORIZED", "message": "Missing Bearer authorization header."}},
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_jwt_token(credentials.credentials)
        if payload.get("token_type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": {"code": "INVALID_TOKEN", "message": "Supplied token is not an access token."}},
            )
        user_id_str = payload.get("user_id")
        if not user_id_str:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": {"code": "INVALID_TOKEN", "message": "Token claims missing user identifier."}},
            )
        user_uuid = uuid.UUID(user_id_str)
    except (JWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "INVALID_TOKEN", "message": "Could not validate credentials or token expired."}},
            headers={"WWW-Authenticate": "Bearer"},
        )

    query = select(User).where(User.id == user_uuid, User.is_active.is_(True))
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "USER_NOT_FOUND", "message": "User does not exist or has been deactivated."}},
        )

    return user


def require_role(*roles: UserRole) -> Callable[[User], User]:
    """Factory creating dependency to verify user possesses one of the specified roles.

    Args:
        *roles: Permitted UserRole instances.

    Returns:
        Dependency verifying the active user role.
    """

    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": "FORBIDDEN",
                        "message": f"Operation requires one of roles: {[r.value for r in roles]}. Current role: {current_user.role.value}.",
                    }
                },
            )
        return current_user

    return role_checker


# Convenience aliases for standard role checks
require_admin = require_role(UserRole.ADMIN)
require_inspector_or_admin = require_role(UserRole.ADMIN, UserRole.INSPECTOR)
require_any_authenticated = require_role(UserRole.ADMIN, UserRole.INSPECTOR, UserRole.VIEWER)


async def validate_device_key(
    x_device_key: str | None = Header(None, alias="X-Device-Key"),
    db: AsyncSession = Depends(get_db),
) -> DeviceKey:
    """Validate edge device key from X-Device-Key header against database SHA-256 hashes.

    Raises:
        HTTPException: 401 Unauthorized if header is missing or key is invalid/expired.
    """
    if not x_device_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "DEVICE_KEY_REQUIRED", "message": "Missing X-Device-Key header."}},
        )

    key_hash = hash_device_key(x_device_key)

    query = select(DeviceKey).where(
        DeviceKey.key_hash == key_hash,
        DeviceKey.is_active.is_(True),
    )
    result = await db.execute(query)
    device_key_obj = result.scalar_one_or_none()

    if not device_key_obj:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "INVALID_DEVICE_KEY", "message": "Invalid or revoked device key."}},
        )

    # Check key expiration if set
    if device_key_obj.expires_at is not None:
        if datetime.now(timezone.utc) > device_key_obj.expires_at:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": {"code": "DEVICE_KEY_EXPIRED", "message": "Device key has expired."}},
            )

    return device_key_obj
