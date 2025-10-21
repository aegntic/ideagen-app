# 🚀 Manual Google Cloud Deployment Instructions

## Step 1: Set Up Google Cloud Account

**Go to Google Cloud Console**: https://console.cloud.google.com/

1. **Sign in** with your Google account
2. **Create a new project** or select existing one
3. **Enable billing** (required for Cloud Run)

## Step 2: Install and Authenticate Google Cloud CLI

```bash
# Install gcloud CLI (if not already installed)
curl https://sdk.cloud.google.com | bash
exec -l $SHELL

# Authenticate with Google Cloud
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

## Step 3: Enable Required APIs

**Go to APIs & Services > Library**: https://console.cloud.google.com/apis/library

Enable these APIs:
- ✅ **Cloud Run API** - `run.googleapis.com`
- ✅ **Cloud Build API** - `cloudbuild.googleapis.com`
- ✅ **Artifact Registry API** - `artifactregistry.googleapis.com`
- ✅ **Vertex AI API** - `aiplatform.googleapis.com`

## Step 4: One-Command Deployment (After Setup)

Once authenticated, run this from your project directory:

```bash
# Set your project ID first
export GOOGLE_CLOUD_PROJECT_ID=your-project-id

# Deploy
./quick-deploy.sh $GOOGLE_CLOUD_PROJECT_ID
```

## Step 5: Deploy via Google Cloud Console (Alternative)

### Option A: Cloud Run Direct Deploy

1. **Go to Cloud Run**: https://console.cloud.google.com/run
2. Click **"Create Service"**
3. **Container image URL**: `us-docker.pkg.dev/cloudrun/container/hello`
4. **Replace with**: `gcr.io/[YOUR_PROJECT_ID]/ideagen:latest`
5. **Settings**:
   - Memory: 2GiB
   - CPU: 1 vCPU
   - Minimum instances: 0
   - Maximum instances: 10
   - Allow unauthenticated traffic: ✅

### Option B: Use Cloud Build

1. **Go to Cloud Build**: https://console.cloud.google.com/cloud-build
2. Click **"Create Trigger"**
3. Connect your GitHub repository
4. Build with Dockerfile (simplified)
5. Deploy to Cloud Run automatically

## Step 6: Configure Vertex AI Access

### Grant Permissions to Cloud Run Service Account

```bash
# Get the service account
PROJECT_NUMBER=$(gcloud projects describe $GOOGLE_CLOUD_PROJECT_ID --format='value(projectNumber)')
SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

# Grant Vertex AI permissions
gcloud projects add-iam-policy-binding $GOOGLE_CLOUD_PROJECT_ID \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/aiplatform.user"
```

## Step 7: Test Your Deployment

After deployment, you'll get a URL like:
`https://ideagen-xxxxx-xx.a.run.app`

Test these endpoints:
- Health: `https://your-url/health`
- Generate Ideas: `POST /api/ideas/generate`
- Frontend: `https://your-url/` (full application)

## Quick Links

**Google Cloud Console**: https://console.cloud.google.com/
**Cloud Run Services**: https://console.cloud.google.com/run
**Vertex AI Studio**: https://console.cloud.google.com/vertex-ai
**Cloud Build**: https://console.cloud.google.com/cloud-build
**API Library**: https://console.cloud.google.com/apis/library

## Environment Variables (Optional)

If you want to configure the deployment with custom settings:

```bash
NODE_ENV=production
GOOGLE_CLOUD_PROJECT_ID=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
VECTOR_DB_TYPE=memory
USE_MEMORY_FALLBACK=true
PORT=8080
```

## Success Checklist

- [ ] Google Cloud account created and billing enabled
- [ ] Project created and selected
- [ ] gcloud CLI installed and authenticated
- [ ] Required APIs enabled (Cloud Run, Cloud Build, Vertex AI)
- [ ] Docker image built successfully
- [ ] Application deployed to Cloud Run
- [ ] Vertex AI permissions configured
- [ ] Testing completed

## Troubleshooting

**Common Issues:**
1. **"Account not active"** → Run `gcloud auth login`
2. **"API not enabled"** → Enable APIs manually in console
3. **"Build failed"** → Use simplified Dockerfile
4. **"Permission denied"** → Check IAM roles for service account

**Get Help**: https://cloud.google.com/docs/support

---

**Your application is ready for deployment!** Once you complete the Google Cloud setup and run the deployment script, you'll have a fully functional AI-powered idea generation platform running on Vertex AI. 🚀