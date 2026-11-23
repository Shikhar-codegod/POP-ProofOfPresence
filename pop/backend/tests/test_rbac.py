"""Integration tests for Role-Based Access Control (RBAC)."""

import httpx
import pytest


@pytest.mark.asyncio
async def test_inspector_cannot_create_user(client: httpx.AsyncClient, inspector_headers: dict[str, str]):
    """Verify inspector is forbidden from registering new platform users."""
    payload = {
        "email": "unauthorized.user@gov.in",
        "password": "Password123!",
        "role": "viewer",
    }
    response = await client.post("/api/v1/auth/users", json=payload, headers=inspector_headers)
    assert response.status_code == 403
    data = response.json()
    assert data["detail"]["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_viewer_cannot_create_user(client: httpx.AsyncClient, viewer_headers: dict[str, str]):
    """Verify viewer is forbidden from registering new platform users."""
    payload = {
        "email": "unauthorized.viewer@gov.in",
        "password": "Password123!",
        "role": "viewer",
    }
    response = await client.post("/api/v1/auth/users", json=payload, headers=viewer_headers)
    assert response.status_code == 403
    data = response.json()
    assert data["detail"]["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_inspector_cannot_provision_device_key(client: httpx.AsyncClient, inspector_headers: dict[str, str]):
    """Verify inspector is forbidden from provisioning edge camera device keys."""
    payload = {
        "name": "Unauthorized Key Test",
        "centre_id": "a1000000-0000-4000-8000-000000000001",
    }
    response = await client.post("/api/v1/auth/device-keys", json=payload, headers=inspector_headers)
    assert response.status_code == 403
    data = response.json()
    assert data["detail"]["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_admin_can_provision_device_key(client: httpx.AsyncClient, admin_headers: dict[str, str]):
    """Verify administrator has privilege to provision a new edge device key."""
    payload = {
        "name": "Audit Temp Gateway Key",
        "centre_id": "a1000000-0000-4000-8000-000000000001",
    }
    response = await client.post("/api/v1/auth/device-keys", json=payload, headers=admin_headers)
    assert response.status_code == 201

    data = response.json()
    assert "id" in data
    assert "plaintext_key" in data
    assert data["name"] == "Audit Temp Gateway Key"
    assert data["plaintext_key"].startswith("devkey_")
