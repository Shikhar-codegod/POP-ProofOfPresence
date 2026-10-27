"""Edge reading telemetry ingestion API route."""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import validate_device_key
from app.models.device_key import DeviceKey
from app.schemas.reading import ReadingCreate, ReadingResponse
from app.services.reading_service import ingest_reading

router = APIRouter(prefix="/readings", tags=["Readings"])


@router.post("", response_model=ReadingResponse)
async def post_reading(
    reading_in: ReadingCreate,
    response: Response,
    device_key: DeviceKey = Depends(validate_device_key),
    db: AsyncSession = Depends(get_db),
) -> ReadingResponse:
    """Ingest aggregated CCTV person count and image quality score from edge client.

    - Authenticated via `X-Device-Key` header.
    - Idempotent: If a reading with the exact (camera_id, timestamp) already exists,
      returns HTTP 200 with the existing record instead of raising an error.
    - Fresh insertions return HTTP 201 Created.
    - Clock skew > 5 minutes into the future is rejected with HTTP 400.
    """
    reading_record, is_new = await ingest_reading(db=db, reading_in=reading_in, device_key=device_key)

    if is_new:
        response.status_code = status.HTTP_201_CREATED
    else:
        response.status_code = status.HTTP_200_OK

    return reading_record
