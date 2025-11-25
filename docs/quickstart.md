# Quick Start Guide

Get the platform running locally in 5 minutes.

## Prerequisites

1. **Docker Desktop** - Make sure it's running
   ```bash
   docker --version
   # Should show: Docker version 20.10+
   ```

2. **OpenAI API Key** - Get from https://platform.openai.com/api-keys
   - Sign up for OpenAI account
   - Generate API key (starts with `sk-...`)
   - Keep it handy for step 3

## Step 1: Configure API Key

Create a `.env` file with your OpenAI key:

```bash
cd /home/yrgen/YrgenProjects/private-doc-intelligence-platform

# Copy the example file
cp .env.example .env

# Edit .env and add your key
nano .env
# Or use any text editor:
# gedit .env
# vim .env
```

Your `.env` file should look like this:
```
OPENAI_API_KEY=sk-your-actual-key-here
```

Save and close the file.

## Step 2: Start the Services

```bash
# Make sure you're in the project directory
cd /home/yrgen/YrgenProjects/private-doc-intelligence-platform

# Start everything with Docker Compose
docker-compose up -d

# Wait 10 seconds for services to start
sleep 10
```

## Step 3: Verify It's Running

```bash
# Test the health endpoint
curl http://localhost:8000/health

# Expected output:
# {"status":"healthy","version":"0.1.0","service":"document-intelligence-api"}
```

If you see the JSON response above, **it's working!**

## Step 4: Test with a Document (Optional)

### Create a test invoice image:

```bash
cd /home/yrgen/YrgenProjects/private-doc-intelligence-platform
mkdir -p test_data

# Create a simple text invoice
cat > test_data/invoice.txt << 'EOF'
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
EOF

# Convert to image using ImageMagick (if installed)
convert -size 800x1000 -background white -fill black -pointsize 16 \
  label:@test_data/invoice.txt test_data/invoice.png

# If you don't have ImageMagick, you can use Python:
python3 << 'PYTHON'
from PIL import Image, ImageDraw
import os

os.makedirs('test_data', exist_ok=True)
img = Image.new('RGB', (800, 1000), color='white')
draw = ImageDraw.Draw(img)

text = """INVOICE

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
Total: $1,650.00"""

draw.text((50, 50), text, fill='black')
img.save('test_data/invoice.png')
print("Created test_data/invoice.png")
PYTHON
```

### Test OCR only (extract text):

```bash
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -F "file=@test_data/invoice.png" \
  | python3 -m json.tool

# You'll see the extracted text
```

### Test full pipeline (OCR + LLM extraction):

This will extract structured data (invoice number, amounts, dates, etc.):

```bash
# Note: This will use your OpenAI API key and cost ~$0.001
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -F "file=@test_data/invoice.png" \
  | python3 -m json.tool

# Expected output:
# {
#   "success": true,
#   "document_id": "...",
#   "text": "INVOICE\n\nInvoice Number: INV-2024-001...",
#   "extracted_data": {
#     "invoice_number": "INV-2024-001",
#     "invoice_date": "2024-11-25",
#     "total_amount": 1650.00,
#     "currency": "USD"
#   }
# }
```

## Step 5: View Logs (Optional)

```bash
# See what's happening
docker-compose logs -f

# Press Ctrl+C to stop watching logs
```

## Step 6: Stop Services

When you're done testing:

```bash
docker-compose down
```

## Troubleshooting

### Problem: "Connection refused"
**Solution:** Wait a bit longer, services take 10-20 seconds to start
```bash
docker-compose ps  # Check if containers are running
docker-compose logs api  # Check for errors
```

### Problem: "OPENAI_API_KEY not set"
**Solution:** Check your .env file exists and has the correct format
```bash
cat .env  # Should show: OPENAI_API_KEY=sk-...
```

### Problem: OCR returns empty text
**Solution:** Make sure the image has clear, readable text
```bash
# Check the image was created
ls -lh test_data/invoice.png
```

## Next Steps

Once you've verified it works locally:

1. **Run unit tests** - See [docs/testing.md](docs/testing.md)
2. **Deploy to Kubernetes** - See [k8s/README.md](../k8s/README.md)
3. **Set up monitoring** - See [docs/step-11-grafana.md](docs/step-11-grafana.md)

## Quick Reference

```bash
# Start services
docker-compose up -d

# Check health
curl http://localhost:8000/health

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Run automated tests
./scripts/test-local.sh
```

---

**That's it!** You now have a working document intelligence platform running locally.

For more detailed testing scenarios, see [docs/testing.md](docs/testing.md).

