"""SanctionedInventory model representing officially approved training lab infrastructure."""

from datetime import datetime
from typing import TYPE_CHECKING
import uuid
from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.centre import Centre


class SanctionedInventory(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Sanctioned infrastructure asset allocation for a certified training centre."""

    __tablename__ = "sanctioned_inventory"

    centre_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("centres.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    item_type: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
        comment="Inventory category (e.g. computer_desktop, sewing_machine, workbench)",
    )
    sanctioned_quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Government approved equipment capacity",
    )
    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp of most recent physical or computer-vision audit",
    )

    # Relationships
    centre: Mapped["Centre"] = relationship("Centre", back_populates="sanctioned_inventory")

    def __repr__(self) -> str:
        return (
            f"<SanctionedInventory centre_id={self.centre_id} item={self.item_type} "
            f"qty={self.sanctioned_quantity}>"
        )
