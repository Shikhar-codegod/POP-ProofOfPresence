"""Centre query service retrieving dossiers, latest readings, and inventory quotas."""

import logging
from typing import Optional
import uuid
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.attendance_record import AttendanceRecord
from app.models.camera import Camera
from app.models.centre import Centre
from app.models.reading import Reading
from app.schemas.centre import (
    AttendanceRecordResponse,
    CameraResponse,
    CentreDetailResponse,
    CentreListItemResponse,
    CentreListPaginated,
    SanctionedInventoryResponse,
)
from app.schemas.reading import LatestReadingSummary

logger = logging.getLogger("pop.services.centres")


async def get_latest_reading_for_camera(
    db: AsyncSession,
    camera_id: uuid.UUID,
) -> Optional[LatestReadingSummary]:
    """Retrieve the most recent reading telemetry for a given camera."""
    query = (
        select(Reading)
        .where(Reading.camera_id == camera_id)
        .order_by(Reading.timestamp.desc())
        .limit(1)
    )
    res = await db.execute(query)
    record = res.scalar_one_or_none()
    if not record:
        return None
    return LatestReadingSummary(
        camera_id=record.camera_id,
        timestamp=record.timestamp,
        raw_count=record.raw_count,
        stable_count=record.stable_count,
        frame_quality=record.frame_quality,
        equipment=record.equipment or {},
    )


async def get_latest_reading_for_centre(
    db: AsyncSession,
    centre_id: uuid.UUID,
) -> Optional[LatestReadingSummary]:
    """Retrieve the most recent reading across all cameras stationed at a centre."""
    query = (
        select(Reading)
        .where(Reading.centre_id == centre_id)
        .order_by(Reading.timestamp.desc())
        .limit(1)
    )
    res = await db.execute(query)
    record = res.scalar_one_or_none()
    if not record:
        return None
    return LatestReadingSummary(
        camera_id=record.camera_id,
        timestamp=record.timestamp,
        raw_count=record.raw_count,
        stable_count=record.stable_count,
        frame_quality=record.frame_quality,
        equipment=record.equipment or {},
    )


async def list_centres(
    db: AsyncSession,
    state: Optional[str] = None,
    is_active: Optional[bool] = True,
    limit: int = 50,
    offset: int = 0,
) -> CentreListPaginated:
    """Retrieve paginated list of skilling centres with camera count and latest observed headcount."""
    base_query = select(Centre)
    count_query = select(func.count(Centre.id))

    if state:
        base_query = base_query.where(Centre.state.ilike(f"%{state.strip()}%"))
        count_query = count_query.where(Centre.state.ilike(f"%{state.strip()}%"))

    if is_active is not None:
        base_query = base_query.where(Centre.is_active == is_active)
        count_query = count_query.where(Centre.is_active == is_active)

    total_res = await db.execute(count_query)
    total = total_res.scalar_one()

    query = (
        base_query.options(selectinload(Centre.cameras))
        .order_by(Centre.name.asc())
        .offset(offset)
        .limit(limit)
    )
    res = await db.execute(query)
    centres = res.scalars().all()

    items = []
    for c in centres:
        latest_reading = await get_latest_reading_for_centre(db, c.id)
        items.append(
            CentreListItemResponse(
                id=c.id,
                name=c.name,
                code=c.code,
                state=c.state,
                district=c.district,
                latitude=c.latitude,
                longitude=c.longitude,
                is_active=c.is_active,
                camera_count=len(c.cameras),
                latest_reading=latest_reading,
            )
        )

    return CentreListPaginated(items=items, total=total)


async def get_centre_by_id(
    db: AsyncSession,
    centre_id: uuid.UUID,
) -> CentreDetailResponse:
    """Retrieve complete centre dossier including cameras, latest readings, inventory, and attendance."""
    query = (
        select(Centre)
        .where(Centre.id == centre_id)
        .options(
            selectinload(Centre.cameras),
            selectinload(Centre.sanctioned_inventory),
            selectinload(Centre.attendance_records),
        )
    )
    res = await db.execute(query)
    centre = res.scalar_one_or_none()

    if not centre:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "CENTRE_NOT_FOUND", "message": f"Centre {centre_id} does not exist."}},
        )

    # Resolve latest reading for each camera
    camera_responses = []
    for cam in centre.cameras:
        cam_latest = await get_latest_reading_for_camera(db, cam.id)
        camera_responses.append(
            CameraResponse(
                id=cam.id,
                name=cam.name,
                rtsp_url=cam.rtsp_url,
                location_description=cam.location_description,
                is_active=cam.is_active,
                latest_reading=cam_latest,
            )
        )

    # Resolve latest attendance record
    latest_att = None
    if centre.attendance_records:
        sorted_att = sorted(centre.attendance_records, key=lambda a: a.date, reverse=True)
        top = sorted_att[0]
        latest_att = AttendanceRecordResponse(
            id=top.id,
            date=top.date,
            enrolled_count=top.enrolled_count,
            official_present_count=top.official_present_count,
            source=top.source,
        )

    inventory_responses = [
        SanctionedInventoryResponse(
            id=inv.id,
            item_type=inv.item_type,
            sanctioned_quantity=inv.sanctioned_quantity,
            last_verified_at=inv.last_verified_at,
        )
        for inv in centre.sanctioned_inventory
    ]

    return CentreDetailResponse(
        id=centre.id,
        name=centre.name,
        code=centre.code,
        state=centre.state,
        district=centre.district,
        latitude=centre.latitude,
        longitude=centre.longitude,
        is_active=centre.is_active,
        created_at=centre.created_at,
        cameras=camera_responses,
        sanctioned_inventory=inventory_responses,
        latest_official_attendance=latest_att,
    )
