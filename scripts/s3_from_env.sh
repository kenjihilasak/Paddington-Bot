#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_PATH="$REPO_ROOT/.env"

if [[ ! -f "$ENV_PATH" ]]; then
  echo "No .env file found at $ENV_PATH" >&2
  return 1 2>/dev/null || exit 1
fi

set -a
source "$ENV_PATH"
set +a

: "${BUCKET:?BUCKET is missing in .env}"
: "${ENDPOINT:?ENDPOINT is missing in .env}"
: "${ACCESS_KEY_ID:?ACCESS_KEY_ID is missing in .env}"
: "${SECRET_ACCESS_KEY:?SECRET_ACCESS_KEY is missing in .env}"

export AWS_ACCESS_KEY_ID="$ACCESS_KEY_ID"
export AWS_SECRET_ACCESS_KEY="$SECRET_ACCESS_KEY"
export AWS_DEFAULT_REGION="${REGION:-auto}"

echo "S3 env loaded from .env"
echo "Bucket: $BUCKET"
echo "Endpoint: $ENDPOINT"
echo "Use: aws s3 ls s3://$BUCKET --endpoint-url $ENDPOINT"
