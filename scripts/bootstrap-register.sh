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
# If you use a non-default port, either export KALSHI_ODDS_DASHBOARD_PORT (matches .env)
# or set the full base URL: export KALSHI_DASHBOARD_URL=http://127.0.0.1:9000
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Port / base URL: same names as the Python app (.env uses KALSHI_ODDS_* prefix).
_port_from_dotenv() {
  local f="$REPO_ROOT/.env"
  [[ -f "$f" ]] || return 0
  grep -E '^[[:space:]]*KALSHI_ODDS_DASHBOARD_PORT=' "$f" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '\r' | tr -d " '\""
}

if [[ -n "${KALSHI_DASHBOARD_URL:-}" ]]; then
  BASE="${KALSHI_DASHBOARD_URL}"
  BASE="${BASE%/}"
else
  PORT="${KALSHI_ODDS_DASHBOARD_PORT:-${KALSHI_DASHBOARD_PORT:-}}"
  if [[ -z "$PORT" ]]; then
    PORT="$(_port_from_dotenv)" || true
  fi
  PORT="${PORT:-8080}"
  BASE="http://127.0.0.1:${PORT}"
fi

USER="${KALSHI_BOOTSTRAP_USER:-}"
PASS="${KALSHI_BOOTSTRAP_PASS:-}"

if [[ -z "$USER" || -z "$PASS" ]]; then
  echo "Set KALSHI_BOOTSTRAP_USER and KALSHI_BOOTSTRAP_PASS (see script header)." >&2
  exit 1
fi

BODY="$(python3 -c 'import json, sys; print(json.dumps({"username": sys.argv[1], "password": sys.argv[2]}))' "$USER" "$PASS")"

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

set +e
code="$(curl -sS --connect-timeout 3 -o "$TMP" -w "%{http_code}" -X POST "${BASE}/api/auth/register" \
  -H "Content-Type: application/json" \
  -c "${KALSHI_COOKIE_JAR:-cookies.txt}" \
  -d "$BODY")"
curl_ec=$?
set -e

if [[ "$curl_ec" -ne 0 ]]; then
  echo "" >&2
  echo "Could not reach the dashboard at ${BASE} (curl exit ${curl_ec})." >&2
  echo "" >&2
  echo "In another terminal, start the server from the repo root:" >&2
  echo "  ./venv/bin/kalshi-odds dashboard" >&2
  echo "  # or: kalshi-odds dashboard" >&2
  echo "" >&2
  echo "If you changed the port in .env, this script reads KALSHI_ODDS_DASHBOARD_PORT from .env," >&2
  echo "or set explicitly:  export KALSHI_DASHBOARD_URL=http://127.0.0.1:YOUR_PORT" >&2
  exit 1
fi

cat "$TMP"
echo ""
echo "HTTP ${code}"

# Back-compat: older server builds may (incorrectly) expect a query param named `payload`.
if [[ "$code" == "422" ]] && grep -q '"loc":\["query","payload"\]' "$TMP"; then
  LEGACY_PAYLOAD="$(python3 -c 'import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))' "$BODY")"
  code="$(curl -sS --connect-timeout 3 -o "$TMP" -w "%{http_code}" -X POST "${BASE}/api/auth/register?payload=${LEGACY_PAYLOAD}" \
    -H "Content-Type: application/json" \
    -c "${KALSHI_COOKIE_JAR:-cookies.txt}")"
  echo ""
  echo "Retried legacy payload mode"
  cat "$TMP"
  echo ""
  echo "HTTP ${code}"
fi

if [[ "$code" == "404" ]]; then
  echo "" >&2
  echo "404: /api/auth/register not found. Use this repo's package, e.g. from repo root:" >&2
  echo "  pip install -e ." >&2
  echo "then restart: kalshi-odds dashboard" >&2
  exit 1
fi

if [[ "$code" == "422" ]]; then
  echo "" >&2
  echo "422: JSON payload was rejected by the server." >&2
  echo "If the auto-retry above did not succeed, reinstall/restart from repo root:" >&2
  echo "  ./venv/bin/python -m pip install -e ." >&2
  echo "  ./venv/bin/kalshi-odds dashboard" >&2
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
