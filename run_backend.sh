#!/bin/bash
# Quick start script for development

echo "🏥 Critical Surgery Supply Coordinator - Development Setup"
echo "=========================================================="
echo ""

# Check Python version
python_version=$(python --version 2>&1 | awk '{print $2}')
echo "✓ Python version: $python_version"

# Create backend environment
echo ""
echo "Setting up backend..."
cd backend

if [ ! -d "venv" ]; then
    python -m venv venv
    echo "✓ Created virtual environment"
else
    echo "✓ Virtual environment already exists"
fi

# Activate virtual environment
source venv/bin/activate 2>/dev/null || . venv/Scripts/activate

# Install dependencies
pip install -q -r requirements.txt
echo "✓ Installed backend dependencies"

# Start backend
echo ""
echo "Starting FastAPI backend..."
echo "Backend will be available at: http://localhost:8000"
echo "Health check: curl http://localhost:8000/health"
echo ""
echo "To test readiness check:"
echo 'curl -X POST http://localhost:8000/check-readiness \'
echo '  -H "user-role: OR_COORDINATOR" \'
echo '  -H "Content-Type: application/json" \'
echo '  -d "{\"surgery_id\": \"SURG001\", \"user_role\": \"OR_COORDINATOR\", \"requested_at\": \"2026-06-29T14:00:00Z\"}"'
echo ""

uvicorn src.main:app --reload --port 8000
