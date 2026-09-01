#!/usr/bin/env bash
# Build and deploy the HSE inspection analysis service to Cloud Run.
#
# Secrets are never passed on the command line: they are mounted from Secret
# Manager by name, so nothing sensitive appears here or in your shell history.
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${REGION:-europe-west1}"
SERVICE="${SERVICE:-hse-audit-agent}"
EVIDENCE_BUCKET="${EVIDENCE_BUCKET:-hse-audit-agent-evidence}"

if [[ -z "${PROJECT_ID}" ]]; then
  echo "PROJECT_ID is not set and no gcloud default project is configured." >&2
  exit 1
fi

echo "Deploying ${SERVICE} to ${REGION} in ${PROJECT_ID}"

gcloud run deploy "${SERVICE}" \
  --source . \
  --project "${PROJECT_ID}" \
  --region europe-west1 \
  --allow-unauthenticated \
  --memory 1Gi \
  --timeout 300 \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT_ID},STORE_BACKEND=firestore,STORAGE_BACKEND=gcs,EVIDENCE_BUCKET=${EVIDENCE_BUCKET}" \
  --set-secrets "ANALYSIS_ENGINE_API_KEY=analysis-engine-api-key:latest,NOTIFIER_API_KEY=notifier-api-key:latest,NOTIFIER_SENDER_EMAIL=notifier-sender-email:latest"

echo
echo "Service URL:"
gcloud run services describe "${SERVICE}" \
  --project "${PROJECT_ID}" --region europe-west1 --format 'value(status.url)'
