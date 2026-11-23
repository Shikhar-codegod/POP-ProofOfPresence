"""Schemas for skilling centres, cameras, sanctioned inventory, and attendance records."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.reading import LatestReadingSummary


class SanctionedInventoryResponse(BaseModel):
    """Sanctioned infrastructure asset quota."""

    id: uuid.UUID
    item_type: str
    sanctioned_quantity: int
    last_verified_at: datetime | None

    model_config = {"from_attributes": True}


class AttendanceRecordResponse(BaseModel):
    """Official batch attendance report record."""

    id: uuid.UUID
    date: date
    enrolled_count: int
    official_present_count: int
    source: str

    model_config = {"from_attributes": True}


class CameraResponse(BaseModel):
    """CCTV camera profile with latest recorded telemetry reading."""

    id: uuid.UUID
    name: str
    rtsp_url: str | None
    location_description: str | None
    is_active: bool
    latest_reading: LatestReadingSummary | None = None

    model_config = {"from_attributes": True}


class CentreListItemResponse(BaseModel):
    """Compact summary of a skilling centre for list views."""

    id: uuid.UUID
    name: str
    code: str
    state: str
    district: str
    latitude: float | None
    longitude: float | None
    is_active: bool
    camera_count: int
    latest_reading: LatestReadingSummary | None = None

    model_config = {"from_attributes": True}


class CentreDetailResponse(BaseModel):
    """Comprehensive centre dossier including cameras, inventory, and attendance records."""

    id: uuid.UUID
    name: str
    code: str
    state: str
    district: str
    latitude: float | None
    longitude: float | None
    is_active: bool
    created_at: datetime
    cameras: list[CameraResponse] = Field(default_factory=list)
    sanctioned_inventory: list[SanctionedInventoryResponse] = Field(default_factory=list)
    latest_official_attendance: AttendanceRecordResponse | None = None

    model_config = {"from_attributes": True}


class CentreListPaginated(BaseModel):
    """Paginated list envelope for skilling centres."""

    items: list[CentreListItemResponse]
    total: int
