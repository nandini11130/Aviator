<#
.SYNOPSIS
  Builds and deploys the Aviator FastAPI + Google ADK backend to Cloud Run.

.PREREQUISITES
  - gcloud CLI installed and authenticated: gcloud auth login
  - A GCP project with billing enabled: gcloud config set project <PROJECT_ID>
  - APIs enabled (one-time):
      gcloud services enable run.googleapis.com cloudbuild.googleapis.com `
        artifactregistry.googleapis.com firestore.googleapis.com aiplatform.googleapis.com

.USAGE
  ./infra/deploy-backend.ps1 -ProjectId "my-project" -FirebaseProjectId "my-firebase-project" -Region "asia-south1"
#>
param(
  [Parameter(Mandatory = $true)][string]$ProjectId,
  [string]$FirebaseProjectId,
  [string]$Region = "asia-south1",
  [string]$ServiceName = "aviator-api"
)

$ErrorActionPreference = "Stop"
if (-not $FirebaseProjectId) {
  $FirebaseProjectId = $ProjectId
}
Push-Location "$PSScriptRoot/../backend"

try {
  Write-Host "Deploying $ServiceName to Cloud Run (project=$ProjectId, region=$Region)..."

  # --source builds the Dockerfile with Cloud Build and deploys in one step.
  # Secrets (Stripe keys, AI Studio key) should be set with --set-secrets
  # instead of --set-env-vars once you have them in Secret Manager.
  gcloud run deploy $ServiceName `
    --project $ProjectId `
    --region $Region `
    --source . `
    --platform managed `
    --allow-unauthenticated `
    --update-env-vars "ENVIRONMENT=production,GOOGLE_CLOUD_PROJECT=$ProjectId,FIREBASE_PROJECT_ID=$FirebaseProjectId,CORS_ALLOW_ORIGINS=https://$FirebaseProjectId.web.app"

  Write-Host "Done. Fetch the service URL with:"
  Write-Host "  gcloud run services describe $ServiceName --project $ProjectId --region $Region --format='value(status.url)'"
}
finally {
  Pop-Location
}
