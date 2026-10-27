"""Authentication token schemas for JWT access and refresh flows."""

import uuid
from typing import Optional
from pydantic import BaseModel, Field

from app.models.user import UserRole


class TokenUser(BaseModel):
    """User profile data included within login authentication responses."""

    id: uuid.UUID
    email: str
    role: UserRole

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """Payload returned upon successful user authentication."""

    access_token: str = Field(..., description="Signed short-lived JWT access token")
    refresh_token: str = Field(..., description="Signed long-lived JWT refresh token")
    token_type: str = Field(default="bearer", description="Token scheme")
    expires_in: int = Field(default=3600, description="Access token expiration period in seconds")
    user: TokenUser


class TokenRefreshResponse(BaseModel):
    """Payload returned upon successful token refresh."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600


class RefreshTokenRequest(BaseModel):
    """Request payload containing the refresh token."""

    refresh_token: str = Field(..., min_length=10, description="Long-lived JWT refresh token")


class TokenPayload(BaseModel):
    """Internal decoded JWT claims payload."""

    sub: str
    user_id: str
    role: UserRole
    token_type: str  # "access" or "refresh"
    exp: Optional[int] = None
