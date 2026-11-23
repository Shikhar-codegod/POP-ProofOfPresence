"""Integration tests for edge reading telemetry ingestion and idempotency rules."""

from datetime import UTC, datetime, timedelta

import httpx
import pytest


@pytest.mark.asyncio
async def test_post_reading_success_and_idempotency(
    client: httpx.AsyncClient,
    device_key_headers: dict[str, str],
):
    """Verify fresh reading returns 201 Created, and duplicate submission returns 200 OK."""
    # Use distinct timestamp to avoid collision with seed readings
    test_dt = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    payload = {
        "centre_id": "a1000000-0000-4000-8000-000000000001",
        "camera_id": "fd38f22b-3065-4f94-a354-0255739d54d0",
        "timestamp": test_dt,
        "raw_count": 18,
        "stable_count": 16,
        "equipment": {"desktops_active": 14},
        "frame_quality": 0.89,
    }

    # 1. First submission -> 201 Created
    response1 = await client.post("/api/v1/readings", json=payload, headers=device_key_headers)
    assert response1.status_code == 201
    reading1 = response1.json()
    assert reading1["centre_id"] == payload["centre_id"]
    assert reading1["camera_id"] == payload["camera_id"]
    assert reading1["stable_count"] == 16
    assert reading1["frame_quality"] == 0.89
    assert "id" in reading1

    # 2. Duplicate submission (same camera_id and timestamp) -> 200 OK (idempotent)
    response2 = await client.post("/api/v1/readings", json=payload, headers=device_key_headers)
    assert response2.status_code == 200
    reading2 = response2.json()
    assert reading2["id"] == reading1["id"]


@pytest.mark.asyncio
async def test_post_reading_future_timestamp_rejected(
    client: httpx.AsyncClient,
    device_key_headers: dict[str, str],
):
    """Verify timestamp skewed > 5 minutes into the future is rejected with 400 TIMESTAMP_FUTURE."""
    future_dt = (datetime.now(UTC) + timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M:%SZ")

    payload = {
        "centre_id": "a1000000-0000-4000-8000-000000000001",
        "camera_id": "fd38f22b-3065-4f94-a354-0255739d54d0",
        "timestamp": future_dt,
        "raw_count": 10,
        "stable_count": 10,
        "frame_quality": 0.80,
    }

    response = await client.post("/api/v1/readings", json=payload, headers=device_key_headers)
    assert response.status_code == 400
    data = response.json()
    assert data["detail"]["error"]["code"] == "TIMESTAMP_FUTURE"


@pytest.mark.asyncio
async def test_post_reading_missing_device_key(client: httpx.AsyncClient):
    """Verify ingestion without X-Device-Key header is rejected with 401 DEVICE_KEY_REQUIRED."""
    payload = {
        "centre_id": "a1000000-0000-4000-8000-000000000001",
        "camera_id": "fd38f22b-3065-4f94-a354-0255739d54d0",
        "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "raw_count": 10,
        "stable_count": 10,
        "frame_quality": 0.80,
    }

    response = await client.post("/api/v1/readings", json=payload)
    assert response.status_code == 401
    data = response.json()
    assert data["detail"]["error"]["code"] == "DEVICE_KEY_REQUIRED"


@pytest.mark.asyncio
async def test_post_reading_invalid_device_key(client: httpx.AsyncClient):
    """Verify ingestion with unrecognized X-Device-Key is rejected with 401 INVALID_DEVICE_KEY."""
    headers = {"X-Device-Key": "devkey_unregistered_fraudulent_key"}
    payload = {
        "centre_id": "a1000000-0000-4000-8000-000000000001",
        "camera_id": "fd38f22b-3065-4f94-a354-0255739d54d0",
        "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "raw_count": 10,
        "stable_count": 10,
        "frame_quality": 0.80,
    }

    response = await client.post("/api/v1/readings", json=payload, headers=headers)
    assert response.status_code == 401
    data = response.json()
    assert data["detail"]["error"]["code"] == "INVALID_DEVICE_KEY"
