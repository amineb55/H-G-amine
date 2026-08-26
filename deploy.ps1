# Build and deploy the HSE inspection analysis service to Cloud Run.
#
# Secrets are never passed on the command line: they are mounted from Secret
# Manager by name, so nothing sensitive appears here or in your shell history.
$ErrorActionPreference = 'Stop'

$ProjectId      = if ($env:PROJECT_ID) { $env:PROJECT_ID } else { (gcloud config get-value project 2>$null) }
$Region         = if ($env:REGION) { $env:REGION } else { 'europe-west1' }
$Service        = if ($env:SERVICE) { $env:SERVICE } else { 'hse-audit-agent' }
$EvidenceBucket = if ($env:EVIDENCE_BUCKET) { $env:EVIDENCE_BUCKET } else { 'hse-audit-agent-evidence' }

if ([string]::IsNullOrWhiteSpace($ProjectId)) {
    Write-Error 'PROJECT_ID is not set and no gcloud default project is configured.'
    exit 1
}

Write-Host "Deploying $Service to $Region in $ProjectId"

$envVars = "GOOGLE_CLOUD_PROJECT=$ProjectId,STORE_BACKEND=firestore,STORAGE_BACKEND=gcs,EVIDENCE_BUCKET=$EvidenceBucket"
$secrets = 'ANALYSIS_ENGINE_API_KEY=analysis-engine-api-key:latest,NOTIFIER_API_KEY=notifier-api-key:latest,NOTIFIER_SENDER_EMAIL=notifier-sender-email:latest'

gcloud run deploy $Service `
  --source . `
  --project $ProjectId `
  --region europe-west1 `
  --allow-unauthenticated `
  --memory 1Gi `
  --timeout 300 `
  --set-env-vars $envVars `
  --set-secrets $secrets

if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ''
Write-Host 'Service URL:'
gcloud run services describe $Service --project $ProjectId --region europe-west1 --format 'value(status.url)'
