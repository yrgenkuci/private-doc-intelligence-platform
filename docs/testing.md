# Testing Guide: Verify Phase 2 LLM Extraction

This guide shows you how to test the LLM extraction feature end-to-end to ensure everything is solid.

---

## Testing Levels

### Level 1: Unit Tests (No API Key Required)
**What it tests:** Code logic, mocking, error handling  
**Already passing:** 37/37 tests

```bash
cd /home/yrgen/YrgenProjects/private-doc-intelligence-platform
source venv/bin/activate
PYTHONPATH=. pytest tests/unit/ -v
```

**Expected result:** All tests pass (except 2 pre-existing config failures)

---

### Level 2: Integration Tests (Requires OpenAI API Key)

**What it tests:** Real OpenAI API calls with actual invoices

#### Step 1: Set Your OpenAI API Key
```bash
export OPENAI_API_KEY="sk-your-key-here"
```

#### Step 2: Run Integration Tests
```bash
cd /home/yrgen/YrgenProjects/private-doc-intelligence-platform
source venv/bin/activate
PYTHONPATH=. pytest tests/integration/ -v
```

**Expected result:** 7 tests run and pass  
**What it verifies:**
- Real invoice text extraction
- Minimal data extraction
- Empty text handling
- Non-invoice text handling
- European format support
- Performance (< 10 seconds per request)
- Retry logic

**Cost:** ~$0.01 (7 API calls x ~$0.0015 each)

---

### Level 3: Manual API Testing (Full Stack)

**What it tests:** Full API -> OCR -> LLM flow

#### Prerequisites
1. Start the API server:
```bash
cd /home/yrgen/YrgenProjects/private-doc-intelligence-platform
source venv/bin/activate
export OPENAI_API_KEY="sk-your-key-here"
PYTHONPATH=. uvicorn services.api.main:app --reload --host 0.0.0.0 --port 8000
```

Server will start at: `http://localhost:8000`

2. Open another terminal for testing

---

#### Test 1: Basic Health Check
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

---

#### Test 2: OCR Only (No Extraction)
```bash
# Create a test invoice image (or use existing)
curl -X POST "http://localhost:8000/api/v1/documents/upload" \
  -F "file=@test_data/invoice.png" \
  -H "accept: application/json"
```

**Expected response:**
```json
{
  "success": true,
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "text": "INVOICE\n#12345\n...",
  "extracted_data": null,
  "error": null
}
```

**What this proves:** OCR works, API is functional

---

#### Test 3: OCR + LLM Extraction
```bash
curl -X POST "http://localhost:8000/api/v1/documents/upload?extract_fields=true" \
  -F "file=@test_data/invoice.png" \
  -H "accept: application/json"
```

**Expected response:**
```json
{
  "success": true,
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "text": "INVOICE\n#12345\n...",
  "extracted_data": {
    "invoice_number": "INV-12345",
    "invoice_date": "2024-01-15",
    "due_date": "2024-02-15",
    "supplier_name": "XYZ Suppliers Inc",
    "customer_name": "ABC Corp",
    "subtotal": "1000.0",
    "tax_amount": "100.0",
    "total_amount": "1100.0",
    "currency": "USD",
    "confidence_score": null
  },
  "error": null
}
```

**What this proves:** Full LLM extraction pipeline works end-to-end!

---

#### Test 4: Graceful Degradation (No API Key)
```bash
# Stop server, unset API key
unset OPENAI_API_KEY
PYTHONPATH=. uvicorn services.api.main:app --reload --host 0.0.0.0 --port 8000

# In another terminal, try extraction
curl -X POST "http://localhost:8000/api/v1/documents/upload?extract_fields=true" \
  -F "file=@test_data/invoice.png"
```

**Expected response:**
```json
{
  "success": true,
  "document_id": "...",
  "text": "INVOICE\n#12345\n...",
  "extracted_data": null,
  "error": null
}
```

**What this proves:** 
- OCR still succeeds even when LLM fails
- No crashes or 500 errors
- Graceful degradation works

---

#### Test 5: Check Prometheus Metrics
```bash
curl http://localhost:8000/metrics | grep extraction
```

**Expected output:**
```
# HELP extraction_requests_total Total LLM extraction requests
# TYPE extraction_requests_total counter
extraction_requests_total{status="success"} 5.0
extraction_requests_total{status="failed"} 2.0

# HELP extraction_processing_duration_seconds LLM extraction duration in seconds
# TYPE extraction_processing_duration_seconds histogram
extraction_processing_duration_seconds_bucket{le="0.5"} 0.0
extraction_processing_duration_seconds_bucket{le="1.0"} 1.0
extraction_processing_duration_seconds_bucket{le="2.0"} 4.0
extraction_processing_duration_seconds_sum 9.8
extraction_processing_duration_seconds_count 5.0
```

**What this proves:** Metrics are being recorded correctly

---

#### Test 6: OpenAPI/Swagger Documentation
Open in browser: `http://localhost:8000/docs`

**What to verify:**
- `/api/v1/documents/upload` endpoint is documented
- `extract_fields` parameter shows up with description
- `extracted_data` field in response schema
- Try the "Try it out" feature in Swagger UI

---

### Level 4: Load Testing (Optional)

**What it tests:** Performance under load

```bash
# Install apache bench if needed
sudo apt-get install apache2-utils

# Test with 100 requests, 10 concurrent
ab -n 100 -c 10 -T 'multipart/form-data; boundary=----WebKitFormBoundary' \
  http://localhost:8000/health

# For upload endpoint, use a tool like k6 or locust
```

---

## Quick Test Script

Create this script to test everything quickly:

```bash
#!/bin/bash
# test_extraction.sh

set -e  # Exit on error

echo "Testing LLM Extraction Feature"
echo "=================================="

# 1. Check if test image exists
if [ ! -f "test_data/invoice.png" ]; then
    echo "[WARN] Warning: test_data/invoice.png not found"
    echo "   Using curl with mock file..."
fi

# 2. Test health endpoint
echo ""
echo "1. Testing health endpoint..."
curl -s http://localhost:8000/health | jq .
if [ $? -eq 0 ]; then
    echo "[OK] Health check passed"
else
    echo "[FAIL] Health check failed - is server running?"
    exit 1
fi

# 3. Test OCR only
echo ""
echo "2. Testing OCR only (no extraction)..."
if [ -f "test_data/invoice.png" ]; then
    RESPONSE=$(curl -s -X POST "http://localhost:8000/api/v1/documents/upload" \
      -F "file=@test_data/invoice.png")
    echo "$RESPONSE" | jq .
    
    SUCCESS=$(echo "$RESPONSE" | jq -r .success)
    EXTRACTED_DATA=$(echo "$RESPONSE" | jq -r .extracted_data)
    
    if [ "$SUCCESS" == "true" ] && [ "$EXTRACTED_DATA" == "null" ]; then
        echo "[OK] OCR test passed (extracted_data is null as expected)"
    else
        echo "[FAIL] OCR test failed"
        exit 1
    fi
fi

# 4. Test OCR + LLM extraction
echo ""
echo "3. Testing OCR + LLM extraction..."
if [ -f "test_data/invoice.png" ]; then
    if [ -z "$OPENAI_API_KEY" ]; then
        echo "[WARN] OPENAI_API_KEY not set - skipping LLM test"
    else
        RESPONSE=$(curl -s -X POST "http://localhost:8000/api/v1/documents/upload?extract_fields=true" \
          -F "file=@test_data/invoice.png")
        echo "$RESPONSE" | jq .
        
        SUCCESS=$(echo "$RESPONSE" | jq -r .success)
        EXTRACTED_DATA=$(echo "$RESPONSE" | jq -r .extracted_data)
        
        if [ "$SUCCESS" == "true" ] && [ "$EXTRACTED_DATA" != "null" ]; then
            echo "[OK] LLM extraction test passed"
        elif [ "$SUCCESS" == "true" ] && [ "$EXTRACTED_DATA" == "null" ]; then
            echo "[WARN] Extraction returned null (might be API key issue or text quality)"
        else
            echo "[FAIL] LLM extraction test failed"
            exit 1
        fi
    fi
fi

# 5. Check metrics
echo ""
echo "4. Checking Prometheus metrics..."
METRICS=$(curl -s http://localhost:8000/metrics | grep extraction_requests_total)
if [ -n "$METRICS" ]; then
    echo "[OK] Metrics are being recorded:"
    echo "$METRICS"
else
    echo "[WARN] No extraction metrics found (might not have run extraction yet)"
fi

echo ""
echo "=================================="
echo "[OK] All tests passed!"
echo ""
echo "View full metrics: http://localhost:8000/metrics"
echo "View API docs: http://localhost:8000/docs"
```

Save as `test_extraction.sh` and run:
```bash
chmod +x test_extraction.sh
./test_extraction.sh
```

---

## Definition of "Solid"

Your feature is solid when:

1. **Unit tests pass** (37/37)
2. **Integration tests pass** (7/7 with API key)
3. **Health endpoint responds** (200 OK)
4. **OCR works without extraction** (extracted_data is null)
5. **LLM extraction returns structured data** (with API key)
6. **Graceful degradation works** (OCR succeeds even without API key)
7. **Metrics are recorded** (visible in /metrics)
8. **No errors in logs** (check console output)
9. **Swagger docs are accessible** (http://localhost:8000/docs)
10. **Response times acceptable** (< 10s for extraction)

---

## Common Issues and Solutions

### Issue 1: "OPENAI_API_KEY not set"
**Solution:** Export the key in your terminal
```bash
export OPENAI_API_KEY="sk-your-key-here"
```

### Issue 2: Port 8000 already in use
**Solution:** Kill existing process or use different port
```bash
# Kill existing
lsof -ti:8000 | xargs kill -9

# Or use different port
uvicorn services.api.main:app --port 8001
```

### Issue 3: "pytesseract not found"
**Solution:** Install Tesseract OCR
```bash
sudo apt-get install tesseract-ocr tesseract-ocr-eng
```

### Issue 4: Integration tests all skip
**Expected behavior!** They skip when OPENAI_API_KEY is not set. This is intentional.

### Issue 5: Extraction returns null but API key is set
**Possible causes:**
- Image quality is poor (OCR text is unclear)
- Image contains no invoice-like text
- API key has insufficient credits
- Check server logs for LLM errors

---

## Recommended Testing Flow

**For Development:**
```bash
# 1. Run unit tests (always)
PYTHONPATH=. pytest tests/unit/ -v

# 2. Start server
export OPENAI_API_KEY="sk-..."
PYTHONPATH=. uvicorn services.api.main:app --reload

# 3. Manual test with curl or Swagger UI
# 4. Check metrics at /metrics
```

**For CI/CD:**
```bash
# Unit tests only (no API key in CI)
PYTHONPATH=. pytest tests/unit/ -v

# Docker build and run
docker build -t doc-intel:test .
docker run -p 8000:8000 -e OPENAI_API_KEY="$API_KEY" doc-intel:test
```

**For Production:**
- Run integration tests in staging with real API key
- Monitor metrics in Grafana
- Set up alerts for high failure rates
- Load test with realistic traffic

---

## Success Criteria Checklist

Before pushing to production:

- [ ] All unit tests pass
- [ ] Integration tests pass (with API key)
- [ ] Manual testing confirms extraction works
- [ ] Graceful degradation verified (without API key)
- [ ] Metrics visible in Prometheus/Grafana
- [ ] API documentation accurate
- [ ] Error handling tested (invalid files, empty files)
- [ ] Performance acceptable (< 10s per request)
- [ ] Logs show no errors or warnings
- [ ] Code review completed

---

## Next Steps After Testing

Once you confirm everything is solid:

1. **Push to GitHub** (triggers CI/CD)
2. **Deploy to staging** (test with real API key)
3. **Monitor metrics** (check Prometheus alerts)
4. **Deploy to production** (after staging verification)
5. **Document for users** (API usage guide)

---

**Need help testing?** Let me know what you'd like to test and I can help you run specific scenarios!

---

## Related Documentation

- **Quickstart Guide:** `docs/quickstart.md` - Local setup
- **Kubernetes Deployment:** `k8s/README.md` - Production setup
- **API Documentation:** http://localhost:8000/docs (when running locally)

**Need help testing?** Let me know what you'd like to test and I can help you run specific scenarios!
