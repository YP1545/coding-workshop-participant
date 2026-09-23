#!/usr/bin/env bash
# Let a deep link into the single-page app load the app.
#
# Part of: deployment tooling.
#
# The problem: opening https://<dist>/incidents directly returns S3's raw
# AccessDenied XML instead of the application. Two given settings combine to
# cause it, and neither is wrong on its own:
#
#   1. infra/cloudfront.tf maps a 404 to /index.html with a 200, which is what
#      makes client-side routes work — but it maps *only* 404.
#   2. The bucket policy grants s3:GetObject and nothing else. Without
#      s3:ListBucket, S3 answers a request for a key that does not exist with
#      403 AccessDenied rather than 404, because it refuses to reveal whether
#      the object exists. CloudFront has no mapping for 403, so the XML is
#      served to the browser as-is.
#
# The fix is to grant s3:ListBucket to the same CloudFront principal. S3 then
# answers 404 for a missing key, CloudFront's existing rule turns that into
# index.html, and the router takes over. This does not make the bucket public:
# the principal is still only CloudFront, still only this distribution.
#
# Editing infra/cloudfront.tf to add a 403 mapping would be the tidier fix, but
# this project treats the scaffold as fixed. The participant role has s3:* on
# app-prefixed buckets, so the policy can be amended from here instead.
#
# IMPORTANT: `terraform apply` owns the bucket policy and will revert this.
# Run it after every deploy, like ./deploy/set-jwt-secret.sh. Safe to re-run.
#
# Usage:
#   ./deploy/fix-spa-routing.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." > /dev/null 2>&1 || exit 1; pwd -P)"

for tool in aws jq; do
    command -v "$tool" > /dev/null 2>&1 || { echo "ERROR: '$tool' is missing."; exit 1; }
done

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

BUCKET="${AWS_S3_WEBSITE_BUCKET:-${PROJECT_NAME:-coding-workshop}-website-${PARTICIPANT_ID:-}}"
echo "Bucket: $BUCKET"

CURRENT=$(aws s3api get-bucket-policy --bucket "$BUCKET" --query Policy --output text)

if echo "$CURRENT" | jq -e '.Statement[] | select(.Action == "s3:ListBucket")' > /dev/null 2>&1; then
    echo "  - s3:ListBucket is already granted; nothing to do."
    exit 0
fi

# Reuse the existing statement's principal and condition rather than writing
# new ones, so this cannot accidentally widen access beyond the distribution
# Terraform already allowed.
UPDATED=$(echo "$CURRENT" | jq '
  .Statement[0] as $existing
  | .Statement += [{
      Sid: "AllowCloudFrontListForSpaRouting",
      Effect: "Allow",
      Principal: $existing.Principal,
      Action: "s3:ListBucket",
      # ListBucket acts on the bucket itself, not on objects, so the resource
      # is the bucket ARN without the trailing /*.
      Resource: ($existing.Resource | rtrimstr("/*")),
      Condition: $existing.Condition
    }]
')

aws s3api put-bucket-policy --bucket "$BUCKET" --policy "$UPDATED"

echo "  - granted s3:ListBucket to the CloudFront distribution"
echo
echo "S3 now answers 404 for a missing key, so CloudFront serves index.html and"
echo "deep links work. Allow a minute for the 404 response already cached at the"
echo "edge to expire, or invalidate:"
echo
echo "  aws cloudfront create-invalidation --distribution-id \$(cd infra && terraform output -raw cloudfront_distribution_id) --paths '/*'"
