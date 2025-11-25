# Docker Deployment Guide

This guide covers containerized deployment of the Document Intelligence Platform services.

## Overview

The platform consists of 3 containerized services:
- **API Service**: FastAPI gateway (port 8000)
- **OCR Service**: Tesseract-based text extraction (port 8001)
- **Extraction Service**: LLM-based structured data extraction (embedded in API)

## Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- OpenAI API key (for extraction service)

## Quick Start

### 1. Set Environment Variables

```bash
export OPENAI_API_KEY=your-api-key-here
```

### 2. Build and Run with Docker Compose

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

### 3. Verify Services

```bash
# Check API health
curl http://localhost:8000/health

# Expected response:
# {"status":"healthy","version":"0.1.0","service":"document-intelligence-api"}

# Check API docs
open http://localhost:8000/docs
```

## Building Individual Services

### API Service

```bash
docker build -f services/api/Dockerfile -t doc-intel-api:latest .
docker run -p 8000:8000 \
  -e OPENAI_API_KEY=$OPENAI_API_KEY \
  -e OCR_SERVICE_URL=http://ocr:8001 \
  doc-intel-api:latest
```

### OCR Service

```bash
docker build -f services/ocr/Dockerfile -t doc-intel-ocr:latest .
docker run -p 8001:8001 doc-intel-ocr:latest
```

## Docker Architecture

### Multi-Stage Builds

All Dockerfiles use multi-stage builds for optimal image size:

1. **Builder Stage**: Install build dependencies + Python packages
2. **Runtime Stage**: Copy only runtime dependencies + app code

**Benefits:**
- Smaller final images (~200MB vs ~800MB)
- Faster deployments
- Reduced attack surface

### Security Features

- - Non-root user (UID 1000)
- - Minimal base image (python:3.12-slim)
- - No secrets in images
- - Health checks included
- - Read-only root filesystem (Kubernetes)

### .dockerignore

The `.dockerignore` file excludes:
- Virtual environments (`venv/`)
- Test files and data
- IDE configs
- Documentation
- Git history

**Result:** Faster builds + smaller context

## Testing Docker Images

### Run Tests in Container

```bash
# Build test image
docker build -f services/api/Dockerfile -t doc-intel-api:test .

# Run tests
docker run --rm doc-intel-api:test pytest tests/
```

### Manual Testing

```bash
# Start services
docker-compose up -d

# Upload test document
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -F "file=@data/test_images/sample_invoice.png"

# Stop services
docker-compose down
```

## Troubleshooting

### Check Container Logs

```bash
docker-compose logs api
docker-compose logs ocr
```

### Exec into Container

```bash
docker-compose exec api bash
docker-compose exec ocr bash
```

### Verify Tesseract in OCR Container

```bash
docker-compose exec ocr tesseract --version
```

### Check Network Connectivity

```bash
docker-compose exec api ping ocr
```

## Production Considerations

### Image Tagging

```bash
# Tag with version
docker tag doc-intel-api:latest doc-intel-api:1.0.0

# Tag for registry
docker tag doc-intel-api:latest your-registry.io/doc-intel-api:1.0.0
```

### Push to Registry

```bash
# Docker Hub
docker push your-username/doc-intel-api:1.0.0

# Private registry
docker push your-registry.io/doc-intel-api:1.0.0
```

### Environment Variables

**Required:**
- `OPENAI_API_KEY`: OpenAI API key for extraction

**Optional:**
- `OCR_SERVICE_URL`: URL to OCR service (default: http://ocr:8001)
- `LOG_LEVEL`: Logging level (default: INFO)

### Resource Limits

Add to `docker-compose.yml`:

```yaml
services:
  api:
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 512M
        reservations:
          cpus: '0.5'
          memory: 256M
```

## Next Steps

- **Step 8**: Deploy to Kubernetes (see `k8s/` directory)
- **Step 10**: Add Prometheus metrics for monitoring

## References

- [Docker Best Practices](https://docs.docker.com/develop/develop-images/dockerfile_best-practices/)
- [FastAPI in Docker](https://fastapi.tiangolo.com/deployment/docker/)
- [Multi-Stage Builds](https://docs.docker.com/build/building/multi-stage/)

