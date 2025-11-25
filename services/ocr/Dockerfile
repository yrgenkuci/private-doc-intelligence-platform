# OCR service with Tesseract
FROM python:3.12-slim

WORKDIR /app

# Install Tesseract OCR
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY services/ocr/ /app/services/ocr/
COPY services/shared/ /app/services/shared/

# Set environment variables
ENV PYTHONPATH=/app

# Verify Tesseract installation
RUN tesseract --version

# Expose port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8001/health', timeout=2.0)" || exit 1

# Run the OCR service
CMD ["uvicorn", "services.ocr.service:app", "--host", "0.0.0.0", "--port", "8001"]

