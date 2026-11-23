"""Pytest fixtures for POP FastAPI backend API testing with PostgreSQL."""

import os
import sys
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
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
    generate_raw_device_key,
    get_password_hash,
    hash_device_key,
)
from app.main import app  # noqa: E402
from app.models.base import Base  # noqa: E402
from app.models.camera import Camera  # noqa: E402
from app.models.centre import Centre  # noqa: E402
from app.models.device_key import DeviceKey  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL") or settings.DATABASE_URL


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
    """Seed users (admin, inspector, viewer), a centre, a camera, and an active device key."""
    admin = User(
        email="admin@test.pop.gov.in",
        hashed_password=get_password_hash("AdminPass123!"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    inspector = User(
        email="inspector@test.pop.gov.in",
        hashed_password=get_password_hash("InspectorPass123!"),
        role=UserRole.INSPECTOR,
        is_active=True,
    )
    viewer = User(
        email="viewer@test.pop.gov.in",
        hashed_password=get_password_hash("ViewerPass123!"),
        role=UserRole.VIEWER,
        is_active=True,
    )
    db_session.add_all([admin, inspector, viewer])

    centre = Centre(
        name="Test PMKK Skilling Centre",
        code="DL-TST-0001",
        state="Delhi",
        district="New Delhi",
        latitude=28.6139,
        longitude=77.2090,
        is_active=True,
    )
    db_session.add(centre)
    await db_session.flush()

    camera = Camera(
        centre_id=centre.id,
        name="Main Classroom Camera",
        rtsp_url="rtsp://test.local/live/ch1",
        location_description="Room 101",
        is_active=True,
    )
    db_session.add(camera)
    await db_session.flush()

    raw_device_key = generate_raw_device_key()
    device_key = DeviceKey(
        key_hash=hash_device_key(raw_device_key),
        name="Test Edge Gateway",
        centre_id=centre.id,
        camera_id=camera.id,
        is_active=True,
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    db_session.add(device_key)
    await db_session.commit()

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
        "device_key": raw_device_key,
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
