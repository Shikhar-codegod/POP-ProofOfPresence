#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
INFRA_DIR="$REPO_ROOT/pop/infra"
EDGE_PYTHON="$REPO_ROOT/pop/edge/.venv/Scripts/python.exe"
API_BASE="${POP_API_URL:-http://localhost:8000}"
CENTRE_ID="${POP_CENTRE_ID:-a1000000-0000-4000-8000-000000000001}"
VIDEO="${POP_VERIFY_VIDEO:-$REPO_ROOT/pop/ml/clips/classroom_cctv_360p.mp4}"
CONFIG="${POP_VERIFY_CONFIG:-$REPO_ROOT/pop/edge/config.local.yaml}"

declare -a CHECKS=()
failed=0

add_result() { CHECKS+=("$1|$2|$3"); }
mask_stderr() {
  sed -E 's/devkey_[A-Za-z0-9_-]+/devkey_[REDACTED]/g' <<<"$1" |
    tail -n 3 | tr '\n' ' '
}

set +e
COMPOSE_OUTPUT="$(cd "$INFRA_DIR" && docker compose ps 2>&1)"
COMPOSE_EXIT=$?
set -e
if [[ $COMPOSE_EXIT -eq 0 && "$COMPOSE_OUTPUT" != *"unhealthy"* && "$COMPOSE_OUTPUT" != *"not running"* ]]; then
  add_result "Compose services" "PASS" "docker compose ps exit=$COMPOSE_EXIT"
else
  add_result "Compose services" "FAIL" "docker compose ps exit=$COMPOSE_EXIT; $(mask_stderr "$COMPOSE_OUTPUT")"
fi

set +e
HEALTH_OUTPUT="$(curl.exe -fsS "$API_BASE/health" 2>&1)"
HEALTH_EXIT=$?
set -e
if [[ $HEALTH_EXIT -eq 0 && "$HEALTH_OUTPUT" == *'"status":"healthy"'* ]]; then
  add_result "/health" "PASS" "GET /health status=healthy"
else
  add_result "/health" "FAIL" "GET /health exit=$HEALTH_EXIT; $(mask_stderr "$HEALTH_OUTPUT")"
fi

if [[ -f "$CONFIG" ]]; then
  add_result "Edge config present" "PASS" "config=$CONFIG"
else
  add_result "Edge config present" "FAIL" "config=$CONFIG"
fi

if [[ -n "${POP_DEVICE_KEY:-}" ]]; then
  add_result "Edge key environment" "PASS" "POP_DEVICE_KEY set=true"
else
  add_result "Edge key environment" "FAIL" "POP_DEVICE_KEY set=false"
fi

LOGIN_TOKEN=""
if [[ -n "${POP_ADMIN_EMAIL:-}" && -n "${POP_ADMIN_PASSWORD:-}" ]]; then
  set +e
  LOGIN_OUTPUT="$(
    curl.exe -fsS -X POST "$API_BASE/api/v1/auth/login" \
      -H "Content-Type: application/json" \
      -d "{\"email\":\"$POP_ADMIN_EMAIL\",\"password\":\"$POP_ADMIN_PASSWORD\"}" 2>&1
  )"
  LOGIN_EXIT=$?
  set -e
  if [[ $LOGIN_EXIT -eq 0 ]]; then
    LOGIN_TOKEN="$(python -c 'import json,sys; print(json.load(sys.stdin)["access_token"])' <<<"$LOGIN_OUTPUT")"
    add_result "Admin login" "PASS" "POST /api/v1/auth/login"
  else
    add_result "Admin login" "FAIL" "POST /api/v1/auth/login exit=$LOGIN_EXIT; $(mask_stderr "$LOGIN_OUTPUT")"
  fi
else
  add_result "Admin login" "FAIL" "POP_ADMIN_EMAIL or POP_ADMIN_PASSWORD is not set"
fi

if [[ -f "$CONFIG" && -f "$VIDEO" && -x "$EDGE_PYTHON" && -n "${POP_DEVICE_KEY:-}" ]]; then
  CAMERA_ID="$("$EDGE_PYTHON" -c "import yaml; d=yaml.safe_load(open(r'$CONFIG',encoding='utf-8')); print(d['backend']['camera_id'])")"

  cd "$INFRA_DIR"
  POSTGRES_USER="$(sed -n 's/^POSTGRES_USER=//p' .env | head -n 1)"
  POSTGRES_DB="$(sed -n 's/^POSTGRES_DB=//p' .env | head -n 1)"
  COUNT_BEFORE="$(docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "select count(*) from readings where camera_id='$CAMERA_ID';" | tr -d '[:space:]')"

  cd "$REPO_ROOT"
  START_TIME="$(python -c 'from datetime import datetime,timezone,timedelta; print((datetime.now(timezone.utc)-timedelta(seconds=30)).strftime("%Y-%m-%dT%H:%M:%SZ"))')"
  set +e
  FIRST_LOG="$("$EDGE_PYTHON" pop/edge/run_edge.py --config "$CONFIG" --video "$VIDEO" --start-time "$START_TIME" 2>&1)"
  FIRST_EXIT=$?
  set -e
  FIRST_201="$(grep -c 'Reading POST HTTP 201' <<<"$FIRST_LOG" || true)"
  FIRST_401="$(grep -c 'Reading POST HTTP 401' <<<"$FIRST_LOG" || true)"
  if [[ $FIRST_EXIT -eq 0 && $FIRST_201 -gt 0 ]]; then
    add_result "Edge first run" "PASS" "HTTP 201=$FIRST_201; HTTP 401=$FIRST_401; exit=$FIRST_EXIT"
  else
    add_result "Edge first run" "FAIL" "HTTP 201=$FIRST_201; HTTP 401=$FIRST_401; exit=$FIRST_EXIT; $(mask_stderr "$FIRST_LOG")"
  fi

  cd "$INFRA_DIR"
  COUNT_AFTER_FIRST="$(docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "select count(*) from readings where camera_id='$CAMERA_ID';" | tr -d '[:space:]')"
  cd "$REPO_ROOT"

  set +e
  SECOND_LOG="$("$EDGE_PYTHON" pop/edge/run_edge.py --config "$CONFIG" --video "$VIDEO" --start-time "$START_TIME" 2>&1)"
  SECOND_EXIT=$?
  set -e
  SECOND_200="$(grep -c 'Reading POST HTTP 200' <<<"$SECOND_LOG" || true)"
  SECOND_401="$(grep -c 'Reading POST HTTP 401' <<<"$SECOND_LOG" || true)"
  if [[ $SECOND_EXIT -eq 0 && $SECOND_200 -gt 0 ]]; then
    add_result "Edge duplicate run" "PASS" "HTTP 200=$SECOND_200; HTTP 401=$SECOND_401; exit=$SECOND_EXIT"
  else
    add_result "Edge duplicate run" "FAIL" "HTTP 200=$SECOND_200; HTTP 401=$SECOND_401; exit=$SECOND_EXIT; $(mask_stderr "$SECOND_LOG")"
  fi

  cd "$INFRA_DIR"
  COUNT_AFTER_SECOND="$(docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "select count(*) from readings where camera_id='$CAMERA_ID';" | tr -d '[:space:]')"
  cd "$REPO_ROOT"
  if [[ "$COUNT_AFTER_FIRST" == "$COUNT_AFTER_SECOND" ]]; then
    add_result "Reading count unchanged" "PASS" "before=$COUNT_BEFORE; after first=$COUNT_AFTER_FIRST; after second=$COUNT_AFTER_SECOND"
  else
    add_result "Reading count unchanged" "FAIL" "before=$COUNT_BEFORE; after first=$COUNT_AFTER_FIRST; after second=$COUNT_AFTER_SECOND"
  fi

  if [[ -n "$LOGIN_TOKEN" ]]; then
    CSV_STABLE="$(python -c 'import csv,sys; r=list(csv.DictReader(open(sys.argv[1],encoding="utf-8"))); print(r[-1]["stable_count"])' "$REPO_ROOT/pop/edge/output/readings.csv")"
    LAST_VIDEO_SEC="$(python -c 'import csv,sys; r=list(csv.DictReader(open(sys.argv[1],encoding="utf-8"))); print(r[-1]["video_time_sec"])' "$REPO_ROOT/pop/edge/output/readings.csv")"
    EXPECTED_TIMESTAMP="$(python -c 'import sys; from datetime import datetime,timedelta,timezone; s=datetime.fromisoformat(sys.argv[1].replace(\"Z\",\"+00:00\")); print((s+timedelta(seconds=float(sys.argv[2]))).astimezone(timezone.utc).strftime(\"%Y-%m-%dT%H:%M:%SZ\"))' "$START_TIME" "$LAST_VIDEO_SEC")"
    cd "$INFRA_DIR"
    DB_STABLE="$(docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "select stable_count from readings where camera_id='$CAMERA_ID' and timestamp='$EXPECTED_TIMESTAMP'::timestamptz;" | tr -d '[:space:]')"
    cd "$REPO_ROOT"
    if [[ "$DB_STABLE" == "$CSV_STABLE" ]]; then
      add_result "Exact timestamp match" "PASS" "timestamp=$EXPECTED_TIMESTAMP; DB stable=$DB_STABLE; CSV stable=$CSV_STABLE"
    else
      add_result "Exact timestamp match" "FAIL" "timestamp=$EXPECTED_TIMESTAMP; DB stable=$DB_STABLE; CSV stable=$CSV_STABLE"
    fi
  else
    add_result "Exact timestamp match" "FAIL" "Skipped: admin login unavailable"
  fi
else
  add_result "Edge first run" "FAIL" "Skipped: edge Python, config, video, or POP_DEVICE_KEY unavailable"
  add_result "Edge duplicate run" "FAIL" "Skipped: edge Python, config, video, or POP_DEVICE_KEY unavailable"
  add_result "Reading count unchanged" "FAIL" "Skipped: edge run unavailable"
  add_result "Exact timestamp match" "FAIL" "Skipped: edge run or admin login unavailable"
fi

printf "%-28s %-4s %s\n" "CHECK" "STATUS" "DETAIL"
printf "%-28s %-4s %s\n" "-----" "------" "------"
for result in "${CHECKS[@]}"; do
  IFS='|' read -r check status detail <<<"$result"
  printf "%-28s %-4s %s\n" "$check" "$status" "$detail"
  [[ "$status" == "PASS" ]] || failed=1
done

exit "$failed"
