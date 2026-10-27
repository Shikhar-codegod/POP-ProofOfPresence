"""Reading ingestion service handling validation, future timestamp checks, and idempotent inserts."""

from datetime import datetime, timedelta, timezone
import logging
from typing import Tuple
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.camera import Camera
from app.models.centre import Centre
from app.models.device_key import DeviceKey
from app.models.reading import Reading
from app.schemas.reading import ReadingCreate

logger = logging.getLogger("pop.services.readings")


async def ingest_reading(
    db: AsyncSession,
    reading_in: ReadingCreate,
    device_key: DeviceKey,
) -> Tuple[Reading, bool]:
    """Validate and ingest an edge reading with strict idempotency and skew checks.

    Args:
        db: Asynchronous database session.
        reading_in: Validated telemetry payload.
        device_key: Authenticated DeviceKey record.

    Returns:
        Tuple[Reading, bool]: The reading entity and a boolean flag `is_new`
        (True if freshly inserted, False if idempotent match).

    Raises:
        HTTPException:
            - 400 if timestamp is unreasonably far in the future or timezone is missing.
            - 403 if device key is not authorized for the specified centre or camera.
            - 404 if camera or centre does not exist.
    """
    # 1. Validate device key authorization scope
    if device_key.centre_id is not None and device_key.centre_id != reading_in.centre_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "DEVICE_KEY_CENTRE_MISMATCH",
                    "message": "Authenticated device key is not authorized for this centre.",
                }
            },
        )

    if device_key.camera_id is not None and device_key.camera_id != reading_in.camera_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "DEVICE_KEY_CAMERA_MISMATCH",
                    "message": "Authenticated device key is not authorized for this camera.",
                }
            },
        )

    # 2. Normalize and validate timestamp
    reading_ts = reading_in.timestamp
    if reading_ts.tzinfo is None:
        reading_ts = reading_ts.replace(tzinfo=timezone.utc)

    now_utc = datetime.now(timezone.utc)
    max_tolerated_future = now_utc + timedelta(seconds=settings.MAX_FUTURE_TIMESTAMP_SKEW_SECONDS)
    if reading_ts > max_tolerated_future:
        logger.warning(
            f"Rejected reading with future timestamp: {reading_ts.isoformat()} > {max_tolerated_future.isoformat()}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "TIMESTAMP_FUTURE",
                    "message": (
                        f"Timestamp {reading_ts.isoformat()} is unreasonably far in the future. "
                        f"Maximum allowed clock skew is {settings.MAX_FUTURE_TIMESTAMP_SKEW_SECONDS}s."
                    ),
                }
            },
        )

    # 3. Verify camera and centre existence
    cam_query = select(Camera).where(Camera.id == reading_in.camera_id)
    cam_res = await db.execute(cam_query)
    camera = cam_res.scalar_one_or_none()
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "CAMERA_NOT_FOUND", "message": f"Camera {reading_in.camera_id} does not exist."}},
        )

    if camera.centre_id != reading_in.centre_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "CAMERA_CENTRE_MISMATCH",
                    "message": f"Camera {reading_in.camera_id} belongs to a different centre than specified.",
                }
            },
        )

    # 4. Check idempotency: unique constraint on (camera_id, timestamp)
    existing_query = select(Reading).where(
        Reading.camera_id == reading_in.camera_id,
        Reading.timestamp == reading_ts,
    )
    existing_res = await db.execute(existing_query)
    existing_reading = existing_res.scalar_one_or_none()

    if existing_reading:
        logger.info(
            f"Idempotent duplicate reading for camera {reading_in.camera_id} at {reading_ts.isoformat()}. "
            f"Returning existing record ID {existing_reading.id}."
        )
        return existing_reading, False

    # 5. Insert fresh reading
    new_reading = Reading(
        centre_id=reading_in.centre_id,
        camera_id=reading_in.camera_id,
        timestamp=reading_ts,
        raw_count=reading_in.raw_count,
        stable_count=reading_in.stable_count,
        equipment=reading_in.equipment,
        frame_quality=reading_in.frame_quality,
    )
    db.add(new_reading)
    await db.flush()
    await db.refresh(new_reading)

    logger.info(
        f"Persisted reading {new_reading.id} for camera {new_reading.camera_id}: "
        f"raw={new_reading.raw_count}, stable={new_reading.stable_count}, quality={new_reading.frame_quality:.2f}"
    )

    return new_reading, True
