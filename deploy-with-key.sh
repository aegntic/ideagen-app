#!/bin/bash
# Deploy with Service Account Key

set -e

echo "🚀 Deploying promptre.quest with Service Account"
echo "==============================================="

# Configuration
PROJECT_ID=${1:-"promptre-quest-hackathon"}
REGION=${2:-"us-central1"}
SERVICE_NAME="promptre-quest-app"
SERVICE_ACCOUNT_EMAIL="promptre-quest-sa@${PROJECT_ID}.iam.gserviceaccount.com"

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

# Check if we have a service account key file
if [[ -n "$GOOGLE_APPLICATION_CREDENTIALS" ]]; then
    log "Using service account key: $GOOGLE_APPLICATION_CREDENTIALS"

    # Authenticate with service account
    gcloud auth activate-service-account --key-file="$GOOGLE_APPLICATION_CREDENTIALS"

    # Set project
    gcloud config set project "$PROJECT_ID"

    log "✅ Authentication successful"
else
    warn "No service account key found. Using application default credentials."

    # Set project anyway
    gcloud config set project "$PROJECT_ID" || warn "Could not set project - will continue"
fi

# Try to create service account if it doesn't exist
if gcloud iam service-accounts describe "$SERVICE_ACCOUNT_EMAIL" &>/dev/null; then
    log "Service account already exists: $SERVICE_ACCOUNT_EMAIL"
else
    log "Creating service account..."
    gcloud iam service-accounts create "promptre-quest-sa" \
        --display-name="promptre.quest Service Account" \
        --description="Service account for promptre.quest deployment" || warn "Could not create service account"
fi

# Grant required roles
log "Granting IAM roles..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
    --role="roles/run.admin" || warn "Could not grant run.admin role"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
    --role="roles/aiplatform.user" || warn "Could not grant aiplatform.user role"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
    --role="roles/artifactregistry.writer" || warn "Could not grant artifactregistry.writer role"

# Enable APIs (might fail without proper auth, but try anyway)
log "Enabling required APIs..."
gcloud services enable run.googleapis.com || warn "Could not enable Cloud Run API"
gcloud services enable aiplatform.googleapis.com || warn "Could not enable Vertex AI API"
gcloud services enable artifactregistry.googleapis.com || warn "Could not enable Artifact Registry API"

# Build Docker image locally
log "Building Docker image locally..."
docker build -f Dockerfile.simple -t "gcr.io/$PROJECT_ID/$SERVICE_NAME" . || error "Docker build failed"

# Push to Container Registry (if auth allows)
log "Attempting to push to Container Registry..."
if docker push "gcr.io/$PROJECT_ID/$SERVICE_NAME" 2>/dev/null; then
    log "✅ Docker image pushed successfully"

    # Deploy to Cloud Run
    log "Deploying to Cloud Run..."
    gcloud run deploy "$SERVICE_NAME" \
        --image "gcr.io/$PROJECT_ID/$SERVICE_NAME" \
        --region "$REGION" \
        --platform "managed" \
        --allow-unauthenticated \
        --service-account "$SERVICE_ACCOUNT_EMAIL" \
        --memory "2Gi" \
        --cpu "1" \
        --timeout "900" \
        --min-instances "0" \
        --max-instances "10" \
        --set-env-vars "NODE_ENV=production,VECTOR_DB_TYPE=memory,USE_MEMORY_FALLBACK=true" || warn "Cloud Run deployment failed"

    # Get service URL
    SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
        --region "$REGION" \
        --format 'value(status.url)' 2>/dev/null)

    if [[ -n "$SERVICE_URL" ]]; then
        log "🎉 Deployment successful!"
        log "Service URL: $SERVICE_URL"

        # Test deployment
        sleep 5
        if curl -f "$SERVICE_URL/health" &>/dev/null; then
            log "✅ Health check passed"
        else
            warn "Health check failed - service may still be starting"
        fi
    else
        warn "Could not retrieve service URL"
    fi
else
    warn "Could not push Docker image - authentication required"
    log "Please run: gcloud auth login or set GOOGLE_APPLICATION_CREDENTIALS"
fi

log "Deployment process completed!"