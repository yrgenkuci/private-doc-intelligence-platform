# Extension Roadmap: MVP to Portfolio-Compliant Platform

**Current Status:** Basic OCR working, Kubernetes-ready  
**Target:** Full portfolio claims validated  
**Timeline:** 4-6 weeks of focused development

---

## Phase 1: Wire Existing Components (Week 1)
**Effort:** 20-30 hours  
**Priority:** HIGH - Makes current code actually work together

### 1.1 Connect LLM Extraction to API
**Current:** Extraction service exists but not used in upload endpoint  
**Action:** Modify `services/api/main.py` to call extraction service

```python
# Add to upload_document function after OCR:
if extract_fields:  # New optional parameter
    extraction_result = extraction_service.extract_invoice_fields(result.text)
    if extraction_result.success:
        return UploadResponse(
            success=True,
            document_id=doc_id,
            text=result.text,
            extracted_data=extraction_result.invoice_data  # Add to response model
        )
```

**Evidence Needed:** Working end-to-end test showing structured JSON output

### 1.2 Run Evaluation Harness
**Current:** Code exists, 3 gold samples, never run in production  
**Action:** 
```bash
OPENAI_API_KEY=sk-... python -m pipeline.eval.eval
```

**Result:** Get actual precision/recall/F1 metrics (likely 85-95% range)

**Update Portfolio:** Replace "92-96%" with actual measured results

---

## Phase 2: Add Self-Hosted LLM (Week 2-3)
**Effort:** 40-50 hours  
**Priority:** HIGH - Fixes "self-hosted" claim contradiction

### 2.1 Deploy LayoutLMv3 or Donut
**Why:** Industry-standard models for document understanding  
**Evidence:** 
- LayoutLMv3: https://huggingface.co/microsoft/layoutlmv3-base
- Donut: https://huggingface.co/naver-clova-ix/donut-base

**Implementation:**
```python
# services/extraction/local_model.py
from transformers import LayoutLMv3Processor, LayoutLMv3ForTokenClassification

class LocalExtractionService:
    def __init__(self):
        self.processor = LayoutLMv3Processor.from_pretrained(
            "microsoft/layoutlmv3-base-finetuned-invoice"
        )
        self.model = LayoutLMv3ForTokenClassification.from_pretrained(
            "microsoft/layoutlmv3-base-finetuned-invoice"
        )
    
    def extract_fields(self, image_path: Path, ocr_text: str) -> InvoiceData:
        # Use LayoutLM with image + text for structured extraction
        # Returns same InvoiceData schema
        pass
```

**Update API:** Add environment flag to switch between OpenAI and local model

**Docker Update:** Add GPU support to Dockerfile
```dockerfile
FROM nvidia/cuda:12.1.0-base-ubuntu22.04
# Install PyTorch with CUDA support
RUN pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

---

## Phase 3: Add GPU Support to Kubernetes (Week 3-4)
**Effort:** 20-30 hours  
**Priority:** MEDIUM - Validates portfolio GPU claims

### 3.1 Update Kubernetes Manifests
**File:** `k8s/base/extraction-deployment.yaml` (new file)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: extraction-deployment
  namespace: doc-intelligence
spec:
  replicas: 2
  template:
    spec:
      containers:
        - name: extraction
          image: doc-intel-extraction:latest
          resources:
            limits:
              nvidia.com/gpu: 1  # Request 1 GPU
            requests:
              memory: "4Gi"
              cpu: "2000m"
          env:
            - name: MODEL_TYPE
              value: "layoutlm"  # or "donut"
```

**Evidence:**
- NVIDIA Device Plugin: https://github.com/NVIDIA/k8s-device-plugin
- Kubernetes GPU scheduling: https://kubernetes.io/docs/tasks/manage-gpus/scheduling-gpus/

### 3.2 Cost Controls
**Add to extraction service:**
```python
# Track GPU usage per document
@metrics_decorator
def extract_with_gpu(self, image_path: Path):
    gpu_start = time.time()
    result = self.model.extract(image_path)
    gpu_duration = time.time() - gpu_start
    
    # Log cost (NVIDIA T4: ~$0.35/hour)
    cost_per_second = 0.35 / 3600
    document_cost = gpu_duration * cost_per_second
    
    metrics.gpu_cost_per_document.observe(document_cost)
    return result
```

**Update Portfolio:** You can now claim "GPU support with cost tracking"

---

## Phase 4: Add MinIO Storage (Week 4)
**Effort:** 15-20 hours  
**Priority:** LOW - Nice to have, validates architecture claim

### 4.1 Deploy MinIO to Kubernetes
**File:** `k8s/base/minio-deployment.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: minio
  namespace: doc-intelligence
spec:
  template:
    spec:
      containers:
        - name: minio
          image: minio/minio:latest
          command: ["minio", "server", "/data"]
          ports:
            - containerPort: 9000
          volumeMounts:
            - name: storage
              mountPath: /data
      volumes:
        - name: storage
          persistentVolumeClaim:
            claimName: minio-pvc
```

### 4.2 Update API to Use S3
**Modify:** `services/api/main.py`

```python
from minio import Minio

# Store uploaded documents in MinIO
s3_client = Minio(
    "minio-service:9000",
    access_key=os.getenv("MINIO_ACCESS_KEY"),
    secret_key=os.getenv("MINIO_SECRET_KEY"),
    secure=False
)

# After processing, store in bucket
s3_client.put_object(
    "documents",
    f"{doc_id}/{file.filename}",
    content,
    len(content)
)
```

**Evidence:** MinIO documentation: https://min.io/docs/minio/kubernetes/upstream/

---

## Phase 5: Add PaddleOCR (Week 5)
**Effort:** 15-20 hours  
**Priority:** LOW - Multi-engine support

### 5.1 Install PaddleOCR
```bash
pip install paddlepaddle paddleocr
```

### 5.2 Create Multi-Engine OCR Service
**File:** `services/ocr/multi_engine.py`

```python
from paddleocr import PaddleOCR
import pytesseract

class MultiEngineOCR:
    def __init__(self):
        self.tesseract = pytesseract
        self.paddle = PaddleOCR(use_angle_cls=True, lang='en')
    
    def extract_with_ensemble(self, image_path: Path) -> OCRResult:
        # Run both engines
        tesseract_result = self.tesseract.image_to_string(image_path)
        paddle_result = self.paddle.ocr(str(image_path), cls=True)
        
        # Combine results (majority voting or confidence-based)
        final_text = self._merge_results(tesseract_result, paddle_result)
        return OCRResult(text=final_text, success=True)
```

**Evidence:** PaddleOCR GitHub: https://github.com/PaddlePaddle/PaddleOCR

---

## Phase 6: Benchmarking & Metrics (Week 6)
**Effort:** 20-30 hours  
**Priority:** HIGH - Validates all performance claims

### 6.1 Expand Gold Dataset
**Current:** 3 samples  
**Target:** 50-100 samples

**Action:**
1. Create synthetic invoices (Python script to generate variations)
2. Run through pipeline
3. Manually verify outputs
4. Store in `data/gold/invoices.json`

### 6.2 Performance Benchmarking
**Create:** `scripts/benchmark.py`

```python
import time
import statistics

def benchmark_throughput():
    """Test documents per second."""
    documents = load_test_documents(100)
    start = time.time()
    
    for doc in documents:
        process_document(doc)
    
    duration = time.time() - start
    throughput = len(documents) / duration
    
    print(f"Throughput: {throughput:.2f} docs/second")
    print(f"Daily capacity: {int(throughput * 86400)} docs/day")
    
def benchmark_latency():
    """Test per-document processing time."""
    latencies = []
    for i in range(100):
        start = time.time()
        process_document(test_doc)
        latencies.append(time.time() - start)
    
    print(f"P50 latency: {statistics.median(latencies):.2f}s")
    print(f"P95 latency: {statistics.quantiles(latencies, n=20)[18]:.2f}s")
```

**Run benchmark:**
```bash
python scripts/benchmark.py
```

**Update Portfolio:** Replace "3-8 seconds" with actual P50/P95 measurements

### 6.3 Accuracy Testing
**Expand gold dataset to 100 samples, run eval:**

```bash
OPENAI_API_KEY=sk-... python -m pipeline.eval.eval
```

**Expected output:**
```
Total Samples: 100
Macro F1 Score: 89.3%

Per-Field Metrics:
invoice_number    95.2%    94.8%    95.0%
total_amount      92.1%    90.5%    91.3%
invoice_date      88.3%    87.1%    87.7%
```

**Update Portfolio:** Use actual measured accuracy (likely 87-93% range, not 92-96%)

---

## Phase 7: Helm Charts (Optional)
**Effort:** 10-15 hours  
**Priority:** LOW - Kustomize is fine, but portfolio claims Helm

### 7.1 Convert Kustomize to Helm
**Create:** `helm/doc-intelligence/`

```
helm/
  doc-intelligence/
    Chart.yaml
    values.yaml
    templates/
      api-deployment.yaml
      extraction-deployment.yaml
      minio-deployment.yaml
      ...
```

**Or:** Update portfolio to say "Kustomize" instead of "Helm" (both are valid)

---

## Evidence Checklist

After completing phases, you'll have:

| Claim | Evidence | Location |
|-------|----------|----------|
| GPU support | K8s manifest with `nvidia.com/gpu: 1` | `k8s/base/extraction-deployment.yaml` |
| Self-hosted LLM | LayoutLM/Donut implementation | `services/extraction/local_model.py` |
| MinIO storage | Deployment + S3 integration | `k8s/base/minio-deployment.yaml` |
| PaddleOCR | Multi-engine OCR code | `services/ocr/multi_engine.py` |
| 92-96% accuracy | Evaluation report on 100+ docs | `reports/evaluation_YYYYMMDD.json` |
| 3-8 sec latency | Benchmark results | `reports/benchmark_YYYYMMDD.txt` |
| 10k+ docs/day | Load test results | `reports/load_test_YYYYMMDD.txt` |
| Helm charts | Chart.yaml + templates | `helm/doc-intelligence/` |

---

## Prioritized Implementation Order

**Week 1 (Critical):**
1. Wire LLM extraction to API
2. Run evaluation harness
3. Get actual metrics

**Week 2-3 (High Priority):**
4. Add LayoutLM/Donut (self-hosted)
5. GPU support in K8s
6. Expand gold dataset to 50-100 samples

**Week 4-5 (Medium Priority):**
7. Add MinIO
8. Add PaddleOCR
9. Cost tracking

**Week 6 (Validation):**
10. Comprehensive benchmarking
11. Accuracy measurements
12. Performance testing

---

## Estimated Costs

**Development Time:** 120-180 hours (4-6 weeks full-time)

**Infrastructure for Testing:**
- GPU node (NVIDIA T4): ~$0.35/hour × 100 hours = $35
- Storage: ~$10/month
- OpenAI API (initial dev): ~$20-50
- **Total:** ~$100-150 for full implementation

**After Implementation:**
- Operating costs drop to near-zero (self-hosted)
- GPU costs only when processing documents

---

## Legal/Ethical Consideration

**Current Issue:** Your portfolio claims features that don't exist. This is:
- Misrepresentation to potential clients
- Could be considered fraudulent in consulting contracts
- Damages your credibility when discovered

**Solution:** Either:
1. **Implement the features** (this roadmap) - 4-6 weeks
2. **Update portfolio to match reality** (1 day) - Remove false claims

**Recommendation:** Do both:
- Update portfolio NOW to remove unimplemented features
- Follow this roadmap to add them over next 6 weeks
- Update portfolio again as each feature is completed

---

## Bottom Line

**Your current platform is ~40% of what you claim.**

**This roadmap gets you to 95%+ compliance with portfolio claims.**

**Timeline:** 4-6 weeks focused development

**Difficulty:** Intermediate - All features are standard industry practice with good documentation

**Is it feasible?** **YES** - Everything you claimed is:
- Technically achievable
- Industry-standard
- Well-documented
- Has open-source implementations available

**My recommendation:** Start with Week 1 (wire existing components) so you can at least demo structured extraction. Then add GPU + self-hosted LLM to fix the "private deployment" contradiction.

