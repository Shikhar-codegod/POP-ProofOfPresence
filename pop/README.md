# ProofOfPresence (POP)

**POP (ProofOfPresence)** is an edge-AI video analytics platform that verifies student attendance counts and infrastructure compliance at government-funded vocational skilling centres using existing CCTV footage—without storing video centrally or identifying individuals.

---

## Architecture Overview

```text
+-----------------------------------------------------------------------------+
|                         SKILLING CENTRE (LOCAL EDGE)                        |
|                                                                             |
|  [CCTV / Video Clip] ---> [capture.py] ---> [YOLO11nDetector]               |
|                           (1 frame/N s)     ("person" class only)           |
|                                                    |                        |
|                                                    v                        |
|  [HTTP Client + Retry] <--- [Rolling Median & Trainer Exclusion + Quality]  |
|   (client.py)                (counter.py, quality.py)                       |
+--------------------------------------+--------------------------------------+
                                       |
                                       | HTTPS POST /api/v1/readings
                                       | Header: X-Device-Key: <key>
                                       | Body: { centre_id, camera_id,
                                       |         timestamp, raw_count,
                                       |         stable_count, equipment,
                                       |         frame_quality }
                                       v
+-----------------------------------------------------------------------------+
|                           CENTRAL POP PLATFORM                              |
|                                                                             |
|   [FastAPI Backend (port 8000)] <---> [Redis 7]                             |
|     - /api/v1/auth (JWT + RBAC)                                             |
|     - /api/v1/readings (Idempotent insert)                                  |
|     - /api/v1/centres (Dossiers + latest counts)                            |
|               |                                                             |
|               v                                                             |
|   [PostgreSQL 16]                                                           |
|     - users, centres, cameras, device_keys (SHA-256 hashed)                 |
|     - readings (JSONB equipment, unique camera_id + timestamp)              |
|     - sanctioned_inventory, attendance_records                              |
+-----------------------------------------------------------------------------+
```

---

## Privacy Design

POP is architected around **privacy by design**:

- **Only Integer Counts and Quality Scores Leave the Edge Device**: Telemetry sent to the central API consists strictly of aggregated integer counts (`raw_count`, `stable_count`), optional equipment tallies (`equipment`), and a scalar `frame_quality` score in `[0.0, 1.0]`.
- **No Face Recognition or Biometrics**: The YOLO11n detector filters solely for COCO class `0` (`person`). No face detection, face recognition, facial embeddings, or demographic attributes are computed or transmitted.
- **No Central Video Storage**: Raw CCTV frames and video files stay on the local edge gateway and are discarded immediately after frame-level counting in memory.
- **Hashed Edge Credentials**: Device API keys (`X-Device-Key`) are stored exclusively as SHA-256 hashes in PostgreSQL; plaintext keys are revealed only once at provisioning time.

---

## Quickstart: Running Phase 1 End-to-End

### 1. Configure Environment Variables

```bash
cd pop/infra
cp .env.example .env
```

*(Edit `pop/infra/.env` if you want to customize `POSTGRES_PASSWORD` or `SECRET_KEY`.)*

### 2. Start Infrastructure (`postgres`, `redis`, `backend`)

```bash
cd pop/infra
docker compose up -d --build
```

Verify all containers are healthy and API docs are reachable:

```bash
docker compose ps
curl -s http://localhost:8000/health
# Interactive Swagger UI: http://localhost:8000/docs
```

### 3. Run Database Migrations

```bash
cd pop/infra
docker compose exec backend alembic upgrade head
```

### 4. Seed Sample Centres, Users, Attendance History & Device Keys

```bash
cd pop/infra
docker compose exec backend python seed.py
```

The seed script creates:
- **Users**:
  - Admin: `admin@pop.gov.in` / `AdminSecret123!`
  - Inspector: `inspector.verma@gov.in` / `InspectorSecret123!`
  - Viewer: `viewer.sharma@gov.in` / `ViewerSecret123!`
- **5 Skilling Centres** across Haryana, Karnataka, Odisha, Rajasthan, and Uttar Pradesh (including 2 centres with deliberate ghost-attendance mismatches across 14 days of history).
- **Provisioned Camera UUIDs & Plaintext `X-Device-Key` credentials**, printed once to stdout.

Copy one of the printed `centre_id`, `camera_id`, and `X-Device-Key` values into `pop/edge/config.yaml` under the `backend:` section.

### 5. Run the Edge Script on a Sample Video

Install edge dependencies with Python 3.10 or newer (Python >=3.10 is supported):

```bash
cd pop/edge
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Generate a deterministic synthetic classroom clip (or supply your own MP4 path):

```bash
python ../ml/generate_test_video.py --output ../ml/sample_classroom.mp4 --duration 14
```

Run the edge counting pipeline and post live readings to the backend:

```bash
# Live ingestion mode (posts readings to http://localhost:8000/api/v1/readings)
python run_edge.py --config config.yaml --video ../ml/sample_classroom.mp4 --save-video

# Or offline mode (writes CSV, timeline plot, and annotated video without posting)
# python run_edge.py --config config.yaml --video ../ml/sample_classroom.mp4 --no-post --save-video
```

Artifacts produced in `pop/edge/output/`:
- `readings.csv`: Per-frame timestamps, raw counts, stable median counts, and quality scores.
- `count_timeline.png`: Matplotlib chart comparing raw vs. stable median counts.
- `annotated_detection.mp4` (when `--save-video` is passed): Preview clip with bounding boxes and trainer exclusion zone.

### 6. Query `GET /api/v1/centres/{id}` with `curl`

Authenticate as the seeded inspector to obtain a Bearer JWT, then inspect a centre dossier (for example, PMKK Gurugram `a1000000-0000-4000-8000-000000000001`):

```bash
# 1. Obtain JWT access token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "inspector.verma@gov.in", "password": "InspectorSecret123!"}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

# 2. Fetch centre dossier including latest observed camera reading
curl -s http://localhost:8000/api/v1/centres/a1000000-0000-4000-8000-000000000001 \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

---

## Accuracy Evaluation (`evaluate.py`)

Compare the edge pipeline's `stable_count` predictions against annotated ground truth (`pop/ml/ground_truth_template.csv`):

```bash
cd pop/edge
python evaluate.py \
  --predictions output/readings.csv \
  --ground-truth ../ml/ground_truth_template.csv \
  --video-id sample_classroom_01 \
  --output-markdown output/evaluation_report.md
```

This prints overall **MAE**, **within-$\pm 1$ percentage**, and a **per-scenario breakdown**, and writes the Markdown table to `output/evaluation_report.md`.

---

## Tests & Linting

Run Ruff and Pytest suites from the repository root (`pop/` parent or passing `-c pop/pyproject.toml`):

```bash
# 1. Lint check
ruff check --config pop/pyproject.toml pop/backend pop/edge

# 2. Edge unit tests (rolling median, trainer exclusion, quality, evaluation)
pytest -c pop/pyproject.toml pop/edge/tests -v

# 3. Backend API tests (requires running PostgreSQL instance)
export DATABASE_URL="postgresql+asyncpg://pop_user:pop_password@localhost:5432/pop_db"
export SECRET_KEY="test_secret_key_local_only"
pytest -c pop/pyproject.toml pop/backend/tests -v
```

---

## Repository Structure

```text
pop/
  edge/               # Edge inference pipeline (capture, YOLO11n detector, counter, quality, client, evaluate)
  backend/            # FastAPI application, SQLAlchemy 2.0 models, Alembic migrations, seed.py, API tests
  frontend/           # Reserved placeholder for Phase 2 React dashboard
  ml/                 # Ground truth CSV template & synthetic CCTV test video generator
  infra/              # Docker Compose stack (PostgreSQL 16, Redis 7, Backend) & .env.example
  docs/               # API Contract specification (docs/api-contract.md)
  .github/workflows/  # GitHub Actions CI workflow (ruff + backend/edge pytest)
  pyproject.toml      # Shared ruff and pytest-asyncio configuration
  LICENSE             # Apache 2.0 License
```

---

## Roadmap

- **Phase 1 (Current)**: Edge YOLO11n counting pipeline, FastAPI ingestion/query API, PostgreSQL + Alembic schema, JWT & `X-Device-Key` auth, seed data, accuracy benchmark, and CI test suite.
- **Phase 2+ (Planned)**: Automated attendance discrepancy flag engine, equipment compliance audits, Celery background jobs, offline edge SQLite spool buffer, and React inspector dashboard.
