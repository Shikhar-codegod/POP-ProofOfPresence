"""Pytest test fixtures for POP backend integration tests."""

from collections.abc import AsyncGenerator

import httpx
import pytest
import pytest_asyncio

from app.core.database import async_engine
from app.main import app


@pytest_asyncio.fixture(scope="session")
async def client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Provide a session-scoped asynchronous HTTP test client."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    await async_engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def inspector_headers(client: httpx.AsyncClient) -> dict[str, str]:
    """Authenticate as seeded inspector and return Bearer headers."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "inspector.verma@gov.in", "password": "InspectorSecret123!"},
    )
    assert response.status_code == 200, f"Inspector login failed: {response.text}"
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture(scope="session")
async def admin_headers(client: httpx.AsyncClient) -> dict[str, str]:
    """Authenticate as seeded administrator and return Bearer headers."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@pop.gov.in", "password": "AdminSecret123!"},
    )
    assert response.status_code == 200, f"Admin login failed: {response.text}"
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture(scope="session")
async def viewer_headers(client: httpx.AsyncClient) -> dict[str, str]:
    """Authenticate as seeded viewer and return Bearer headers."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "viewer.sharma@gov.in", "password": "ViewerSecret123!"},
    )
    assert response.status_code == 200, f"Viewer login failed: {response.text}"
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def device_key_headers() -> dict[str, str]:
    """Return valid X-Device-Key header for Lab 1 camera node."""
    return {"X-Device-Key": "devkey_WHiHL4Krl-cPFy0F2ReMFKOlMAhuvLaesMDPxpb2ZLY"}
