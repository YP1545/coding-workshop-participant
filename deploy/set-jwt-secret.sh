#!/usr/bin/env bash
# Put JWT_SECRET on every deployed Lambda.
#
# Part of: deployment tooling.
#
# Why this exists: infra/locals.tf injects APP_*, IS_LOCAL, POSTGRES_* and
# MONGO_*, but no signing secret — and infra/ is the scaffold, which this
# project does not modify. Without a secret, auth.jwt_secret() raises rather
# than falling back to the development default that is committed in this
# repository, so a deployed service returns 500 on the first sign-in. That
# failure is deliberate: a default anyone can read from git would let them mint
# a facility_admin token for any account.
#
# infra/policy.tftpl grants the participant role lambda:* on functions matching
# the app prefix, so setting the variable from here needs no infra change.
#
# IMPORTANT: Terraform owns environment_variables, so the next
# `terraform apply` (or ./bin/deploy-backend.sh) removes what this sets. Run
# this after every deploy. The script is safe to run repeatedly.
#
# Usage:
#   ./deploy/set-jwt-secret.sh              generate a secret and apply it
#   JWT_SECRET='...' ./deploy/set-jwt-secret.sh    use one you already have
#
# Save the generated value somewhere you can find it: every service must sign
# with the same key, and rotating it invalidates every token in circulation.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." > /dev/null 2>&1 || exit 1; pwd -P)"

for tool in aws jq; do
    command -v "$tool" > /dev/null 2>&1 || { echo "ERROR: '$tool' is missing."; exit 1; }
done

# The scaffold writes the participant's credentials and APP_* values here.
CONFIG="$ROOT/ENVIRONMENT.config"
if [ -f "$CONFIG" ]; then
    set -a
    # shellcheck disable=SC1090
    . "$CONFIG"
    set +a
fi

if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo "ERROR: AWS credentials are missing or expired."
    echo "       Refresh them with ./bin/setup-participant.sh and try again."
    exit 1
fi

# 32 random bytes, base64. Long enough that brute-forcing an HS256 signature is
# not a realistic attack, and generated locally so it never travels anywhere it
# does not need to.
SECRET="${JWT_SECRET:-$(openssl rand -base64 32)}"
GENERATED=false
[ -z "${JWT_SECRET:-}" ] && GENERATED=true

PREFIX="${PROJECT_NAME:-coding-workshop}"
SUFFIX="${PARTICIPANT_ID:-${TF_VAR_aws_app_code:-}}"

# Names are derived rather than listed. infra/policy.tftpl grants lambda:* only
# on ARNs matching the app prefix, and lambda:ListFunctions is account-wide, so
# listing is denied. The names are deterministic anyway: Terraform discovers
# services with the same glob used here and names each one <prefix>-<dir>-<id>.
FUNCTIONS=""
for requirements in "$ROOT"/backend/*/requirements.txt; do
    service="$(basename "$(dirname "$requirements")")"

    # Directories starting with "_" are excluded from discovery by
    # infra/locals.tf, so they are not services.
    case "$service" in _*) continue ;; esac

    # The migration runner has no authentication and never issues a token, so
    # it has no use for a signing key. Leaving it out keeps the secret on the
    # functions that actually need it.
    [ "$service" = "migrate-service" ] && continue

    FUNCTIONS="$FUNCTIONS $PREFIX-$service-$SUFFIX"
done

if [ -z "$FUNCTIONS" ]; then
    echo "ERROR: no services found under backend/."
    exit 1
fi

for name in $FUNCTIONS; do
    # The API replaces the whole variable map rather than merging into it, so
    # the current values have to be read back and combined — otherwise this
    # would wipe POSTGRES_* and the service could not reach the database.
    current=$(aws lambda get-function-configuration --function-name "$name" \
        --query 'Environment.Variables' --output json)

    merged=$(echo "$current" | jq --arg secret "$SECRET" '. + {JWT_SECRET: $secret}')

    aws lambda update-function-configuration \
        --function-name "$name" \
        --environment "{\"Variables\":$merged}" \
        > /dev/null

    echo "  set on $name"
done

echo
echo "Done. Every service now signs with the same key."

if [ "$GENERATED" = true ]; then
    echo
    echo "The generated secret — save this somewhere safe:"
    echo
    echo "  $SECRET"
    echo
    echo "Re-apply it after any deploy with:"
    echo "  JWT_SECRET='$SECRET' ./deploy/set-jwt-secret.sh"
    echo
    echo "Changing it signs out everyone holding a current token."
fi
