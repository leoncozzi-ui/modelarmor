#!/bin/bash

# 1. Point to your local LiteLLM Proxy (Vertex Passthrough Mode)
# IMPORTANT: Official docs say to include /v1
export ANTHROPIC_VERTEX_BASE_URL="http://localhost:4000/vertex_ai/v1"

# 2. Set the default model (MUST match the backend model ID)
export ANTHROPIC_DEFAULT_SONNET_MODEL="claude-sonnet-4-6"

# 3. Project Configuration
export ANTHROPIC_VERTEX_PROJECT_ID="duetai-399118"
export CLOUD_ML_REGION="global"

# 4. Authentication (Skip since we are using local proxy)
export CLAUDE_CODE_SKIP_VERTEX_AUTH=1
export CLAUDE_CODE_USE_VERTEX=1

# Disable the variables that might conflict from Proxy mode
unset ANTHROPIC_BASE_URL
unset ANTHROPIC_API_KEY

echo "Claude Code environment variables set!"
echo "Default Model: $ANTHROPIC_DEFAULT_SONNET_MODEL"
echo "Base URL: $ANTHROPIC_VERTEX_BASE_URL"
