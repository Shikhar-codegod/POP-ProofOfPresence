"""Centre model representing an accredited skilling facility."""

from typing import List, TYPE_CHECKING
from sqlalchemy import Boolean, Float, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.camera import Camera
    from app.models.reading import Reading
    from app.models.device_key import DeviceKey
    from app.models.sanctioned_inventory import SanctionedInventory
    from app.models.attendance_record import AttendanceRecord


class Centre(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Accredited vocational training centre entity."""

    __tablename__ = "centres"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    state: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    district: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    cameras: Mapped[List["Camera"]] = relationship(
        "Camera", back_populates="centre", cascade="all, delete-orphan", lazy="selectin"
    )
    readings: Mapped[List["Reading"]] = relationship(
        "Reading", back_populates="centre", cascade="all, delete-orphan"
    )
    device_keys: Mapped[List["DeviceKey"]] = relationship(
        "DeviceKey", back_populates="centre"
    )
    sanctioned_inventory: Mapped[List["SanctionedInventory"]] = relationship(
        "SanctionedInventory", back_populates="centre", cascade="all, delete-orphan", lazy="selectin"
    )
    attendance_records: Mapped[List["AttendanceRecord"]] = relationship(
        "AttendanceRecord", back_populates="centre", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Centre code={self.code} name={self.name}>"
