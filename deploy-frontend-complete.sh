#!/bin/bash

# Complete Quibo Frontend Deployment Script
# This script handles the full deployment process including secrets setup

set -e

# Configuration
PROJECT_ID="personal-os-475406"
REGION="us-central1"
SERVICE_NAME="quibo-frontend"
BACKEND_URL="https://quibo-backend-870041009851.us-central1.run.app"

echo "🚀 Starting complete Quibo Frontend deployment..."

# Step 1: Get API Key from user
echo "🔑 Please enter your Quibo API Key (from GCP Secret Manager):"
read -s API_KEY

# Step 2: Create .env file for deployment
echo "⚙️  Creating environment configuration..."
cd root/frontend

cat > .env << EOF
# Backend API Configuration
API_BASE_URL=$BACKEND_URL
QUIBO_API_KEY=$API_KEY

# Streamlit Configuration
STREAMLIT_SERVER_PORT=8501
STREAMLIT_SERVER_ADDRESS=0.0.0.0
EOF

# Step 3: Build and deploy
echo "🏗️  Building and deploying to Cloud Run..."
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
  --set-secrets="QUIBO_API_KEY=quibo-api-key:latest" \
  --allow-unauthenticated

# Step 4: Get the service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME \
  --region=$REGION \
  --project=$PROJECT_ID \
  --format='value(status.url)')

# Step 5: Clean up local .env file
rm -f .env

echo ""
echo "✅ Frontend deployment complete!"
echo "🌐 Your frontend is available at: $SERVICE_URL"
echo ""
echo "📋 Deployment Summary:"
echo "   - Service Name: $SERVICE_NAME"
echo "   - Region: $REGION"
echo "   - Backend URL: $BACKEND_URL"
echo "   - Memory: 2Gi"
echo "   - CPU: 1"
echo "   - Scaling: 0-3 instances"
echo ""
echo "🔧 Next steps:"
echo "   1. Test the frontend by visiting the URL above"
echo "   2. Verify backend connectivity by creating a test project"
echo "   3. Monitor logs with: gcloud logging read 'resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"$SERVICE_NAME\"' --limit=50"

# Optional: Open the URL in browser
if command -v open &> /dev/null; then
    echo ""
    read -p "🌐 Would you like to open the frontend in your browser? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        open "$SERVICE_URL"
    fi
fi