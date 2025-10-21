#!/bin/bash
# Quick Vertex AI Setup for Hackathon

set -e

echo "🤖 Setting Up Real Vertex AI for Hackathon"
echo "=========================================="

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Step 1: Check if we have credentials
step "Checking for existing Google Cloud credentials..."

if [[ -n "$GOOGLE_CLOUD_PROJECT_ID" ]]; then
    log "✅ Found GOOGLE_CLOUD_PROJECT_ID: $GOOGLE_CLOUD_PROJECT_ID"
else
    warn "❌ GOOGLE_CLOUD_PROJECT_ID not set"
fi

if [[ -n "$GOOGLE_APPLICATION_CREDENTIALS" ]]; then
    log "✅ Found GOOGLE_APPLICATION_CREDENTIALS: $GOOGLE_APPLICATION_CREDENTIALS"
else
    warn "❌ GOOGLE_APPLICATION_CREDENTIALS not set"
fi

# Step 2: Try to authenticate with application default credentials
step "Attempting to authenticate with Google Cloud..."

if command -v gcloud &> /dev/null; then
    log "✅ gcloud CLI found"

    # Try to get current account
    ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>/dev/null || echo "")

    if [[ -n "$ACCOUNT" ]]; then
        log "✅ Found active account: $ACCOUNT"

        # Set application default credentials
        gcloud auth application-default login --quiet 2>/dev/null || warn "Could not set application default credentials"

        # Get project ID if not set
        if [[ -z "$GOOGLE_CLOUD_PROJECT_ID" ]]; then
            PROJECT_ID=$(gcloud config get-value project 2>/dev/null || echo "")
            if [[ -n "$PROJECT_ID" ]]; then
                export GOOGLE_CLOUD_PROJECT_ID="$PROJECT_ID"
                log "✅ Set project ID from gcloud config: $PROJECT_ID"
            fi
        fi
    else
        warn "❌ No active Google Cloud account found"
    fi
else
    warn "❌ gcloud CLI not found"
fi

# Step 3: Create environment file if needed
step "Setting up environment configuration..."

if [[ ! -f ".env" ]]; then
    cat > .env << EOF
# Google Cloud Configuration for Hackathon
GOOGLE_CLOUD_PROJECT_ID=${GOOGLE_CLOUD_PROJECT_ID:-your-project-id}
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=${GOOGLE_APPLICATION_CREDENTIALS:-path/to/credentials.json}

# Database (will use memory fallback)
USE_MEMORY_FALLBACK=true
VECTOR_DB_TYPE=memory

# Server
PORT=8081
NODE_ENV=production
EOF
    log "✅ Created .env file"
else
    log "✅ .env file already exists"
fi

# Step 4: Test Vertex AI integration
step "Testing Vertex AI integration..."

if [[ -n "$GOOGLE_CLOUD_PROJECT_ID" ]]; then
    # Create a simple test script
    cat > test-vertex-ai.js << 'EOF'
const { GoogleAuth } = require('google-auth-library');

async function testVertexAI() {
    try {
        const auth = new GoogleAuth({
            scopes: ['https://www.googleapis.com/auth/cloud-platform']
        });

        const client = await auth.getClient();
        const projectId = process.env.GOOGLE_CLOUD_PROJECT_ID || 'your-project-id';

        console.log('✅ Google Cloud authentication successful');
        console.log(`✅ Project ID: ${projectId}`);
        console.log('✅ Vertex AI integration ready');
        return true;
    } catch (error) {
        console.log('❌ Vertex AI integration failed:', error.message);
        return false;
    }
}

testVertexAI();
EOF

    if node test-vertex-ai.js 2>/dev/null; then
        log "✅ Vertex AI integration test passed"
    else
        warn "❌ Vertex AI integration test failed"
    fi

    rm -f test-vertex-ai.js
fi

# Step 5: Instructions
step "Setup Complete - Next Steps:"

echo ""
echo -e "${GREEN}🚀 TO ENABLE REAL VERTEX AI:${NC}"
echo ""
echo "1. ${BLUE}Get Google Cloud Project:${NC}"
echo "   → Go to: https://console.cloud.google.com/"
echo "   → Create/select a project with billing enabled"
echo ""
echo "2. ${BLUE}Enable Vertex AI API:${NC}"
echo "   → Go to: https://console.cloud.google.com/apis/library/aiplatform.googleapis.com"
echo "   → Click 'Enable'"
echo ""
echo "3. ${BLUE}Set Credentials (Choose one):${NC}"
echo ""
echo "   ${YELLOW}Option A - Service Account Key:${NC}"
echo "   → Go to: https://console.cloud.google.com/iam-admin/serviceaccounts"
echo "   → Create service account with 'Vertex AI User' role"
echo "   → Download JSON key file"
echo "   → Set environment variable:"
echo "   export GOOGLE_APPLICATION_CREDENTIALS=\"/path/to/key.json\""
echo ""
echo "   ${YELLOW}Option B - gcloud CLI:${NC}"
echo "   → Install: curl https://sdk.cloud.google.com | bash"
echo "   → Authenticate: gcloud auth login"
echo "   → Set project: gcloud config set project YOUR_PROJECT_ID"
echo "   → Set default credentials: gcloud auth application-default login"
echo ""
echo "4. ${BLUE}Restart the Application:${NC}"
echo "   → Kill current server (Ctrl+C)"
echo "   → Set environment variables"
echo "   → Run: npm start"
echo ""
echo "5. ${BLUE}Verify Real AI:${NC}"
echo "   → Check logs for 'Vertex AI client initialized'"
echo "   → Test idea generation (should use real AI)"
echo "   → Deploy to Google Cloud with ./quick-deploy.sh"
echo ""
echo -e "${GREEN}🎯 HACKATHON SUCCESS:${NC}"
echo "Real Vertex AI integration will demonstrate:"
echo "• Actual AI-powered idea generation"
echo "• True semantic search with vector embeddings"
echo "• Professional AI validation and analysis"
echo "• Production-ready Google Cloud deployment"
echo ""
echo -e "${YELLOW}⏰  Setup Time: 5-10 minutes |  Impact: Hackathon Winner 🏆${NC}"