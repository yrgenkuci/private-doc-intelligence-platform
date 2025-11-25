# Kubernetes Deployment Guide

This guide covers deploying the Document Intelligence Platform to Kubernetes using Kustomize.

## Overview

The platform is deployed using Kustomize with a base configuration and environment-specific overlays:
- **Base**: Common manifests (namespace, deployments, services, ingress)
- **Dev**: Development environment (1 replica, minimal resources)
- **Prod**: Production environment (3 replicas, increased resources)

## Prerequisites

- Kubernetes cluster (1.24+)
- kubectl (1.24+)
- kustomize (5.0+) - built into kubectl
- NGINX Ingress Controller
- Metrics Server (for HPA)

## Quick Start

### 1. Deploy to Development

```bash
# Navigate to k8s directory
cd k8s

# Create secret with API key
kubectl create secret generic doc-intel-secrets \
  --from-literal=OPENAI_API_KEY=your-api-key \
  -n doc-intelligence --dry-run=client -o yaml | kubectl apply -f -

# Deploy development overlay
kubectl apply -k overlays/dev/

# Verify deployment
kubectl get all -n doc-intelligence
```

### 2. Deploy to Production

```bash
# Update production images in overlays/prod/*-patch.yaml
# Replace your-registry.io with your actual container registry

# Create secret with API key
kubectl create secret generic doc-intel-secrets \
  --from-literal=OPENAI_API_KEY=your-api-key \
  -n doc-intelligence --dry-run=client -o yaml | kubectl apply -f -

# Deploy production overlay
kubectl apply -k overlays/prod/

# Verify deployment
kubectl get all -n doc-intelligence
```

## Architecture

### Services

**API Service (api-deployment)**
- Port: 8000
- Replicas: 2 (base), 1 (dev), 3 (prod)
- Resources:
  - Dev: 128Mi-256Mi RAM, 100m-250m CPU
  - Base: 256Mi-512Mi RAM, 250m-500m CPU
  - Prod: 512Mi-1Gi RAM, 500m-1000m CPU

**OCR Service (ocr-deployment)**
- Port: 8001
- Replicas: 2 (base), 1 (dev), 3 (prod)
- Resources:
  - Dev: 256Mi-512Mi RAM, 250m-500m CPU
  - Base: 512Mi-1Gi RAM, 500m-1000m CPU
  - Prod: 1Gi-2Gi RAM, 1000m-2000m CPU

### Networking

**Services (ClusterIP)**
- `api-service`: Exposes API on port 8000
- `ocr-service`: Exposes OCR on port 8001

**Ingress**
- Host: `doc-intel.example.com` (replace with your domain)
- Path: `/` → api-service:8000
- Annotations:
  - SSL redirect enabled
  - 10MB body size limit (for document uploads)
  - Rate limiting: 100 req/s

### Auto-scaling (HPA)

**API HPA**
- Min replicas: 2
- Max replicas: 10
- Target CPU: 70%
- Target Memory: 80%

**OCR HPA**
- Min replicas: 2
- Max replicas: 8
- Target CPU: 75%
- Target Memory: 85%

## Configuration

### ConfigMap (doc-intel-config)

```yaml
SERVICE_NAME: "document-intelligence-api"
SERVICE_VERSION: "0.1.0"
LOG_LEVEL: "INFO"  # DEBUG (dev), WARNING (prod)
OCR_SERVICE_URL: "http://ocr-service:8001"
```

### Secrets (doc-intel-secrets)

```yaml
OPENAI_API_KEY: <base64-encoded>
```

**Creating secrets:**

```bash
# From literal
kubectl create secret generic doc-intel-secrets \
  --from-literal=OPENAI_API_KEY=your-key \
  -n doc-intelligence

# From file
echo -n "your-key" > /tmp/api-key
kubectl create secret generic doc-intel-secrets \
  --from-file=OPENAI_API_KEY=/tmp/api-key \
  -n doc-intelligence
rm /tmp/api-key
```

## Security

### Pod Security

- - Non-root user (UID 1000)
- - Read-only root filesystem
- - Drop all capabilities
- - No privilege escalation

### Network Policies

TODO: Add NetworkPolicy manifests for:
- Allow API → OCR communication
- Allow Ingress → API traffic
- Deny all other traffic

## Monitoring

### Health Checks

**Liveness Probes**
- API: `GET /health` (every 30s)
- Initial delay: 10s

**Readiness Probes**
- API: `GET /ready` (every 10s)
- Initial delay: 5s

### Resource Monitoring

```bash
# Check pod metrics
kubectl top pods -n doc-intelligence

# Check HPA status
kubectl get hpa -n doc-intelligence

# Watch HPA scaling
kubectl get hpa -n doc-intelligence -w
```

## Operations

### Viewing Logs

```bash
# All pods
kubectl logs -n doc-intelligence -l app=api --tail=100 -f

# Specific pod
kubectl logs -n doc-intelligence api-deployment-xxx -f
```

### Scaling Manually

```bash
# Scale API
kubectl scale deployment api-deployment -n doc-intelligence --replicas=5

# Scale OCR
kubectl scale deployment ocr-deployment -n doc-intelligence --replicas=4
```

### Rolling Updates

```bash
# Update image
kubectl set image deployment/api-deployment \
  api=your-registry.io/doc-intel-api:1.1.0 \
  -n doc-intelligence

# Check rollout status
kubectl rollout status deployment/api-deployment -n doc-intelligence

# Rollback if needed
kubectl rollout undo deployment/api-deployment -n doc-intelligence
```

### Port Forwarding (for testing)

```bash
# Forward API service
kubectl port-forward -n doc-intelligence svc/api-service 8000:8000

# Test locally
curl http://localhost:8000/health
```

## Troubleshooting

### Pod Not Starting

```bash
# Describe pod
kubectl describe pod -n doc-intelligence api-deployment-xxx

# Check events
kubectl get events -n doc-intelligence --sort-by='.lastTimestamp'

# Check logs
kubectl logs -n doc-intelligence api-deployment-xxx --previous
```

### Image Pull Errors

```bash
# Check image pull secrets
kubectl get secrets -n doc-intelligence

# Verify image exists
docker pull your-registry.io/doc-intel-api:1.0.0
```

### HPA Not Scaling

```bash
# Check metrics server
kubectl get apiservice v1beta1.metrics.k8s.io

# Check HPA status
kubectl describe hpa -n doc-intelligence api-hpa

# Verify resource requests are set
kubectl get deployment api-deployment -n doc-intelligence -o yaml | grep -A 5 resources
```

## Cleanup

### Delete Everything

```bash
# Delete all resources in namespace
kubectl delete namespace doc-intelligence
```

### Delete Specific Resources

```bash
# Delete deployment
kubectl delete -k overlays/dev/

# Keep namespace and secrets
kubectl delete deployment,service,ingress,hpa -n doc-intelligence --all
```

## Production Checklist

Before deploying to production:

- [ ] Update image tags in `overlays/prod/*-patch.yaml`
- [ ] Set up TLS/SSL certificates (cert-manager)
- [ ] Configure DNS for ingress host
- [ ] Set up external secret manager (Vault, AWS Secrets Manager)
- [ ] Add NetworkPolicies for network segmentation
- [ ] Configure resource quotas and limits
- [ ] Set up monitoring and alerting (Step 10)
- [ ] Test HPA scaling under load
- [ ] Document rollback procedures
- [ ] Set up backup for persistent data

## Next Steps

- **Step 10**: Add Prometheus metrics for monitoring
- **Step 11**: Add Grafana dashboards
- **Step 12**: Set up CI/CD pipeline

## References

- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Kustomize Documentation](https://kustomize.io/)
- [NGINX Ingress Controller](https://kubernetes.github.io/ingress-nginx/)
- [Horizontal Pod Autoscaler](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/)

