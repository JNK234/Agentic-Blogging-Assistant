#!/bin/bash

# Deploy Quibo Frontend to Google Cloud Run
# This script deploys the Streamlit frontend application

set -e

# Configuration
PROJECT_ID="personal-os-475406"
REGION="us-central1"
SERVICE_NAME="quibo-frontend"
BACKEND_URL="https://quibo-backend-870041009851.us-central1.run.app"

echo "🚀 Deploying Quibo Frontend to Cloud Run..."

# Navigate to frontend directory
cd root/frontend

# Deploy to Cloud Run
gcloud run deploy $SERVICE_NAME \
  --source . \
  --region=$REGION \
  --project=$PROJECT_ID \
  --platform=managed \
  --memory=2Gi \
  --cpu=1 \
  --min-instances=0 \
  --max-instances=3 \
  --concurrency=10 \
  --timeout=300 \
  --cpu-boost \
  --set-env-vars="API_BASE_URL=$BACKEND_URL,STREAMLIT_SERVER_PORT=8501,STREAMLIT_SERVER_ADDRESS=0.0.0.0" \
  --allow-unauthenticated

echo "✅ Frontend deployment complete!"
echo "🌐 Your frontend will be available at: https://$SERVICE_NAME-$(gcloud config get-value project).$REGION.run.app"