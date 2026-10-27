"""Schemas for edge reading telemetry ingestion and serialization."""

from datetime import datetime
from typing import Any, Dict
import uuid
from pydantic import BaseModel, Field


class ReadingBase(BaseModel):
    """Base telemetry reading fields."""

    centre_id: uuid.UUID = Field(..., description="Target skilling centre UUID")
    camera_id: uuid.UUID = Field(..., description="Target CCTV camera UUID")
    timestamp: datetime = Field(..., description="UTC ISO 8601 timestamp of sampled video frame")
    raw_count: int = Field(..., ge=0, description="Raw detected person bounding boxes")
    stable_count: int = Field(..., ge=0, description="Rolling median filtered headcount after trainer exclusion")
    equipment: Dict[str, Any] = Field(default_factory=dict, description="Active infrastructure breakdown")
    frame_quality: float = Field(..., ge=0.0, le=1.0, description="Normalized image quality metric (0.0 to 1.0)")


class ReadingCreate(ReadingBase):
    """Payload sent by edge device client."""
    pass


class ReadingResponse(ReadingBase):
    """Serialized stored reading entity."""

    id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class LatestReadingSummary(BaseModel):
    """Compact summary of the latest reading for a camera or centre."""

    camera_id: uuid.UUID
    timestamp: datetime
    raw_count: int
    stable_count: int
    frame_quality: float
    equipment: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}
