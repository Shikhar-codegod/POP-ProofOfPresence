#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
INFRA_DIR="$REPO_ROOT/pop/infra"
EDGE_PYTHON="$REPO_ROOT/pop/edge/.venv/bin/python"
API_BASE="${POP_API_URL:-http://localhost:8000}"
CENTRE_ID="${POP_CENTRE_ID:-a1000000-0000-4000-8000-000000000001}"
VIDEO="${POP_VERIFY_VIDEO:-$REPO_ROOT/pop/ml/clips/classroom_cctv_360p.mp4}"
CONFIG="${POP_VERIFY_CONFIG:-$REPO_ROOT/pop/edge/config.local.yaml}"

declare -a CHECKS=()
failed=0

add_result() {
  CHECKS+=("$1|$2|$3")
}

if [[ -z "${POP_ADMIN_EMAIL:-}" || -z "${POP_ADMIN_PASSWORD:-}" ]]; then
  add_result "Credentials" "FAIL" "POP_ADMIN_EMAIL or POP_ADMIN_PASSWORD is not set"
  failed=1
fi
if [[ -z "${POP_DEVICE_KEY:-}" ]]; then
  add_result "Device key" "FAIL" "POP_DEVICE_KEY is not set"
  failed=1
fi
if [[ ! -x "$EDGE_PYTHON" && ! -x "$REPO_ROOT/pop/edge/.venv/Scripts/python.exe" ]]; then
  add_result "Environment" "FAIL" "Edge Python venv not found"
  failed=1
fi
if [[ ! -f "$CONFIG" ]]; then
  add_result "Edge config" "FAIL" "Config not found"
  failed=1
fi
if [[ ! -f "$VIDEO" ]]; then
  add_result "Test video" "FAIL" "Video not found"
  failed=1
fi

if (( failed == 0)); then
  if (cd "$INFRA_DIR" && docker compose ps >/dev/null); then
    add_result "Docker Compose services" "PASS" "docker compose ps"
  else
    add_result "Docker Compose services" "FAIL" "docker compose ps"
    failed=1
  fi
fi

if (( failed == 0)); then
  if curl -fsS "$API_BASE/health" >/dev/null; then
    add_result "/health" "PASS" "GET /health"
  else
    add_result "/health" "FAIL" "GET /health"
    failed=1
  fi
fi

if (( failed == 0)); then
  LOGIN_JSON="$(curl -fsS -X POST "$API_BASE/api/v1/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$POP_ADMIN_EMAIL\",\"password\":\"$POP_ADMIN_PASSWORD\"}")"
  TOKEN="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])' <<<"$LOGIN_JSON")"
  add_result "Admin login" "PASS" "POST /api/v1/auth/login"

  COUNT_BEFORE="$(cd "$INFRA_DIR" && docker compose exec -T postgres psql -U pop_user -d pop_db -tAc 'SELECT COUNT(*) FROM readings;' | tr -d '[:space:]')"
  START_TIME="$(python3 -c 'from datetime import datetime,timezone,timedelta; print((datetime.now(timezone.utc)-timedelta(seconds=30)).strftime("%Y-%m-%dT%H:%M:%SZ"))')"

  if [[ -x "$REPO_ROOT/pop/edge/.venv/Scripts/python.exe" ]]; then
    EDGE_PYTHON="$REPO_ROOT/pop/edge/.venv/Scripts/python.exe"
  fi

  FIRST_LOG="$("$EDGE_PYTHON" "$REPO_ROOT/pop/edge/run_edge.py" --config "$CONFIG" --video "$VIDEO" --start-time "$START_TIME" 2>&1)"
  FIRST_201="$(grep -c 'Reading POST HTTP 201' <<<"$FIRST_LOG" || true)"
  if [[ "$FIRST_201" -gt 0 ]]; then
    add_result "Edge first run" "PASS" "$FIRST_201 reading POST(s) returned HTTP 201"
  else
    add_result "Edge first run" "FAIL" "No HTTP 201 reading POST detected"
  fi

  COUNT_AFTER_FIRST="$(cd "$INFRA_DIR" && docker compose exec -T postgres psql -U pop_user -d pop_db -tAc 'SELECT COUNT(*) FROM readings;' | tr -d '[:space:]')"
  SECOND_LOG="$("$EDGE_PYTHON" "$REPO_ROOT/pop/edge/run_edge.py" --config "$CONFIG" --video "$VIDEO" --start-time "$START_TIME" 2>&1)"
  SECOND_200="$(grep -c 'Reading POST HTTP 200' <<<"$SECOND_LOG" || true)"
  if [[ "$SECOND_200" -gt 0 ]]; then
    add_result "Edge duplicate run" "PASS" "$SECOND_200 reading POST(s) returned HTTP 200"
  else
    add_result "Edge duplicate run" "FAIL" "No HTTP 200 reading POST detected"
  fi

  COUNT_AFTER_SECOND="$(cd "$INFRA_DIR" && docker compose exec -T postgres psql -U pop_user -d pop_db -tAc 'SELECT COUNT(*) FROM readings;' | tr -d '[:space:]')"
  if [[ "$COUNT_AFTER_FIRST" == "$COUNT_AFTER_SECOND" ]]; then
    add_result "Reading count unchanged" "PASS" "Before=$COUNT_BEFORE; after first=$COUNT_AFTER_FIRST; after second=$COUNT_AFTER_SECOND"
  else
    add_result "Reading count unchanged" "FAIL" "Before=$COUNT_BEFORE; after first=$COUNT_AFTER_FIRST; after second=$COUNT_AFTER_SECOND"
  fi

  CSV_STABLE="$(python3 -c 'import csv,sys; r=list(csv.DictReader(open(sys.argv[1], encoding="utf-8"))); print(r[-1]["stable_count"])' "$REPO_ROOT/pop/edge/output/readings.csv")"
  CENTRE_JSON="$(curl -fsS -H "Authorization: Bearer $TOKEN" "$API_BASE/api/v1/centres/$CENTRE_ID")"
  API_STABLE="$(python3 -c 'import json,sys; d=json.load(sys.stdin); print(next((int(c["latest_reading"]["stable_count"]) for c in d["cameras"] if c.get("latest_reading")), ""))' <<<"$CENTRE_JSON")"
  if [[ "$API_STABLE" == "$CSV_STABLE" ]]; then
    add_result "Latest stable_count match" "PASS" "API=$API_STABLE; CSV=$CSV_STABLE"
  else
    add_result "Latest stable_count match" "FAIL" "API=$API_STABLE; CSV=$CSV_STABLE"
  fi
fi

printf "%-28s %-4s %s\n" "CHECK" "STATUS" "DETAIL"
printf "%-28s %-4s %s\n" "-----" "------" "------"
for result in "${CHECKS[@]}"; do
  IFS='|' read -r check status detail <<<"$result"
  printf "%-28s %-4s %s\n" "$check" "$status" "$detail"
  [[ "$status" == "PASS" ]] || failed=1
done

exit "$failed"
