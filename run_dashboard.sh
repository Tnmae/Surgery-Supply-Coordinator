#!/bin/bash
# Quick start script for frontend

echo "Critical Surgery Supply Coordinator - Frontend Setup"
echo "===================================================="
echo ""

# Navigate to frontend
cd frontend

# Install dependencies
npm install
echo "Installed frontend dependencies"

# Start frontend
echo ""
echo "Starting React frontend..."
echo "Frontend will be available at: http://localhost:5173"
echo ""
echo "Ensure the FastAPI backend is running on http://localhost:8000"
echo ""

npm run dev
