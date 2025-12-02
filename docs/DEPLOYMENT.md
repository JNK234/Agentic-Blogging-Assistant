# Quibo Architecture Decisions

This document tracks architectural decisions, infrastructure configuration, and deployment details.

---

## Backend Deployment: Google Cloud Run

### Configuration

| Setting | Value |
|---------|-------|
| Platform | Google Cloud Run (managed) |
| Project | `personal-os-475406` |
| Region | `us-central1` |
| Service Name | `quibo-backend` |
| Memory | 4Gi |
| CPU | 2 |
| Min Instances | 0 (scale to zero) |
| Max Instances | 5 |
| Concurrency | 10 |
| Timeout | 300s |
| CPU Boost | Enabled |

### Service URL

```
https://quibo-backend-870041009851.us-central1.run.app
```

### Authentication

The backend uses **two-layer authentication**:

1. **Cloud Run IAM**: Service account-based authentication (org policy requirement)
2. **API Key**: Application-level validation via `X-API-Key` header

#### Frontend Authentication Setup

The frontend authenticates to Cloud Run using:
- **Service Account**: `quibo-frontend@personal-os-475406.iam.gserviceaccount.com`
- **API Key**: Stored in GCP Secret Manager as `quibo-api-key`

#### Required Environment Variables (Frontend)

```bash
# In .env file
QUIBO_API_KEY=<your-api-key>
GCP_SERVICE_ACCOUNT_FILE=frontend-sa-key.json
```

#### Testing API Access

```bash
# Health check (no auth required)
curl https://quibo-backend-870041009851.us-central1.run.app/health

# Authenticated request
curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
     -H "X-API-Key: <your-api-key>" \
  https://quibo-backend-870041009851.us-central1.run.app/models
```

#### Service Account Setup (One-time)

```bash
# Create service account
gcloud iam service-accounts create quibo-frontend \
  --display-name="Quibo Frontend Service Account" \
  --project=personal-os-475406

# Grant Cloud Run invoker permission
gcloud run services add-iam-policy-binding quibo-backend \
  --member="serviceAccount:quibo-frontend@personal-os-475406.iam.gserviceaccount.com" \
  --role="roles/run.invoker" \
  --region=us-central1 \
  --project=personal-os-475406

# Create key file for local development
gcloud iam service-accounts keys create frontend-sa-key.json \
  --iam-account=quibo-frontend@personal-os-475406.iam.gserviceaccount.com \
  --project=personal-os-475406
```

**Important**: Never commit `frontend-sa-key.json` to version control.

---

## Environment Variables

Set via Cloud Run deployment:

| Variable | Value | Purpose |
|----------|-------|---------|
| `EMBEDDING_PROVIDER` | `sentence_transformer` | Embedding model provider |
| `SENTENCE_TRANSFORMER_MODEL_NAME` | `all-MiniLM-L6-v2` | Embedding model (pre-downloaded in Docker build) |
| `CHROMA_PERSIST_DIR` | `/tmp/vector_store` | Ephemeral ChromaDB storage |
| `GEMINI_MODEL_NAME` | `gemini-2.5-pro` | LLM model for generation |

---

## Secrets (GCP Secret Manager)

Secrets stored with user-managed replication in `us-central1`:

| Secret Name | Purpose |
|-------------|---------|
| `gemini-api-key` | Gemini API authentication |
| `supabase-url` | Supabase project URL |
| `supabase-key` | Supabase anonymous key |
| `quibo-api-key` | API key for frontend authentication |

### Creating/Updating Secrets

```bash
# Create secret with regional replication (required by org policy)
gcloud secrets create <secret-name> \
  --replication-policy="user-managed" \
  --locations="us-central1" \
  --project=personal-os-475406

# Add secret version
echo -n "secret-value" | gcloud secrets versions add <secret-name> --data-file=-

# Grant access to Cloud Run service account
gcloud secrets add-iam-policy-binding <secret-name> \
  --member="serviceAccount:870041009851-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

---

## Deployment Command

```bash
cd root && \
gcloud run deploy quibo-backend \
  --source . \
  --region=us-central1 \
  --project=personal-os-475406 \
  --platform=managed \
  --memory=4Gi \
  --cpu=2 \
  --min-instances=0 \
  --max-instances=5 \
  --concurrency=10 \
  --timeout=300 \
  --cpu-boost \
  --set-env-vars="EMBEDDING_PROVIDER=sentence_transformer,SENTENCE_TRANSFORMER_MODEL_NAME=all-MiniLM-L6-v2,CHROMA_PERSIST_DIR=/tmp/vector_store,GEMINI_MODEL_NAME=gemini-2.5-pro" \
  --set-secrets="GEMINI_API_KEY=gemini-api-key:latest,SUPABASE_URL=supabase-url:latest,SUPABASE_KEY=supabase-key:latest,QUIBO_API_KEY=quibo-api-key:latest"
```

---

## Storage Architecture

| Component | Storage | Persistence |
|-----------|---------|-------------|
| ChromaDB (vector store) | `/tmp/vector_store` | Ephemeral (per instance) |
| Project state | Supabase PostgreSQL | Persistent |
| File uploads | `/app/data/uploads` | Ephemeral (per instance) |

**Note**: Vector embeddings and uploads are ephemeral in Cloud Run. Supabase handles persistent state.

---

## Docker Build

- Multi-stage build for reduced image size
- SentenceTransformer model pre-downloaded during build (reduces cold start)
- Python 3.11-slim base image
- Health check endpoint: `/health`

---

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Health check |
| `/models` | GET | List available LLM models |
| `/personas` | GET | List available writing personas |
| `/upload` | POST | Upload files for processing |
| `/process` | POST | Process uploaded content |
| `/outline` | POST | Generate blog outline |
| `/draft` | POST | Generate blog draft |

---

## Adding LLM Providers

To add additional LLM providers, create secrets and update deployment:

```bash
# Example: Add OpenAI
gcloud secrets create openai-api-key \
  --replication-policy="user-managed" \
  --locations="us-central1"

echo -n "sk-..." | gcloud secrets versions add openai-api-key --data-file=-

# Update deployment with additional secret
gcloud run deploy quibo-backend \
  ... \
  --set-secrets="...,OPENAI_API_KEY=openai-api-key:latest"
```
