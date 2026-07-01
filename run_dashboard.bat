@echo off
REM Quick start script for frontend (Windows)

echo Critical Surgery Supply Coordinator - Frontend Setup
echo ====================================================
echo.

REM Navigate to frontend
cd frontend

REM Install dependencies
call npm install
echo Installed frontend dependencies
echo.

REM Start frontend
echo Starting React frontend...
echo Frontend will be available at: http://localhost:5173
echo.
echo Ensure the FastAPI backend is running on http://localhost:8000
echo.

call npm run dev
