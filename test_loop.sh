#!/bin/bash

# Configuration
URL="http://localhost:4000/v1/chat/completions"
AUTH="Authorization: Bearer sk-1234"
MODEL="claude-sonnet"

echo "Starting Model Armor test loop. Press [CTRL+C] to stop."
echo "Sending requests every 5 seconds..."

while true; do
  # 1. Send Clean Prompt
  echo -e "\n[$(date +%H:%M:%S)] Sending CLEAN prompt..."
  curl -s -X POST "$URL" \
    -H "Content-Type: application/json" \
    -H "$AUTH" \
    -d "{
      \"model\": \"$MODEL\",
      \"messages\": [{\"role\": \"user\", \"content\": \"Hello! How are you?\"}]
    }" | grep -o '"content":"[^"]*"' || echo "Request Failed"

  sleep 5

  # 2. Send Sensitive Prompt (Blocked)
  echo -e "\n[$(date +%H:%M:%S)] Sending SENSITIVE prompt (Credit Card)..."
  curl -s -X POST "$URL" \
    -H "Content-Type: application/json" \
    -H "$AUTH" \
    -d "{
      \"model\": \"$MODEL\",
      \"messages\": [{\"role\": \"user\", \"content\": \"My CREDIT_CARD_NUMBER is 1234567890123456\"}]
    }" | grep -o '"error":{[^}]*}' || echo "Request Blocked/Failed"

  sleep 5
done
