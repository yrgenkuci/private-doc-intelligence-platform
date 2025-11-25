# Setup Guide

## Prerequisites

- Python 3.11 or 3.12
- Docker 20.10+ and Docker Compose 2.0+ (for containerized deployment)
- kubectl 1.24+ (for Kubernetes deployment)
- OpenAI API key (get one at https://platform.openai.com/api-keys)

## Step 1: Get Your OpenAI API Key

1. Go to https://platform.openai.com/api-keys
2. Sign up or log in
3. Click "Create new secret key"
4. Copy the key (starts with `sk-...`)

## Step 2: Configure Environment Variables

### Option A: Local Development

```bash
# Copy the example file
cp .env.example .env

# Edit .env and add your key
nano .env  # or use your preferred editor
```

Your `.env` should look like:
```
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxx
APP_SERVICE_NAME=doc-intel-api
APP_SERVICE_VERSION=0.1.0
APP_LOG_LEVEL=INFO
```

### Option B: Docker Compose

Same as Option A - Docker Compose automatically reads `.env` file.

### Option C: Kubernetes

```bash
# Create the secret (base64 encoding happens automatically)
kubectl create secret generic doc-intel-secrets \
  --from-literal=OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxx \
  -n doc-intelligence

# Or update the existing secret
kubectl delete secret doc-intel-secrets -n doc-intelligence
kubectl create secret generic doc-intel-secrets \
  --from-literal=OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxx \
  -n doc-intelligence
```

## Step 3: Run the Application

### Local Development

```bash
# Activate virtual environment
source venv/bin/activate  # Linux/Mac
# OR
venv\Scripts\activate  # Windows

# Install dependencies (if not done already)
pip install -r requirements.txt

# Run tests to verify setup
PYTHONPATH=. pytest tests/ -v

# Run API service (in terminal 1)
cd services/api
uvicorn main:app --reload --port 8000

# Run OCR service (in terminal 2)
cd services/ocr
uvicorn service:app --reload --port 8001
```

### Docker Compose

```bash
# Build and start all services
docker-compose up -d

# Check logs
docker-compose logs -f

# Test the API
curl http://localhost:8000/health

# Stop services
docker-compose down
```

### Kubernetes

```bash
# Deploy to development
kubectl apply -k k8s/overlays/dev/

# Deploy to production
kubectl apply -k k8s/overlays/prod/

# Check status
kubectl get all -n doc-intelligence

# Check if secret exists
kubectl get secret doc-intel-secrets -n doc-intelligence
```

## Step 4: Verify Installation

### Test Health Endpoint
```bash
curl http://localhost:8000/health
# Expected: {"status":"healthy"}
```

### Test Metrics Endpoint
```bash
curl http://localhost:8000/metrics
# Expected: Prometheus metrics output
```

### Test Document Upload
```bash
# Upload a test invoice image
curl -X POST http://localhost:8000/upload \
  -F "file=@/path/to/invoice.png" \
  -F "extract_fields=true"
```

## Troubleshooting

### Issue: "OPENAI_API_KEY environment variable not set"

**Solution:**
- **Local:** Make sure `.env` file exists and contains your key
- **Docker:** Make sure `.env` file exists in project root
- **K8s:** Run `kubectl get secret doc-intel-secrets -n doc-intelligence -o yaml`

### Issue: Docker Compose can't find .env file

**Solution:**
```bash
# Make sure you're in the project root
pwd
# Should show: /home/yrgen/YrgenProjects/private-doc-intelligence-platform

# Check if .env exists
ls -la .env

# If not, copy from example
cp .env.example .env
```

### Issue: Tests fail with "No module named 'openai'"

**Solution:**
```bash
# Reinstall dependencies
pip install -r requirements.txt
```

### Issue: Kubernetes secret not found

**Solution:**
```bash
# Create namespace first
kubectl apply -f k8s/base/namespace.yaml

# Then create secret
kubectl create secret generic doc-intel-secrets \
  --from-literal=OPENAI_API_KEY=your-key-here \
  -n doc-intelligence
```

## GitHub Actions Setup (Optional)

If you want to use the CI/CD pipeline:

### Required Secrets
Go to **GitHub Settings > Secrets and variables > Actions**:

1. **KUBE_CONFIG** (for Kubernetes deployment):
   ```bash
   # Get your kubeconfig and base64 encode it
   cat ~/.kube/config | base64 -w 0
   ```
   Copy the output and add as secret `KUBE_CONFIG`

2. **KUBE_CONTEXT** (for Kubernetes deployment):
   ```bash
   # Get your context name
   kubectl config current-context
   ```
   Add as secret `KUBE_CONTEXT`

### Optional Secrets
- `CODECOV_TOKEN`: Only needed for private repos

## What Secrets Are Used Where

| Secret | Local Dev | Docker Compose | Kubernetes | GitHub Actions |
|--------|-----------|----------------|------------|----------------|
| OPENAI_API_KEY | `.env` file | `.env` file | K8s Secret | Not needed (uses K8s secret) |
| KUBE_CONFIG | N/A | N/A | N/A | GitHub Secret |
| KUBE_CONTEXT | N/A | N/A | N/A | GitHub Secret |

## Security Best Practices

- **Never commit `.env` files** - already in `.gitignore`
- **Never commit secrets to Git** - use environment variables
- **Rotate API keys regularly** - update in all environments
- **Use different keys per environment** - dev vs prod
- **Limit key permissions** - use least privilege principle

## Next Steps

- [ ] Get OpenAI API key
- [ ] Create `.env` file
- [ ] Run tests: `PYTHONPATH=. pytest tests/ -v`
- [ ] Start services: `docker-compose up -d`
- [ ] Test upload: Upload a sample invoice
- [ ] Check metrics: Visit `http://localhost:8000/metrics`

For more details, see:
- [Docker Documentation](docs/step-07-docker.md)
- [Kubernetes Documentation](k8s/README.md)
- [GitHub Actions](.github/workflows/)
