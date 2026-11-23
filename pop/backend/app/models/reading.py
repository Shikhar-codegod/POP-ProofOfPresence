"""Reading model representing aggregated headcount telemetry from edge CCTV nodes."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.camera import Camera
    from app.models.centre import Centre


class Reading(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Aggregated numerical attendance count and camera quality metrics emitted by edge nodes.

    Enforces idempotency via a composite unique constraint on (camera_id, timestamp).
    """

    __tablename__ = "readings"
    __table_args__ = (
        UniqueConstraint("camera_id", "timestamp", name="uq_readings_camera_timestamp"),
        Index("ix_readings_centre_timestamp", "centre_id", "timestamp"),
        Index("ix_readings_camera_timestamp", "camera_id", "timestamp"),
    )

    centre_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("centres.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    camera_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("cameras.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="UTC timestamp corresponding to the video frame sample",
    )
    raw_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Raw instant person detections without filtering",
    )
    stable_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Rolling median filtered headcount after trainer exclusion",
    )
    equipment: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        default=dict,
        nullable=False,
        comment="Detected equipment breakdown (e.g. active workstations)",
    )
    frame_quality: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Normalized image quality metric (0.0 to 1.0) derived from brightness and Laplacian variance",
    )

    # Relationships
    centre: Mapped["Centre"] = relationship("Centre", back_populates="readings")
    camera: Mapped["Camera"] = relationship("Camera", back_populates="readings")

    def __repr__(self) -> str:
        return (
            f"<Reading camera_id={self.camera_id} timestamp={self.timestamp.isoformat()} "
            f"stable_count={self.stable_count}>"
        )
