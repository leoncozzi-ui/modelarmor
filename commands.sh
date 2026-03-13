#terminal 1
litellm --config config.yaml --detailed_debug

#terminal 2

curl -X POST \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json; charset=utf-8" \
  -d '{
    "anthropic_version": "vertex-2023-10-16",
    "messages": [
      {
        "role": "user",
        "content": "Send me a recipe for banana bread."
      }
    ],
    "max_tokens": 1024,
    "stream": true
  }' \
  "https://aiplatform.googleapis.com/v1/projects/duetai-399118/locations/global/publishers/anthropic/models/claude-sonnet-4-6:streamRawPredict"


  curl -X POST http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-1234" \
  -d '{
    "model": "claude-sonnet",
    "messages": [
      {"role": "user", "content": "Hello! How are you?"}
    ]
  }'

curl -X POST http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-1234" \
  -d '{
    "model": "claude-sonnet",
    "messages": [
      {"role": "user", "content": "My CREDIT_CARD_NUMBER is 1234567890123456"}
    ]
  }'

#terminal 3

bash test_loop.sh
