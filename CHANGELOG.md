# Changelog

All notable changes to POP are documented in this file.

## [v0.1-phase1] - 2026-11-24

### Added
- YOLO/OpenCV edge counting pipeline with trainer exclusion and rolling median filtering.
- FastAPI reading ingestion and idempotent duplicate handling.
- PostgreSQL schema, migrations, Redis-backed Docker Compose infrastructure, and seed data.
- JWT authentication and `X-Device-Key` edge authorization.
- Deterministic edge timestamps and local edge configuration support.
- Accuracy evaluation tooling and timestamped frame labelling helper.
- PowerShell and Bash Phase 1 verification scripts.
- GitHub Actions CI, Dependabot configuration, and pull request template.

### Changed
- Edge code is compatible with Python 3.10 and 3.11.
- Repository retains one root `pyproject.toml`.
- Backend development dependencies are separated from runtime dependencies.
- AI Studio scaffold files were removed.

### Known limitations
- Live Docker end-to-end verification requires Docker Desktop and environment credentials.
- Accuracy MAE and +/-1 percentage are pending human ground-truth labels.
