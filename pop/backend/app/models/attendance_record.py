"""AttendanceRecord model representing officially reported batch attendance figures."""

from datetime import date
from typing import TYPE_CHECKING
import uuid
from sqlalchemy import Date, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.centre import Centre


class AttendanceRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Official batch attendance reported via traditional portal / biometric registers."""

    __tablename__ = "attendance_records"
    __table_args__ = (
        UniqueConstraint("centre_id", "date", name="uq_attendance_centre_date"),
    )

    centre_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("centres.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
        comment="Calendar date of official attendance session",
    )
    enrolled_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Total officially enrolled candidates in active batches",
    )
    official_present_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Number of candidates marked present in official register",
    )
    source: Mapped[str] = mapped_column(
        String(64),
        default="portal",
        nullable=False,
        comment="Origin system (e.g. manual_register, aadhaar_biometric, skill_india_portal)",
    )

    # Relationships
    centre: Mapped["Centre"] = relationship("Centre", back_populates="attendance_records")

    def __repr__(self) -> str:
        return (
            f"<AttendanceRecord centre_id={self.centre_id} date={self.date} "
            f"present={self.official_present_count}/{self.enrolled_count}>"
        )
