"""Security utilities for password hashing, device key generation, and JWT handling."""

from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from typing import Any, Dict, Optional
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# Password hashing context using standard bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain text password against bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generate bcrypt password hash."""
    return pwd_context.hash(password)


def generate_raw_device_key() -> str:
    """Generate high-entropy random edge device key."""
    return f"devkey_{secrets.token_urlsafe(32)}"


def hash_device_key(raw_key: str) -> str:
    """Compute SHA-256 hexadecimal hash of raw device key for storage and lookup."""
    return hashlib.sha256(raw_key.strip().encode("utf-8")).hexdigest()


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Encode JWT access token with user claims and expiration."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": int(expire.timestamp()), "token_type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Encode JWT refresh token with user claims and extended expiration."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": int(expire.timestamp()), "token_type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_jwt_token(token: str) -> Dict[str, Any]:
    """Decode and validate a signed JWT token string.

    Raises:
        JWTError: If token signature or expiration is invalid.
    """
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
