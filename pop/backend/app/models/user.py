"""User model and role definitions for authentication and authorization."""

import enum
from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class UserRole(str, enum.Enum):
    """Access control roles within the POP platform."""

    ADMIN = "admin"
    INSPECTOR = "inspector"
    VIEWER = "viewer"


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """User account entity for platform administrators, inspectors, and viewers."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role_enum", values_callable=lambda x: [e.value for e in x]),
        default=UserRole.VIEWER,
        nullable=False,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<User email={self.email} role={self.role}>"
