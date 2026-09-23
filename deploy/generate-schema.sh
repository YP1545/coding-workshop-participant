#!/usr/bin/env bash
# Regenerate deploy/schema.sql from the Alembic migrations.
#
# Part of: deployment tooling.
#
# Why this exists: Aurora sits in the VPC with no public endpoint, so
# `alembic upgrade head` cannot be run from a developer's machine. Alembic can
# emit the same DDL as plain SQL without connecting to anything, and that file
# can be run from anywhere that *can* reach the database — see deploy/README.md.
#
# The output is generated, never hand-edited. Run this after adding a migration
# so the file and the migrations cannot drift apart; a schema.sql that no longer
# matches models.py is worse than no file at all, because it looks authoritative.
#
# Usage:
#   ./deploy/generate-schema.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." > /dev/null 2>&1 || exit 1; pwd -P)"
SHARED="$ROOT/backend/_shared"
OUTPUT="$ROOT/deploy/schema.sql"

# Alembic needs the environment variables its env.py reads, even in offline
# mode where it never opens a connection: database_url() builds a URL string
# regardless, and IS_LOCAL decides whether it appends sslmode=require.
export IS_LOCAL=true
export POSTGRES_NAME="${POSTGRES_NAME:-postgres}"

echo "Generating $OUTPUT from the migrations in $SHARED/alembic/versions"

{
    echo "-- GENERATED FILE — do not edit by hand."
    echo "--"
    echo "-- Produced by deploy/generate-schema.sh from the Alembic migrations in"
    echo "-- backend/_shared/alembic/versions. Re-run that script after adding a"
    echo "-- migration; editing this file directly makes it disagree with models.py."
    echo "--"
    echo "-- What it contains: every table, enum type, index, constraint and the"
    echo "-- seeded incident_categories rows, wrapped in one transaction, plus the"
    echo "-- alembic_version stamp so Alembic can still take over later."
    echo "--"
    echo "-- Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "-- Head revision: $(cd "$SHARED" && "$ROOT/.venv/bin/alembic" heads 2>/dev/null | head -1)"
    echo ""
    cd "$SHARED" && "$ROOT/.venv/bin/alembic" upgrade head --sql 2>/dev/null
} > "$OUTPUT"

echo "Done. $(grep -c '^CREATE TABLE' "$OUTPUT") tables, $(wc -l < "$OUTPUT") lines."
