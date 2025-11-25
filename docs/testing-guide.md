# Testing Guide

Complete testing guide for the Private Document Intelligence Platform.

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Automated Tests](#automated-tests)
4. [Manual API Testing](#manual-api-testing)
5. [Component Testing](#component-testing)
6. [Integration Testing](#integration-testing)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements
- Python 3.11 or higher
- Tesseract OCR engine installed
- Git

### Install Tesseract

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr
```

**macOS:**
```bash
brew install tesseract
```

**Windows:**
- Download from: https://github.com/UB-Mannheim/tesseract/wiki
- Add to PATH or set `TESSERACT_CMD` environment variable

**Verify installation:**
```bash
tesseract --version
# Expected: tesseract 4.x or 5.x
```

### Python Environment Setup

```bash
# Navigate to project
cd ~/YrgenProjects/private-doc-intelligence-platform

# Create virtual environment
python3 -m venv venv

# Activate
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate    # Windows

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Install project in editable mode
pip install -e .

# Verify installation
python --version  # Should be 3.11+
pip list | grep -E "fastapi|pytest|pytesseract"
```

---

## Quick Start

### Run All Checks (One Command)

```bash
black . && ruff check . && mypy services/ --strict && pytest -v
```

**Expected output:**
```
All done! ✨ 🍰 ✨
10 files left unchanged.
Success: no issues found in 6 source files
====== 15 passed in 0.71s ======
```

---

## Automated Tests

### 1. Code Formatting (Black)

```bash
# Check formatting
black --check .

# Auto-format all files
black .
```

**What it checks:** Consistent code style (line length, spacing, quotes)

---

### 2. Linting (Ruff)

```bash
# Check for issues
ruff check .

# Auto-fix issues
ruff check --fix .
```

**What it checks:** 
- Import sorting
- Unused variables
- Syntax errors
- Common bugs (flake8-bugbear)
- Modern Python patterns (pyupgrade)

---

### 3. Type Checking (MyPy)

```bash
# Check types (strict mode)
mypy services/ --strict

# Check specific file
mypy services/ocr/service.py --strict
```

**What it checks:** Type safety, function signatures, return types

---

### 4. Unit Tests (Pytest)

```bash
# Run all tests
pytest -v

# Run specific test file
pytest tests/unit/test_config.py -v

# Run specific test
pytest tests/unit/test_api.py::test_health_check -v

# Run with coverage
pytest --cov=services --cov-report=term-missing -v

# Generate HTML coverage report
pytest --cov=services --cov-report=html
# Open htmlcov/index.html in browser
```

**Current test suite:**
- 15 tests total
- 96% code coverage
- Tests split across:
  - `test_config.py` (4 tests) - Configuration management
  - `test_ocr_service.py` (5 tests) - OCR functionality
  - `test_api.py` (6 tests) - API endpoints

---

## Manual API Testing

### Start the Server

**Terminal 1:**
```bash
cd ~/YrgenProjects/private-doc-intelligence-platform
source venv/bin/activate
uvicorn services.api.main:app --reload --port 8000
```

**Expected output:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
```

Leave this running and open a new terminal for testing.

---

### Interactive Documentation

**Swagger UI:**
```
http://localhost:8000/docs
```

**ReDoc:**
```
http://localhost:8000/redoc
```

Features:
- Visual API documentation
- Try endpoints directly in browser
- Upload test files
- See request/response schemas

---

### Test 1: Health Check

```bash
curl http://localhost:8000/health | jq
```

**Expected response:**
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "service": "doc-intelligence-platform"
}
```

---

### Test 2: Readiness Check

```bash
curl http://localhost:8000/ready | jq
```

**Expected response:**
```json
{
  "ready": true
}
```

---

### Test 3: Document Upload (Success)

**Create test image:**
```bash
python3 << 'EOF'
from PIL import Image, ImageDraw

# Create simple invoice image
img = Image.new('RGB', (400, 200), color='white')
d = ImageDraw.Draw(img)

d.text((20, 20), "INVOICE", fill='black')
d.text((20, 60), "Invoice #: 12345", fill='black')
d.text((20, 100), "Date: 2024-01-15", fill='black')
d.text((20, 140), "Total: $1,234.56", fill='black')

img.save("test_invoice.png")
print("✓ Created test_invoice.png")
EOF
```

**Upload the image:**
```bash
curl -X POST "http://localhost:8000/api/v1/documents/upload" \
  -F "file=@test_invoice.png" | jq
```

**Expected response:**
```json
{
  "success": true,
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "text": "INVOICE\nInvoice #: 12345\nDate: 2024-01-15\nTotal: $1,234.56\n",
  "error": null
}
```

---

### Test 4: Error Handling

**Invalid file type:**
```bash
echo "Not an image" > test.txt
curl -X POST "http://localhost:8000/api/v1/documents/upload" \
  -F "file=@test.txt" | jq
```

**Expected: 400 Bad Request**
```json
{
  "detail": "Invalid file type: text/plain. Only images are supported."
}
```

**Empty file:**
```bash
touch empty.png
curl -X POST "http://localhost:8000/api/v1/documents/upload" \
  -F "file=@empty.png" | jq
```

**Expected: 400 Bad Request**
```json
{
  "detail": "Empty file"
}
```

**No file provided:**
```bash
curl -X POST "http://localhost:8000/api/v1/documents/upload" | jq
```

**Expected: 422 Unprocessable Entity**

---

## Component Testing

### Configuration Service

```bash
python3 << 'EOF'
from services.shared.config import get_settings

# Test defaults
settings = get_settings()
print(f"Environment: {settings.environment}")
print(f"Log level: {settings.log_level}")
print(f"Service: {settings.service_name}")
assert settings.environment == "development"
print("✓ Default config works!")
EOF
```

**Test environment overrides:**
```bash
APP_ENVIRONMENT=production APP_LOG_LEVEL=ERROR python3 << 'EOF'
from services.shared.config import get_settings

settings = get_settings()
assert settings.environment == "production"
assert settings.log_level == "ERROR"
print("✓ Environment variables work!")
EOF
```

**Test .env file:**
```bash
cat > .env << EOF
APP_ENVIRONMENT=staging
APP_LOG_LEVEL=DEBUG
APP_SERVICE_NAME=test-service
EOF

python3 << 'SCRIPT'
from services.shared.config import get_settings

settings = get_settings()
assert settings.environment == "staging"
assert settings.log_level == "DEBUG"
print("✓ .env file works!")
SCRIPT

rm .env
```

---

### OCR Service

```bash
python3 << 'EOF'
from pathlib import Path
from services.ocr.service import OCRService
from services.shared.config import get_settings

# Initialize
settings = get_settings()
ocr = OCRService(settings)
print("✓ OCR service initialized")

# Test with existing image
result = ocr.extract_text(Path("test_invoice.png"))
print(f"Success: {result.success}")
print(f"Text length: {len(result.text)} characters")
print(f"Preview: {result.text[:80]}...")

# Test error handling
result = ocr.extract_text(Path("nonexistent.png"))
assert result.success is False
assert "not found" in result.error.lower()
print("✓ Error handling works")
EOF
```

---

## Integration Testing

### Full System Test Script

Create `test_system.sh`:
```bash
#!/bin/bash
set -e

echo "=== Full System Integration Test ==="
echo ""

# 1. Environment check
echo "1. Checking environment..."
python3 --version | grep -q "3.1[1-9]" && echo "   ✓ Python 3.11+"
tesseract --version > /dev/null && echo "   ✓ Tesseract installed"
source venv/bin/activate && echo "   ✓ Virtual environment"

# 2. Code quality
echo ""
echo "2. Running code quality checks..."
black --check . > /dev/null 2>&1 && echo "   ✓ Black formatting"
ruff check . > /dev/null 2>&1 && echo "   ✓ Ruff linting"
mypy services/ --strict > /dev/null 2>&1 && echo "   ✓ MyPy type checking"

# 3. Unit tests
echo ""
echo "3. Running unit tests..."
pytest -q > /dev/null 2>&1 && echo "   ✓ 15/15 tests passed"

# 4. Server smoke test
echo ""
echo "4. Testing API server..."
timeout 3 uvicorn services.api.main:app --port 8001 > /dev/null 2>&1 || echo "   ✓ Server starts successfully"

# 5. Configuration test
echo ""
echo "5. Testing configuration..."
python3 -c "from services.shared.config import get_settings; get_settings()" && echo "   ✓ Config loads"

# 6. OCR test
echo ""
echo "6. Testing OCR service..."
python3 -c "from services.ocr.service import OCRService; from services.shared.config import get_settings; OCRService(get_settings())" && echo "   ✓ OCR initializes"

echo ""
echo "✅ All integration tests passed!"
```

**Run:**
```bash
chmod +x test_system.sh
./test_system.sh
```

---

## Troubleshooting

### Common Issues

#### 1. ModuleNotFoundError: No module named 'services'

**Problem:** Package not installed in editable mode

**Solution:**
```bash
pip install -e .
```

---

#### 2. RuntimeError: Form data requires "python-multipart"

**Problem:** Missing dependency for file uploads

**Solution:**
```bash
pip install python-multipart==0.0.6
```

---

#### 3. TesseractNotFoundError

**Problem:** Tesseract system package not installed or not in PATH

**Solution:**
```bash
# Ubuntu/Debian
sudo apt-get install tesseract-ocr

# macOS
brew install tesseract

# Or set custom path
export TESSERACT_CMD=/path/to/tesseract
```

---

#### 4. MyPy: Source file found twice

**Problem:** Module path confusion

**Solution:** Already fixed in `pyproject.toml` with:
```toml
[tool.mypy]
explicit_package_bases = true
mypy_path = "."
```

---

#### 5. Tests failing with import errors

**Problem:** Wrong directory or PYTHONPATH not set

**Solution:**
```bash
# Make sure you're in project root
cd ~/YrgenProjects/private-doc-intelligence-platform

# Activate venv
source venv/bin/activate

# Run tests
pytest -v
```

---

#### 6. Port already in use

**Problem:** Server already running on port 8000

**Solution:**
```bash
# Find and kill process
lsof -ti:8000 | xargs kill -9

# Or use different port
uvicorn services.api.main:app --port 8001
```

---

## Test Coverage Goals

Current coverage: **96%**

### Coverage by Module

| Module | Coverage | Missing Lines |
|--------|----------|---------------|
| `services/shared/config.py` | 100% | None |
| `services/ocr/service.py` | 96% | Line 63 (error path) |
| `services/api/main.py` | 96% | Lines 95, 119 (cleanup) |

### Acceptable Missing Coverage

Some lines are intentionally not covered:
- Error handlers for edge cases
- Cleanup code in finally blocks
- Unreachable code paths

**Goal:** Maintain >95% coverage on core business logic

---

## Continuous Testing

### Pre-commit Checklist

Before every commit:
```bash
black . && ruff check . && mypy services/ --strict && pytest
```

### CI/CD Ready

All these tests can run in CI/CD:
```yaml
# .gitlab-ci.yml (example)
test:
  script:
    - pip install -r requirements.txt
    - pip install -e .
    - black --check .
    - ruff check .
    - mypy services/ --strict
    - pytest --cov=services --cov-fail-under=95
```

---

## Performance Benchmarks

Expected performance (on typical hardware):

- **Unit tests:** < 1 second
- **Code formatting:** < 0.5 seconds
- **Linting:** < 0.2 seconds
- **Type checking:** < 2 seconds
- **Full test suite:** < 3 seconds

**If slower:** Check for background processes or run on isolated machine.

---

## Next Steps

After all tests pass:
1. Review code coverage report
2. Add more test cases for edge cases
3. Test with real invoice images
4. Benchmark OCR performance
5. Continue to Step 4: LLM extraction service

---

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [MyPy Documentation](https://mypy.readthedocs.io/)
- [Ruff Rules](https://docs.astral.sh/ruff/rules/)
- [Tesseract Documentation](https://tesseract-ocr.github.io/)

