"""Schemas for Device Key generation and registration."""

from datetime import datetime
import uuid
from typing import Optional
from pydantic import BaseModel, Field


class DeviceKeyCreate(BaseModel):
    """Payload to provision a new edge device authentication key."""

    name: str = Field(..., min_length=3, max_length=128, description="Identifier for this edge node")
    centre_id: Optional[uuid.UUID] = Field(default=None, description="Associated skilling centre UUID")
    camera_id: Optional[uuid.UUID] = Field(default=None, description="Associated CCTV camera UUID")
    expires_in_days: Optional[int] = Field(default=365, description="Validity period in days (null for non-expiring)")


class DeviceKeyCreatedResponse(BaseModel):
    """Response returned upon key creation, displaying the plaintext secret ONLY ONCE."""

    id: uuid.UUID
    name: str
    centre_id: Optional[uuid.UUID]
    camera_id: Optional[uuid.UUID]
    plaintext_key: str = Field(
        ...,
        description="The raw device key. Store this securely; it will NOT be recoverable or shown again.",
    )
    is_active: bool
    created_at: datetime
    expires_at: Optional[datetime]

    model_config = {"from_attributes": True}


class DeviceKeyPublic(BaseModel):
    """Public representation of an existing device key without secret credentials."""

    id: uuid.UUID
    name: str
    centre_id: Optional[uuid.UUID]
    camera_id: Optional[uuid.UUID]
    is_active: bool
    created_at: datetime
    expires_at: Optional[datetime]

    model_config = {"from_attributes": True}
