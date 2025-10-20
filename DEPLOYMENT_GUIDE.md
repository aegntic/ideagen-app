# IdeaGen Deployment Guide - Google Cloud + Vertex AI

## Quick Start for Hackathon

This guide will get your IdeaGen app running on Google Cloud with Vertex AI integration in under 15 minutes.

## Prerequisites

### Google Cloud Setup
```bash
# Install Google Cloud SDK
curl https://sdk.cloud.google.com | bash
exec -l $SHELL

# Login and set project
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# Enable required APIs
gcloud services enable \
  run.googleapis.com \
  sql-component.googleapis.com \
  aiplatform.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com
```

### Service Account Setup
```bash
# Create service account
gcloud iam service-accounts create idea-gen-sa \
  --description="IdeaGen Hackathon Service Account" \
  --display-name="IdeaGen"

# Grant necessary roles
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:idea-gen-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:idea-gen-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/run.invoker"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:idea-gen-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Create and download service account key
gcloud iam service-accounts keys create ~/key.json \
  --iam-account=idea-gen-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com
```

## 🌩️ Deployment Options

### Option 1: Automated Deployment (Recommended)
```bash
# Clone the project
cd /home/tabs/hackathon/copied-projects/ideaGen-app

# Set environment variables
export GOOGLE_CLOUD_PROJECT_ID=YOUR_PROJECT_ID
export GOOGLE_CLOUD_LOCATION=us-central1
export GOOGLE_APPLICATION_CREDENTIALS=~/key.json

# Optional: Set API keys
export PRODUCTHUNT_API_KEY=your_producthunt_key
export SERP_API_KEY=your_serp_key

# Run deployment script
./deploy/google-cloud-deploy.sh
```

### Option 2: Manual Deployment
```bash
# Build the container
gcloud builds submit \
  --tag us-central1-docker.pkg.dev/YOUR_PROJECT_ID/idea-gen-repo/idea-gen:latest

# Deploy to Cloud Run
gcloud run deploy idea-gen \
  --image us-central1-docker.pkg.dev/YOUR_PROJECT_ID/idea-gen-repo/idea-gen:latest \
  --region us-central1 \
  --allow-unauthenticated \
  --service-account idea-gen-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com \
  --memory 2Gi \
  --cpu 1 \
  --timeout 900s \
  --min-instances 1
```

## Local Development

### Environment Setup
```bash
# Copy environment template
cp .env.example .env

# Edit .env file
nano .env
```

### .env Configuration
```bash
# Google Cloud
GOOGLE_CLOUD_PROJECT_ID=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=path/to/key.json

# Database (for local)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=idea_engine
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password

# API Keys (optional for testing)
PRODUCTHUNT_API_KEY=your_key
SERP_API_KEY=your_key
```

### Running Locally
```bash
# Install dependencies
npm install

# Test Vertex AI integration
npm run local:test

# Start the server
npm run dev

# Access the app
open http://localhost:8080
```

## 🧪 Testing the Integration

### 1. Health Check
```bash
curl http://localhost:8080/health
```

### 2. Test Vertex AI Connection
```bash
curl -X POST http://localhost:8080/api/test/vertex-ai \
  -H "Content-Type: application/json" \
  -d '{"test": "connection"}'
```

### 3. Generate Ideas
```bash
curl -X POST http://localhost:8080/api/ideas/generate \
  -H "Content-Type: application/json" \
  -d '{
    "sources": ["trends", "reddit"],
    "count": 5,
    "trends": [
      {"title": "AI Automation", "description": "Growing trend in AI tools"}
    ]
  }'
```

### 4. Validate an Idea
```bash
curl -X POST http://localhost:8080/api/ideas/validate \
  -H "Content-Type: application/json" \
  -d '{
    "idea": {
      "title": "AI Customer Service",
      "description": "Automated customer support platform",
      "marketProblem": "High cost of 24/7 support",
      "solution": "AI agents handle common inquiries",
      "targetMarket": "Small businesses",
      "revenueModel": "SaaS subscription"
    }
  }'
```

## 📊 Monitoring and Logging

### View Logs
```bash
# Cloud Run logs
gcloud logs read "resource.type=cloud_run_revision" --limit 50

# Application logs
gcloud logs read "resource.type=cloud_run_revision AND resource.labels.service-name=idea-gen"
```

### Monitoring
```bash
# Check service status
gcloud run services describe idea-gen --region us-central1

# Get service URL
SERVICE_URL=$(gcloud run services describe idea-gen --region us-central1 --format 'value(status.url)')
echo "Service URL: $SERVICE_URL"
```

## 🔍 Troubleshooting

### Common Issues

#### 1. Vertex AI Authentication Error
```bash
# Check service account permissions
gcloud projects get-iam-policy YOUR_PROJECT_ID \
  --flatten="bindings[].members" \
  --format='table(bindings.role, bindings.members)' \
  --filter="bindings.members:idea-gen-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com"
```

#### 2. Insufficient Memory
```bash
# Update Cloud Run service with more memory
gcloud run services update idea-gen \
  --region us-central1 \
  --memory 4Gi
```

#### 3. API Rate Limits
```bash
# Check Vertex AI quotas
gcloud compute project-info describe --project=YOUR_PROJECT_ID
```

#### 4. Database Connection Issues
```bash
# Check Cloud SQL instance
gcloud sql instances describe idea-gen-db

# Test database connection
gcloud sql connect idea-gen-db --user=postgres
```

## Performance Optimization

### Recommended Settings
- **Memory**: 2Gi (minimum), 4Gi (production)
- **CPU**: 1 vCPU (minimum), 2 vCPU (production)
- **Concurrency**: 10 requests
- **Timeout**: 900 seconds
- **Min Instances**: 1 (avoid cold starts)
- **Max Instances**: 10 (scale based on demand)

### Caching Strategy
```javascript
// Enable response caching for repeated requests
const cacheOptions = {
  ttl: 300, // 5 minutes
  maxSize: 100 // max cached items
};
```

## 📈 Scaling for Hackathon Demo

### Load Testing
```bash
# Install artillery for load testing
npm install -g artillery

# Run load test
artillery run load-test.yml
```

### Sample Load Test Config (load-test.yml)
```yaml
config:
  target: '{{ $processEnvironment.SERVICE_URL }}'
  phases:
    - duration: 60
      arrivalRate: 10
  payload:
    path: "test-data.csv"
    fields:
      - "prompt"
scenarios:
  - name: "Test idea generation"
    weight: 70
    flow:
      - post:
          url: "/api/ideas/generate"
          json:
            sources: ["trends"]
            count: 3
  - name: "Test idea validation"
    weight: 30
    flow:
      - post:
          url: "/api/ideas/validate"
          json:
            idea:
              title: "Test Idea"
              description: "Test description"
```

## 🏆 Hackathon Success Metrics

### Key Performance Indicators
- **Response Time**: < 3 seconds for idea generation
- **Uptime**: > 99% during demo
- **Error Rate**: < 1%
- **Concurrent Users**: Handle 50+ simultaneous requests

### Demo Checklist
- [ ] Service deployed and accessible
- [ ] Vertex AI integration working
- [ ] Sample ideas generated successfully
- [ ] Validation scores calculated
- [ ] Performance metrics displayed
- [ ] Error handling demonstrated
- [ ] Monitoring dashboard ready

## 📚 Additional Resources

- [Google Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Vertex AI Documentation](https://cloud.google.com/vertex-ai/docs)
- [Gemini Model Documentation](https://ai.google.dev/docs)
- [Cloud SQL Documentation](https://cloud.google.com/sql/docs)

## 🎯 Next Steps for Hackathon

1. **Enhance Search Integration**: Add Elasticsearch for idea search
2. **Fivetran Connectors**: Build data pipelines for trending topics
3. **Advanced Analytics**: Add more sophisticated idea scoring
4. **Real-time Dashboard**: Build frontend for idea management
5. **Mobile Responsiveness**: Ensure demo works on mobile devices

---

**Good luck with the hackathon!**

Remember: The judges will look for:
- **Technical Innovation**: Vertex AI integration
- **Business Value**: Practical idea generation and validation
- **Presentation**: Clear demo and metrics
- **Scalability**: Cloud-native architecture