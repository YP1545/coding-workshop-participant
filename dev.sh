#!/usr/bin/env bash
# Start the app for local development: the backend, then the frontend.
#
# Part of: project tooling.
#
# Why this exists rather than bin/start-dev.sh: that script starts the full
# LocalStack path — MongoDB, Docker, LocalStack, and a Terraform deploy that
# packages each service into a Lambda. This app uses neither MongoDB nor
# LocalStack, and backend/_shared/serve_local.py runs the same four FastAPI
# applications directly, at the same URLs. That is seconds instead of minutes,
# and needs no sudo. bin/ is left exactly as it was shipped.
#
# What this does NOT cover: Mangum and the CloudFront path prefix, which only
# exist on the Lambda path. backend/_shared/tests/test_lambda_entry.py tests
# those, and bin/start-dev.sh is still the way to exercise them for real.
#
# Usage:
#   ./dev.sh            backend on :8000, frontend on :3000
#   ./dev.sh --api-only just the backend
#
# Press Ctrl+C to stop everything.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" > /dev/null 2>&1 || exit 1; pwd -P)"
VENV="$ROOT/.venv/bin"

API_PORT=8000
WEB_PORT=3000

API_ONLY=false
if [ "${1:-}" = "--api-only" ]; then
    API_ONLY=true
fi

# IS_LOCAL is the switch auth.py and db.py both read: it selects the local
# signing secret and turns off sslmode=require. Without it the server starts
# and answers /health, but refuses to issue a token — see auth.jwt_secret().
export IS_LOCAL=true
export POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
export POSTGRES_PORT="${POSTGRES_PORT:-5432}"
export POSTGRES_NAME="${POSTGRES_NAME:-postgres}"
export POSTGRES_USER="${POSTGRES_USER:-postgres}"
export POSTGRES_PASS="${POSTGRES_PASS:-postgres123}"

# Report whoever holds a port, so "address already in use" names the process
# instead of sending you looking for it.
port_holder() {
    # "|| true": no match means the port is free, which is the good case. Without
    # it, grep's exit status 1 combines with `set -o pipefail` to abort the whole
    # script — silently, because nothing has been printed yet.
    { ss -ltnp 2>/dev/null | grep ":$1 " | grep -oP 'pid=\K[0-9]+' | head -1; } || true
}

require_free_port() {
    local port="$1" name="$2" pid
    pid="$(port_holder "$port")"
    if [ -n "$pid" ]; then
        echo "  x Port $port is already in use by pid $pid ($name)."
        echo "    Stop it with:  kill $pid"
        exit 1
    fi
}

echo "============================================================"
echo "  ACME Facility Incident Platform  —  local development"
echo "============================================================"
echo

echo "[1/4] PostgreSQL"
if ! pg_isready -q -h "$POSTGRES_HOST" -p "$POSTGRES_PORT"; then
    echo "  x PostgreSQL is not answering on $POSTGRES_HOST:$POSTGRES_PORT."
    echo "    Start it with:  sudo systemctl start postgresql"
    exit 1
fi
echo "  - running on $POSTGRES_HOST:$POSTGRES_PORT"
echo

# Copy the canonical shared modules into the four service directories. Cheap,
# and it removes "did I forget to sync?" as an explanation for odd behaviour.
echo "[2/4] Shared modules"
"$ROOT/backend/_shared/sync.sh" | sed 's/^/  /'
echo

echo "[3/4] Backend"
require_free_port "$API_PORT" "backend"
cd "$ROOT/backend/_shared"
"$VENV/python" serve_local.py --port "$API_PORT" &
API_PID=$!

# Kill whatever we started, however this script exits — Ctrl+C included.
# Without this the servers outlive the terminal and the next run hits
# "address already in use", which is what makes them hard to find.
cleanup() {
    echo
    echo "Stopping..."
    kill "$API_PID" 2> /dev/null || true
    [ -n "${WEB_PID:-}" ] && kill "$WEB_PID" 2> /dev/null || true
    wait 2> /dev/null || true
    echo "Stopped."
}
trap cleanup EXIT INT TERM

# Wait for it to answer rather than guessing with sleep: the first request
# opens a database connection, which is the slow part of startup.
for _ in $(seq 1 20); do
    if curl -sf -o /dev/null "http://127.0.0.1:$API_PORT/api/users-service/health"; then
        break
    fi
    sleep 0.5
done

if ! curl -sf -o /dev/null "http://127.0.0.1:$API_PORT/api/users-service/health"; then
    echo "  x Backend did not come up on :$API_PORT"
    exit 1
fi
echo "  - http://127.0.0.1:$API_PORT/api/{service}/health"
echo "  - http://127.0.0.1:$API_PORT/api/{service}/docs   (API documentation)"
echo

if [ "$API_ONLY" = true ]; then
    echo "Backend only. Press Ctrl+C to stop."
    wait "$API_PID"
    exit 0
fi

echo "[4/4] Frontend"
require_free_port "$WEB_PORT" "frontend"
cd "$ROOT/frontend"
if [ ! -d node_modules ]; then
    echo "  - installing dependencies (first run)"
    npm install
fi
npm run dev &
WEB_PID=$!
echo "  - http://localhost:$WEB_PORT"
echo

echo "============================================================"
echo "  Ready. Sign in as dana.admin@acme.inc / LocalDev!2026"
echo "  Press Ctrl+C to stop both servers."
echo "============================================================"

wait
