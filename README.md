# Private Document Intelligence Platform

Production-grade document intelligence platform on Kubernetes. OCR + LLM extraction for regulated environments with full data sovereignty.

## Project Status

**Phase 1: Foundation** ✓ Complete
- [x] Step 1: Project structure and configuration management

**Phase 2: Core Services** (In Progress)
- [x] Step 2: Basic OCR service with Tesseract
- [ ] Step 3: Document ingestion API
- [ ] Step 4: LLM extraction service
- [ ] Step 5: Data validation and storage
- [ ] Step 6: Evaluation harness

**Phase 3: Infrastructure** (Planned)
- [ ] Step 7: Docker containers
- [ ] Step 8: Kubernetes manifests
- [ ] Step 9: Helm charts

**Phase 4: Observability & CI/CD** (Planned)
- [ ] Step 10: Prometheus metrics
- [ ] Step 11: Grafana dashboards
- [ ] Step 12: GitLab CI pipeline

## Quick Start

### Prerequisites
- Python 3.11+
- Git

### Setup
```bash
# Clone the repository
git clone <repository-url>
cd private-doc-intelligence-platform

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run tests
PYTHONPATH=. pytest tests/ -v
```

## Architecture

Based on industry best practices from:
- Azure Document Intelligence
- Google Document AI
- Klippa Document Processing
- FluxAI Private Document Intelligence

### Core Components

1. **Document Ingestion** - API and batch processing
2. **OCR & Layout Analysis** - Tesseract + EasyOCR
3. **LLM Extraction** - Hugging Face models on GPU
4. **Validation & Storage** - PostgreSQL with schema validation
5. **Evaluation Harness** - Precision/Recall/F1 metrics
6. **Kubernetes Deployment** - Helm charts with GitOps

## Documentation

- [Step 1: Foundation Setup](docs/step-01-foundation.md)
- [Step 2: OCR Service](docs/step-02-ocr-service.md)
- [Testing Guide](docs/testing-guide.md)

## Technology Stack

- **Framework:** FastAPI 0.104.1
- **Configuration:** Pydantic Settings 2.1.0
- **Testing:** Pytest with 100% coverage target
- **Type Checking:** MyPy (strict mode)
- **Code Quality:** Black + Ruff
- **Container Orchestration:** Kubernetes + Helm
- **Monitoring:** Prometheus + Grafana

## Development Guidelines

- Micro-task development (≤60 LOC per change)
- Tests-first approach
- Strict typing (no `any`)
- Production-grade code quality
- All code must pass: black, ruff, mypy, pytest

## License

MIT
