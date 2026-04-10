#!/bin/bash
# One-time Cloud Run deployment for IPL 2026 Fantasy auto-update.
# Run from the ipl-2026-fantasy/ directory.
# Prereq: gcloud CLI authenticated (run `gcloud auth login` if needed).

set -e  # stop on any error

PROJECT_ID="cricinfo-273202"
SERVICE_ACCOUNT="streamlit-crictalk@cricinfo-273202.iam.gserviceaccount.com"
REGION="us-central1"
IMAGE="us-central1-docker.pkg.dev/${PROJECT_ID}/ipl-fantasy/auto-update:latest"
JOB_NAME="ipl-auto-update"
SCHEDULER_JOB="ipl-daily-update"

echo "=== Setting project ==="
gcloud config set project "${PROJECT_ID}"

echo "=== Enabling APIs ==="
gcloud services enable \
  run.googleapis.com \
  cloudscheduler.googleapis.com \
  secretmanager.googleapis.com \
  artifactregistry.googleapis.com

echo "=== Creating Artifact Registry repo ==="
gcloud artifacts repositories create ipl-fantasy \
  --repository-format=docker \
  --location="${REGION}" \
  --description="IPL fantasy auto-update container" \
  || echo "Repo already exists, skipping."

echo "=== Storing secrets in Secret Manager ==="
gcloud secrets create gcp-credentials-json \
  --data-file=credentials/cricinfo-273202-a7420ddc1abd.json \
  || echo "Secret gcp-credentials-json already exists, updating..."

# If the secret already exists, add a new version
gcloud secrets versions add gcp-credentials-json \
  --data-file=credentials/cricinfo-273202-a7420ddc1abd.json 2>/dev/null || true

printf "67dd6af4b4c692a37a2a419b944aaef0" | \
  gcloud secrets create scraper-api-key --data-from-file=- \
  || echo "Secret scraper-api-key already exists, skipping."

echo "=== Granting service account access to secrets ==="
gcloud secrets add-iam-policy-binding gcp-credentials-json \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding scraper-api-key \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/secretmanager.secretAccessor"

echo "=== Building and pushing Docker image ==="
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet
docker build -t "${IMAGE}" .
docker push "${IMAGE}"

echo "=== Creating Cloud Run Job ==="
gcloud run jobs create "${JOB_NAME}" \
  --image="${IMAGE}" \
  --region="${REGION}" \
  --service-account="${SERVICE_ACCOUNT}" \
  --set-secrets="/app/credentials/cricinfo-273202-a7420ddc1abd.json=gcp-credentials-json:latest" \
  --set-secrets="SCRAPER_API_KEY=scraper-api-key:latest" \
  --task-timeout=600 \
  --max-retries=1 \
  || echo "Job exists — updating image..."

# If job already exists, update it
gcloud run jobs update "${JOB_NAME}" \
  --image="${IMAGE}" \
  --region="${REGION}" 2>/dev/null || true

echo ""
echo "=== Test: run the job manually now ==="
echo "Run: gcloud run jobs execute ${JOB_NAME} --region=${REGION} --wait"
echo ""
read -p "Run the test job now? (y/n): " RUN_TEST
if [[ "${RUN_TEST}" == "y" ]]; then
  gcloud run jobs execute "${JOB_NAME}" --region="${REGION}" --wait
fi

echo "=== Creating Cloud Scheduler trigger (midnight IST = 18:30 UTC) ==="
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/run.invoker"

gcloud scheduler jobs create http "${SCHEDULER_JOB}" \
  --location="${REGION}" \
  --schedule="30 18 * * *" \
  --time-zone="UTC" \
  --uri="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${JOB_NAME}:run" \
  --message-body="{}" \
  --oauth-service-account-email="${SERVICE_ACCOUNT}" \
  || echo "Scheduler job already exists, skipping."

echo ""
echo "=== Deployment complete! ==="
echo "  Job:       ${JOB_NAME}"
echo "  Schedule:  daily at 18:30 UTC (midnight IST)"
echo "  Logs:      gcloud logging read \"resource.type=cloud_run_job AND resource.labels.job_name=${JOB_NAME}\" --limit=50"
echo "  Manual run: gcloud run jobs execute ${JOB_NAME} --region=${REGION} --wait"
