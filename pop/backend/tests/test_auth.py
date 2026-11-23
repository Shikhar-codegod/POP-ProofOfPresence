"""Integration tests for authentication, JWT issuance, token refresh, and user profile."""

import httpx
import pytest


@pytest.mark.asyncio
async def test_login_success(client: httpx.AsyncClient):
    """Verify login with seeded inspector credentials returns valid tokens."""
    payload = {
        "email": "inspector.verma@gov.in",
        "password": "InspectorSecret123!",
    }
    response = await client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 3600
    assert data["user"]["email"] == "inspector.verma@gov.in"
    assert data["user"]["role"] == "inspector"


@pytest.mark.asyncio
async def test_login_invalid_password(client: httpx.AsyncClient):
    """Verify login with incorrect password returns 401 INVALID_CREDENTIALS."""
    payload = {
        "email": "inspector.verma@gov.in",
        "password": "WrongPassword999!",
    }
    response = await client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 401
    data = response.json()
    assert data["detail"]["error"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: httpx.AsyncClient):
    """Verify login with unknown email returns 401 INVALID_CREDENTIALS."""
    payload = {
        "email": "unknown.ghost@pop.gov.in",
        "password": "SomePassword123!",
    }
    response = await client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 401
    data = response.json()
    assert data["detail"]["error"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_get_current_user_me_authenticated(client: httpx.AsyncClient, inspector_headers: dict[str, str]):
    """Verify GET /api/v1/auth/me returns active user profile when authenticated."""
    response = await client.get("/api/v1/auth/me", headers=inspector_headers)
    assert response.status_code == 200

    data = response.json()
    assert data["email"] == "inspector.verma@gov.in"
    assert data["role"] == "inspector"
    assert data["is_active"] is True
    assert "id" in data


@pytest.mark.asyncio
async def test_get_current_user_me_unauthorized(client: httpx.AsyncClient):
    """Verify GET /api/v1/auth/me rejects requests without Authorization header."""
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
    data = response.json()
    assert data["detail"]["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_refresh_token_lifecycle(client: httpx.AsyncClient):
    """Verify that a valid refresh token issues a new short-lived access token."""
    # 1. Login to obtain a refresh token
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "viewer.sharma@gov.in", "password": "ViewerSecret123!"},
    )
    assert login_res.status_code == 200
    refresh_token = login_res.json()["refresh_token"]

    # 2. Use refresh token to obtain new access token
    refresh_res = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_res.status_code == 200
    refresh_data = refresh_res.json()
    assert "access_token" in refresh_data
    assert refresh_data["token_type"] == "bearer"

    # 3. Verify the new access token can query protected profile
    new_headers = {"Authorization": f"Bearer {refresh_data['access_token']}"}
    me_res = await client.get("/api/v1/auth/me", headers=new_headers)
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "viewer.sharma@gov.in"


@pytest.mark.asyncio
async def test_refresh_token_invalid(client: httpx.AsyncClient):
    """Verify invalid refresh token is rejected with 401."""
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "invalid_malformed_token_string"},
    )
    assert response.status_code == 401
    data = response.json()
    assert data["detail"]["error"]["code"] == "INVALID_REFRESH_TOKEN"
