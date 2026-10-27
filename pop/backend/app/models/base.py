"""SQLAlchemy 2.0 declarative base and common model mixins."""

from datetime import datetime, timezone
import uuid
from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    """Return current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Base declarative class for all POP database entities."""
    pass


class UUIDPrimaryKeyMixin:
    """Mixin that provides a standard UUID primary key."""

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        sort_order=-10,
    )


class TimestampMixin:
    """Mixin that records creation and update timestamps in UTC."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
