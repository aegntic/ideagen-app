# 🌐 Custom Domain Setup Guide for IdeaGen

## 🎯 **Perfect for Hackathon Presentation**

A custom domain makes your project look professional and impresses judges!

---

## 🔧 **Google Cloud Domain Setup**

### **Step 1: Deploy to Google Cloud Run**
```bash
# After Vertex AI setup, deploy:
./quick-deploy.sh your-project-id

# Get your service URL:
SERVICE_URL=$(gcloud run services describe ideagen --format 'value(status.url)')
echo "Service URL: $SERVICE_URL"
```

### **Step 2: Configure Custom Domain**

#### **Option A: Google Cloud Managed SSL (Recommended)**
```bash
# 1. Map your custom domain
gcloud run services update-traffic ideagen \
  --to-latest \
  --region us-central1

# 2. Add domain mapping
gcloud run domain-mappings create \
  --service=ideagen \
  --domain=your-domain.com \
  --region=us-central1

# 3. Get DNS records to add
gcloud run domain-mappings describe your-domain.com \
  --region=us-central1 \
  --format='value(resourceRecords)'

# 4. Add these records to Porkbun:
#    - A record for @ pointing to the provided IP
#    - CNAME record for www pointing to the provided target
```

#### **Option B: Manual DNS Configuration**
```bash
# 1. Get the Cloud Run service URL
SERVICE_URL=$(gcloud run services describe ideagen --format 'value(status.url)')

# 2. In Porkbun DNS settings:
#    Create CNAME record: www → your-service-url.run.app
#    Create CNAME record: @ → your-service-url.run.app
#    (or use A records if you prefer)
```

---

## 🐖 **Porkbun Configuration**

### **DNS Records to Add:**

#### **For Root Domain (@):**
```
Type: CNAME
Name: @ (or leave blank)
Value: [your-cloud-run-url].run.app
TTL: 300 (Automatic)
```

#### **For WWW:**
```
Type: CNAME
Name: www
Value: [your-cloud-run-url].run.app
TTL: 300 (Automatic)
```

#### **Alternative (A Records):**
```
Type: A
Name: @
Value: [IP address from gcloud domain-mapping]
TTL: 300

Type: A
Name: www
Value: [IP address from gcloud domain-mapping]
TTL: 300
```

---

## 🚀 **Cloudflare Alternative (Free & Easy)**

If you want easier SSL management:

1. **Sign up for Cloudflare** (free tier)
2. **Add your domain** to Cloudflare
3. **Point nameservers** to Cloudflare (in Porkbun)
4. **Create CNAME records** in Cloudflare:
   - `www` → `[your-cloud-run-url].run.app`
   - `@` → `[your-cloud-run-url].run.app`
5. **Enable SSL/TLS** in Cloudflare (Full mode)

---

## 🔍 **Domain Verification**

After setting up DNS:

```bash
# Check DNS propagation
dig your-domain.com
dig www.your-domain.com

# Test the application
curl -I https://your-domain.com/health

# Check SSL certificate
curl -I https://your-domain.com
```

---

## 🎯 **Hackathon-Optimal Domain Ideas**

### **Professional & Memorable:**
- `ideagen.app` (if available)
- `ai-ideagen.com`
- `business-ai-generator.com`
- `venture-ideagen.com`
- `startup-ai-generator.com`

### **Short & Catchy:**
- `ideahub.app`
- `venture-ai.app`
- `bizgen.app`
- `ideagenai.com`
- `startidea.app`

### **Hackathon-Specific:**
- `hackathon-ai.com`
- `venture-genius.com`
- `ai-venture-tool.com`
- `idea-vertex.com` (references Vertex AI)

---

## 📊 **Domain Benefits for Hackathon**

### **Judge Impression:**
✅ Professional appearance
✅ Technical competence (domain management)
✅ Commitment to project quality
✅ Production-ready mindset

### **Presentation Advantages:**
✅ Clean, memorable URL for demos
✅ Professional email addresses possible
✅ Brand identity establishment
✅ Easy to share with judges

---

## ⚡ **Quick Setup Checklist**

### **Pre-Deployment:**
- [ ] Choose and register domain on Porkbun
- [ ] Deploy IdeaGen to Google Cloud Run
- [ ] Get service URL from deployment

### **Post-Deployment:**
- [ ] Add CNAME records in Porkbun
- [ ] Wait for DNS propagation (5-30 minutes)
- [ ] Test domain with curl or browser
- [ ] Verify SSL certificate
- [ ] Update presentation materials

### **Final Verification:**
```bash
# Test all endpoints on custom domain
curl https://your-domain.com/health
curl https://your-domain.com/api/ideas
curl -X POST https://your-domain.com/api/ideas/generate \
  -H "Content-Type: application/json" \
  -d '{"sources": ["trends"], "count": 1}'
```

---

## 🏆 **Hackathon Success Tips**

1. **Domain Choice**: Pick something short, memorable, and relevant
2. **Quick Setup**: Use Cloudflare for easier SSL management
3. **Test Thoroughly**: Ensure all endpoints work on the custom domain
4. **Backup Plan**: Keep the Cloud Run URL as fallback
5. **Presentation**: Feature the custom domain prominently in slides

**A professional custom domain can be the difference between a good project and a hackathon winner!** 🎯

---

## 🔄 **Troubleshooting**

### **Common Issues:**
- **DNS not propagating**: Wait longer, check with `dig`
- **SSL certificate errors**: Ensure correct DNS records
- **404 errors**: Verify Cloud Run service is running
- **CORS issues**: Check domain configuration in Cloud Run

### **Quick Test:**
```bash
# Should show your domain working with real AI
curl -s https://your-domain.com/health | jq '.status'
```

**Your custom domain will make your AI-powered idea generator look like a real startup!** 🚀