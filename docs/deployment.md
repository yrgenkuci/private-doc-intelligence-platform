# Deployment Guide

Complete guide for deploying the Document Intelligence Platform from local development to production.

---

## Table of Contents

1. [Deployment Overview](#deployment-overview)
2. [Local Development](#local-development)
3. [Docker Deployment](#docker-deployment)
4. [Production Deployment](#production-deployment)
5. [Environment Configuration](#environment-configuration)
6. [Troubleshooting](#troubleshooting)

---

## Deployment Overview

The platform supports multiple deployment modes:

| Environment | Method | Use Case | Setup Time |
|-------------|--------|----------|------------|
| **Local Dev** | Python venv | Development & testing | 2 min |
| **Docker Compose** | docker-compose.yml | Local & CI testing | 5 min |
| **Kubernetes** | Kustomize | Production deployments | 15 min |

**Key Point:** The application has NO hardcoded URLs. It adapts to any environment automatically.

---

## Local Development

### Quick Start

```bash
# 1. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up environment
cp .env.example .env
# Edit .env and add: OPENAI_API_KEY=sk-...

# 4. Run the application
PYTHONPATH=. uvicorn services.api.main:app --reload --port 8000
```

### Access

- API: `http://localhost:8000`
- Docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`
- Metrics: `http://localhost:8000/metrics`

---

## Docker Deployment

### Docker Compose (Recommended for Local)

**Best for:** Local testing, CI/CD, development teams

```bash
# 1. Configure environment
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY

# 2. Start services
docker-compose up -d

# 3. Verify
curl http://localhost:8000/health

# 4. View logs
docker-compose logs -f

# 5. Stop
docker-compose down
```

### Manual Docker Build

```bash
# Build API image
docker build -t doc-intel-api:latest services/api/

# Build OCR image  
docker build -t doc-intel-ocr:latest services/ocr/

# Run API container
docker run -d \
  -p 8000:8000 \
  -e OPENAI_API_KEY=sk-your-key \
  --name doc-intel-api \
  doc-intel-api:latest
```

### Docker Healthchecks

**Note:** Healthchecks use `localhost` to check the container itself:

```dockerfile
HEALTHCHECK --interval=30s --timeout=3s \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health')"
```

**This is correct!** The container checks its own health internally.

---

## Production Deployment

### Prerequisites

1. **Container Registry** - GitHub Container Registry (GHCR), Docker Hub, or ECR
2. **Kubernetes Cluster** - GKE, EKS, AKS, or self-hosted
3. **Domain Name** - For public access
4. **TLS Certificate** - Let's Encrypt or cloud provider
5. **OpenAI API Key** - Production key with sufficient quota

---

### Step 1: Build and Push Images

```bash
# Login to registry
echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin

# Build with version tags
export VERSION=v0.1.0
docker build -t ghcr.io/yourusername/doc-intel-api:${VERSION} services/api/
docker build -t ghcr.io/yourusername/doc-intel-ocr:${VERSION} services/ocr/

# Push to registry
docker push ghcr.io/yourusername/doc-intel-api:${VERSION}
docker push ghcr.io/yourusername/doc-intel-ocr:${VERSION}

# Tag as latest
docker tag ghcr.io/yourusername/doc-intel-api:${VERSION} \
           ghcr.io/yourusername/doc-intel-api:latest
docker push ghcr.io/yourusername/doc-intel-api:latest
```

---

### Step 2: Configure Kubernetes

```bash
# Create namespace
kubectl create namespace doc-intelligence

# Create secrets
kubectl create secret generic doc-intel-secrets \
  --from-literal=OPENAI_API_KEY=sk-your-production-key \
  -n doc-intelligence

# Verify secret
kubectl get secret doc-intel-secrets -n doc-intelligence
```

---

### Step 3: Update Manifests

Edit `k8s/overlays/prod/kustomization.yaml`:

```yaml
images:
  - name: doc-intel-api
    newName: ghcr.io/yourusername/doc-intel-api
    newTag: v0.1.0
  - name: doc-intel-ocr
    newName: ghcr.io/yourusername/doc-intel-ocr
    newTag: v0.1.0
```

Edit `k8s/base/api-ingress.yaml` with your domain:

```yaml
spec:
  rules:
  - host: api.yourdomain.com  # ← Your domain
```

---

### Step 4: Deploy

```bash
# Deploy to production
kubectl apply -k k8s/overlays/prod/

# Watch deployment
kubectl get pods -n doc-intelligence -w

# Check status
kubectl get all -n doc-intelligence
```

---

### Step 5: Verify

```bash
# Check pods are running
kubectl get pods -n doc-intelligence
# Expected: All pods Running

# Check services
kubectl get svc -n doc-intelligence

# Check ingress
kubectl get ingress -n doc-intelligence

# Test health endpoint
curl https://api.yourdomain.com/health
# Expected: {"status":"healthy",...}
```

---

## Environment Configuration

The application uses environment variables for all configuration:

### Development (.env file)

```env
ENVIRONMENT=development
LOG_LEVEL=DEBUG
OPENAI_API_KEY=sk-dev-key-here
```

### Staging (Kubernetes ConfigMap)

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: doc-intel-config
data:
  ENVIRONMENT: "staging"
  LOG_LEVEL: "INFO"
```

### Production (Kubernetes Secrets)

```bash
# Never commit secrets!
kubectl create secret generic doc-intel-secrets \
  --from-literal=OPENAI_API_KEY=sk-prod-key \
  --from-literal=ENVIRONMENT=production \
  --from-literal=LOG_LEVEL=WARNING \
  -n doc-intelligence
```

---

## Deployment Comparison

| Feature | Local Dev | Docker Compose | Kubernetes |
|---------|-----------|----------------|------------|
| **Setup Time** | 2 min | 5 min | 15 min |
| **Scaling** | No | Manual | Auto (HPA) |
| **Monitoring** | Manual | Docker logs | Prometheus/Grafana |
| **SSL/TLS** | No | No | Yes (Ingress) |
| **Load Balancing** | No | No | Yes |
| **Health Checks** | No | Yes | Yes |
| **Rolling Updates** | No | Manual | Automatic |
| **Best For** | Dev/Test | CI/Local | Production |

---

## Understanding "localhost"

**Common Question:** Why does documentation mention `localhost` if it's production-ready?

**Answer:** `localhost` only appears in:

1. **Documentation examples** - For local testing
2. **Docker healthchecks** - Container checks itself
3. **NEVER in application code** - Uses environment variables

### How URLs Work by Environment

```python
# Application code (services/shared/config.py)
class Settings(BaseSettings):
    # NO hardcoded URLs!
    openai_api_key: str | None = None  # From env var
    environment: str = "development"    # From env var
```

| Environment | You Access Via | Application Binds To |
|-------------|----------------|----------------------|
| Local Dev | `http://localhost:8000` | `0.0.0.0:8000` |
| Docker | `http://localhost:8000` | `0.0.0.0:8000` |
| Kubernetes | `https://api.yourdomain.com` | `0.0.0.0:8000` |

The application **always** binds to `0.0.0.0` (all interfaces) and adapts to any environment!

---

## Production Checklist

Before deploying to production:

### Security
- [ ] OpenAI API key in Kubernetes Secret (not ConfigMap)
- [ ] TLS certificate configured
- [ ] Ingress firewall rules set
- [x] Non-root containers (already configured)
- [x] Read-only filesystem (already configured)
- [ ] Network policies defined

### Monitoring
- [ ] Prometheus scraping metrics
- [ ] Grafana dashboards imported
- [ ] Alerts configured (high error rate, slow responses)
- [ ] Log aggregation set up (ELK, Loki)

### Reliability
- [x] Resource limits defined (already configured)
- [x] HPA configured (already configured)
- [x] Health checks working (already configured)
- [x] Readiness probes set (already configured)
- [ ] PodDisruptionBudget defined
- [ ] Multi-zone deployment

### Testing
- [ ] Staging environment deployed
- [ ] Load testing completed
- [ ] Integration tests passing
- [ ] Rollback procedure documented

---

## Troubleshooting

### Issue: "ImagePullBackOff" in Kubernetes

**Cause:** Kubernetes can't pull image from registry

**Solution:**
```bash
# Check image name is correct
kubectl describe pod <pod-name> -n doc-intelligence

# Create image pull secret
kubectl create secret docker-registry ghcr-secret \
  --docker-server=ghcr.io \
  --docker-username=USERNAME \
  --docker-password=$GITHUB_TOKEN \
  -n doc-intelligence

# Update deployment to use secret
# (already configured in k8s/base/api-deployment.yaml)
```

### Issue: "CrashLoopBackOff"

**Cause:** Container starts but crashes immediately

**Solution:**
```bash
# Check logs
kubectl logs <pod-name> -n doc-intelligence

# Common causes:
# 1. Missing OPENAI_API_KEY
kubectl get secret doc-intel-secrets -n doc-intelligence

# 2. Wrong port configuration
# 3. Health check failing
```

### Issue: Ingress not working

**Cause:** Ingress controller not installed or misconfigured

**Solution:**
```bash
# Install NGINX Ingress Controller
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/cloud/deploy.yaml

# Check ingress
kubectl get ingress -n doc-intelligence
kubectl describe ingress doc-intel-ingress -n doc-intelligence
```

### Issue: "localhost" in production logs

**This is NORMAL!** Healthchecks use localhost to check the container itself.

---

## Next Steps

Once deployed:

1. **Set up Monitoring** - See [MONITORING.md](MONITORING.md)
2. **Configure Alerts** - Prometheus AlertManager rules
3. **Test API** - See [TESTING.md](TESTING.md)
4. **Review Metrics** - Grafana dashboards

---

## Additional Resources

- **[GETTING-STARTED.md](GETTING-STARTED.md)** - Initial setup guide
- **[KUBERNETES.md](KUBERNETES.md)** - Detailed Kubernetes guide
- **[MONITORING.md](MONITORING.md)** - Prometheus & Grafana setup
- **[TESTING.md](TESTING.md)** - Complete testing guide
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Technical decisions

---

**Need Help?** Check the troubleshooting section above or open an issue on GitHub.

