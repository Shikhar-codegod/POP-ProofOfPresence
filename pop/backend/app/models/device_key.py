"""DeviceKey model for authenticating edge gateways and CCTV video analytics clients."""

from datetime import datetime
import uuid
from typing import TYPE_CHECKING
from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.centre import Centre
    from app.models.camera import Camera


class DeviceKey(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Cryptographic authorization credential for edge gateway devices.

    The database stores strictly the SHA-256 hash of the generated secret key.
    The raw plaintext key is shown only once upon creation.
    """

    __tablename__ = "device_keys"

    key_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
        comment="SHA-256 hexadecimal hash of the raw device key",
    )
    name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="Human-readable label (e.g. 'Lab 1 Edge Gateway Box #3')",
    )
    centre_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("centres.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    camera_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("cameras.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    centre: Mapped["Centre | None"] = relationship("Centre", back_populates="device_keys")
    camera: Mapped["Camera | None"] = relationship("Camera", back_populates="device_keys")

    def __repr__(self) -> str:
        return f"<DeviceKey id={self.id} name={self.name} is_active={self.is_active}>"
