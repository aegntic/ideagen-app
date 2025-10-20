#!/bin/bash
# Google Cloud Deployment Script for IdeaGen with Vertex AI

set -e

echo "🚀 Deploying IdeaGen to Google Cloud with Vertex AI"
echo "================================================="

# Configuration
PROJECT_ID=${GOOGLE_CLOUD_PROJECT_ID}
REGION=${GOOGLE_CLOUD_LOCATION:-us-central1}
SERVICE_NAME="idea-gen-api"
REPOSITORY_NAME="idea-gen-repo"
IMAGE_NAME="idea-gen"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

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

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."

    # Check if gcloud is installed
    if ! command -v gcloud &> /dev/null; then
        error "gcloud CLI not found. Please install Google Cloud SDK first."
    fi

    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        error "Docker not found. Please install Docker first."
    fi

    # Check if user is logged in to gcloud
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -1 > /dev/null 2>&1; then
        error "Not logged in to Google Cloud. Run 'gcloud auth login' first."
    fi

    log "✅ Prerequisites check passed"
}

# Set up Google Cloud project
setup_project() {
    log "Setting up Google Cloud project..."

    if [[ -z "$PROJECT_ID" ]]; then
        error "GOOGLE_CLOUD_PROJECT_ID environment variable not set"
    fi

    # Set the project
    gcloud config set project "$PROJECT_ID"

    # Enable required APIs
    log "Enabling required Google Cloud APIs..."
    gcloud services enable \
        run.googleapis.com \
        sql-component.googleapis.com \
        sqladmin.googleapis.com \
        aiplatform.googleapis.com \
        artifactregistry.googleapis.com \
        cloudbuild.googleapis.com \
        secretmanager.googleapis.com

    log "✅ Project setup complete"
}

# Create service account and permissions
setup_service_account() {
    log "Setting up service account..."

    SA_NAME="idea-gen-sa"
    SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

    # Create service account if it doesn't exist
    if ! gcloud iam service-accounts describe "$SA_EMAIL" &>/dev/null; then
        gcloud iam service-accounts create "$SA_NAME" \
            --description="Service account for IdeaGen application" \
            --display-name="IdeaGen Service Account"
    fi

    # Grant required roles
    log "Granting IAM roles to service account..."
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:$SA_EMAIL" \
        --role="roles/aiplatform.user"

    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:$SA_EMAIL" \
        --role="roles/run.invoker"

    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:$SA_EMAIL" \
        --role="roles/secretmanager.secretAccessor"

    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:$SA_EMAIL" \
        --role="roles/cloudsql.client"

    log "✅ Service account setup complete"
}

# Create and configure secrets
setup_secrets() {
    log "Setting up secrets..."

    # Database password
    if ! gcloud secrets describe idea-gen-db-password &>/dev/null; then
        DB_PASSWORD=$(openssl rand -base64 32)
        echo -n "$DB_PASSWORD" | gcloud secrets create idea-gen-db-password --data-file=-
        log "Created database password secret"
    fi

    # Google credentials
    if [[ -n "$GOOGLE_APPLICATION_CREDENTIALS" ]]; then
        if ! gcloud secrets describe idea-gen-google-credentials &>/dev/null; then
            gcloud secrets create idea-gen-google-credentials --replication-policy="automatic"
            gcloud secrets versions add idea-gen-google-credentials --data-file="$GOOGLE_APPLICATION_CREDENTIALS"
            log "Created Google credentials secret"
        fi
    fi

    # API keys
    if ! gcloud secrets describe idea-gen-api-keys &>/dev/null; then
        cat << EOF | gcloud secrets create idea-gen-api-keys --replication-policy="automatic" --data-file=-
{
  "PRODUCTHUNT_API_KEY": "$PRODUCTHUNT_API_KEY",
  "SERP_API_KEY": "$SERP_API_KEY",
  "GITHUB_TOKEN": "$GITHUB_TOKEN",
  "NETLIFY_TOKEN": "$NETLIFY_TOKEN"
}
EOF
        log "Created API keys secret"
    fi

    log "✅ Secrets setup complete"
}

# Create Cloud SQL instance
setup_database() {
    log "Setting up Cloud SQL database..."

    DB_INSTANCE_NAME="idea-gen-db"
    DB_NAME="idea_engine"

    # Check if instance already exists
    if ! gcloud sql instances describe "$DB_INSTANCE_NAME" &>/dev/null; then
        log "Creating Cloud SQL instance..."
        gcloud sql instances create "$DB_INSTANCE_NAME" \
            --database-version=POSTGRES_15 \
            --tier=db-f1-micro \
            --region="$REGION" \
            --storage-auto-increase \
            --storage-size=10GB
    fi

    # Create database if it doesn't exist
    if ! gcloud sql databases describe "$DB_NAME" --instance="$DB_INSTANCE_NAME" &>/dev/null; then
        log "Creating database..."
        gcloud sql databases create "$DB_NAME" --instance="$DB_INSTANCE_NAME"
    fi

    log "✅ Database setup complete"
}

# Build and deploy container image
build_and_deploy() {
    log "Building and deploying application..."

    # Create Artifact Registry repository
    if ! gcloud artifacts repositories describe "$REPOSITORY_NAME" --location="$REGION" &>/dev/null; then
        gcloud artifacts repositories create "$REPOSITORY_NAME" \
            --repository-format=docker \
            --location="$REGION"
    fi

    # Build the image
    log "Building Docker image..."
    gcloud builds submit \
        --tag "${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY_NAME}/${IMAGE_NAME}:latest" \
        --timeout=1800

    # Deploy to Cloud Run
    log "Deploying to Cloud Run..."

    # Get database connection details
    DB_CONNECTION_NAME=$(gcloud sql instances describe idea-gen-db --format='value(connectionName)')

    gcloud run deploy "$SERVICE_NAME" \
        --image "${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY_NAME}/${IMAGE_NAME}:latest" \
        --region "$REGION" \
        --platform "managed" \
        --allow-unauthenticated \
        --service-account "${SA_EMAIL}" \
        --set-env-vars "GOOGLE_CLOUD_PROJECT_ID=$PROJECT_ID" \
        --set-env-vars "GOOGLE_CLOUD_LOCATION=$REGION" \
        --set-env-vars "DB_CONNECTION_NAME=$DB_CONNECTION_NAME" \
        --set-env-vars "DB_NAME=idea_engine" \
        --set-secrets "DB_PASSWORD=idea-gen-db-password:latest" \
        --set-secrets "GOOGLE_APPLICATION_CREDENTIALS=idea-gen-google-credentials:latest" \
        --set-secrets "API_KEYS=idea-gen-api-keys:latest" \
        --memory "2Gi" \
        --cpu "1" \
        --timeout "900" \
        --concurrency "10" \
        --min-instances "1" \
        --max-instances "10"

    log "✅ Deployment complete"
}

# Configure Vertex AI
setup_vertex_ai() {
    log "Setting up Vertex AI access..."

    # Vertex AI doesn't require additional setup if APIs are enabled
    # But we can configure model endpoints if needed

    log "✅ Vertex AI setup complete"
}

# Test deployment
test_deployment() {
    log "Testing deployment..."

    # Get service URL
    SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
        --region "$REGION" \
        --format 'value(status.url)')

    log "Service deployed to: $SERVICE_URL"

    # Wait a moment for the service to be ready
    sleep 10

    # Test health endpoint
    if curl -f "$SERVICE_URL/health" &>/dev/null; then
        log "✅ Health check passed"
    else
        warn "Health check failed - service may still be starting"
    fi

    # Test Vertex AI integration
    log "Testing Vertex AI integration..."
    curl -X POST "$SERVICE_URL/api/test/vertex-ai" \
        -H "Content-Type: application/json" \
        -d '{"test": "connection"}' || warn "Vertex AI test failed"
}

# Main deployment flow
main() {
    log "Starting deployment process..."

    check_prerequisites
    setup_project
    setup_service_account
    setup_secrets
    setup_database
    setup_vertex_ai
    build_and_deploy
    test_deployment

    log "🎉 Deployment completed successfully!"
    log "Service URL: $(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)')"

    log ""
    log "Next steps:"
    log "1. Visit the service URL to test the application"
    log "2. Monitor the deployment in Google Cloud Console"
    log "3. Set up additional monitoring and alerting as needed"
    log "4. Configure custom domain if required"
}

# Run deployment
main "$@"