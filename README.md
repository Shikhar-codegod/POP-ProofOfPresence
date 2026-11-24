# ProofOfPresence (POP)

[![POP CI](https://github.com/Shikhar-codegod/POP-ProofOfPresence/actions/workflows/ci.yml/badge.svg)](https://github.com/Shikhar-codegod/POP-ProofOfPresence/actions/workflows/ci.yml)

POP is an edge-AI video analytics platform for privacy-preserving attendance and infrastructure verification at government-funded vocational skilling centres.

## Status

- **Phase 1:** Complete
- **Phase 2:** Next

Phase 2 will add equipment detection, tamper detection, rule engine, Celery jobs, and a flags API.

## Roadmap

- **Phase 2:** Intelligence - equipment detection, tamper detection, rule engine, Celery, and flags API.
- **Phase 3:** React dashboard.
- **Phase 4:** Low-bandwidth/offline edge buffer and expanded evaluation.
- **Phase 5:** Deployment.

## Architecture

The edge pipeline captures frames, runs YOLO person detection, excludes trainers, and emits stable counts to the FastAPI backend. PostgreSQL stores readings and device credentials; Redis supports platform infrastructure.

See [API contract](pop/docs/api-contract.md), [edge and ML README](pop/README.md), and [accuracy baseline template](pop/docs/accuracy_baseline.md).

## Demo credentials

Seed credentials are **demo-only** and must not be reused in production. Never commit real passwords, JWTs, or device keys.

## Requirements

- Python 3.10+
- Docker with Docker Compose
- PowerShell or Bash

## Quickstart

PowerShell:

```powershell
Copy-Item pop\infra\.env.example pop\infra\.env
cd pop\infra
docker compose up -d --build
docker compose exec backend alembic upgrade head
docker compose exec backend python seed.py
```

Bash:

```bash
cp pop/infra/.env.example pop/infra/.env
cd pop/infra
docker compose up -d --build
docker compose exec backend alembic upgrade head
docker compose exec backend python seed.py
```

See [full POP quickstart](pop/README.md).

## Edge configuration

Commit only placeholders in [pop/edge/config.yaml](pop/edge/config.yaml). Create the git-ignored local file:

```yaml
backend:
  device_key: "<DEVICE_KEY>"
  centre_id: "<CENTRE_ID>"
  camera_id: "<CAMERA_ID>"
```

Set `POP_DEVICE_KEY` to override `backend.device_key` for the process.

PowerShell:

```powershell
$env:POP_DEVICE_KEY = "..."
pop\edge\.venv\Scripts\python.exe pop\edge\run_edge.py `
  --config pop\edge\config.local.yaml `
  --video pop\ml\clips\classroom_cctv_360p.mp4 `
  --no-post
```

Bash:

```bash
export POP_DEVICE_KEY='...'
python3 pop/edge/run_edge.py \
  --config pop/edge/config.local.yaml \
  --video pop/ml/clips/classroom_cctv_360p.mp4 \
  --no-post
```

## Verification

PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify_phase1.ps1
```

Bash:

```bash
bash scripts/verify_phase1.sh
```

Set `POP_ADMIN_EMAIL`, `POP_ADMIN_PASSWORD`, and `POP_DEVICE_KEY` before verification.
