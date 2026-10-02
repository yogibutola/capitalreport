#!/bin/bash

# Ensure we are in the project root
cd "$(dirname "$0")"

# Set environment variables for local development
export GOOGLE_APPLICATION_CREDENTIALS="$(pwd)/credentials.json"
export GOOGLE_CLOUD_PROJECT="stable-smithy-270416"
export GOOGLE_CLOUD_LOCATION="us-central1"

# Comma-separated emails that are elevated to the hidden platform-admin console
# (/x9k2-console) on sign-in. Leave unset to disable superadmin locally.
# export SUPERADMIN_EMAILS="you@example.com"
# export AUDIT_LOG_ENABLED="true"   # set to "false" to turn off the activity log
# Reset emails aren't sent yet; this logs the reset link so you can test the flow
# locally. Never set it in a deployed environment.
export LOG_PASSWORD_RESET_LINKS="true"

# Check if credentials.json exists
if [ ! -f "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
    echo "Warning: credentials.json not found at $GOOGLE_APPLICATION_CREDENTIALS"
    echo "Please ensure you have your Google Cloud credentials file in the project root."
fi

# Run the application with uvicorn in reload mode
echo "Starting app in debug mode on port 8000..."
poetry run uvicorn app.main:app --reload --port 8000 --host 0.0.0.0
