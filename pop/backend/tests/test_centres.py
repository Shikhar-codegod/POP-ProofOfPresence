"""Integration tests for centre listing, filtering, and dossier inspection."""

import httpx
import pytest


@pytest.mark.asyncio
async def test_list_centres_authenticated(client: httpx.AsyncClient, inspector_headers: dict[str, str]):
    """Verify listing skilling centres returns paginated items and total."""
    response = await client.get("/api/v1/centres", headers=inspector_headers)
    assert response.status_code == 200

    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] == 5
    assert len(data["items"]) == 5

    codes = [c["code"] for c in data["items"]]
    assert "HR-GGN-0104" in codes
    assert "KA-BLR-0219" in codes


@pytest.mark.asyncio
async def test_list_centres_filter_by_state(client: httpx.AsyncClient, viewer_headers: dict[str, str]):
    """Verify state query parameter correctly filters returned centres."""
    response = await client.get("/api/v1/centres?state=Haryana", headers=viewer_headers)
    assert response.status_code == 200

    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["code"] == "HR-GGN-0104"
    assert data["items"][0]["state"] == "Haryana"


@pytest.mark.asyncio
async def test_get_centre_dossier_by_id(client: httpx.AsyncClient, inspector_headers: dict[str, str]):
    """Verify retrieving complete centre dossier with cameras, inventory, and attendance records."""
    centre_id = "a1000000-0000-4000-8000-000000000001"
    response = await client.get(f"/api/v1/centres/{centre_id}", headers=inspector_headers)
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == centre_id
    assert data["code"] == "HR-GGN-0104"
    assert len(data["cameras"]) == 2
    assert len(data["sanctioned_inventory"]) >= 1
    assert data["latest_official_attendance"] is not None
    assert data["latest_official_attendance"]["enrolled_count"] == 30


@pytest.mark.asyncio
async def test_get_centre_by_id_not_found(client: httpx.AsyncClient, inspector_headers: dict[str, str]):
    """Verify requesting a nonexistent centre returns 404 CENTRE_NOT_FOUND."""
    nonexistent = "00000000-0000-0000-0000-000000000000"
    response = await client.get(f"/api/v1/centres/{nonexistent}", headers=inspector_headers)
    assert response.status_code == 404
    data = response.json()
    assert data["detail"]["error"]["code"] == "CENTRE_NOT_FOUND"


@pytest.mark.asyncio
async def test_centres_endpoint_unauthorized(client: httpx.AsyncClient):
    """Verify access is denied if Authorization header is missing."""
    response = await client.get("/api/v1/centres")
    assert response.status_code == 401
