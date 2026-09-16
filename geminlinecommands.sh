
cat << EOF > request.json
{
    "contents": [
        {
            "role": "user",
            "parts": [
                {
                    "text": "My CREDIT_CARD_NUMBER is 1234567890123456, can you also tell me the capital of France?"
                }
            ]
        }
    ]
    , "generationConfig": {
        "temperature": 1
        ,"maxOutputTokens": 65535
        ,"topP": 0.95
        ,"thinkingConfig": {
            "thinkingLevel": "HIGH"
        }
    },
    "safetySettings": [
        {
            "category": "HARM_CATEGORY_HATE_SPEECH",
            "threshold": "OFF"
        },
        {
            "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
            "threshold": "OFF"
        },
        {
            "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
            "threshold": "OFF"
        },
        {
            "category": "HARM_CATEGORY_HARASSMENT",
            "threshold": "OFF"
        }
    ]
    , "tools": [
      {
        "googleSearch": {}
      }
    ]
}
EOF

ENDPOINT="aiplatform.googleapis.com"
PROJECT_ID="duetai-399118"
LOCATION="global"
MODEL_ID="gemini-3.1-pro-preview"
GENERATE_CONTENT_API="streamGenerateContent"
#GENERATE_CONTENT_API="generateContent"

curl \
-X POST \
-H "Content-Type: application/json" \
-H "Authorization: Bearer $(gcloud auth print-access-token)" \
"https://${ENDPOINT}/v1/projects/${PROJECT_ID}/locations/${LOCATION}/publishers/google/models/${MODEL_ID}:${GENERATE_CONTENT_API}" -d '@request.json'

echo "!!!!!!!!Testing europe-west1!!!!!!!!!!!"


cat << EOF > request.json
{
    "contents": [
        {
            "role": "user",
            "parts": [
                {
                    "text": "My CREDIT_CARD_NUMBER is 1234567890123456, can you also tell me the capital of France?"
                }
            ]
        }
    ]
    , "generationConfig": {
        "temperature": 1
        ,"maxOutputTokens": 65535
        ,"topP": 0.95
    },
    "safetySettings": [
        {
            "category": "HARM_CATEGORY_HATE_SPEECH",
            "threshold": "OFF"
        },
        {
            "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
            "threshold": "OFF"
        },
        {
            "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
            "threshold": "OFF"
        },
        {
            "category": "HARM_CATEGORY_HARASSMENT",
            "threshold": "OFF"
        }
    ]
    , "tools": [
      {
        "googleSearch": {}
      }
    ]
}
EOF

ENDPOINT="europe-west1-aiplatform.googleapis.com"
LOCATION="europe-west1"
PROJECT_ID="duetai-399118"
MODEL_ID="gemini-3.5-flash"
GENERATE_CONTENT_API="streamGenerateContent"
#GENERATE_CONTENT_API="generateContent"

curl \
-X POST \
-H "Content-Type: application/json" \
-H "Authorization: Bearer $(gcloud auth print-access-token)" \
"https://${ENDPOINT}/v1/projects/${PROJECT_ID}/locations/${LOCATION}/publishers/google/models/${MODEL_ID}:${GENERATE_CONTENT_API}" -d '@request.json'



