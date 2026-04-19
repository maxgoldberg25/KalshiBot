#!/usr/bin/env bash
# Register the first account via POST /api/auth/register (session cookie → cookies.txt).
#
# Prerequisites:
#   1. Dashboard running: kalshi-odds dashboard  (default http://127.0.0.1:8080)
#   2. In .env: KALSHI_ODDS_PUBLIC_REGISTRATION_ENABLED=true
#   3. KALSHI_ODDS_ADMIN_BOOTSTRAP_USERNAMES must include the same username you register.
#
# Usage:
#   export KALSHI_BOOTSTRAP_USER=myadmin
#   export KALSHI_BOOTSTRAP_PASS='your-secure-password'
#   ./scripts/bootstrap-register.sh
#
set -euo pipefail

PORT="${KALSHI_DASHBOARD_PORT:-8080}"
BASE="${KALSHI_DASHBOARD_URL:-http://127.0.0.1:${PORT}}"

USER="${KALSHI_BOOTSTRAP_USER:-}"
PASS="${KALSHI_BOOTSTRAP_PASS:-}"

if [[ -z "$USER" || -z "$PASS" ]]; then
  echo "Set KALSHI_BOOTSTRAP_USER and KALSHI_BOOTSTRAP_PASS (see script header)." >&2
  exit 1
fi

BODY="$(python3 -c 'import json, sys; print(json.dumps({"username": sys.argv[1], "password": sys.argv[2]}))' "$USER" "$PASS")"

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

code="$(curl -sS -o "$TMP" -w "%{http_code}" -X POST "${BASE}/api/auth/register" \
  -H "Content-Type: application/json" \
  -c "${KALSHI_COOKIE_JAR:-cookies.txt}" \
  -d "$BODY")"

cat "$TMP"
echo ""
echo "HTTP ${code}"

if [[ "$code" == "404" ]]; then
  echo "" >&2
  echo "404: /api/auth/register not found. Use this repo's package, e.g. from repo root:" >&2
  echo "  pip install -e ." >&2
  echo "then restart: kalshi-odds dashboard" >&2
  exit 1
fi

if [[ "$code" == "403" ]]; then
  echo "" >&2
  echo "403: Registration is invite-only. Set KALSHI_ODDS_PUBLIC_REGISTRATION_ENABLED=true in .env and restart." >&2
  exit 1
fi

if [[ "$code" != "200" ]]; then
  exit 1
fi
