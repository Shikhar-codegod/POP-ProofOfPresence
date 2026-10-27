"""Models package initialization and declarative registry export."""

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.user import User, UserRole
from app.models.centre import Centre
from app.models.camera import Camera
from app.models.device_key import DeviceKey
from app.models.reading import Reading
from app.models.sanctioned_inventory import SanctionedInventory
from app.models.attendance_record import AttendanceRecord

__all__ = [
    "Base",
    "TimestampMixin",
    "UUIDPrimaryKeyMixin",
    "User",
    "UserRole",
    "Centre",
    "Camera",
    "DeviceKey",
    "Reading",
    "SanctionedInventory",
    "AttendanceRecord",
]
