#!/usr/bin/env bash
# Copy the shared backend modules into every service directory.
#
# Part of: backend / build tooling.
#
# Why this exists: Terraform packages each Lambda from its own directory
# (infra/locals.tf), so a service cannot import code from outside that
# directory. The shared modules therefore have to be physically present in each
# service. They are copied from here rather than edited in place so there is
# still one source of truth; run this after changing anything in _shared.

set -euo pipefail

SHARED_DIR="$(cd "$(dirname "$0")" > /dev/null 2>&1 || exit 1; pwd -P)"
BACKEND_DIR="$(cd "$SHARED_DIR/.." > /dev/null 2>&1 || exit 1; pwd -P)"

# Modules every service needs. Add to this list when a new shared module appears.
MODULES=(app.py errors.py deps.py schemas.py db.py models.py auth.py crud.py)

echo "Syncing shared modules from $SHARED_DIR"

for service_dir in "$BACKEND_DIR"/*/; do
    service="$(basename "$service_dir")"

    # Directories starting with "_" are excluded from service discovery by both
    # infra/locals.tf and bin/start-dev.sh, so they are not services.
    [[ "$service" == _* ]] && continue

    # The migration runner imports no web framework, so it gets only the two
    # modules Alembic's env.py needs. Copying app.py or deps.py there would put
    # fastapi imports in a package whose requirements.txt has no fastapi —
    # harmless while nothing imports them, and misleading to whoever reads it
    # next.
    if [ "$service" = "migrate-service" ]; then
        service_modules=(db.py models.py seed.py)
    else
        service_modules=("${MODULES[@]}")
    fi

    for module in "${service_modules[@]}"; do
        if cmp -s "$SHARED_DIR/$module" "$service_dir/$module"; then
            echo "  = $service/$module"
        else
            cp "$SHARED_DIR/$module" "$service_dir/$module"
            echo "  > $service/$module updated"
        fi
    done
done

# The migration runner needs the migrations themselves, which the other
# services have no use for. Copied here rather than kept in its own directory so
# there is still exactly one set of migration files, matching one models.py.
MIGRATE_DIR="$BACKEND_DIR/migrate-service"
if [ -d "$MIGRATE_DIR" ]; then
    echo "Syncing migrations into migrate-service"
    cp "$SHARED_DIR/alembic.ini" "$MIGRATE_DIR/alembic.ini"
    rm -rf "$MIGRATE_DIR/alembic"
    # --parents would carry __pycache__ across; the find keeps the copy to the
    # files Alembic actually reads.
    mkdir -p "$MIGRATE_DIR/alembic/versions"
    cp "$SHARED_DIR/alembic/env.py" "$MIGRATE_DIR/alembic/env.py"
    cp "$SHARED_DIR/alembic/script.py.mako" "$MIGRATE_DIR/alembic/script.py.mako"
    cp "$SHARED_DIR"/alembic/versions/*.py "$MIGRATE_DIR/alembic/versions/"
    echo "  > $(ls "$MIGRATE_DIR/alembic/versions" | wc -l) migration(s)"
fi

echo "Done."
