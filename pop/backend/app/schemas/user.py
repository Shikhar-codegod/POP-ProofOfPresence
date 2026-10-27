"""Schemas for User management and credentials."""

from datetime import datetime
import uuid
from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole


class UserBase(BaseModel):
    """Base user fields."""

    email: EmailStr
    role: UserRole = UserRole.VIEWER


class UserCreate(UserBase):
    """Payload for creating a new platform user."""

    password: str = Field(..., min_length=8, description="User password (min 8 characters)")


class UserLogin(BaseModel):
    """Payload for user authentication."""

    email: EmailStr
    password: str = Field(..., min_length=1)


class UserResponse(UserBase):
    """Serialized public user profile."""

    id: uuid.UUID
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
