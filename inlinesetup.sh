# Set variables for your project
export PROJECT_ID="duetai-399118"
export PROJECT_NUMBER="1011276420111"

# Create Service Identity if not already provisioned
gcloud beta services identity create --service=modelarmor.googleapis.com --project=${PROJECT_ID}
gcloud beta services identity create --service=aiplatform.googleapis.com --project=${PROJECT_ID}

# --- Service Account 1: Model Armor Service Agent ---
export SA1="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-modelarmor.iam.gserviceaccount.com"

# Bind roles/modelarmor.calloutUser to SA1
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="${SA1}" \
  --role="roles/modelarmor.calloutUser"

# Bind roles/modelarmor.user to SA1
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="${SA1}" \
  --role="roles/modelarmor.user"

# --- Service Account 2: Vertex AI Service Agent ---
export SA2="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-aiplatform.iam.gserviceaccount.com"

# Bind roles/modelarmor.calloutUser to SA2
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="${SA2}" \
  --role="roles/modelarmor.calloutUser"

# Bind roles/modelarmor.user to SA2
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="${SA2}" \
  --role="roles/modelarmor.user"

echo "IAM policy bindings updated for ${SA1} and ${SA2} in project ${PROJECT_ID}"
