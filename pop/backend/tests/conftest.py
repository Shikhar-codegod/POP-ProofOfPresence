"""Pytest fixtures for POP FastAPI backend API testing with PostgreSQL."""

import os
import sys
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

# Ensure pop/backend is importable when pytest runs from repository root
BACKEND_DIR = str(Path(__file__).resolve().parents[1])
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.core.config import settings  # noqa: E402
from app.core.database import get_db  # noqa: E402
from app.core.security import (  # noqa: E402
    create_access_token,
    get_password_hash,
    hash_device_key,
)
from app.main import app  # noqa: E402
from app.models.attendance_record import AttendanceRecord  # noqa: E402
from app.models.base import Base  # noqa: E402
from app.models.camera import Camera  # noqa: E402
from app.models.centre import Centre  # noqa: E402
from app.models.device_key import DeviceKey  # noqa: E402
from app.models.sanctioned_inventory import SanctionedInventory  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL") or settings.DATABASE_URL


async def _seed_test_data(session: AsyncSession) -> None:
    """Seed the shared integration-test users, centres, camera, and device key."""
    users = [
        User(
            email="admin@test.pop.gov.in",
            hashed_password=get_password_hash("AdminPass123!"),
            role=UserRole.ADMIN,
            is_active=True,
        ),
        User(
            email="inspector@test.pop.gov.in",
            hashed_password=get_password_hash("InspectorPass123!"),
            role=UserRole.INSPECTOR,
            is_active=True,
        ),
        User(
            email="viewer@test.pop.gov.in",
            hashed_password=get_password_hash("ViewerPass123!"),
            role=UserRole.VIEWER,
            is_active=True,
        ),
        User(
            id="11111111-1111-4111-8111-111111111111",
            email="admin@pop.gov.in",
            hashed_password=get_password_hash("AdminSecret123!"),
            role=UserRole.ADMIN,
            is_active=True,
        ),
        User(
            id="22222222-2222-4222-8222-222222222222",
            email="inspector.verma@gov.in",
            hashed_password=get_password_hash("InspectorSecret123!"),
            role=UserRole.INSPECTOR,
            is_active=True,
        ),
        User(
            id="33333333-3333-4333-8333-333333333333",
            email="viewer.sharma@gov.in",
            hashed_password=get_password_hash("ViewerSecret123!"),
            role=UserRole.VIEWER,
            is_active=True,
        ),
    ]
    session.add_all(users)

    centre_specs = [
        ("a1000000-0000-4000-8000-000000000001", "PMKK Gurugram - Technology & Green Skills Hub", "HR-GGN-0104", "Haryana", "Gurugram"),
        ("a2000000-0000-4000-8000-000000000002", "PMKK Bengaluru Urban - Robotics & Automation Centre", "KA-BLR-0219", "Karnataka", "Bengaluru Urban"),
        ("a3000000-0000-4000-8000-000000000003", "PMKK Bhubaneswar - Apparel & Textile Design Centre", "OD-BBI-0342", "Odisha", "Khordha"),
        ("a4000000-0000-4000-8000-000000000004", "PMKK Jaipur - Precision Automotive Academy", "RJ-JPR-0418", "Rajasthan", "Jaipur"),
        ("a5000000-0000-4000-8000-000000000005", "PMKK Varanasi - Heritage Handloom & Digital Crafts", "UP-VNS-0581", "Uttar Pradesh", "Varanasi"),
    ]
    centres = [
        Centre(
            id=centre_id,
            name=name,
            code=code,
            state=state,
            district=district,
            latitude=28.6139,
            longitude=77.2090,
            is_active=True,
        )
        for centre_id, name, code, state, district in centre_specs
    ]
    session.add_all(centres)
    await session.flush()

    camera = Camera(
        id="fd38f22b-3065-4f94-a354-0255739d54d0",
        centre_id=centres[0].id,
        name="Main Classroom Camera",
        rtsp_url="rtsp://test.local/live/ch1",
        location_description="Room 101",
        is_active=True,
    )
    second_camera = Camera(
        centre_id=centres[0].id,
        name="Secondary Classroom Camera",
        rtsp_url="rtsp://test.local/live/ch2",
        location_description="Room 204",
        is_active=True,
    )
    session.add_all([camera, second_camera])
    await session.flush()

    session.add(
        AttendanceRecord(
            centre_id=centres[0].id,
            date=datetime.now(UTC).date(),
            enrolled_count=30,
            official_present_count=27,
            source="portal",
        )
    )
    session.add(
        SanctionedInventory(
            centre_id=centres[0].id,
            item_type="desktop_computer",
            sanctioned_quantity=30,
            last_verified_at=datetime.now(UTC),
        )
    )

    raw_device_key = "devkey_test_integration_gateway"
    session.add(
        DeviceKey(
            key_hash=hash_device_key(raw_device_key),
            name="Test Edge Gateway",
            centre_id=centres[0].id,
            camera_id=camera.id,
            is_active=True,
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )
    )
    await session.commit()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh schema per test using NullPool and yield an AsyncSession."""
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool, future=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db

    async with session_factory() as session:
        await _seed_test_data(session)
        yield session

    app.dependency_overrides.clear()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Return an httpx.AsyncClient bound to the FastAPI ASGI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest_asyncio.fixture
async def test_fixtures(db_session: AsyncSession) -> dict[str, Any]:
    """Return the shared integration-test users, centre, camera, and device key."""
    admin = await db_session.scalar(select(User).where(User.email == "admin@pop.gov.in"))
    inspector = await db_session.scalar(select(User).where(User.email == "inspector.verma@gov.in"))
    viewer = await db_session.scalar(select(User).where(User.email == "viewer.sharma@gov.in"))
    centre = await db_session.scalar(select(Centre).where(Centre.code == "HR-GGN-0104"))
    camera = await db_session.scalar(select(Camera).where(Camera.id == "fd38f22b-3065-4f94-a354-0255739d54d0"))
    device_key = await db_session.scalar(select(DeviceKey).where(DeviceKey.camera_id == camera.id))

    assert admin is not None
    assert inspector is not None
    assert viewer is not None
    assert centre is not None
    assert camera is not None
    assert device_key is not None

    def make_token(user: User, delta: timedelta | None = None) -> str:
        return create_access_token(
            {"sub": user.email, "user_id": str(user.id), "role": user.role.value},
            expires_delta=delta,
        )

    return {
        "admin": admin,
        "inspector": inspector,
        "viewer": viewer,
        "admin_token": make_token(admin),
        "inspector_token": make_token(inspector),
        "viewer_token": make_token(viewer),
        "expired_admin_token": make_token(admin, delta=timedelta(minutes=-15)),
        "centre": centre,
        "camera": camera,
        "device_key": "devkey_test_integration_gateway",
    }

@pytest_asyncio.fixture
async def inspector_headers(client: AsyncClient, test_fixtures: dict[str, Any]) -> dict[str, str]:
    """Return Authorization headers for the seeded inspector test user."""
    return {"Authorization": "Bearer " + test_fixtures["inspector_token"]}


@pytest_asyncio.fixture
async def admin_headers(client: AsyncClient, test_fixtures: dict[str, Any]) -> dict[str, str]:
    """Return Authorization headers for the seeded admin test user."""
    return {"Authorization": "Bearer " + test_fixtures["admin_token"]}


@pytest_asyncio.fixture
async def viewer_headers(client: AsyncClient, test_fixtures: dict[str, Any]) -> dict[str, str]:
    """Return Authorization headers for the seeded viewer test user."""
    return {"Authorization": "Bearer " + test_fixtures["viewer_token"]}


@pytest_asyncio.fixture
async def device_key_headers(test_fixtures: dict[str, Any]) -> dict[str, str]:
    """Return the active test edge device key header."""
    return {"X-Device-Key": test_fixtures["device_key"]}
