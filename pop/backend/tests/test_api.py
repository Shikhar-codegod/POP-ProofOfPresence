"""End-to-end API tests covering readings ingestion, idempotency, auth, and RBAC."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from httpx import AsyncClient
import pytest


@pytest.mark.asyncio
async def test_health_probe(client: AsyncClient) -> None:
    """GET /health should return 200 with healthy status."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"
    assert body["service"] == "pop-backend"


@pytest.mark.asyncio
async def test_valid_reading_ingestion_and_centre_retrieval(
    client: AsyncClient,
    test_fixtures: Dict[str, Any],
) -> None:
    """Valid edge reading should persist with 201 and appear as latest_reading on centre dossier."""
    centre = test_fixtures["centre"]
    camera = test_fixtures["camera"]
    sample_ts = (datetime.now(timezone.utc) - timedelta(seconds=15)).replace(microsecond=0)

    payload = {
        "centre_id": str(centre.id),
        "camera_id": str(camera.id),
        "timestamp": sample_ts.isoformat(),
        "raw_count": 18,
        "stable_count": 16,
        "equipment": {"desktop_computers": 15},
        "frame_quality": 0.89,
    }

    post_resp = await client.post(
        "/api/v1/readings",
        json=payload,
        headers={"X-Device-Key": test_fixtures["device_key"]},
    )
    assert post_resp.status_code == 201
    created = post_resp.json()
    assert created["centre_id"] == str(centre.id)
    assert created["camera_id"] == str(camera.id)
    assert created["raw_count"] == 18
    assert created["stable_count"] == 16
    assert created["frame_quality"] == pytest.approx(0.89)
    assert created["equipment"] == {"desktop_computers": 15}

    # Verify reading shows up on GET /api/v1/centres/{id}
    centre_resp = await client.get(
        f"/api/v1/centres/{centre.id}",
        headers={"Authorization": f"Bearer {test_fixtures['viewer_token']}"},
    )
    assert centre_resp.status_code == 200
    dossier = centre_resp.json()
    assert len(dossier["cameras"]) == 1
    assert dossier["cameras"][0]["latest_reading"]["stable_count"] == 16

    # Verify reading shows up on GET /api/v1/centres list
    list_resp = await client.get(
        "/api/v1/centres",
        headers={"Authorization": f"Bearer {test_fixtures['inspector_token']}"},
    )
    assert list_resp.status_code == 200
    list_body = list_resp.json()
    assert list_body["total"] == 1
    assert list_body["items"][0]["latest_reading"]["stable_count"] == 16


@pytest.mark.asyncio
async def test_duplicate_reading_is_idempotent(
    client: AsyncClient,
    test_fixtures: Dict[str, Any],
) -> None:
    """Duplicate (camera_id, timestamp) submission should return 200 with existing record."""
    centre = test_fixtures["centre"]
    camera = test_fixtures["camera"]
    sample_ts = (datetime.now(timezone.utc) - timedelta(seconds=30)).replace(microsecond=0)

    payload = {
        "centre_id": str(centre.id),
        "camera_id": str(camera.id),
        "timestamp": sample_ts.isoformat(),
        "raw_count": 14,
        "stable_count": 13,
        "equipment": {},
        "frame_quality": 0.85,
    }
    headers = {"X-Device-Key": test_fixtures["device_key"]}

    first_resp = await client.post("/api/v1/readings", json=payload, headers=headers)
    assert first_resp.status_code == 201
    first_id = first_resp.json()["id"]

    # Retry with same camera_id and timestamp (even if counts differ slightly on retry)
    retry_payload = {**payload, "stable_count": 99}
    second_resp = await client.post("/api/v1/readings", json=retry_payload, headers=headers)
    assert second_resp.status_code == 200
    second_body = second_resp.json()
    assert second_body["id"] == first_id
    assert second_body["stable_count"] == 13


@pytest.mark.asyncio
async def test_future_timestamp_rejected(
    client: AsyncClient,
    test_fixtures: Dict[str, Any],
) -> None:
    """Readings timestamped far in the future must be rejected with HTTP 400."""
    future_ts = datetime.now(timezone.utc) + timedelta(hours=2)
    payload = {
        "centre_id": str(test_fixtures["centre"].id),
        "camera_id": str(test_fixtures["camera"].id),
        "timestamp": future_ts.isoformat(),
        "raw_count": 10,
        "stable_count": 10,
        "equipment": {},
        "frame_quality": 0.9,
    }
    resp = await client.post(
        "/api/v1/readings",
        json=payload,
        headers={"X-Device-Key": test_fixtures["device_key"]},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "TIMESTAMP_FUTURE"


@pytest.mark.asyncio
async def test_bad_or_missing_device_key_rejected(
    client: AsyncClient,
    test_fixtures: Dict[str, Any],
) -> None:
    """Missing or invalid X-Device-Key header must return 401 Unauthorized."""
    payload = {
        "centre_id": str(test_fixtures["centre"].id),
        "camera_id": str(test_fixtures["camera"].id),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "raw_count": 5,
        "stable_count": 5,
        "equipment": {},
        "frame_quality": 0.8,
    }

    missing_resp = await client.post("/api/v1/readings", json=payload)
    assert missing_resp.status_code == 401
    assert missing_resp.json()["error"]["code"] == "DEVICE_KEY_REQUIRED"

    bad_resp = await client.post(
        "/api/v1/readings",
        json=payload,
        headers={"X-Device-Key": "devkey_invalid_bogus_secret"},
    )
    assert bad_resp.status_code == 401
    assert bad_resp.json()["error"]["code"] == "INVALID_DEVICE_KEY"


@pytest.mark.asyncio
async def test_expired_and_missing_jwt_rejected(
    client: AsyncClient,
    test_fixtures: Dict[str, Any],
) -> None:
    """Expired or missing Bearer JWT tokens must return 401 Unauthorized."""
    no_auth_resp = await client.get("/api/v1/centres")
    assert no_auth_resp.status_code == 401

    expired_resp = await client.get(
        "/api/v1/centres",
        headers={"Authorization": f"Bearer {test_fixtures['expired_admin_token']}"},
    )
    assert expired_resp.status_code == 401
    assert expired_resp.json()["error"]["code"] == "INVALID_TOKEN"


@pytest.mark.asyncio
async def test_role_enforcement(
    client: AsyncClient,
    test_fixtures: Dict[str, Any],
) -> None:
    """Admin-only endpoints must return 403 for inspector and viewer, and 201 for admin."""
    new_user_payload = {
        "email": "new.inspector@test.pop.gov.in",
        "password": "StrongPassword123!",
        "role": "inspector",
    }
    new_key_payload = {
        "name": "Lab 2 Camera Key",
        "centre_id": str(test_fixtures["centre"].id),
        "camera_id": str(test_fixtures["camera"].id),
    }

    # Viewer and Inspector blocked from admin endpoints (403)
    for role_token_key in ("viewer_token", "inspector_token"):
        headers = {"Authorization": f"Bearer {test_fixtures[role_token_key]}"}
        user_resp = await client.post("/api/v1/auth/users", json=new_user_payload, headers=headers)
        assert user_resp.status_code == 403
        assert user_resp.json()["error"]["code"] == "FORBIDDEN"

        key_resp = await client.post("/api/v1/auth/device-keys", json=new_key_payload, headers=headers)
        assert key_resp.status_code == 403
        assert key_resp.json()["error"]["code"] == "FORBIDDEN"

    # Admin succeeds on both admin endpoints (201)
    admin_headers = {"Authorization": f"Bearer {test_fixtures['admin_token']}"}
    admin_user_resp = await client.post("/api/v1/auth/users", json=new_user_payload, headers=admin_headers)
    assert admin_user_resp.status_code == 201
    assert admin_user_resp.json()["email"] == "new.inspector@test.pop.gov.in"

    admin_key_resp = await client.post("/api/v1/auth/device-keys", json=new_key_payload, headers=admin_headers)
    assert admin_key_resp.status_code == 201
    plaintext_key = admin_key_resp.json()["plaintext_key"]
    assert plaintext_key.startswith("devkey_")

    # Newly provisioned device key can immediately post a reading
    reading_resp = await client.post(
        "/api/v1/readings",
        json={
            "centre_id": str(test_fixtures["centre"].id),
            "camera_id": str(test_fixtures["camera"].id),
            "timestamp": (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat(),
            "raw_count": 12,
            "stable_count": 11,
            "equipment": {},
            "frame_quality": 0.91,
        },
        headers={"X-Device-Key": plaintext_key},
    )
    assert reading_resp.status_code == 201


@pytest.mark.asyncio
async def test_login_and_refresh_token_flow(
    client: AsyncClient,
    test_fixtures: Dict[str, Any],
) -> None:
    """Login returns access + refresh tokens; refresh returns a new access token."""
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "inspector@test.pop.gov.in", "password": "InspectorPass123!"},
    )
    assert login_resp.status_code == 200
    tokens = login_resp.json()
    assert tokens["token_type"] == "bearer"
    assert tokens["user"]["role"] == "inspector"

    refresh_resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh_resp.status_code == 200
    assert "access_token" in refresh_resp.json()

    # Passing access token instead of refresh token must fail
    bad_refresh = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["access_token"]},
    )
    assert bad_refresh.status_code == 401
