#!/bin/bash
set -e

echo "🧪 Testing Document Intelligence Platform Locally"
echo "=================================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if services are running
check_service() {
    local url=$1
    local name=$2
    
    if curl -s -f "$url" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ $name is running${NC}"
        return 0
    else
        echo -e "${RED}❌ $name is NOT running${NC}"
        return 1
    fi
}

echo "📋 Step 1: Checking Prerequisites"
echo "-----------------------------------"

# Check Python
if command -v python3 &> /dev/null; then
    echo -e "${GREEN}✅ Python3 installed:${NC} $(python3 --version)"
else
    echo -e "${RED}❌ Python3 not found${NC}"
    exit 1
fi

# Check virtual environment
if [ -d "venv" ]; then
    echo -e "${GREEN}✅ Virtual environment exists${NC}"
else
    echo -e "${YELLOW}⚠️  Virtual environment not found${NC}"
    echo "   Run: python3 -m venv venv"
fi

# Check .env file
if [ -f ".env" ]; then
    echo -e "${GREEN}✅ .env file exists${NC}"
    if grep -q "OPENAI_API_KEY=sk-" .env; then
        echo -e "${GREEN}✅ OPENAI_API_KEY is set${NC}"
    else
        echo -e "${YELLOW}⚠️  OPENAI_API_KEY not set in .env${NC}"
        echo "   Edit .env and add your OpenAI API key"
    fi
else
    echo -e "${RED}❌ .env file not found${NC}"
    echo "   Run: cp .env.example .env"
    exit 1
fi

echo ""
echo "🔍 Step 2: Checking Services"
echo "----------------------------"

API_RUNNING=false

if check_service "http://localhost:8000/health" "API Service (8000)"; then
    API_RUNNING=true
fi

if [ "$API_RUNNING" = false ]; then
    echo ""
    echo -e "${YELLOW}⚠️  API service not running. Start it with:${NC}"
    echo "   docker compose up -d"
    echo "   OR run manually (see LOCAL-TESTING.md)"
    exit 1
fi

echo ""
echo "🧪 Step 3: Running Tests"
echo "------------------------"

# Test 1: API Health
echo -n "Test 1: API Health... "
if curl -s http://localhost:8000/health | grep -q "healthy"; then
    echo -e "${GREEN}PASS${NC}"
else
    echo -e "${RED}FAIL${NC}"
    exit 1
fi

# Test 2: Metrics Endpoint
echo -n "Test 2: Metrics Endpoint... "
if curl -s http://localhost:8000/metrics | grep -q "http_requests_total"; then
    echo -e "${GREEN}PASS${NC}"
else
    echo -e "${RED}FAIL${NC}"
    exit 1
fi

# Test 3: API Documentation
echo -n "Test 3: API Documentation... "
if curl -s http://localhost:8000/docs | grep -q "Swagger"; then
    echo -e "${GREEN}PASS${NC}"
else
    echo -e "${RED}FAIL${NC}"
    exit 1
fi

echo ""
echo "📊 Step 4: Service Information"
echo "------------------------------"
echo "API Service:    http://localhost:8000"
echo "API Docs:       http://localhost:8000/docs"
echo "API Metrics:    http://localhost:8000/metrics"
echo "OpenAPI Schema: http://localhost:8000/openapi.json"

echo ""
echo "🎯 Step 5: Docker Commands"
echo "--------------------------"
# Detect which docker compose command is available
if command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker compose"
fi
echo "Your Docker Compose command: $COMPOSE_CMD"
echo ""
echo "Stop services:   $COMPOSE_CMD down"
echo "View logs:       $COMPOSE_CMD logs -f"
echo "Restart:         $COMPOSE_CMD restart"
echo ""

echo "🎯 Step 6: Sample Requests"
echo "--------------------------"
echo ""
echo "Health Check:"
echo "  curl http://localhost:8000/health"
echo ""
echo "View Metrics:"
echo "  curl http://localhost:8000/metrics"
echo ""
echo "Upload Document (no extraction):"
echo "  curl -X POST http://localhost:8000/upload \\"
echo "    -F \"file=@your-invoice.png\" \\"
echo "    -F \"extract_fields=false\""
echo ""
echo "Upload with LLM Extraction:"
echo "  curl -X POST http://localhost:8000/upload \\"
echo "    -F \"file=@your-invoice.png\" \\"
echo "    -F \"extract_fields=true\""
echo ""

echo ""
echo -e "${GREEN}✅ All tests passed! Your platform is running correctly.${NC}"
echo ""
echo "Next steps:"
echo "  1. Open http://localhost:8000/docs in your browser"
echo "  2. Try uploading a document via the interactive UI"
echo "  3. Check metrics at http://localhost:8000/metrics"
echo ""
