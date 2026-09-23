#!/usr/bin/env bash
# Re-apply everything `terraform apply` reverts.
#
# Part of: deployment tooling.
#
# Why this exists: two settings this application needs are not in infra/, which
# this project treats as fixed. They are applied out of band afterwards — and
# Terraform owns both resources, so every `./bin/deploy-backend.sh` silently
# removes them again:
#
#   * JWT_SECRET on each Lambda. Without it sign-in returns 500.
#   * s3:ListBucket for CloudFront. Without it every deep link returns S3's
#     AccessDenied XML instead of the app.
#
# Neither failure appears until somebody tries to sign in or opens a link, by
# which point the deploy looks finished. One command after every deploy is the
# cheapest way not to be caught by that.
#
# Usage:
#   ./bin/deploy-backend.sh && ./deploy/after-deploy.sh
#
#   JWT_SECRET='<the saved value>' ./deploy/after-deploy.sh
#
# Pass the same JWT_SECRET each time. Generating a new one signs out everyone
# holding a current token.

set -euo pipefail

HERE="$(cd "$(dirname "$0")" > /dev/null 2>&1 || exit 1; pwd -P)"

echo "============================================================"
echo "  Re-applying what Terraform reverts"
echo "============================================================"
echo

echo "[1/2] Signing secret"
"$HERE/set-jwt-secret.sh" | sed 's/^/  /'
echo

echo "[2/2] Single-page-app routing"
"$HERE/fix-spa-routing.sh" | sed 's/^/  /'
echo

echo "============================================================"
echo "  Done. Sign-in and deep links should both work."
echo "============================================================"
