# POP Phase 1 Closeout Report

## 1. Summary

| Phase 1 item | Status | Commit | Evidence |
|---|---|---|---|
| Python 3.10/3.11 edge compatibility | DONE | `543abca` | `pop\edge\.venv\Scripts\python.exe -m ruff check --config pyproject.toml pop/backend pop/edge pop/ml` |
| Edge config overlay and environment key precedence | DONE | `a850101` | Focused path tests: 7 passed; missing-config smoke test listed the searched absolute path |
| Edge run path fixes and real-clip smoke runs | DONE | `b9177fb` | `pop\edge\.venv\Scripts\python.exe -m pytest -c pyproject.toml pop/edge/tests -q`; real clip runs from repository root and `pop/edge` |
| Deterministic timestamps and idempotency implementation | DONE-NOT-VERIFIED | `92724a3`, `d1f1b2f` | Offline run produced repeatable timestamps; live 201/200 and row count not verified |
| Verification scripts | DONE-NOT-VERIFIED | `24fdd23` | PowerShell syntax and Bash `bash -n` passed; live script execution failed because Docker/credentials were unavailable |
| Accuracy baseline tooling | PENDING-HUMAN | `259d122` | 11 label frames exported; MAE and +/-1 metrics remain pending manual labels |
| Repo cleanup and documentation | DONE | `f54a856` | AI Studio files removed after approval; Ruff passed after cleanup |
| Repo hygiene and release drafts | DONE | `f21d01f` | YAML parsed; Dependabot, PR template, branch protection guide, changelog, and draft release added |
| Final report and checks | DONE-NOT-VERIFIED | `d1f1b2f` | Ruff and edge pytest passed; Docker, live verifier, backend Postgres tests, and GitHub CLI status were not available |

## 2. What Was Built

### Task 3 - Edge run unblock

- Updated `pop/ml/generate_test_video.py` to resolve its default output beside the script.
- Replaced the broken auto-import fallback in `pop/edge/run_edge.py` with a clear absolute-path error and generation command.
- Added path tests in `pop/edge/tests/test_run_edge_paths.py` and `pop/ml/test_generate_test_video_paths.py`.
- Removed the stray `pop/edge/pop/` folder.

### Task 4 - Deterministic ingestion

- Added `--start-time` and `sampling.start_time` support in `pop/edge/run_edge.py` and `pop/edge/config.yaml`.
- Added ISO-8601 parsing and HTTP 201/200 logging in `pop/edge/client.py`.
- Added deterministic timestamp tests and converted remaining backend datetime usage to `timezone.utc`.

### Task 5 - Verification scripts

- Added `scripts/verify_phase1.ps1` and `scripts/verify_phase1.sh`.
- Both scripts validate Compose, health, login, posting, duplicate status, row count, and latest stable count.
- Added PowerShell and Bash usage to the README.

### Task 6 - Accuracy tooling

- Added missing-column and unmatched-video-id validation to `pop/edge/evaluate.py`.
- Added `pop/ml/make_label_sheet.py`.
- Added `pop/docs/accuracy_baseline.md` and recording/labelling instructions.

### Task 7 - Repository cleanup

- Replaced the AI Studio root README and LICENSE.
- Consolidated to root `pyproject.toml` with Python 3.10 Ruff target.
- Moved pytest/Ruff to `pop/backend/requirements-dev.txt`.
- Removed the temporary Dockerfile package install.
- Removed the approved AI Studio scaffold and root Gemini `.env.example`.

### Task 8 - Repository hygiene

- Added `.github/dependabot.yml`.
- Added `.github/pull_request_template.md`.
- Added `docs/branch-protection.md`.
- Added `CHANGELOG.md` and `docs/releases/v0.1-phase1.md`.

## 3. Verification Evidence

### Ruff

Command:

```powershell
pop\edge\.venv\Scripts\python.exe -m ruff check --config pyproject.toml pop/backend pop/edge pop/ml
```

Result: **All checks passed**.

### Edge pytest

Command:

```powershell
pop\edge\.venv\Scripts\python.exe -m pytest -c pyproject.toml pop/edge/tests -q
```

Result: **30 passed**.

### Real edge clip smoke run

Command pattern:

```powershell
pop\edge\.venv\Scripts\python.exe pop\edge\run_edge.py --no-post --config pop\edge\config.yaml --video D:\pop\POP-ProofOfPresence\pop\ml\clips\classroom_cctv_360p.mp4
```

Verified from both the repository root and `pop/edge`:

- Processed 6 frames.
- CSV: `D:\pop\POP-ProofOfPresence\pop\edge\output\readings.csv`
- Plot: `D:\pop\POP-ProofOfPresence\pop\edge\output\count_timeline.png`
- First row: `2026-11-24T10:00:00+00:00,0.0,8,8,1.0`
- Last row: `2026-11-24T10:00:10+00:00,10.0,8,8,1.0`

### Deterministic timestamps

Command:

```powershell
pop\edge\.venv\Scripts\python.exe pop\edge\run_edge.py --no-post --config pop\edge\config.yaml --video pop\ml\clips\classroom_cctv_360p.mp4 --start-time "2026-11-24T10:00:00Z"
```

Result: timestamps started at `2026-11-24T10:00:00+00:00` and increased in two-second video intervals.

### Label frames

Command:

```powershell
pop\edge\.venv\Scripts\python.exe pop\ml\make_label_sheet.py pop\ml\clips\classroom_cctv_360p.mp4 --interval 1
```

Result: 11 JPEG frames exported to `pop/ml/label_frames/`.

### Backend pytest

Command:

```powershell
pop\edge\.venv\Scripts\python.exe -m pytest -c pyproject.toml pop/backend/tests -q
```

Result: **NOT VERIFIED**. Fixture setup received `ConnectionRefusedError`/`WinError 1225` when connecting to PostgreSQL because Docker Desktop was unavailable.

### PowerShell verification

Command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify_phase1.ps1
```

Observed table:

| Check | Status |
|---|---|
| Credentials | FAIL - environment variables absent |
| Device key | FAIL - environment variable absent |
| Edge config | FAIL - `config.local.yaml` absent |
| Docker Compose services | FAIL - Docker API unavailable |

### CI

`gh run list` was attempted but GitHub CLI was not authenticated. No CI run URL or status is claimed.

## 4. Accuracy Baseline

**MAE: PENDING - needs human ground-truth labelling**

**Percentage within +/-1: PENDING - needs human ground-truth labelling**

No true counts were guessed. Label frames and create `pop/ml/ground_truth.csv`, then run:

```powershell
pop\edge\.venv\Scripts\python.exe pop\edge\evaluate.py `
  --predictions pop\edge\output\readings.csv `
  --ground-truth pop\ml\ground_truth.csv
```

## 5. Known Issues and Limitations

- Docker Desktop was unavailable, so live 201/200 idempotency and reading row-count checks remain unverified.
- A `pop/edge/config.local.yaml` and credential environment variables were not available.
- Backend pytest requires a reachable PostgreSQL test database.
- The 360p real clip is approximately 11 seconds and is one short overhead sample.
- The YOLO model is COCO-pretrained and may undercount or miss people in overhead footage.
- GitHub Actions status could not be queried because `gh` is unauthenticated.
- `.vscode/` remains untracked and was not committed.

## 6. Security Checklist

- A final tracked-file grep was run for `devkey_`, `ghp_`, `github_pat_`, and `password=`.
- Matches were limited to source variable names/parameter names and an explicit API contract example; no plaintext credential or JWT was committed.
- `pop/edge/config.local.yaml`, `pop/edge/output/`, `pop/ml/clips/`, and `pop/ml/label_frames/` are ignored.
- Previously exposed GitHub tokens, if any, should be revoked in GitHub settings and replaced through environment variables.

## 7. Remaining Manual Steps

1. Start Docker Desktop and run `docker compose up -d --build`.
2. Set `POP_ADMIN_EMAIL`, `POP_ADMIN_PASSWORD`, and `POP_DEVICE_KEY` in the verification shell.
3. Create `pop/edge/config.local.yaml` with the seeded local centre, camera, and device key.
4. Run `scripts/verify_phase1.ps1` and record the live 201/200, stable-count, and row-count evidence.
5. Label the exported frames and fill `pop/ml/ground_truth.csv`.
6. Record more clips across baseline, occlusion, lighting, trainer, and transient-passersby scenarios.
7. Configure GitHub branch protection using `docs/branch-protection.md`.
8. Authenticate `gh` if GitHub Actions status is needed, then run `gh run list`.
9. Create the `v0.1-phase1` release and tag only after validation.
