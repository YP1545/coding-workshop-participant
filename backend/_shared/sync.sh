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

    for module in "${MODULES[@]}"; do
        if cmp -s "$SHARED_DIR/$module" "$service_dir/$module"; then
            echo "  = $service/$module"
        else
            cp "$SHARED_DIR/$module" "$service_dir/$module"
            echo "  > $service/$module updated"
        fi
    done
done

echo "Done."
