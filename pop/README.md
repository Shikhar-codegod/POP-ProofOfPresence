# ProofOfPresence (POP)

**POP (ProofOfPresence)** is an edge-AI video analytics platform that verifies attendance counts and infrastructure compliance at government-funded vocational skilling centres using existing CCTV footage without compromising individual privacy.

---

## 🔒 Privacy-First Design

POP operates under a strict, non-negotiable aggregate privacy policy:
- **No Face Recognition**: No biometric encodings, facial embeddings, face crops, or identity extraction.
- **Aggregate Person Counting Only**: The edge pipeline outputs numerical headcounts and image quality scores only.
- **No Video Stored Centrally**: Raw CCTV video streams and individual frames never leave the local edge gateway.
- **Data Minimization**: The central backend only receives:
  `{ centre_id, camera_id, timestamp, raw_count, stable_count, equipment, frame_quality }`.

---

## 📁 Repository Structure

```
pop/
  edge/               # Edge inference pipeline (OpenCV, YOLO11n, trainer exclusion, client)
  backend/            # FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL, Pydantic v2
  frontend/           # Web inspection UI (Reserved for Phase 2)
  ml/                 # Evaluation dataset templates, benchmarks, synthetic video fixtures
  infra/              # Docker Compose (PostgreSQL 16, Redis 7, Backend)
  docs/               # API contract specifications and architectural guidelines
  .github/workflows/  # CI pipeline (Ruff, pytest for edge & backend)
```

---

## 🚀 Quickstart & Verification (Phase 1)

Detailed instructions for Step 1 through Step 10 are documented in `docs/api-contract.md` and subsequent phase milestones.
