# ProofOfPresence (POP) — API Contract Specification

**Version:** 1.0.0 (Phase 1)  
**Base URL:** `/api/v1`  
**Protocol:** HTTPS / JSON  

---

## 1. Architectural & Privacy Principles

1. **Strict Privacy Boundary**: The POP API accepts numeric and qualitative edge telemetry only. No facial images, raw video frames, biometric encodings, or identifying markers are accepted or persisted.
2. **Standard Identifiers**: All resources are identified by standard RFC 4122 **UUID v4** strings (e.g. `3fa85f64-5717-4562-b3fc-2c963f66afa6`).
3. **Timestamp Standard**: All timestamps must be in **UTC** formatted according to ISO 8601 / RFC 3339 with an explicit `Z` or `+00:00` suffix (e.g., `2026-10-27T12:00:00Z`). Timestamps skewed more than 5 minutes into the future are rejected.
4. **Authentication Headers**:
   - **User Sessions (Inspectors, Admins, Viewers)**:
     ```http
     Authorization: Bearer <jwt_access_token>
     ```
   - **Edge Devices (CCTV gateways / field micro-PCs)**:
     ```http
     X-Device-Key: <plaintext_device_key>
     ```
     The backend computes the SHA-256 hash of the header value and compares it against active, registered device credentials.

---

## 2. Standard Error Format

All error responses return HTTP status codes in the 4xx or 5xx range with a structured JSON body:

```json
{
  "error": {
    "code": "INVALID_CREDENTIALS",
    "message": "Incorrect email or password provided.",
    "details": null
  }
}
```

### Standard Error Codes
| HTTP Status | Error Code | Description |
|:---|:---|:---|
| 400 | `BAD_REQUEST` | Malformed JSON or schema validation failure |
| 400 | `TIMESTAMP_FUTURE` | Timestamp is unrealistically in the future |
| 401 | `UNAUTHORIZED` | Missing, malformed, or expired JWT / Device key |
| 403 | `FORBIDDEN` | Authenticated user lacks required role permissions |
| 404 | `NOT_FOUND` | Target resource does not exist |
| 422 | `VALIDATION_ERROR` | Pydantic request body validation error |
| 500 | `INTERNAL_SERVER_ERROR`| Unhandled server exception |

---

## 3. Authentication Endpoints

### 3.1 User Login (`POST /api/v1/auth/login`)
Authenticates an administrator, state inspector, or viewer.

- **Access**: Public
- **Request Headers**: `Content-Type: application/json`
- **Request Body**:
  ```json
  {
    "email": "inspector.verma@gov.in",
    "password": "SecurePassword123!"
  }
  ```
- **Response (200 OK)**:
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "expires_in": 3600,
    "user": {
      "id": "c1f7a0b5-716d-495e-993d-4c3d3ef0c78a",
      "email": "inspector.verma@gov.in",
      "role": "inspector"
    }
  }
  ```
- **Error (401 Unauthorized)**:
  ```json
  {
    "error": {
      "code": "INVALID_CREDENTIALS",
      "message": "Incorrect email or password."
    }
  }
  ```

---

### 3.2 Refresh Access Token (`POST /api/v1/auth/refresh`)
Issues a fresh short-lived access token using a valid refresh token.

- **Access**: Public (requires valid refresh token in body)
- **Request Headers**: `Content-Type: application/json`
- **Request Body**:
  ```json
  {
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
  ```
- **Response (200 OK)**:
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "expires_in": 3600
  }
  ```
- **Error (401 Unauthorized)**:
  ```json
  {
    "error": {
      "code": "INVALID_REFRESH_TOKEN",
      "message": "The refresh token is invalid or has expired."
    }
  }
  ```

---

## 4. Edge Telemetry Endpoints

### 4.1 Ingest Edge Reading (`POST /api/v1/readings`)
Receives aggregated person counts and camera metrics from edge devices.

- **Access**: Edge Device only (Requires `X-Device-Key` header)
- **Idempotency Guarantee**: Unique constraint on `(camera_id, timestamp)`. If a duplicate reading is sent (e.g. following network retries), the API returns `200 OK` with the existing persisted reading rather than a conflict error.
- **Request Headers**:
  ```http
  Content-Type: application/json
  X-Device-Key: devkey_9a8b7c6d5e4f3a2b1c0d
  ```
- **Request Body**:
  ```json
  {
    "centre_id": "8f3b610c-3331-4899-b1d3-356ee19159d2",
    "camera_id": "7b68b812-4f35-43a1-9bb4-6db3227a9228",
    "timestamp": "2026-10-27T12:00:00Z",
    "raw_count": 24,
    "stable_count": 22,
    "equipment": {
      "desktops_active": 18,
      "sewing_machines": 0
    },
    "frame_quality": 0.87
  }
  ```
- **Field Constraints**:
  - `centre_id`: UUID (required, must exist in DB)
  - `camera_id`: UUID (required, must exist and match device authorization)
  - `timestamp`: UTC ISO 8601 string (required, cannot be > 5 minutes in future)
  - `raw_count`: Integer $\ge 0$ (required)
  - `stable_count`: Integer $\ge 0$ (required, median filtered)
  - `equipment`: Key-value JSON object of integer quantities (optional, defaults to `{}`)
  - `frame_quality`: Float $0.0 \le q \le 1.0$ (required, composite score from normalized brightness and blur variance)
- **Response (201 Created or 200 OK for idempotent duplicate)**:
  ```json
  {
    "id": "e4b373cf-6752-4735-a6e3-5120a1ce2477",
    "centre_id": "8f3b610c-3331-4899-b1d3-356ee19159d2",
    "camera_id": "7b68b812-4f35-43a1-9bb4-6db3227a9228",
    "timestamp": "2026-10-27T12:00:00Z",
    "raw_count": 24,
    "stable_count": 22,
    "equipment": {
      "desktops_active": 18,
      "sewing_machines": 0
    },
    "frame_quality": 0.87,
    "created_at": "2026-10-27T12:00:01.124Z"
  }
  ```

---

## 5. Centre & Inspection Endpoints

### 5.1 List All Centres (`GET /api/v1/centres`)
Retrieves list of accredited skilling centres with basic metadata and latest recorded headcount.

- **Access**: User JWT (`admin`, `inspector`, or `viewer`)
- **Query Parameters**:
  - `state` (optional string): Filter by Indian state / UT (e.g. `"Haryana"`, `"Karnataka"`)
  - `is_active` (optional bool): Filter active centres (default `true`)
  - `limit` (optional int, default `50`)
  - `offset` (optional int, default `0`)
- **Response (200 OK)**:
  ```json
  {
    "items": [
      {
        "id": "8f3b610c-3331-4899-b1d3-356ee19159d2",
        "name": "Pradhan Mantri Kaushal Kendra (PMKK) - Gurugram",
        "code": "HR-GGN-0104",
        "state": "Haryana",
        "district": "Gurugram",
        "latitude": 28.4595,
        "longitude": 77.0266,
        "is_active": true,
        "camera_count": 2,
        "latest_reading": {
          "camera_id": "7b68b812-4f35-43a1-9bb4-6db3227a9228",
          "timestamp": "2026-10-27T11:58:00Z",
          "stable_count": 22,
          "frame_quality": 0.87
        }
      }
    ],
    "total": 1
  }
  ```

---

### 5.2 Get Centre Details (`GET /api/v1/centres/{id}`)
Retrieves comprehensive centre dossier, including associated cameras, sanctioned inventory, official attendance figures, and latest readings per camera.

- **Access**: User JWT (`admin`, `inspector`, or `viewer`)
- **Path Parameter**: `id` (UUID)
- **Response (200 OK)**:
  ```json
  {
    "id": "8f3b610c-3331-4899-b1d3-356ee19159d2",
    "name": "Pradhan Mantri Kaushal Kendra (PMKK) - Gurugram",
    "code": "HR-GGN-0104",
    "state": "Haryana",
    "district": "Gurugram",
    "latitude": 28.4595,
    "longitude": 77.0266,
    "is_active": true,
    "created_at": "2026-01-15T09:00:00Z",
    "cameras": [
      {
        "id": "7b68b812-4f35-43a1-9bb4-6db3227a9228",
        "name": "Lab 1 - IT & Networking",
        "rtsp_url": "rtsp://edge-gateway.local:554/live/ch1",
        "location_description": "First floor training lab, wide angle lens",
        "is_active": true,
        "latest_reading": {
          "timestamp": "2026-10-27T11:58:00Z",
          "raw_count": 24,
          "stable_count": 22,
          "equipment": {
            "desktops_active": 18
          },
          "frame_quality": 0.87
        }
      }
    ],
    "sanctioned_inventory": [
      {
        "id": "90e10b1d-2856-42bb-98f9-d6e0dbbb931a",
        "item_type": "computer_desktop",
        "sanctioned_quantity": 25,
        "last_verified_at": "2026-10-20T10:00:00Z"
      }
    ],
    "latest_official_attendance": {
      "date": "2026-10-27",
      "enrolled_count": 30,
      "official_present_count": 28,
      "source": "manual_biometric_portal"
    }
  }
  ```

---

## 6. Phase 2 Placeholder Contracts (Preview Shapes)

The following contract shapes define extension points reserved for Phase 2 implementation. In Phase 1, they return null or default values.

### 6.1 Anomaly & Discrepancy Flags (`GET /api/v1/centres/{id}/flags` - Placeholder)
Anticipated schema for real-time audit flags comparing CCTV stable counts with official attendance records.

```json
{
  "centre_id": "8f3b610c-3331-4899-b1d3-356ee19159d2",
  "flags": [
    {
      "id": "flag_01j7b8d0e...",
      "flag_type": "GHOST_ATTENDANCE_MISMATCH",
      "severity": "HIGH",
      "description": "Official portal reports 28 present, but CCTV edge median observes max 12 present (57% discrepancy).",
      "date": "2026-10-27",
      "official_count": 28,
      "observed_count": 12,
      "status": "OPEN",
      "created_at": "2026-10-27T12:05:00Z"
    }
  ]
}
```

### 6.2 Equipment & Infrastructure Verification (`GET /api/v1/centres/{id}/inventory-audit` - Placeholder)
Anticipated schema for automated physical inventory compliance checking.

```json
{
  "centre_id": "8f3b610c-3331-4899-b1d3-356ee19159d2",
  "audit_date": "2026-10-27",
  "items": [
    {
      "item_type": "computer_desktop",
      "sanctioned_quantity": 25,
      "detected_active_quantity": 18,
      "compliance_ratio": 0.72,
      "status": "DEFICIT"
    }
  ]
}
```
