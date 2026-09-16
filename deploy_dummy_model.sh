#!/usr/bin/env bash
set -e

PROJECT_ID="duetai-399118"
REGION="us-central1"
ENDPOINT_ID="6288507771239268352"
BUCKET_NAME="duetai-399118-test-models-uscentral1"

echo "1. Creating GCS Bucket gs://${BUCKET_NAME} if not existing..."
gcloud storage buckets create gs://${BUCKET_NAME} --location=${REGION} --project=${PROJECT_ID} || true

echo "2. Uploading model.joblib to Cloud Storage..."
gcloud storage cp model.joblib gs://${BUCKET_NAME}/dummy_model/model.joblib

echo "3. Getting existing model or uploading new model..."
MODEL_ID=$(gcloud ai models list --project="${PROJECT_ID}" --region="${REGION}" --filter="display_name=dummy-sklearn-model" --format="value(name)" | head -n 1 | awk -F'/' '{print $NF}')

if [ -z "${MODEL_ID}" ]; then
  echo "Uploading model artifact to Vertex AI Model Registry..."
  MODEL_URI=$(gcloud ai models upload \
    --project="${PROJECT_ID}" \
    --region="${REGION}" \
    --display-name="dummy-sklearn-model" \
    --container-image-uri="us-docker.pkg.dev/vertex-ai/prediction/sklearn-cpu.1-3:latest" \
    --artifact-uri="gs://${BUCKET_NAME}/dummy_model/" \
    --format="value(name)")
  MODEL_ID=$(echo "${MODEL_URI}" | awk -F'/' '{print $6}')
fi

echo "Using Model ID: ${MODEL_ID}"

echo "4. Deploying model to endpoint ${ENDPOINT_ID}..."
gcloud ai endpoints deploy-model ${ENDPOINT_ID} \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --model="${MODEL_ID}" \
  --display-name="dummy-model-deployment" \
  --machine-type="n1-standard-2" \
  --min-replica-count=1 \
  --max-replica-count=1

echo "Model successfully deployed to endpoint ${ENDPOINT_ID}!"
