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

Get running in 5 minutes - see [getting-started.md](docs/getting-started.md)

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

See [getting-started.md](docs/getting-started.md) for testing with actual documents.

### Advanced Setup

Python development:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. pytest tests/ -v
```

Kubernetes deployment:
```bash
kubectl apply -k k8s/overlays/dev/
```

See detailed guides:
- [getting-started.md](docs/getting-started.md) - Setup and configuration
- [deployment.md](docs/deployment.md) - Docker and Kubernetes deployment
- [kubernetes.md](docs/kubernetes.md) - Advanced Kubernetes configuration

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

- [getting-started.md](docs/getting-started.md) - Setup and configuration
- [testing.md](docs/testing.md) - Testing guide with examples
- [deployment.md](docs/deployment.md) - Docker and production deployment
- [kubernetes.md](docs/kubernetes.md) - Kubernetes deployment guide
- [monitoring.md](docs/monitoring.md) - Prometheus and Grafana dashboards
- [architecture.md](docs/architecture.md) - Technical decisions and validation
- [roadmap.md](docs/roadmap.md) - Future enhancements
- [.github/workflows/](.github/workflows/) - CI/CD workflows

## Technology Stack

- **Framework:** FastAPI 0.122.0
- **Configuration:** Pydantic Settings 2.1.0
- **LLM:** OpenAI GPT-4o-mini (via openai 1.109.1)
- **OCR:** Tesseract + Pillow 10.4.0
- **Testing:** Pytest with comprehensive test coverage
- **Type Checking:** MyPy (strict mode)
- **Code Quality:** Black + Ruff
- **Container Orchestration:** Kubernetes + Kustomize
- **Monitoring:** Prometheus + Grafana

## Development Guidelines

- Micro-task development (≤60 LOC per change)
- Tests-first approach
- Strict typing (no `any`)
- Production-grade code quality
- All code must pass: black, ruff, mypy, pytest

## License

MIT
