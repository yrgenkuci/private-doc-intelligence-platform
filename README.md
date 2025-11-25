# Private Document Intelligence Platform

Production-grade document intelligence platform on Kubernetes. OCR + LLM extraction for regulated environments with full data sovereignty.

## Project Status

**Phase 1: Foundation** - Complete
- Project structure and configuration management

**Phase 2: Core Services** - Complete
- Basic OCR service with Tesseract
- Document ingestion API
- LLM extraction service
- Evaluation harness

**Phase 3: Infrastructure** - Complete
- Docker containers
- Kubernetes manifests

**Phase 4: Observability & CI/CD** - Complete
- Prometheus metrics
- Grafana dashboards
- GitHub Actions CI/CD

## Quick Start

**Get running in 5 minutes:** See [Quick Start Guide](docs/quickstart.md)

### Prerequisites
- Docker Desktop (running)
- OpenAI API key from https://platform.openai.com/api-keys

### Basic Setup

```bash
# 1. Configure API key
cp .env.example .env
# Edit .env and add: OPENAI_API_KEY=sk-your-key-here

# 2. Start services
docker-compose up -d

# 3. Test it works
curl http://localhost:8000/health
# Expected: {"status":"healthy",...}
```

**That's it!** See [quickstart.md](docs/quickstart.md) for testing with actual documents.

### Advanced Setup

**Python development:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. pytest tests/ -v
```

**Kubernetes deployment:**
```bash
kubectl apply -k k8s/overlays/dev/
```

See detailed guides:
- [Docker Deployment](docs/step-07-docker.md)
- [Kubernetes Deployment](k8s/README.md)

## Architecture

Based on industry best practices from:
- Azure Document Intelligence
- Google Document AI
- Klippa Document Processing
- FluxAI Private Document Intelligence

### Core Components

1. **Document Ingestion** - API and batch processing
2. **OCR & Layout Analysis** - Tesseract + EasyOCR (Tesseract implemented)
3. **LLM Extraction** - OpenAI GPT-4o-mini for structured field extraction
4. **Validation & Storage** - PostgreSQL with schema validation (planned)
5. **Evaluation Harness** - Precision/Recall/F1 metrics (planned)
6. **Kubernetes Deployment** - Helm charts with GitOps (planned)

## Documentation

- **[Quick Start](docs/quickstart.md)** - Get running in 5 minutes
- [Setup Guide](docs/setup.md) - Detailed setup with secrets management
- [Testing Guide](docs/testing.md) - Complete testing guide with examples
- [Implementation Notes](docs/implementation-notes.md) - Technical validation
- [Docker Deployment](docs/step-07-docker.md)
- [Grafana Dashboards](docs/step-11-grafana.md)
- [Kubernetes Deployment](k8s/README.md)
- [GitHub Actions CI/CD](.github/workflows/)

## Technology Stack

- **Framework:** FastAPI 0.104.1
- **Configuration:** Pydantic Settings 2.1.0
- **LLM:** OpenAI GPT-4o-mini (via openai 1.3.7)
- **OCR:** Tesseract + Pillow
- **Testing:** Pytest with 100% coverage target
- **Type Checking:** MyPy (strict mode)
- **Code Quality:** Black + Ruff
- **Container Orchestration:** Kubernetes + Kustomize
- **Monitoring:** Prometheus + Grafana (planned)

## Development Guidelines

- Micro-task development (≤60 LOC per change)
- Tests-first approach
- Strict typing (no `any`)
- Production-grade code quality
- All code must pass: black, ruff, mypy, pytest

## License

MIT
