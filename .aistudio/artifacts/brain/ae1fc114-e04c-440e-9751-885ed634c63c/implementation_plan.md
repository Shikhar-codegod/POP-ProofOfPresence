# POP (ProofOfPresence) — Phase 1 Implementation Plan

A resume-grade, privacy-first edge-AI video analytics platform that verifies attendance counts and infrastructure compliance at government-funded vocational skilling centres using existing CCTV feeds without storing video or identifying individuals.

---

### User Review & Critical Decisions

> [!IMPORTANT]
> The following technical choices were confirmed during Phase 1 clarification:
> - **Edge Detector**: Ultralytics YOLO11n nano model (`yolo11n.pt`) with class-filter restricted strictly to class index `0` ("person"). Swappable interface ready for ONNX runtime in future iterations.
> - **Authentication Hashing**: `bcrypt` via standard `passlib` / `bcrypt` for user credential hashing, combined with SHA-256 pre-hashing for high-entropy device keys (`X-Device-Key`).
> - **Testing & Evaluation Fixture**: In addition to standard file input parsing, includes a deterministic synthetic video generator (`ml/generate_test_video.py` / `edge/capture.py` helper) producing test clips with configurable person bounding boxes and timestamps to ensure reproducible CI and evaluation tests without external video downloads.
> - **Execution Mode**: Staged execution adhering strictly to the user's Step 1 through Step 10 order, stopping after each step with verification instructions.

---

### 1. Overview & Core Concept

**POP (ProofOfPresence)** solves a major public governance challenge: ghost attendance and fictitious batch reporting in government-funded skill development centres. Traditional biometric punch-in can be spoofed or bypassed, while manual inspection visits are infrequent and expensive.

- **What It Does**: Processes existing CCTV camera streams or recorded footage locally at the edge. The edge node detects persons, filters out stationary trainers or designated zones, computes a rolling stable median count, extracts frame quality metrics, and transmits aggregated integer counts to a central FastAPI backend over HTTPS.
- **Target Audience / Persona**:
  - *Skill Mission Officers & State Inspectors*: Review attendance patterns, detect deliberate attendance mismatches, and flag anomalies across accredited centres.
  - *Centre Administrators*: Manage cameras, view real-time occupancy counts, and monitor equipment compliance.
  - *Edge Devices (CCTV gateways / micro-PCs)*: Automated headless agents authenticated via cryptographic device keys.
- **Privacy Constitution**:
  - Zero facial recognition, zero facial embeddings, zero demographic/biometric identification.
  - Zero central transmission or cloud storage of raw video frames or high-resolution facial crops.
  - Edge devices only emit telemetry: `(centre_id, camera_id, timestamp, raw_count, stable_count, equipment, frame_quality)`.

---

### 2. System Experience & API Workflows

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           EDGE PIPELINE WORKFLOW                            │
│                                                                             │
│  [CCTV Stream / MP4] ──► [Frame Sampler (1/N s)] ──► [YOLO11n Detector]     │
│                                                              │ (Person BBoxes)
│                                                              ▼              │
│  [Backend Ingestion] ◄── [Device Client] ◄── [Counter & Quality Scorer]     │
│   - POST /readings        - X-Device-Key        - Trainer Exclusion         │
│   - Idempotent upsert     - Backoff retry       - Rolling Median (Window K) │
│                                                 - Brightness + Laplacian    │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### Key API Workflows
1. **Edge Telemetry Ingestion (`POST /api/v1/readings`)**:
   - Authenticated via `X-Device-Key: <plaintext_key>` header.
   - Backend matches SHA-256 hash against registered active `device_keys`.
   - Validates timestamp (UTC, rejecting future timestamps beyond 5-minute skew tolerance).
   - Idempotently stores reading with unique constraint on `(camera_id, timestamp)`. Duplicate submissions return HTTP 200 with the existing record rather than 409 conflict.
2. **Inspector / Admin Access (`GET /api/v1/centres` & `GET /api/v1/centres/{id}`)**:
   - Authenticated via JWT `Bearer <access_token>` with role-based permissions (`admin`, `inspector`, `viewer`).
   - Retrieves centre metadata, camera listings, sanctioned inventory, and the latest stable reading per camera.
3. **Accuracy Benchmarking (`edge/evaluate.py`)**:
   - Edge run generates timestamped count logs alongside ground-truth annotations (`ml/ground_truth_template.csv`).
   - Computes Mean Absolute Error (MAE), Percentage within $\pm 1$ person, and per-scenario breakdowns (e.g. baseline, occlusion, high glare, trainer motion).

---

### 3. Key Architectural Decisions & Trade-Offs

- **Decision 1: Edge-Native Processing vs. Central Video Streaming**
  - *Chosen Approach*: All computer vision inference executes on the edge device; central backend only accepts structured numeric readings.
  - *Why*: Strict data privacy compliance for public institutions, 99.9% bandwidth reduction over rural 4G/broadband links, and legal shielding against raw surveillance storage liabilities.
  - *Alternatives Considered*: Centralised video ingestion (rejected due to excessive network cost, latency, and privacy compliance violations).

- **Decision 2: Hashed Device Key Scheme (`X-Device-Key`) vs. mTLS or Device JWT**
  - *Chosen Approach*: High-entropy random hex token generated by the admin, hashed using SHA-256 prior to database storage, and transmitted in header `X-Device-Key`. Plaintext is shown only once at creation.
  - *Why*: Ultra-lightweight for low-power edge gateways; avoids token expiration churn on headless edge scripts while maintaining leak-proof database security.
  - *Alternatives Considered*: Full OAuth client credentials flow (adds unnecessary state and complexity for low-power edge nodes in Phase 1).

- **Decision 3: Rolling Median Filtering & Trainer Exclusion**
  - *Chosen Approach*: Pure functional implementation in `counter.py` supporting both geometric exclusion zones (normalized bounding box center check) and subtractive offset (`subtract_one`), followed by a rolling window of size $K$.
  - *Why*: Eliminates transient flickering in object detection counts caused by brief occlusions or people walking through camera sightlines, delivering stable headcount figures.

---

### 4. Technical Architecture & Data Strategy

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          POP SYSTEM ARCHITECTURE                        │
│                                                                         │
│   ┌───────────────────────────┐         ┌───────────────────────────┐   │
│   │        Edge Layer         │         │       Backend Layer       │   │
│   │                           │  HTTPS  │  (FastAPI + Pydantic v2)  │   │
│   │  - capture.py (Video/RTSP)│ ──────► │  - /api/v1/readings       │   │
│   │  - detector.py (YOLO11n)  │         │  - /api/v1/centres        │   │
│   │  - counter.py (Filters)   │         │  - /api/v1/auth           │   │
│   │  - client.py (HTTP + retry│         │  - deps.py & security.py  │   │
│   └───────────────────────────┘         └─────────────┬─────────────┘   │
│                                                       │                 │
│                                         SQLAlchemy 2.0 (Async/Sync)     │
│                                                       ▼                 │
│                                         ┌───────────────────────────┐   │
│                                         │      PostgreSQL 16        │   │
│                                         │  - users & roles          │   │
│                                         │  - centres & cameras      │   │
│                                         │  - readings (JSONB equip) │   │
│                                         │  - device_keys (hashed)   │   │
│                                         │  - attendance_records     │   │
│                                         └───────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

#### Database Schema Overview (SQLAlchemy 2.0 Declarative)
- **`users`**: `id` (UUID), `email` (unique), `hashed_password`, `role` (`admin` | `inspector` | `viewer`), `is_active`, `created_at`.
- **`centres`**: `id` (UUID), `name`, `code` (unique), `state`, `district`, `latitude`, `longitude`, `is_active`, `created_at`.
- **`cameras`**: `id` (UUID), `centre_id` (FK), `name`, `rtsp_url`, `location_description`, `is_active`, `created_at`.
- **`device_keys`**: `id` (UUID), `centre_id` (FK nullable), `camera_id` (FK nullable), `key_hash` (unique SHA-256), `name`, `is_active`, `expires_at`, `created_at`.
- **`readings`**: `id` (UUID), `camera_id` (FK), `centre_id` (FK), `timestamp` (UTC datetime), `raw_count` (int), `stable_count` (int), `equipment` (JSONB), `frame_quality` (float), `created_at`. Unique constraint on `(camera_id, timestamp)`.
- **`sanctioned_inventory`**: `id` (UUID), `centre_id` (FK), `item_type` (e.g. computer, sewing machine, welding booth), `sanctioned_quantity`, `last_verified_at`.
- **`attendance_records`**: `id` (UUID), `centre_id` (FK), `date` (Date), `enrolled_count` (int), `official_present_count` (int), `source` (string).

#### Execution Plan (10 Distinct Steps)
1. **Step 1: Repo and Contract**: Monorepo directory scaffold, top-level `.gitignore`, and detailed `docs/api-contract.md`.
2. **Step 2: Infrastructure**: `infra/docker-compose.yml`, `infra/.env.example`, `backend/Dockerfile`, healthchecks, volumes.
3. **Step 3: Backend Skeleton & Database**: Pydantic settings, SQLAlchemy 2.0 declarative models, Alembic migrations, `/health`.
4. **Step 4: Authentication**: Password hashing (bcrypt), JWT access & refresh flow, RBAC dependencies, device key generator CLI/endpoint.
5. **Step 5: Core Endpoints & Seed**: `/api/v1/readings` idempotent handler, `/api/v1/centres`, comprehensive `seed.py` with 5 realistic centres & mismatch cases.
6. **Step 6: Edge Counting Pipeline**: YOLO11n detector wrapper, trainer exclusion & rolling median logic, quality score, `run_edge.py` with plots.
7. **Step 7: Edge to Backend Connection**: Resilient `client.py` with exponential backoff and `--no-post` toggle.
8. **Step 8: Accuracy Check**: Ground truth benchmark format & `edge/evaluate.py` evaluation script with MAE / percentage metrics.
9. **Step 9: Tests and CI**: Unit tests for edge algorithms, API integration test suite (pytest + httpx), GitHub Actions CI workflow.
10. **Step 10: Documentation & Handover**: Complete `README.md` with operational guide, privacy design statement, and verification commands.
