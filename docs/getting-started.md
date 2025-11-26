# Getting Started

Get the Document Intelligence Platform running in 5 minutes, or follow the detailed setup for production deployments.

---

## 📋 Table of Contents

1. [Quick Start (5 minutes)](#quick-start-5-minutes) - Local development
2. [Detailed Setup](#detailed-setup) - Production & Kubernetes
3. [Verification](#verification)
4. [Troubleshooting](#troubleshooting)

---

## Quick Start (5 Minutes)

### Prerequisites

1. **Docker Desktop** - Make sure it's running
   ```bash
   docker --version
   # Should show: Docker version 20.10+
   ```

2. **OpenAI API Key** - Get from https://platform.openai.com/api-keys
   - Sign up for OpenAI account
   - Generate API key (starts with `sk-...`)

### Step 1: Configure API Key

Create a `.env` file with your OpenAI key:

```bash
cd /home/yrgen/YrgenProjects/private-doc-intelligence-platform

# Copy the example file
cp .env.example .env

# Edit .env and add your key
nano .env
```

Your `.env` file should look like this:
```env
OPENAI_API_KEY=sk-your-actual-key-here
```

Save and close the file.

### Step 2: Start the Services

```bash
# Start everything with Docker Compose
docker-compose up -d

# Wait 10 seconds for services to start
sleep 10
```

### Step 3: Verify It's Running

```bash
# Test the health endpoint
curl http://localhost:8000/health

# Expected output:
# {"status":"healthy","version":"0.1.0","service":"doc-intel-api"}
```

If you see the JSON response above, **it's working!** 🎉

### Step 4: Test with a Document (Optional)

#### Create a test invoice:

```bash
mkdir -p test_data

# Create using Python
python3 << 'PYTHON'
from PIL import Image, ImageDraw
import os

os.makedirs('test_data', exist_ok=True)
img = Image.new('RGB', (800, 1000), color='white')
draw = ImageDraw.Draw(img)

text = """INVOICE

Invoice Number: INV-2024-001
Date: November 25, 2024
Due Date: December 25, 2024

Bill To:
Acme Corporation
123 Business Street
New York, NY 10001

From:
Tech Services LLC
456 Tech Avenue
San Francisco, CA 94102

Items:
- Software License: $1,000.00
- Support Services: $500.00

Subtotal: $1,500.00
Tax (10%): $150.00
Total: $1,650.00"""

draw.text((50, 50), text, fill='black')
img.save('test_data/invoice.png')
print("✅ Created test_data/invoice.png")
PYTHON
```

#### Test OCR + LLM Extraction:

```bash
curl -X POST "http://localhost:8000/api/v1/documents/upload?extract_fields=true" \
  -F "file=@test_data/invoice.png" \
  | python3 -m json.tool

# Expected: Structured JSON with invoice_number, total_amount, etc.
```

### Quick Reference

```bash
# Start services
docker-compose up -d

# Check health
curl http://localhost:8000/health

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

**That's it for quick start!** For production setup, continue below. ⬇️

---

## Detailed Setup

For production deployments, development environments, or Kubernetes.

### Prerequisites

- **Python 3.11 or 3.12**
- **Docker 20.10+** and **Docker Compose 2.0+**
- **kubectl 1.24+** (for Kubernetes deployment)
- **OpenAI API key** (from https://platform.openai.com/api-keys)

---

### Local Development (Python)

For developing without Docker:

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# OR
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
nano .env  # Add your OPENAI_API_KEY

# Run tests
PYTHONPATH=. pytest tests/ -v

# Run API service
PYTHONPATH=. uvicorn services.api.main:app --reload --port 8000
```

---

### Docker Compose Deployment

Best for local testing and development:

#### 1. Configure Environment

```bash
# Copy example file
cp .env.example .env

# Edit and add your key
nano .env
```

Your `.env` should contain:
```env
OPENAI_API_KEY=sk-your-key-here
APP_SERVICE_NAME=doc-intel-api
APP_SERVICE_VERSION=0.1.0
APP_LOG_LEVEL=INFO
```

#### 2. Build and Run

```bash
# Build all services
docker-compose build

# Start services
docker-compose up -d

# Check logs
docker-compose logs -f

# Stop services
docker-compose down
```

---

### Kubernetes Deployment

For production environments:

#### 1. Create Namespace and Secrets

```bash
# Create namespace
kubectl create namespace doc-intelligence

# Create secret with API key
kubectl create secret generic doc-intel-secrets \
  --from-literal=OPENAI_API_KEY=sk-your-production-key \
  -n doc-intelligence
```

#### 2. Deploy to Development

```bash
# Deploy development overlay
kubectl apply -k k8s/overlays/dev/

# Verify deployment
kubectl get all -n doc-intelligence
```

#### 3. Deploy to Production

```bash
# Update production images in k8s/overlays/prod/*-patch.yaml
# Replace image registry with your actual registry

# Deploy production overlay
kubectl apply -k k8s/overlays/prod/

# Verify deployment
kubectl get all -n doc-intelligence

# Check pods are running
kubectl get pods -n doc-intelligence
```

---

### GitHub Actions CI/CD Setup

For automated deployments:

#### Required Secrets

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

---

## Verification

### Test Health Endpoint

```bash
curl http://localhost:8000/health
```

**Expected response:**
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "service": "doc-intel-api"
}
```

### Test Metrics Endpoint

```bash
curl http://localhost:8000/metrics | head -20
```

**Expected:** Prometheus metrics output

### Test Interactive API Documentation

Open in browser:
```
http://localhost:8000/docs
```

You'll see Swagger UI with all endpoints documented.

### Test Document Upload

```bash
curl -X POST "http://localhost:8000/api/v1/documents/upload?extract_fields=true" \
  -F "file=@test_data/invoice.png" \
  | jq .
```

**Expected:** JSON with success=true and extracted_data populated

---

## Troubleshooting

### Problem: "Connection refused" on port 8000

**Solution:**
```bash
# Check if container is running
docker-compose ps

# If not running, start it
docker-compose up -d

# Check logs for errors
docker-compose logs api
```

### Problem: "OPENAI_API_KEY not set"

**Solution:**

**Local/Docker:**
```bash
# Check .env file exists
cat .env

# Should contain: OPENAI_API_KEY=sk-...
# If not, add your key
echo "OPENAI_API_KEY=sk-your-key-here" > .env

# Restart services
docker-compose down
docker-compose up -d
```

**Kubernetes:**
```bash
# Check secret exists
kubectl get secret doc-intel-secrets -n doc-intelligence

# If missing, create it
kubectl create secret generic doc-intel-secrets \
  --from-literal=OPENAI_API_KEY=sk-your-key \
  -n doc-intelligence
```

### Problem: Port 8000 already in use

**Solution:**
```bash
# Find process using port 8000
lsof -ti:8000

# Kill it
lsof -ti:8000 | xargs kill -9

# Or use different port
docker-compose down
# Edit docker-compose.yml to use different port
docker-compose up -d
```

### Problem: OCR returns empty text

**Solution:**
- Check image quality (should be clear, readable)
- Try with a different image
- Ensure Tesseract is installed: `docker-compose exec api tesseract --version`

### Problem: Docker Compose can't find .env file

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

### Problem: Tests fail with "No module named 'openai'"

**Solution:**
```bash
# Reinstall dependencies
source venv/bin/activate
pip install -r requirements.txt
```

### Problem: Kubernetes secret not found

**Solution:**
```bash
# Create namespace first
kubectl create namespace doc-intelligence

# Then create secret
kubectl create secret generic doc-intel-secrets \
  --from-literal=OPENAI_API_KEY=your-key-here \
  -n doc-intelligence
```

---

## What Secrets Are Used Where

| Secret | Local Dev | Docker Compose | Kubernetes | GitHub Actions |
|--------|-----------|----------------|------------|----------------|
| OPENAI_API_KEY | `.env` file | `.env` file | K8s Secret | Via K8s secret |
| KUBE_CONFIG | N/A | N/A | N/A | GitHub Secret |
| KUBE_CONTEXT | N/A | N/A | N/A | GitHub Secret |

---

## Security Best Practices

- ✅ **Never commit `.env` files** - already in `.gitignore`
- ✅ **Never commit secrets to Git** - use environment variables
- ✅ **Rotate API keys regularly** - update in all environments
- ✅ **Use different keys per environment** - dev vs staging vs prod
- ✅ **Limit key permissions** - use least privilege principle

---

## Next Steps

Once you've verified it works:

1. **Run Tests** - See [TESTING.md](TESTING.md)
2. **Deploy to Production** - See [DEPLOYMENT.md](DEPLOYMENT.md)
3. **Set up Monitoring** - See [MONITORING.md](MONITORING.md)
4. **Kubernetes Details** - See [KUBERNETES.md](KUBERNETES.md)

---

## Quick Commands Reference

```bash
# Local Development
source venv/bin/activate
PYTHONPATH=. pytest tests/ -v
PYTHONPATH=. uvicorn services.api.main:app --reload

# Docker Compose
docker-compose up -d
docker-compose logs -f
docker-compose down

# Kubernetes
kubectl apply -k k8s/overlays/dev/
kubectl get all -n doc-intelligence
kubectl logs -f deployment/doc-intel-api -n doc-intelligence

# Testing
curl http://localhost:8000/health
curl http://localhost:8000/docs
curl -X POST "http://localhost:8000/api/v1/documents/upload?extract_fields=true" \
  -F "file=@test_data/invoice.png"
```

---

**Need help?** See [TROUBLESHOOTING section](#troubleshooting) above or check other documentation:
- [TESTING.md](TESTING.md) - Complete testing guide
- [DEPLOYMENT.md](DEPLOYMENT.md) - Production deployment
- [KUBERNETES.md](KUBERNETES.md) - Kubernetes details

