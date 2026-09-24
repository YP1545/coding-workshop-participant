#!/usr/bin/env bash
# Give each Lambda enough memory to be quick.
#
# Part of: deployment tooling.
#
# infra/lambda.tf sets memory_size = 128, the minimum. Lambda allocates CPU in
# proportion to memory — 128 MB is roughly a twelfth of a vCPU — and bcrypt is
# deliberately CPU-expensive, so signing in took about four seconds. Measured:
#
#     128 MB    login 4.2s
#    1024 MB    login 0.61s
#
# It is close to free. Lambda bills GB-seconds, and a function that finishes
# seven times sooner uses almost the same total:
#
#     0.128 GB x 4.2s  = 0.54 GB-s
#     1.024 GB x 0.61s = 0.62 GB-s
#
# So this buys a seven-fold speed-up for about 15% more cost on the one call
# that was slow, and makes every other call quicker too.
#
# infra/ is the scaffold and is not modified, so this is applied afterwards.
# Terraform owns memory_size and reverts it, so it runs after every deploy —
# ./deploy/after-deploy.sh does that for you.
#
# Usage:
#   ./deploy/set-lambda-memory.sh          1024 MB
#   MEMORY_MB=512 ./deploy/set-lambda-memory.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." > /dev/null 2>&1 || exit 1; pwd -P)"
MEMORY_MB="${MEMORY_MB:-1024}"

command -v aws > /dev/null 2>&1 || { echo "ERROR: 'aws' is missing."; exit 1; }

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

PREFIX="${PROJECT_NAME:-coding-workshop}"
SUFFIX="${PARTICIPANT_ID:-${TF_VAR_aws_app_code:-}}"

# Names are derived, not listed: the IAM policy grants lambda:* only on ARNs
# matching the app prefix, and lambda:ListFunctions is account-wide.
for requirements in "$ROOT"/backend/*/requirements.txt; do
    service="$(basename "$(dirname "$requirements")")"
    case "$service" in _*) continue ;; esac

    name="$PREFIX-$service-$SUFFIX"

    current=$(aws lambda get-function-configuration --function-name "$name" \
        --query MemorySize --output text 2> /dev/null || echo "")

    if [ "$current" = "$MEMORY_MB" ]; then
        echo "  = $service already at ${MEMORY_MB}MB"
        continue
    fi

    aws lambda update-function-configuration --function-name "$name" \
        --memory-size "$MEMORY_MB" > /dev/null

    echo "  > $service ${current:-?}MB -> ${MEMORY_MB}MB"
done

echo
echo "Changing memory replaces the container, so the next call to each service"
echo "is a cold start. After that, signing in should take well under a second."
