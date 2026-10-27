"""Skilling centres inspection and dossier API routes."""

from typing import Optional
import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_any_authenticated
from app.models.user import User
from app.schemas.centre import CentreDetailResponse, CentreListPaginated
from app.services.centre_service import get_centre_by_id, list_centres

router = APIRouter(prefix="/centres", tags=["Centres"])


@router.get("", response_model=CentreListPaginated)
async def get_centres(
    state: Optional[str] = Query(None, description="Filter by state (e.g. Haryana, Karnataka)"),
    is_active: Optional[bool] = Query(True, description="Filter active/inactive centres"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _: User = Depends(require_any_authenticated),
    db: AsyncSession = Depends(get_db),
) -> CentreListPaginated:
    """Retrieve list of accredited skilling centres with camera count and latest observed headcount.

    Accessible by all authenticated roles (admin, inspector, viewer).
    """
    return await list_centres(db=db, state=state, is_active=is_active, limit=limit, offset=offset)


@router.get("/{id}", response_model=CentreDetailResponse)
async def get_centre(
    id: uuid.UUID,
    _: User = Depends(require_any_authenticated),
    db: AsyncSession = Depends(get_db),
) -> CentreDetailResponse:
    """Retrieve complete dossier for a centre, including installed cameras, latest readings, and inventory quotas.

    Accessible by all authenticated roles (admin, inspector, viewer).
    """
    return await get_centre_by_id(db=db, centre_id=id)
