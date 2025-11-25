# Complete Testing Guide

Step-by-step guide to test your Document Intelligence Platform locally.

## Prerequisites

Before testing, ensure:
- - Docker is running: `docker ps`
- - Services are up: `docker compose ps`
- - `.env` file exists with your OpenAI API key

---

## Quick Test (Automated)

Run the automated test script:

```bash
cd /home/yrgen/YrgenProjects/private-doc-intelligence-platform
./scripts/test-local.sh
```

**Expected output:**
```
- API Service (8000) is running
Test 1: API Health... PASS
Test 2: Metrics Endpoint... PASS
Test 3: API Documentation... PASS
```

---

## Manual Testing (Step-by-Step)

### 1. Test API Health

```bash
curl http://localhost:8000/health
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

### 2. Test Prometheus Metrics

```bash
curl http://localhost:8000/metrics | head -20
```

**Expected:** Prometheus metrics output with counters and histograms

---

### 3. View Interactive API Documentation

Open in your browser:
```bash
firefox http://localhost:8000/docs
# Or
google-chrome http://localhost:8000/docs
```

You'll see **Swagger UI** with all endpoints documented.

---

### 4. Create a Test Invoice Image

Let's create a simple test invoice:

```bash
cd /home/yrgen/YrgenProjects/private-doc-intelligence-platform
mkdir -p test_data

# Create a text file with invoice content
cat > test_data/test_invoice.txt << 'EOF'
INVOICE

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
Total: $1,650.00

Thank you for your business!
EOF

# Convert text to image using ImageMagick
# If you don't have it: sudo apt-get install imagemagick
convert -size 800x1000 \
  -background white \
  -fill black \
  -pointsize 16 \
  -gravity northwest \
  label:@test_data/test_invoice.txt \
  test_data/test_invoice.png

echo "- Test invoice created: test_data/test_invoice.png"
```

**Alternative (if you don't have ImageMagick):**

Create a simple invoice using Python:

```bash
cd /home/yrgen/YrgenProjects/private-doc-intelligence-platform
source venv/bin/activate

python3 << 'PYTHON'
from PIL import Image, ImageDraw, ImageFont
import os

# Create directory
os.makedirs('test_data', exist_ok=True)

# Create image
img = Image.new('RGB', (800, 1000), color='white')
draw = ImageDraw.Draw(img)

# Invoice text
text = """
INVOICE

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
Total: $1,650.00
"""

# Draw text
draw.text((50, 50), text, fill='black')

# Save
img.save('test_data/test_invoice.png')
print("- Test invoice created: test_data/test_invoice.png")
PYTHON
```

---

### 5. Test Document Upload (OCR Only)

Upload the invoice and extract text with OCR (no LLM):

```bash
curl -X POST http://localhost:8000/upload \
  -F "file=@test_data/test_invoice.png" \
  -F "extract_fields=false" \
  | jq .
```

**Expected response:**
```json
{
  "success": true,
  "document_id": "some-uuid",
  "text": "INVOICE\n\nInvoice Number: INV-2024-001\n..."
}
```

**What this tests:**
- - File upload endpoint
- - OCR functionality (Tesseract)
- - Text extraction

---

### 6. Test LLM Extraction (Full Pipeline)

Upload with LLM extraction enabled:

```bash
curl -X POST http://localhost:8000/upload \
  -F "file=@test_data/test_invoice.png" \
  -F "extract_fields=true" \
  | jq .
```

**Expected response:**
```json
{
  "success": true,
  "document_id": "some-uuid",
  "text": "INVOICE\n\nInvoice Number: INV-2024-001\n...",
  "extracted_data": {
    "invoice_number": "INV-2024-001",
    "invoice_date": "2024-11-25",
    "due_date": "2024-12-25",
    "supplier_name": "Tech Services LLC",
    "customer_name": "Acme Corporation",
    "subtotal": 1500.00,
    "tax_amount": 150.00,
    "total_amount": 1650.00,
    "currency": "USD"
  }
}
```

**What this tests:**
- - File upload
- - OCR extraction
- - LLM structured data extraction
- - OpenAI API integration
- - Full end-to-end pipeline

---

### 7. Test with Real Invoice (Optional)

If you have a real invoice image:

```bash
curl -X POST http://localhost:8000/upload \
  -F "file=@/path/to/your/real_invoice.pdf" \
  -F "extract_fields=true" \
  | jq .
```

**Supported formats:**
- PNG, JPG, JPEG
- PDF (if pdf2image is installed)

---

### 8. Monitor Metrics After Tests

Check that metrics are being recorded:

```bash
curl -s http://localhost:8000/metrics | grep -E "(documents_uploaded|ocr_requests|http_requests)"
```

**Expected output:**
```
documents_uploaded_total{status="success"} 2.0
ocr_requests_total{status="success"} 2.0
http_requests_total{method="POST",endpoint="/upload",status="200"} 2.0
```

---

### 9. View Logs

Check application logs:

```bash
# View live logs
docker compose logs -f

# View last 50 lines
docker compose logs --tail 50

# View only API logs
docker compose logs api
```

---

### 10. Test Error Handling

#### Test with invalid file:

```bash
echo "not an image" > test_data/invalid.txt
curl -X POST http://localhost:8000/upload \
  -F "file=@test_data/invalid.txt" \
  -F "extract_fields=false"
```

**Expected:** Error response with appropriate status code

#### Test without file:

```bash
curl -X POST http://localhost:8000/upload
```

**Expected:** 422 Unprocessable Entity

---

## Python Unit Tests

Run the full test suite:

```bash
cd /home/yrgen/YrgenProjects/private-doc-intelligence-platform
source venv/bin/activate

# Run all tests
PYTHONPATH=. pytest tests/ -v

# Run with coverage
PYTHONPATH=. pytest tests/ -v --cov=services --cov=pipeline

# Run specific test file
PYTHONPATH=. pytest tests/unit/test_api.py -v

# Run specific test
PYTHONPATH=. pytest tests/unit/test_api.py::test_health_endpoint -v
```

**Expected:** All tests pass

---

## Interactive Testing via Swagger UI

1. **Open Swagger UI:**
   ```bash
   firefox http://localhost:8000/docs
   ```

2. **Try the `/upload` endpoint:**
   - Click on `POST /upload`
   - Click "Try it out"
   - Upload your test image
   - Set `extract_fields` to `true` or `false`
   - Click "Execute"
   - View the response

3. **Try other endpoints:**
   - `GET /health` - Check system health
   - `GET /metrics` - View Prometheus metrics

---

## Performance Testing (Optional)

Test with multiple concurrent requests:

```bash
# Install hey (HTTP load testing tool)
# sudo apt-get install hey
# Or: go install github.com/rakyll/hey@latest

# Test with 10 concurrent requests
hey -n 10 -c 2 -m POST \
  -T "multipart/form-data; boundary=----WebKitFormBoundary" \
  -D test_data/test_invoice.png \
  http://localhost:8000/upload
```

---

## Evaluation Harness

Test extraction accuracy with the gold dataset:

```bash
cd /home/yrgen/YrgenProjects/private-doc-intelligence-platform
source venv/bin/activate

# Run evaluation
PYTHONPATH=. python -m pipeline.eval.eval
```

**Expected output:**
```json
{
  "overall_precision": 0.95,
  "overall_recall": 0.92,
  "overall_f1": 0.93,
  "field_metrics": {
    "invoice_number": {"precision": 1.0, "recall": 1.0, "f1": 1.0},
    "total_amount": {"precision": 1.0, "recall": 0.9, "f1": 0.95}
  }
}
```

---

## Troubleshooting

### Issue: "Connection refused" on port 8000

**Solution:**
```bash
# Check if container is running
docker compose ps

# If not running, start it
docker compose up -d

# Check logs for errors
docker compose logs api
```

### Issue: "OPENAI_API_KEY not set"

**Solution:**
```bash
# Check .env file exists
cat .env

# Should contain: OPENAI_API_KEY=sk-...
# If not, add your key
echo "OPENAI_API_KEY=sk-your-key-here" >> .env

# Restart services
docker compose down
docker compose up -d
```

### Issue: OCR returns empty text

**Solution:**
- Check image quality (should be clear, readable)
- Try with a different image
- Ensure Tesseract is installed: `docker compose exec api tesseract --version`

### Issue: LLM extraction fails

**Solution:**
- Verify OpenAI API key is valid
- Check you have API credits: https://platform.openai.com/usage
- Check logs: `docker compose logs api | grep -i error`

---

## Success Checklist

After running tests, you should have:

- - API responding on port 8000
- - Health check passing
- - Metrics being collected
- - OCR extracting text from images
- - LLM extracting structured data
- - All unit tests passing
- - No errors in logs

---

## What to Test Next

1. **Upload different invoice formats** (PDF, different layouts)
2. **Test with poor quality images** (see how OCR handles it)
3. **Test concurrent uploads** (performance testing)
4. **Deploy to Kubernetes** (see k8s/README.md)
5. **Set up Prometheus + Grafana** (see docs/step-11-grafana.md)

---

## Quick Reference

```bash
# Start services
docker compose up -d

# Run automated tests
./scripts/test-local.sh

# View logs
docker compose logs -f

# Stop services
docker compose down

# Restart services
docker compose restart

# Upload test invoice
curl -X POST http://localhost:8000/upload \
  -F "file=@test_data/test_invoice.png" \
  -F "extract_fields=true" | jq .
```

---

**Happy Testing!**

For more details, see:
- [SETUP.md](SETUP.md) - Initial setup
- [docs/testing-guide.md](docs/testing-guide.md) - Pytest patterns
- [README.md](README.md) - Project overview

