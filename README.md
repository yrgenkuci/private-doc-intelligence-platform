# Private Document Intelligence Platform

Production-grade document intelligence platform for regulated environments with full data sovereignty. Supports both cloud (OpenAI) and self-hosted (Ollama) LLM extraction.

## Features

- **OCR Processing** - Tesseract and PaddleOCR support
- **LLM Extraction** - OpenAI GPT-4o-mini, Ollama (self-hosted), local Donut model
- **Async Processing** - Redis-backed job queue with batch support
- **Object Storage** - MinIO (S3-compatible) for document persistence
- **Drift Detection** - Real-time accuracy monitoring with alerting
- **Production Ready** - Helm charts, HPA, security contexts, Prometheus metrics

## Quick Start

### Prerequisites

- Python 3.11+
- Docker (optional, for Redis/MinIO)
- Tesseract OCR: `sudo apt install tesseract-ocr`

### Installation

```bash
git clone https://github.com/yrgenkuci/private-doc-intelligence-platform.git
cd private-doc-intelligence-platform
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Configuration

```bash
cp .env.example .env
# Edit .env with your settings:
# OPENAI_API_KEY=sk-...  (for cloud LLM)
# APP_EXTRACTION_PROVIDER=ollama  (for self-hosted)
```

### Run API Server

```bash
source .env
uvicorn services.api.main:app --host 0.0.0.0 --port 8000
```

### Test

```bash
curl http://localhost:8000/health
# {"status":"healthy","version":"0.1.0","service":"doc-intelligence-platform"}

curl -X POST "http://localhost:8000/api/v1/documents/upload?extract_fields=true" \
  -F "file=@invoice.png"
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/ready` | GET | Readiness probe |
| `/metrics` | GET | Prometheus metrics |
| `/api/v1/documents/upload` | POST | Sync OCR + extraction |
| `/api/v1/documents/upload/async` | POST | Async job submission |
| `/api/v1/documents/upload/batch` | POST | Batch processing (up to 100) |
| `/api/v1/jobs/{job_id}` | GET | Job status |
| `/api/v1/batches/{batch_id}` | GET | Batch status |
| `/api/v1/drift/stats` | GET | Accuracy drift metrics |

## Production Deployment

### Helm (Recommended)

```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
cd helm/doc-intelligence && helm dependency update
helm install doc-intel . \
  --namespace doc-intelligence \
  --create-namespace \
  --set secrets.storageAccessKey=<minio-key> \
  --set secrets.storageSecretKey=<minio-secret>
```

### Kubernetes (Kustomize)

```bash
kubectl apply -k k8s/overlays/prod/
```

### Docker Compose

```bash
docker-compose up -d
```

### Docker (Self-Hosted with Ollama)

```bash
# 1. Install and start Ollama
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull qwen2.5:7b

# 2. Run container (Linux - use --network host)
docker run --network host \
  -e APP_EXTRACTION_PROVIDER=ollama \
  -e APP_OLLAMA_BASE_URL=http://localhost:11434 \
  yrgenkuci/doc-intelligence:v0.1.0

# 3. Test
curl -X POST "http://localhost:8000/api/v1/documents/upload?extract_fields=true" \
  -F "file=@invoice.png"
```

## Configuration Options

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_OCR_PROVIDER` | tesseract | OCR: `tesseract`, `paddleocr` |
| `APP_EXTRACTION_PROVIDER` | openai | LLM: `openai`, `ollama`, `local` |
| `APP_OPENAI_MODEL` | gpt-4o-mini | Model: `gpt-4o-mini` (fast), `gpt-4o` (accurate) |
| `APP_OLLAMA_BASE_URL` | http://localhost:11434 | Ollama server URL |
| `APP_QUEUE_ENABLED` | false | Enable async processing |
| `APP_REDIS_URL` | redis://localhost:6379 | Redis connection |
| `APP_STORAGE_ENABLED` | false | Enable MinIO storage |

See `services/shared/config.py` for all options.

## Documentation

- [Getting Started](docs/getting-started.md) - Setup guide
- [Testing](docs/testing.md) - Test procedures
- [Deployment](docs/deployment.md) - Production deployment
- [Kubernetes](docs/kubernetes.md) - K8s configuration

## Technology Stack

| Component | Technology |
|-----------|------------|
| Framework | FastAPI 0.122.0 |
| OCR | Tesseract, PaddleOCR |
| LLM | OpenAI, Ollama, Donut |
| Queue | arq (Redis) |
| Storage | MinIO (S3) |
| Monitoring | Prometheus, Grafana |
| Deployment | Helm, Kubernetes |

## Development

```bash
# Run tests
pytest tests/unit/ -v

# Code quality
black . && ruff check . && mypy services/

# Run evaluation
python pipeline/eval/eval.py --gold data/gold/invoices_external.json
```

## License

MIT
