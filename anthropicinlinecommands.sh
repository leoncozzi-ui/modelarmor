PREDICT_API="streamRawPredict"
#PREDICT_API="rawPredict"
curl -X POST \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json; charset=utf-8" \
  -d '{
    "anthropic_version": "vertex-2023-10-16",
    "messages": [
      {
        "role": "user",
        "content": "My CREDIT_CARD_NUMBER is 1234567890123456, can you also tell me the capital of France?"
      }
    ],
    "max_tokens": 1024,
    "stream": true
  }' \
  "https://aiplatform.googleapis.com/v1/projects/duetai-399118/locations/global/publishers/anthropic/models/claude-sonnet-4-6:${PREDICT_API}"

#ENDPOINT="europe-west1-aiplatform.googleapis.com"
#LOCATION_ID="europe-west1"

#ENDPOINT="europe-west4-aiplatform.googleapis.com"  
#LOCATION_ID="europe-west4"

#ENDPOINT="us-east1-aiplatform.googleapis.com"
#LOCATION_ID="us-east1"

ENDPOINT="asia-southeast1-aiplatform.googleapis.com"
LOCATION_ID="asia-southeast1"
PREDICT_API="streamRawPredict"
#PREDICT_API="rawPredict"
curl -X POST \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json; charset=utf-8" \
  -d '{
    "anthropic_version": "vertex-2023-10-16",
    "messages": [
      {
        "role": "user",
        "content": "My CREDIT_CARD_NUMBER is 1234567890123456, can you also tell me the capital of France?"
      }
    ],
    "max_tokens": 1024,
    "stream": true
  }' \
  "https://${ENDPOINT}/v1/projects/duetai-399118/locations/${LOCATION_ID}/publishers/anthropic/models/claude-sonnet-4-6:${PREDICT_API}"


