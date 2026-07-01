@echo off
REM Quick start script for development (Windows)

echo 🏥 Critical Surgery Supply Coordinator - Backend Setup
echo ======================================================
echo.

REM Check Python version
python --version
echo ✓ Python installed
echo.

REM Navigate to backend
cd backend

REM Create virtual environment
if not exist venv (
    python -m venv venv
    echo ✓ Created virtual environment
) else (
    echo ✓ Virtual environment already exists
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Install dependencies
pip install -q -r requirements.txt
echo ✓ Installed backend dependencies
echo.

REM Start backend
echo Starting FastAPI backend...
echo Backend will be available at: http://localhost:8000
echo Health check: curl http://localhost:8000/health
echo.
echo To test readiness check:
echo curl -X POST http://localhost:8000/check-readiness ^
echo   -H "user-role: OR_COORDINATOR" ^
echo   -H "Content-Type: application/json" ^
echo   -d "{\"surgery_id\": \"SURG001\", \"user_role\": \"OR_COORDINATOR\", \"requested_at\": \"2026-06-29T14:00:00Z\"}"
echo.

uvicorn src.main:app --reload --port 8000
