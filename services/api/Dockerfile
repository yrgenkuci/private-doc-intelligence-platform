# API service with OCR capabilities
FROM python:3.12-slim

WORKDIR /app

# Install Tesseract OCR (needed for OCR functionality)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY services/api/ /app/services/api/
COPY services/shared/ /app/services/shared/
COPY services/extraction/ /app/services/extraction/
COPY services/ocr/ /app/services/ocr/
COPY pipeline/ /app/pipeline/

# Set environment variables
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health', timeout=2.0)" || exit 1

# Run FastAPI with uvicorn
CMD ["uvicorn", "services.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

