#!/bin/bash
# Quick Google Cloud Deployment for promptre.quest

set -e

echo "🚀 Quick Deploy promptre.quest to Google Cloud"
echo "==============================================="

# Configuration
PROJECT_ID=${1:-"promptre-quest-hackathon"}
REGION=${2:-"us-central1"}
SERVICE_NAME="promptre-quest-app"

echo "Project ID: $PROJECT_ID"
echo "Region: $REGION"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

# Check if gcloud is available
if ! command -v gcloud &> /dev/null; then
    error "gcloud CLI not found. Please install Google Cloud SDK first."
fi

# Set project
log "Setting project to: $PROJECT_ID"
gcloud config set project "$PROJECT_ID" || warn "Project setup failed - will continue"

# Enable APIs
log "Enabling required APIs..."
gcloud services enable run.googleapis.com \
    aiplatform.googleapis.com \
    artifactregistry.googleapis.com || warn "API enable failed - continuing"

# Build image
log "Building Docker image..."
IMAGE_URI="gcr.io/$PROJECT_ID/$SERVICE_NAME"

# Build with Cloud Build
gcloud builds submit --tag "$IMAGE_URI" --timeout=1800 || {
    warn "Cloud Build failed, trying local Docker build..."
    docker build -t "$IMAGE_URI" .
    docker push "$IMAGE_URI"
}

# Deploy to Cloud Run
log "Deploying to Cloud Run..."
gcloud run deploy "$SERVICE_NAME" \
    --image "$IMAGE_URI" \
    --region "$REGION" \
    --platform "managed" \
    --allow-unauthenticated \
    --memory "2Gi" \
    --cpu "1" \
    --timeout "900" \
    --concurrency "10" \
    --min-instances "0" \
    --max-instances "10" \
    --set-env-vars "NODE_ENV=production" \
    --set-env-vars "VECTOR_DB_TYPE=memory" \
    --set-env-vars "USE_MEMORY_FALLBACK=true" || error "Deployment failed"

# Get service URL
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
    --region "$REGION" \
    --format 'value(status.url)')

log "🎉 Deployment complete!"
log "Service URL: $SERVICE_URL"

# Test deployment
log "Testing deployment..."
sleep 5
if curl -f "$SERVICE_URL/health" &>/dev/null; then
    log "✅ Health check passed"
else
    warn "Health check failed - service may still be starting"
fi

echo ""
echo "🌟 Your promptre.quest application is now live!"
echo "🔗 URL: $SERVICE_URL"
echo ""
echo "Next steps:"
echo "1. Visit the URL to test the application"
echo "2. Test AI idea generation with Vertex AI"
echo "3. Try the semantic search features"
echo "4. Check the analytics dashboard"