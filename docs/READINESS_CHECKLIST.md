# Deployment Readiness Checklist

## ✅ Completed & Tested

### Infrastructure Setup
- [x] **Neon PostgreSQL** - Prod & Dev databases created
- [x] **Database Migrations** - Schema migrated to both environments
- [x] **Google Cloud Storage** - Prod & Dev buckets created
- [x] **GCS CORS Configuration** - Configured for frontend access
- [x] **Service Account** - Created with GCS permissions
- [x] **Backend GCS Integration** - Code updated to use GCS with signed URLs

### Backend Code
- [x] **Dockerfile** - Created and tested
- [x] **Docker Build** - Successfully builds without warnings
- [x] **Docker Run** - Successfully runs locally
- [x] **File Upload** - Tested and working with GCS
- [x] **Service Account Handling** - Supports file, env var, and Cloud Run default credentials
- [x] **Relative URLs** - Images use `/api/v1/files/{filename}` for no expiration issues

### Testing
- [x] **Local Docker Test** - Container runs successfully
- [x] **File Upload Test** - Images upload to GCS successfully
- [x] **Signed URLs** - Generated correctly and securely

---

## 🚀 Ready for Deployment

### Phase 2: Deploy Backend to Cloud Run

**Next Steps:**

1. **Push Docker Image to Google Container Registry**
   ```bash
   export GCP_PROJECT_ID="your-project-id"
   gcloud auth configure-docker
   docker tag renovationtech-backend:latest gcr.io/${GCP_PROJECT_ID}/renovationtech-backend:latest
   docker push gcr.io/${GCP_PROJECT_ID}/renovationtech-backend:latest
   ```

2. **Grant Service Account Permissions**
   ```bash
   gcloud projects add-iam-policy-binding ${GCP_PROJECT_ID} \
     --member="serviceAccount:usebowerbird-backend@${GCP_PROJECT_ID}.iam.gserviceaccount.com" \
     --role="roles/storage.objectAdmin"
   ```

3. **Deploy to Cloud Run (DEV)**
   - Follow Step 6 in `DEPLOYMENT_GUIDE.md`
   - Test the deployed service
   - Verify file uploads work

4. **Deploy to Cloud Run (PROD)**
   - Follow Step 7 in `DEPLOYMENT_GUIDE.md`
   - Use production environment variables
   - Test thoroughly

### Phase 3: Deploy Frontend to Firebase Hosting

**After backend is deployed:**

1. **Install Firebase CLI**
   ```bash
   npm install -g firebase-tools
   firebase login
   ```

2. **Initialize Firebase**
   ```bash
   cd frontend
   firebase init hosting
   ```

3. **Update Frontend Environment**
   - Set `VITE_API_BASE_URL` to your Cloud Run URL
   - Build: `npm run build`
   - Deploy: `firebase deploy --only hosting`

---

## 📋 Pre-Deployment Checklist

Before deploying to Cloud Run, ensure:

- [ ] GCP project is set up
- [ ] `gcloud` CLI is installed and authenticated
- [ ] Docker is installed and working
- [ ] Service account has correct permissions
- [ ] Environment variables are ready (from `.env`)
- [ ] Cloud Run API is enabled in GCP project
- [ ] Container Registry API is enabled

---

## 🎯 Current Status

**✅ READY TO DEPLOY**

All infrastructure is set up, code is tested, and Docker image is ready. You can proceed with:

1. **Immediate Next Step:** Push Docker image to GCR and deploy to Cloud Run (DEV)
2. **Then:** Deploy frontend to Firebase Hosting
3. **Finally:** Set up CI/CD (optional but recommended)

---

## 📚 Reference Documents

- **Deployment Guide:** `docs/DEPLOYMENT_GUIDE.md` - Step-by-step deployment instructions
- **Docker Workflow:** `docs/DOCKER_WORKFLOW.md` - When to build vs run
- **This Checklist:** `docs/READINESS_CHECKLIST.md` - What's done and what's next
