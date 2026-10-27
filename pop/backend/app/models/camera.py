"""Camera model representing a CCTV sensor installed at a skilling centre."""

import uuid
from typing import List, TYPE_CHECKING
from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.centre import Centre
    from app.models.reading import Reading
    from app.models.device_key import DeviceKey


class Camera(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """CCTV camera / sensor node stationed at a training centre classroom or lab."""

    __tablename__ = "cameras"

    centre_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("centres.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    rtsp_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    location_description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    centre: Mapped["Centre"] = relationship("Centre", back_populates="cameras")
    readings: Mapped[List["Reading"]] = relationship(
        "Reading", back_populates="camera", cascade="all, delete-orphan"
    )
    device_keys: Mapped[List["DeviceKey"]] = relationship(
        "DeviceKey", back_populates="camera"
    )

    def __repr__(self) -> str:
        return f"<Camera id={self.id} name={self.name} centre_id={self.centre_id}>"
