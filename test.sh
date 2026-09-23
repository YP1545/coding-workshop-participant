#!/usr/bin/env bash
# Run every test in the project: backend, then frontend.
#
# Part of: project tooling.
#
# Why this exists: the two halves are tested with different tools, and a single
# command means nobody has to remember either. The backend suite creates its own
# throwaway database and drops it afterwards, so this is safe to run at any time
# and never touches the development data.
#
# Usage:
#   ./test.sh              run everything
#   ./test.sh --coverage   run everything and report coverage

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" > /dev/null 2>&1 || exit 1; pwd -P)"
VENV="$ROOT/.venv/bin"

COVERAGE=false
if [ "${1:-}" = "--coverage" ]; then
    COVERAGE=true
fi

# The backend tests connect as this user to create their own database. Override
# any of these in the environment if your local PostgreSQL differs.
export POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
export POSTGRES_PORT="${POSTGRES_PORT:-5432}"
export POSTGRES_USER="${POSTGRES_USER:-postgres}"
export POSTGRES_PASS="${POSTGRES_PASS:-postgres123}"
export IS_LOCAL=true

echo "============================================================"
echo "Backend  —  pytest against a disposable database"
echo "============================================================"
cd "$ROOT/backend/_shared"
if [ "$COVERAGE" = true ]; then
    # Measured on the four service directories only. The copies in _shared are
    # the sources those are synced from, so counting both would report every
    # shared module twice — once at 0%, because nothing imports the original.
    "$VENV/pytest" --cov=../users-service --cov=../incidents-service \
        --cov=../facilities-service --cov=../engineers-service \
        --cov-report=term-missing:skip-covered
else
    "$VENV/pytest"
fi

echo
echo "============================================================"
echo "Frontend  —  Vitest with React Testing Library"
echo "============================================================"
cd "$ROOT/frontend"
if [ "$COVERAGE" = true ]; then
    npm run coverage
else
    npm test
fi

echo
echo "============================================================"
echo "  All tests passed"
echo "============================================================"
