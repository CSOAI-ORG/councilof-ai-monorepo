#!/usr/bin/env bash
# ADX staging (N5-22) — PREP-ONLY. AMMP seller registration is owner-gated; NOT executed.
# CSOAI Ltd is jurisdiction-eligible (UK on the eligible list). This stages the data-set
# creation flow (aws dataexchange). Free-product posture: no tax/banking needed today.
# Reference: aws-samples/aws-dataexchange-api-samples
set -uo pipefail
AWS_PROFILE="${AWS_PROFILE:-default}"
DATASET_NAME="csoai-gspc-evidence"
BUCKET="${S3_BUCKET:-s3://csoai-adx-staging}"
echo "[PREP-ONLY] ADX create-data-set flow (not executed against AMMP):"
echo "  aws dataexchange create-data-set --type Files --name $DATASET_NAME"
echo "  aws dataexchange create-revision --data-set-id <id>"
echo "  aws dataexchange create-job --type IMPORT_ASSETS_FROM_S3 --details ..."
echo "  aws dataexchange start-job --job-id <id>"
echo "  aws dataexchange update-revision --data-set-id <id> --revision-id <id> --finalized"
echo "  staging prefix: $BUCKET/csoai-evidence/ (listing captured, not uploaded)"
